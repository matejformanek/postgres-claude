# Heap tuple freeze — plan-then-execute with HEAP_XMIN_FROZEN sentinel

A 32-bit TransactionId wraps every ~4 billion XIDs. Without intervention, a
row's `t_xmin` from xact 100 would become *newer* than a fresh xact's
`xmin` after wraparound, and visibility logic would mark the old (still-live)
row as "not yet visible." VACUUM's **freeze** pass prevents this: any
still-live tuple whose `t_xmin` precedes a cutoff is rewritten so its xmin
is treated as "before all snapshots," forever.

The implementation is a **two-phase plan-then-execute** split:

1. `heap_prepare_freeze_tuple` (outside any critical section) reads the
   tuple, computes a `HeapTupleFreeze` describing the changes, validates
   xmin/xmax via CLOG sanity checks, and returns *whether* a freeze is
   needed. No tuple bytes are modified.
2. `heap_freeze_prepared_tuples` (inside the prune/freeze critical
   section) applies the precomputed plans via `heap_execute_freeze_tuple`.

The split lets VACUUM batch all per-page checks before entering the crit
section, and lets `vacuumlazy.c` *decline* to freeze a page even after
preparing plans (keeping two relfrozenxid candidate trackers — one for
each decision).

The freeze itself is **not** a new XID. The sentinel `FrozenTransactionId
= 2` is occasionally stored, but the canonical freeze is to leave
`t_xmin` unchanged and set the **`HEAP_XMIN_FROZEN` infomask combination**
(`HEAP_XMIN_COMMITTED | HEAP_XMIN_INVALID` = `0x0300`). Visibility code
recognizes this impossible combination as "frozen" and skips the
in-progress / CLOG dance.

This doc walks the plan struct, the cutoffs, the xmin/xmax/xvac
processing, the MultiXact-stripping logic in `FreezeMultiXactId`, and
the lazy-vs-eager freezing tradeoff the trackers expose.

Companion docs:
- [[heap-tuple-visibility-mvcc]] — the visibility consumer of `HEAP_XMIN_FROZEN`.
- [[hint-bits-setbufferdirty]] — explains why setting these bits is normally a hint, but freeze is WAL-logged.
- [[multixact-slru]] — MultiXact storage; `FreezeMultiXactId` may strip lock-only members.
- [[xmin-horizon-management]] — how `OldestXmin` and `FreezeLimit` are computed.

## Anchors

- `source/src/include/access/transam.h:31-35` — special XIDs (`Invalid=0`, `Bootstrap=1`, `Frozen=2`, `FirstNormal=3`).
- `source/src/include/access/heapam.h:149-150` — `HEAP_FREEZE_CHECK_XMIN_COMMITTED` / `_XMAX_ABORTED` flags.
- `source/src/include/access/heapam.h:152-165` — `HeapTupleFreeze` struct (the plan).
- `source/src/include/access/heapam.h:191-246` — `HeapPageFreeze` (per-page tracker pair).
- `source/src/include/access/heapam.h:523-545` — `heap_execute_freeze_tuple` inline.
- `source/src/include/access/htup_details.h:204-206` — `HEAP_XMIN_FROZEN` macro.
- `source/src/backend/access/heap/heapam.c:7026-7296` — `heap_prepare_freeze_tuple` (the planning function).
- `source/src/backend/access/heap/heapam.c:7306-7350` — `heap_pre_freeze_checks` (CLOG sanity).
- `source/src/backend/access/heap/heapam.c:7359-7373` — `heap_freeze_prepared_tuples`.
- `source/src/backend/access/heap/heapam.c:7376-7417` — `heap_freeze_tuple` (CLUSTER's single-tuple wrapper).
- `source/src/backend/access/heap/heapam.c:7845-7938` — `heap_tuple_should_freeze` (no-freeze tracker maintenance).
- `source/src/backend/access/heap/heapam.c` — `FreezeMultiXactId` (the multixact-stripping engine; called from `heap_prepare_freeze_tuple`).

## The freeze sentinel — HEAP_XMIN_FROZEN

```c
/* htup_details.h:204-206 */
#define HEAP_XMIN_COMMITTED  0x0100
#define HEAP_XMIN_INVALID    0x0200
#define HEAP_XMIN_FROZEN     (HEAP_XMIN_COMMITTED | HEAP_XMIN_INVALID)  /* 0x0300 */
```

Both `committed` and `invalid` set is otherwise a contradiction — freezing
exploits this for an in-band sentinel. `HeapTupleHeaderXminFrozen(tup)`
returns true when both bits are set; `HeapTupleHeaderXminCommitted(tup)`
returns true when **either** the committed bit alone or both bits are set
(so frozen tuples short-circuit the gauntlet in
[[heap-tuple-visibility-mvcc]]).

The actual `t_xmin` field is **not zeroed** by a freeze. The original
TransactionId is preserved for forensics (debugging, pageinspect). Only
the infomask flag is the source of truth for "frozen." This means a
frozen tuple's `t_xmin` field can refer to an XID that no longer exists
in CLOG (because vacuum has since truncated `pg_xact`) — that's why
[[heap-tuple-visibility-mvcc]] short-circuits `XidInMVCCSnapshot` for
frozen rows. [verified-by-code] (`heapam_visibility.c:1021-1023`).

A different code path uses `FrozenTransactionId = 2` directly. The xvac
field (for pre-9.0 VACUUM FULL `HEAP_MOVED_OFF/IN` tuples) gets
`HeapTupleHeaderSetXvac(tuple, FrozenTransactionId)`. The xvac path is
binary-upgrade legacy; `FrozenTransactionId` is the only place modern
code routinely stores the literal 2. [verified-by-code]
(`heapam.h:537-541`).

## The plan struct — HeapTupleFreeze

```c
/* heapam.h:152-165 */
typedef struct HeapTupleFreeze {
    /* The to-be-written values */
    TransactionId xmax;
    uint16        t_infomask2;
    uint16        t_infomask;
    uint8         frzflags;        /* XLH_FREEZE_XVAC | XLH_INVALID_XVAC */

    /* xmin/xmax check flags (consumed by heap_pre_freeze_checks) */
    uint8         checkflags;      /* HEAP_FREEZE_CHECK_XMIN_COMMITTED |
                                      HEAP_FREEZE_CHECK_XMAX_ABORTED */
    /* Page offset of the tuple this plan describes */
    OffsetNumber  offset;
} HeapTupleFreeze;
```

Each entry is ~12 bytes. `vacuumlazy.c` allocates one per tuple
on the page that needs freezing (sized by `MaxHeapTuplesPerPage`).
The `offset` is filled in by the caller; everything else is set by
`heap_prepare_freeze_tuple`. [verified-by-code] (`heapam.h:152-165`).

The `checkflags` are deliberately deferred from prepare to a separate
`heap_pre_freeze_checks` call. The point is that `pg_xact` lookups are
relatively expensive, and successive VACUUMs that look at the same page
but **decline** to freeze (the lazy-tracker path below) should not pay
that cost every time. [from-comment] (`heapam.c:7299-7305`).

## The cutoffs — VacuumCutoffs

`heap_prepare_freeze_tuple` reads four cutoff XIDs/MXIDs from
`VacuumCutoffs`:

- `relfrozenxid` — current `pg_class.relfrozenxid` for this relation;
  invariant: every live tuple's xmin is `>=` this.
- `OldestXmin` — global `GetOldestNonRemovableTransactionId()`; xmin
  before this is safe to freeze.
- `FreezeLimit` — the threshold below which freezing is *mandatory*
  (i.e. `freeze_required` gets set if any xmin/xmax is older).
- `OldestMxact` / `MultiXactCutoff` — same idea for MultiXactIds.

`OldestXmin >= FreezeLimit` always (FreezeLimit is older). The eligible
zone for freezing is `[relfrozenxid, OldestXmin)`; the mandatory zone is
`[relfrozenxid, FreezeLimit)`. Tuples in `[FreezeLimit, OldestXmin)`
*could* be frozen but VACUUM may choose laziness. [verified-by-code]
(`heapam.c:7063-7070`).

## The processing — xmin, xmax, xvac

`heap_prepare_freeze_tuple` examines three XID fields independently:
`xmin`, `xmax`, `xvac`. Each can be in one of:

- **Already frozen** (xmin: `!IsNormal`, i.e. invalid/bootstrap/frozen; xmax: `!IsValid`).
- **Eligible to freeze** (normal XID, precedes `OldestXmin`).
- **Not yet eligible** (normal XID, ≥ `OldestXmin`).
- **Corrupt** (precedes `relfrozenxid` — pageinspect's nightmare; raises `ERRCODE_DATA_CORRUPTED`).

### Xmin

```c
/* heapam.c:7051-7072 */
xid = HeapTupleHeaderGetXmin(tuple);
if (!TransactionIdIsNormal(xid))
    xmin_already_frozen = true;
else {
    if (TransactionIdPrecedes(xid, cutoffs->relfrozenxid))
        ereport(ERROR, ...);            /* corruption */
    freeze_xmin = TransactionIdPrecedes(xid, cutoffs->OldestXmin);
    if (freeze_xmin) {
        frz->checkflags |= HEAP_FREEZE_CHECK_XMIN_COMMITTED;
        if (TransactionIdFollows(xid, pagefrz->FreezePageConflictXid))
            pagefrz->FreezePageConflictXid = xid;
    }
}
```

If we plan to freeze xmin, we must verify (later, in
`heap_pre_freeze_checks`) that this XID **committed** — freezing an
aborted xact's xmin would resurrect an invisible row. The `checkflags`
bit defers the CLOG lookup to a single batch right before execution.

`FreezePageConflictXid` tracks the newest XID that the page-freeze will
remove from visibility. On a standby, replaying the freeze WAL record
must wait for any snapshot that could see this XID as still-running;
otherwise the standby could see a row that was being concurrently
deleted. [from-comment] (`heapam.h:223-233`).

### Xmax

Three sub-branches (`heapam.c:7096-7229`):

**1. MultiXact xmax** (`HEAP_XMAX_IS_MULTI`): delegate to
`FreezeMultiXactId`, which can return one of:

- `FRM_NOOP` — leave the multi alone. May happen when freezing would
  require allocating a new MultiXactId and we'd rather avoid that
  cost. The lazy-page-trackers get ratcheted back so the multi remains
  representable. Only path where `freeze_required` is not forced.
- `FRM_RETURN_IS_XID` — the multi had exactly one non-aborted updater
  XID; replace the multi with that bare XID. The `HEAP_XMAX_*` bits are
  cleared and re-set as a simple xmax. May also set `HEAP_XMAX_COMMITTED`
  if `FRM_MARK_COMMITTED` came back.
- `FRM_RETURN_IS_MULTI` — old multi had multiple still-live members;
  allocate a new multi containing only those, replace xmax. The new
  multi's hint bits are computed via `GetMultiXactIdHintBits`
  (`heapam.c:7426`) which preserves "unrelated" bits.
- `FRM_INVALIDATE_XMAX` — the multi is entirely lockers/aborters past
  cutoff; clear xmax completely.

**2. Plain xmax** (normal XID): straightforward eligibility check. If
freezing and not LOCKED_ONLY, set `HEAP_FREEZE_CHECK_XMAX_ABORTED` (we
must verify the deleter aborted — freezing a committed xmax would
unwind a delete). Note the asymmetry with xmin: we check "xmin
**committed**" for freeze-xmin but "xmax **aborted**" for freeze-xmax,
because the banner explains `TransactionIdDidAbort` is unreliable for
crashed xacts but `!TransactionIdDidCommit` is the safe-by-elimination
test. [from-comment] (`heapam.c:7211-7215`).

**3. Invalid xmax**: already frozen (nothing to do).

### Xvac (legacy)

Pre-9.0 VACUUM FULL would set `HEAP_MOVED_OFF` / `HEAP_MOVED_IN` on
tuples it physically relocated. Modern PG no longer creates these but
must still process them for pg_upgrade. `replace_xvac = pagefrz->freeze_required
= true` — xvac freezing is always mandatory (and the `freeze_required`
flag is sticky upward). [from-comment] (`heapam.c:7084-7088`).

## Setting the flags — the plan's t_infomask

```c
/* heapam.c:7231-7272 */
if (freeze_xmin)
    frz->t_infomask |= HEAP_XMIN_FROZEN;       /* 0x0300 — the sentinel */
if (replace_xvac)
    frz->frzflags |= (HEAP_MOVED_OFF ? XLH_INVALID_XVAC : XLH_FREEZE_XVAC);
if (replace_xmax)
    /* t_infomask was set by the FRM_RETURN_IS_* branch */ ;
if (freeze_xmax) {
    frz->xmax = InvalidTransactionId;
    frz->t_infomask &= ~HEAP_XMAX_BITS;        /* clear all xmax bits */
    frz->t_infomask |= HEAP_XMAX_INVALID;
    frz->t_infomask2 &= ~(HEAP_HOT_UPDATED | HEAP_KEYS_UPDATED);
}
```

`HEAP_XMAX_BITS` (`htup_details.h:285`) is the mask of all xmax-related
infomask bits — clearing then re-setting ensures any stale lock-only,
multi-flag, key-shared, etc. bits don't survive. [verified-by-code]
(`htup_details.h:285-286`).

## The plan executor — heap_execute_freeze_tuple

```c
/* heapam.h:532-545 */
static inline void
heap_execute_freeze_tuple(HeapTupleHeader tuple, HeapTupleFreeze *frz) {
    HeapTupleHeaderSetXmax(tuple, frz->xmax);

    if (frz->frzflags & XLH_FREEZE_XVAC)
        HeapTupleHeaderSetXvac(tuple, FrozenTransactionId);
    if (frz->frzflags & XLH_INVALID_XVAC)
        HeapTupleHeaderSetXvac(tuple, InvalidTransactionId);

    tuple->t_infomask  = frz->t_infomask;
    tuple->t_infomask2 = frz->t_infomask2;
}
```

Five field writes. Note that **`t_xmin` is never written here** — the
freeze sentinel is purely an infomask flag flip; the raw xmin stays for
forensics. The caller must hold an **exclusive buffer content lock** and
be inside a critical section (the comment is explicit), because this
sits inside `heap_page_prune_and_freeze`'s WAL-logged region. [from-comment]
(`heapam.h:524-530`).

## The CLOG sanity gate — heap_pre_freeze_checks

```c
/* heapam.c:7306-7350 */
void heap_pre_freeze_checks(Buffer buffer, HeapTupleFreeze *tuples, int n) {
    for each frz {
        if (frz->checkflags & HEAP_FREEZE_CHECK_XMIN_COMMITTED) {
            xmin = HeapTupleHeaderGetRawXmin(htup);
            if (!TransactionIdDidCommit(xmin))
                ereport(ERROR, ... "uncommitted xmin %u needs to be frozen");
        }
        if (frz->checkflags & HEAP_FREEZE_CHECK_XMAX_ABORTED) {
            xmax = HeapTupleHeaderGetRawXmax(htup);
            if (TransactionIdDidCommit(xmax))
                ereport(ERROR, ... "cannot freeze committed xmax %u");
        }
    }
}
```

Two crucial properties:

- **Hint bits are NOT consulted** — the comment is explicit: "Deliberately
  avoid relying on tuple hint bits here." A wrongly-set hint bit would
  let us freeze an aborted xact's tuple, which is data loss.
  [verified-by-code] (`heapam.c:7320`).
- **`TransactionIdDidCommit` only**, not `TransactionIdDidAbort`. The
  banner's process-of-elimination rule: a crashed-in-progress xact
  doesn't show up as aborted, but we can rule out committed.
  [from-comment] (`heapam.c:7333-7337`).

This separation lets VACUUM run the cheap arithmetic checks on every
page but defer the CLOG lookup to only the pages that actually get
frozen.

## The plan's bool return — should-I-freeze

`heap_prepare_freeze_tuple` returns true if a freeze plan was filled in
(at least one of `freeze_xmin`, `replace_xvac`, `replace_xmax`,
`freeze_xmax` is true). VACUUM iterates tuples on a page and collects
plans; then either:

- **`pagefrz->freeze_required` is set** (because a mandatory freeze
  exists, e.g. some XID precedes `FreezeLimit`) → VACUUM **must** execute
  the plans, no choice.
- **`freeze_required` is unset** → VACUUM gets to decide. The hint
  policy: "vacuumlazy.c avoid early freezing when freezing does not
  enable setting the target page all-frozen in the visibility map
  afterwards." [from-comment] (`heapam.h:187-189`).

## The two relfrozenxid trackers

The `HeapPageFreeze` struct keeps **two** parallel `(NewRelfrozenXid,
NewRelminMxid)` candidate pairs:

- `FreezePage*` — the value that will be safe if we **do** execute
  freeze plans.
- `NoFreezePage*` — the value that will be safe if we **don't** freeze
  this page (leave the XIDs alone).

These are updated independently because the decision is made
*per-page*: VACUUM scans the whole relation, and for each page chooses
freeze vs no-freeze. The relation's final `pg_class.relfrozenxid` after
VACUUM is determined by the **minimum** XID still potentially live in
any unfrozen page — both trackers must remain conservative.

`heap_tuple_should_freeze` (`heapam.c:7845`) maintains the
`NoFreezePage*` trackers by ratcheting them back when a tuple's xmin/xmax
is older than the current candidate. It also returns true if any
xmin/xmax precedes `FreezeLimit`, which sticky-sets
`pagefrz->freeze_required` for the caller (the freeze becomes mandatory).
[verified-by-code] (`heapam.c:7281-7295`, `heapam.c:7857-7864`).

For pages with a MultiXact xmax, `heap_tuple_should_freeze` also walks
the MultiXact members via `GetMultiXactIdMembers` so that the freeze
decision sees every XID nested inside the multi. [verified-by-code]
(`heapam.c:7895-7921`).

## CLUSTER's path — heap_freeze_tuple

`heap_freeze_tuple` (`heapam.c:7376`) is a thin wrapper used by CLUSTER
and other rewrite paths. It forces `freeze_required = true`, sets
`FreezeLimit = OldestXmin = MultiXactCutoff = OldestMxact` (no laziness),
calls `heap_prepare_freeze_tuple`, then immediately
`heap_execute_freeze_tuple`. No WAL is emitted — CLUSTER handles its own
WAL for the rewritten heap as a whole. The offset field is intentionally
unfilled because there is no WAL record needing it. [from-comment]
(`heapam.c:7376-7416`).

## Invariants and races

1. **Freezing requires exclusive buffer content lock** and a critical
   section. The plan-vs-execute split lets the expensive CLOG sanity
   stay outside the crit section. [from-comment] (`heapam.h:524-530`,
   `heapam.c:7299-7305`).
2. **`HEAP_XMIN_FROZEN` is the only legal both-bits-set combination** —
   visibility code relies on this for the short-circuit.
   [verified-by-code] (`heapam_visibility.c:1021-1023`).
3. **Frozen tuples preserve their original `t_xmin`** for debugging; the
   semantic xmin is the all-snapshots-old sentinel via the flag.
   [verified-by-code] (`heapam.h:532-545` shows no `SetXmin` call).
4. **`heap_pre_freeze_checks` ignores hint bits**, consulting CLOG
   directly. A corrupted hint bit must not enable a corruption-amplifying
   freeze. [verified-by-code] (`heapam.c:7320`).
5. **The check uses `TransactionIdDidCommit`, not `TransactionIdDidAbort`**
   — crashed in-progress xacts don't reach the latter reliably.
   [from-comment] (`heapam.c:7333-7337`).
6. **`FreezePageConflictXid` is the standby snapshot-conflict horizon**
   for the freeze WAL record. Replay must wait for snapshots ≤ this
   XID to drain. [from-comment] (`heapam.h:223-233`).
7. **Two relfrozenxid candidates per page** (freeze vs no-freeze)
   because the choice is per-page in vacuumlazy.c. [from-comment]
   (`heapam.h:195-218`).
8. **`FRM_NOOP` is the only multixact-freeze outcome that doesn't force
   `freeze_required`** — used when allocating a new multi would be
   more expensive than waiting for the next VACUUM. The lazy
   trackers get ratcheted instead. [from-comment] (`heapam.c:7113-7136`).
9. **`xid < relfrozenxid` is always corruption** — raises
   `ERRCODE_DATA_CORRUPTED`. Means an XID survived past the table's
   advertised horizon. [verified-by-code] (`heapam.c:7056-7060`,
   `heapam.c:7202-7206`).

## Useful greps

```bash
# The plan / execute / check trio:
grep -nE "heap_prepare_freeze_tuple|heap_freeze_prepared_tuples|heap_pre_freeze_checks|heap_execute_freeze_tuple" \
       source/src/backend/access/heap/

# Where freeze is called from VACUUM:
grep -rn "heap_prepare_freeze_tuple\|heap_freeze_prepared_tuples" \
       source/src/backend/access/heap/vacuumlazy.c \
       source/src/backend/access/heap/pruneheap.c

# MultiXact freezing internals:
grep -n "FreezeMultiXactId\|FRM_NOOP\|FRM_RETURN_IS_XID\|FRM_RETURN_IS_MULTI\|FRM_INVALIDATE_XMAX\|FRM_MARK_COMMITTED" \
       source/src/backend/access/heap/heapam.c

# All callers of heap_freeze_tuple (the CLUSTER wrapper):
grep -rn "heap_freeze_tuple\b" source/src/backend/

# How vacuumlazy.c chooses freeze vs no-freeze:
grep -n "FreezePageRelfrozenXid\|NoFreezePageRelfrozenXid\|freeze_required" \
       source/src/backend/access/heap/vacuumlazy.c
```



## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/access/heap/heapam.c`](../files/src/backend/access/heap/heapam.c.md) | 7026 | heap_prepare_freeze_tuple (the planning function) |
| [`src/backend/access/heap/heapam.c`](../files/src/backend/access/heap/heapam.c.md) | 7306 | heap_pre_freeze_checks (CLOG sanity) |
| [`src/backend/access/heap/heapam.c`](../files/src/backend/access/heap/heapam.c.md) | 7359 | heap_freeze_prepared_tuples |
| [`src/backend/access/heap/heapam.c`](../files/src/backend/access/heap/heapam.c.md) | 7376 | heap_freeze_tuple (CLUSTER's single-tuple wrapper) |
| [`src/backend/access/heap/heapam.c`](../files/src/backend/access/heap/heapam.c.md) | 7845 | heap_tuple_should_freeze (no-freeze tracker maintenance) |
| [`src/backend/access/heap/heapam.c`](../files/src/backend/access/heap/heapam.c.md) | — | FreezeMultiXactId (the multixact-stripping engine; called from heap_prepare_freeze_tuple) |
| [`src/include/access/heapam.h`](../files/src/include/access/heapam.h.md) | 149 | HEAP_FREEZE_CHECK_XMIN_COMMITTED / _XMAX_ABORTED flags |
| [`src/include/access/heapam.h`](../files/src/include/access/heapam.h.md) | 152 | HeapTupleFreeze struct (the plan) |
| [`src/include/access/heapam.h`](../files/src/include/access/heapam.h.md) | 191 | HeapPageFreeze (per-page tracker pair) |
| [`src/include/access/heapam.h`](../files/src/include/access/heapam.h.md) | 523 | heap_execute_freeze_tuple inline |
| [`src/include/access/htup_details.h`](../files/src/include/access/htup_details.h.md) | 204 | HEAP_XMIN_FROZEN macro |
| [`src/include/access/transam.h`](../files/src/include/access/transam.h.md) | 31 | special XIDs (Invalid=0, Bootstrap=1, Frozen=2, FirstNormal=3) |

<!-- /callsites:auto -->



## Scenarios that use me
<!-- scenarios:auto -->

*Auto-derived from direct references + transitive file-overlap.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

- [`add-new-buffer-strategy`](../scenarios/add-new-buffer-strategy.md)

<!-- /scenarios:auto -->

## Cross-references

- [[heap-tuple-visibility-mvcc]] — visibility consumes `HEAP_XMIN_FROZEN`.
- [[hint-bits-setbufferdirty]] — `HEAP_XMIN_COMMITTED` is a hint; `HEAP_XMIN_FROZEN` is a freeze (WAL-logged via `heap_page_prune_and_freeze`).
- [[multixact-slru]] — `FreezeMultiXactId` consumes/produces these.
- [[xmin-horizon-management]] — `OldestXmin` / `FreezeLimit` / `relfrozenxid` computation.
- [[clog-slru]] — `TransactionIdDidCommit` consults this for the sanity gate.
- `knowledge/subsystems/access-heap.md` §"Freeze / vacuum cycle" — subsystem-level view.
