# Heap tuple visibility — the HeapTupleSatisfiesMVCC gauntlet

A heap-page row is just bytes until visibility resolves whether **this
snapshot, this command, this transaction** is allowed to see it. The
`HeapTupleSatisfies*` family in `heapam_visibility.c` is the oracle that
turns `(HeapTuple, Snapshot)` into `true`/`false`. The MVCC variant is the
hot path — every sequential scan, every index-condition recheck, every
`heap_fetch` from an executor ultimately goes through it.

This doc walks the **MVCC gauntlet**: the four sequential gates
(`xmin-committed?` → `xmin-aborted?` → `snapshot-includes-xmin?` →
`xmax-state?`), the dispatcher in `HeapTupleSatisfiesVisibility`, the
batched MVCC variant added for amortized buffer-hint bookkeeping, and
the special HistoricMVCC path used by logical decoding.

Companion docs:
- [[hint-bits-setbufferdirty]] — the SetHintBits side-effect that every Satisfies routine performs.
- [[combocid-handling]] — the cmin/cmax encoding for self-modifying transactions.
- [[heap-tuple-freeze]] — the freeze that makes `HEAP_XMIN_FROZEN` skip the in-progress check.
- [[heaptuple-update-chain]] — how `HeapTupleSatisfiesUpdate` differs (returns `TM_Ok`/`TM_Updated`/`TM_Deleted` instead of bool).

## Anchors

- `source/src/backend/access/heap/heapam_visibility.c:1-65` — module banner: the **race rule** (TransactionIdIsInProgress before TransactionIdDidCommit).
- `source/src/backend/access/heap/heapam_visibility.c:38-56` — summary of all seven Satisfies routines.
- `source/src/backend/access/heap/heapam_visibility.c:939-1096` — `HeapTupleSatisfiesMVCC` (the gauntlet itself).
- `source/src/backend/access/heap/heapam_visibility.c:1731-1753` — `HeapTupleSatisfiesVisibility` (the dispatcher).
- `source/src/backend/access/heap/heapam_visibility.c:1689-1719` — `HeapTupleSatisfiesMVCCBatch` (amortized hint-bit overhead).
- `source/src/backend/access/heap/heapam_visibility.c:1504-1685` — `HeapTupleSatisfiesHistoricMVCC` (logical decoding).
- `source/src/backend/access/heap/heapam_visibility.c:1113-1343` — `HeapTupleSatisfiesVacuum` / `…VacuumHorizon` (the vacuum oracle).
- `source/src/include/access/htup_details.h:204-210` — the infomask bit definitions (`HEAP_XMIN_COMMITTED`/`_INVALID`/`_FROZEN`, `HEAP_XMAX_*`).
- `source/src/include/utils/snapshot.h` — `SnapshotData` and `snapshot_type` enum.

## The seven Satisfies routines

```c
/* heapam_visibility.c:38-56 (banner summary) */
HeapTupleSatisfiesMVCC()           — supplied MVCC snapshot, excludes current command
HeapTupleSatisfiesUpdate()         — instant snapshot + user cmd; returns TM_* enum
HeapTupleSatisfiesSelf()           — instant snapshot + current command
HeapTupleSatisfiesDirty()          — like Self, but includes uncommitted others
HeapTupleSatisfiesVacuum()         — visible to *any* running xact
HeapTupleSatisfiesNonVacuumable()  — Snapshot-style API for Vacuum
HeapTupleSatisfiesToast()          — visible unless part of an interrupted vacuum
HeapTupleSatisfiesAny()            — always true
```

The dispatcher just switches on `snapshot->snapshot_type`:

```c
/* heapam_visibility.c:1731-1753 */
bool HeapTupleSatisfiesVisibility(HeapTuple, Snapshot, Buffer) {
    switch (snapshot->snapshot_type) {
      case SNAPSHOT_MVCC:           return HeapTupleSatisfiesMVCC(..., NULL);
      case SNAPSHOT_SELF:           return HeapTupleSatisfiesSelf(...);
      case SNAPSHOT_ANY:            return HeapTupleSatisfiesAny(...);
      case SNAPSHOT_TOAST:          return HeapTupleSatisfiesToast(...);
      case SNAPSHOT_DIRTY:          return HeapTupleSatisfiesDirty(...);
      case SNAPSHOT_HISTORIC_MVCC:  return HeapTupleSatisfiesHistoricMVCC(...);
      case SNAPSHOT_NON_VACUUMABLE: return HeapTupleSatisfiesNonVacuumable(...);
    }
}
```

There is no fallthrough — every enum value is handled. The trailing
`return false` is "to keep compiler quiet" per the comment. [verified-by-code]
(`heapam_visibility.c:1731-1753`).

## The cardinal race rule

A backend's commit happens in two non-atomic phases:

1. `xact.c` records `COMMITTED` in `pg_xact` (CLOG).
2. `xact.c` clears `MyProc->xid` in the PGPROC array.

In between, `TransactionIdDidCommit(xid)` returns true while
`TransactionIdIsInProgress(xid)` *also* returns true. If a snapshot were
taken in that window and we consulted CLOG first, we would mark a tuple
visible whose committer is still in the snapshot's "running" set — a
read-your-write hazard.

The fix is **always check in-progress before consulting CLOG**:

```text
non-MVCC path:   TransactionIdIsInProgress(xid)  then  TransactionIdDidCommit(xid)
MVCC path:       XidInMVCCSnapshot(xid, snap)    then  TransactionIdDidCommit(xid)
```

`XidInMVCCSnapshot` is the snapshot-local equivalent of "is this xact in
the running set?" — testing the snapshot's `xip`/`subxip` arrays plus the
`xmin`/`xmax` bounds. The visibility code never consults CLOG without
having first ruled out in-progress. [from-comment]
(`heapam_visibility.c:13-35`).

## Infomask bits — the cached truth

Visibility consults the tuple header's `t_infomask` (uint16) for cached
commit-state bits. The 4-bit visibility cluster:

| Bit | Value | Meaning |
|---|---|---|
| `HEAP_XMIN_COMMITTED` | `0x0100` | xmin's transaction committed |
| `HEAP_XMIN_INVALID`   | `0x0200` | xmin's transaction aborted/crashed |
| `HEAP_XMIN_FROZEN`    | `0x0300` | both set = frozen; treat xmin as "before all snapshots" |
| `HEAP_XMAX_COMMITTED` | `0x0400` | xmax's transaction committed |
| `HEAP_XMAX_INVALID`   | `0x0800` | xmax's transaction aborted/crashed |
| `HEAP_XMAX_IS_MULTI`  | `0x1000` | xmax is a MultiXactId, not a TransactionId |

The 0x0100 + 0x0200 = 0x0300 encoding for `HEAP_XMIN_FROZEN` is deliberate:
the two "we know xmin's fate" bits are both set, which is otherwise
contradictory (committed AND aborted). Freezing exploits this impossible
combination as a sentinel. [verified-by-code] (`htup_details.h:204-206`).

These bits are **hint bits** — see [[hint-bits-setbufferdirty]]. They are
set lazily by `SetHintBits` during visibility checks; they are not WAL
logged (a lost hint bit just causes a future visitor to redo the work
and consult CLOG/PGPROC again).

## The MVCC gauntlet — step by step

`HeapTupleSatisfiesMVCC(htup, snapshot, buffer, state)` (`heapam_visibility.c:939`)
splits cleanly into **xmin resolution** then **xmax resolution**.

### Gate 1 — Is xmin resolved?

```c
if (!HeapTupleHeaderXminCommitted(tuple)) {           /* HEAP_XMIN_COMMITTED off */
    if (HeapTupleHeaderXminInvalid(tuple))            /* HEAP_XMIN_INVALID set */
        return false;                                 /* xmin aborted → invisible */

    if (!HeapTupleCleanMoved(tuple, buffer))          /* pre-9.0 MOVED_* bits */
        return false;
    ...
}
```

If `HEAP_XMIN_COMMITTED` is set (or both bits = `HEAP_XMIN_FROZEN`), we
skip the gauntlet entirely and head to gate 4 (xmax). If only
`HEAP_XMIN_INVALID` is set, return false immediately — the inserter
aborted. [verified-by-code] (`heapam_visibility.c:956-962`).

### Gate 2 — Is xmin "us" (self-visibility)?

```c
else if (TransactionIdIsCurrentTransactionId(HeapTupleHeaderGetRawXmin(tuple))) {
    if (HeapTupleHeaderGetCmin(tuple) >= snapshot->curcid)
        return false;     /* inserted by a later command in this xact */
    /* otherwise our insert: continue to xmax gate (but inline-handled) */
}
```

Tuples inserted by the current transaction must be filtered by `cmin` vs
the snapshot's `curcid`. This is what makes "INSERT ... RETURNING" inside
a function not see its own rows when the function's query was started
before the INSERT. The `HeapTupleHeaderGetCmin` may consult the
[[combocid-handling]] map if the tuple has been self-modified.
[verified-by-code] (`heapam_visibility.c:963-967`).

The self-branch then handles xmax inline (lines 968-1003) because the
dispatch logic is identical but with `cmax >= snapshot->curcid` semantics
for tuples we ourselves deleted. The full sub-tree:

- `HEAP_XMAX_INVALID` → visible (we inserted, nobody deleted).
- `HEAP_XMAX_IS_LOCKED_ONLY` → visible (locked is not deleted).
- `HEAP_XMAX_IS_MULTI` → resolve update-xid; if it's also us, compare cmax
  to curcid; if it's not us (the other subxact aborted), visible.
- Plain xmax = us: compare cmax to curcid.
- Plain xmax != us: must have aborted (the multixact/PGPROC array would
  have caught us first); set `HEAP_XMAX_INVALID` hint and return visible.

[verified-by-code] (`heapam_visibility.c:968-1004`).

### Gate 3 — Is xmin in our snapshot's in-progress set?

```c
else if (XidInMVCCSnapshot(HeapTupleHeaderGetRawXmin(tuple), snapshot))
    return false;
else if (TransactionIdDidCommit(HeapTupleHeaderGetRawXmin(tuple)))
    SetHintBitsExt(tuple, buffer, HEAP_XMIN_COMMITTED,
                   HeapTupleHeaderGetRawXmin(tuple), state);
else {
    /* it must have aborted or crashed */
    SetHintBitsExt(tuple, buffer, HEAP_XMIN_INVALID,
                   InvalidTransactionId, state);
    return false;
}
```

`XidInMVCCSnapshot` returns true if `xmin` is `>= snapshot->xmin` and
either `>= snapshot->xmax` or in `snapshot->xip[]`. If true: this xact
was running when the snapshot was taken, so it is invisible to us.

If false: the xact was not running at snapshot time, so its fate is
fixed. Consult CLOG via `TransactionIdDidCommit`:
- **Committed** → set `HEAP_XMIN_COMMITTED` hint, fall through to xmax gate.
- **Aborted/crashed** → set `HEAP_XMIN_INVALID` hint, return false.

The `else` for aborted relies on "process of elimination": we already
ruled out in-progress, so a not-yet-committed xact must have aborted or
the process crashed. The banner explains why `TransactionIdDidAbort`
cannot be used directly — it doesn't catch crashed-in-progress xacts.
[from-comment] (`heapam_visibility.c:29-31`).

### Gate 4 — Resolve xmax

Reached when xmin is known-visible. Same in-progress-then-CLOG dance, but
the semantics invert: a committed xmax means **invisible** (somebody
deleted/updated this row), and an in-progress xmax means **visible**
(deleter hasn't committed yet, we should see the row).

```c
/* heapam_visibility.c:1028-1095, in xmax-resolution form */
if (tuple->t_infomask & HEAP_XMAX_INVALID)             return true;
if (HEAP_XMAX_IS_LOCKED_ONLY(tuple->t_infomask))       return true;
if (tuple->t_infomask & HEAP_XMAX_IS_MULTI)            { /* resolve update-xid */ }

if (!(tuple->t_infomask & HEAP_XMAX_COMMITTED)) {
    if (TransactionIdIsCurrentTransactionId(...))      { /* compare cmax/curcid */ }
    if (XidInMVCCSnapshot(xmax, snapshot))             return true;   /* still running */
    if (!TransactionIdDidCommit(xmax)) {
        SetHintBitsExt(..., HEAP_XMAX_INVALID, ...);
        return true;     /* aborted/crashed: row is alive */
    }
    SetHintBitsExt(..., HEAP_XMAX_COMMITTED, ...);     /* deleter committed */
}
else {
    if (XidInMVCCSnapshot(xmax, snapshot))             return true;
                                /* committed but not in our snapshot’s view yet */
}

return false;            /* xmax committed and visible to our snapshot: row is dead */
```

The `HEAP_XMAX_IS_LOCKED_ONLY` short-circuit catches rows that are only
*locked* by xmax (e.g. `FOR UPDATE` without an actual update) — the row
itself is still alive. The `HEAP_XMAX_IS_MULTI` branch calls
`HeapTupleGetUpdateXid` which scans the multixact's members for the
single update-xid (or returns `InvalidTransactionId` if it was
locks-only). See [[tuple-locking-modes]] for the multixact decoding.
[verified-by-code] (`heapam_visibility.c:1028-1059`).

## Why xmin-frozen short-circuits

```c
/* heapam_visibility.c:1021-1023 */
if (!HeapTupleHeaderXminFrozen(tuple) &&
    XidInMVCCSnapshot(HeapTupleHeaderGetRawXmin(tuple), snapshot))
    return false;
```

A tuple with `HEAP_XMIN_FROZEN` set (both committed and invalid bits) has
had its xmin replaced or marked-as-replaced by VACUUM
(`[[heap-tuple-freeze]]`). The actual `t_xmin` field may still hold the
original XID for forensics, but the semantics are "this xact is before
the oldest snapshot anyone could possibly hold." So we skip
`XidInMVCCSnapshot` (which would otherwise compare a wrapped-around
or pre-truncation XID to a fresh snapshot's bounds and produce nonsense).
[verified-by-code] (`heapam_visibility.c:1021-1023`,
`htup_details.h:355-362`).

`HeapTupleHeaderXminCommitted(tuple)` returns true if **either** the
committed-bit or both-bits-frozen is set, so `HEAP_XMIN_FROZEN` always
hits gate 4 (xmax). [verified-by-code] (`htup_details.h:341-353`).

## Batched MVCC — amortizing the hint-bit bookkeeping

`SetHintBits` may want to call `BufferBeginSetHintBits` (page-level
coordination so multiple backends don't fight). That's not free. When a
caller is running MVCC on many tuples in the same buffer (e.g. a
`heap_scan_page` after pruning), `HeapTupleSatisfiesMVCCBatch` amortizes
the cost:

```c
/* heapam_visibility.c:1689-1719 */
int HeapTupleSatisfiesMVCCBatch(snap, buf, ntups, batchmvcc, vistuples_dense) {
    int nvis = 0;
    SetHintBitsState state = SHB_INITIAL;
    for (int i = 0; i < ntups; i++) {
        bool valid = HeapTupleSatisfiesMVCC(&batchmvcc->tuples[i], snap, buf, &state);
        batchmvcc->visible[i] = valid;
        if (likely(valid))
            vistuples_dense[nvis++] = batchmvcc->tuples[i].t_self.ip_posid;
    }
    if (state == SHB_ENABLED)
        BufferFinishSetHintBits(buf, true, true);
    return nvis;
}
```

The `SetHintBitsState` is shared across all `ntups` invocations:
- `SHB_INITIAL` — the first hint-bit attempt calls
  `BufferBeginSetHintBits`; if it fails (someone else is mid-IO), flip
  to `SHB_DISABLED` and skip all subsequent hint sets in this batch.
- `SHB_ENABLED` — keep setting hints; one `BufferFinishSetHintBits` call
  at the end.
- `SHB_DISABLED` — silently skip.

This pattern is also the gate that makes hint-bit setting **per-page,
serialized across backends** so a checksummed page-IO can't tear under a
concurrent hint write. [verified-by-code] (`heapam_visibility.c:91-99`).
[from-comment] (`heapam_visibility.c:82-99`).

## HistoricMVCC — the logical-decoding twist

Logical decoding replays a transaction's changes "as if" running against
the catalog snapshot at the moment of each change. A normal MVCC snapshot
won't work because the catalog xacts may all be long-committed; HistoricMVCC
flips the test (`heapam_visibility.c:1504`):

1. **xmin in our subxip[]** (i.e. one of the xacts we are decoding) →
   resolve cmin via `ResolveCminCmaxDuringDecoding`, which consults a
   side-table that logical decoding populates from the
   `HEAP_INSERT`/`HEAP_UPDATE` records' combocid info.
2. **xmin < snapshot->xmin** (committed before our decoding window) →
   normal CLOG check.
3. **xmin >= snapshot->xmax** (after our window) → invisible.
4. **xmin in xip[]** (committed in our window) → visible.
5. **None of the above** (in our window but not committed) → invisible.

The cmin/cmax resolution is the key inversion: normal MVCC reads the
tuple header directly, but a tuple inside a still-being-decoded
transaction may have had a combocid stored in `t_cid`, and the actual
`(cmin, cmax)` pair lives in the decoder's
`HistoricSnapshotGetTupleCids()` side-table.
[verified-by-code] (`heapam_visibility.c:1521-1561`). See
[[combocid-handling]] for the combocid mechanics.

## HeapTupleSatisfiesVacuum — the other oracle

VACUUM doesn't ask "is this visible to a snapshot?"; it asks "could any
snapshot still see this?" The answer drives **prune** (recently-dead-but-
maybe-needed) vs **remove** (definitely-removable).

```c
/* heapam_visibility.c:1112 */
HTSV_Result {
    HEAPTUPLE_DEAD,                /* removable now */
    HEAPTUPLE_LIVE,                /* visible to someone */
    HEAPTUPLE_RECENTLY_DEAD,       /* dead, but maybe visible to an older snap */
    HEAPTUPLE_INSERT_IN_PROGRESS,  /* inserting xact still running */
    HEAPTUPLE_DELETE_IN_PROGRESS,  /* deleting xact still running */
}
```

The cutoff is `OldestXmin` from `GetOldestNonRemovableTransactionId()` —
the global "oldest xid that any snapshot could see." A tuple deleted by
`xmax >= OldestXmin` is `RECENTLY_DEAD`; only when `xmax < OldestXmin`
can we be sure no snapshot still references it. See
[[xmin-horizon-management]] for how this horizon is computed and
advanced. [from-comment] (`heapam_visibility.c:1099-1110`).

## Invariants and edge cases

1. **`HEAP_XMIN_FROZEN` short-circuits `XidInMVCCSnapshot`** — a frozen
   xmin is treated as "before any current snapshot's xmin", regardless of
   the raw XID value. [verified-by-code] (`heapam_visibility.c:1021-1023`).
2. **`HEAP_XMAX_INVALID` is set lazily** by visibility code when it
   observes that xmax aborted/crashed. Subsequent visitors short-circuit.
   [verified-by-code] (`heapam_visibility.c:995-998`,
   `heapam_visibility.c:1077-1078`).
3. **`HEAP_XMAX_LOCK_ONLY` means tuple is alive** even if xmax is valid.
   `FOR UPDATE`/`FOR SHARE` lockers write a multixact (or a single locker
   xmax with the LOCK_ONLY bit) but the row is not deleted.
   [verified-by-code] (`htup_details.h:222-234`).
4. **Self-visibility uses combocid when needed.** A tuple updated by an
   earlier command in the same xact has its `cmin` (insert-cmd) AND `cmax`
   (delete-cmd) packed into a combocid via `[[combocid-handling]]`.
   [verified-by-code] (`heapam_visibility.c:963-965`,
   `htup_details.h:323-339`).
5. **`SetHintBitsExt` may silently skip** if the WAL flush precondition
   isn't met or if hint-bit acquisition fails. The caller doesn't know
   and proceeds with the unhinted tuple; a future visitor will retry.
   [from-comment] (`heapam_visibility.c:115-122`). See
   [[hint-bits-setbufferdirty]].
6. **`HeapTupleSatisfiesUpdate` returns `TM_*` not bool** so callers
   (`heap_update`/`heap_delete`/`heap_lock_tuple`) can distinguish "row
   was modified by another xact" from "row is invisible to me."
   [verified-by-code] (`heapam_visibility.c:511-757`).
7. **`HeapTupleSatisfiesAny` always returns true** — used for system
   bootstrap, `pg_visibility` extension introspection, and a few corner
   cases. [verified-by-code] (`heapam_visibility.c:430-450`).

## Useful greps

```bash
# Every Satisfies routine entry:
grep -n "HeapTupleSatisfies" source/src/backend/access/heap/heapam_visibility.c

# Where the dispatcher is called from:
grep -rn "HeapTupleSatisfiesVisibility" source/src/backend/

# Hint-bit setting sites:
grep -n "SetHintBits\|SetHintBitsExt" source/src/backend/access/heap/heapam_visibility.c

# How XidInMVCCSnapshot works:
grep -n "XidInMVCCSnapshot" source/src/backend/utils/time/snapmgr.c

# All callers of HeapTupleSatisfiesUpdate (the TM_* version):
grep -rn "HeapTupleSatisfiesUpdate\b" source/src/backend/access/heap/
```

## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/access/heap/heapam_visibility.c`](../files/src/backend/access/heap/heapam_visibility.c.md) | 1 | module banner: the race rule (TransactionIdIsInProgress before TransactionIdDidCommit) |
| [`src/backend/access/heap/heapam_visibility.c`](../files/src/backend/access/heap/heapam_visibility.c.md) | 38 | summary of all seven Satisfies routines |
| [`src/backend/access/heap/heapam_visibility.c`](../files/src/backend/access/heap/heapam_visibility.c.md) | 939 | HeapTupleSatisfiesMVCC (the gauntlet itself) |
| [`src/backend/access/heap/heapam_visibility.c`](../files/src/backend/access/heap/heapam_visibility.c.md) | 1113 | HeapTupleSatisfiesVacuum / …VacuumHorizon (the vacuum oracle) |
| [`src/backend/access/heap/heapam_visibility.c`](../files/src/backend/access/heap/heapam_visibility.c.md) | 1504 | HeapTupleSatisfiesHistoricMVCC (logical decoding) |
| [`src/backend/access/heap/heapam_visibility.c`](../files/src/backend/access/heap/heapam_visibility.c.md) | 1689 | HeapTupleSatisfiesMVCCBatch (amortized hint-bit overhead) |
| [`src/backend/access/heap/heapam_visibility.c`](../files/src/backend/access/heap/heapam_visibility.c.md) | 1731 | HeapTupleSatisfiesVisibility (the dispatcher) |
| [`src/include/access/htup_details.h`](../files/src/include/access/htup_details.h.md) | 204 | the infomask bit definitions (HEAP_XMIN_COMMITTED/_INVALID/_FROZEN, HEAP_XMAX_) |
| [`src/include/utils/snapshot.h`](../files/src/include/utils/snapshot.h.md) | — | SnapshotData and snapshot_type enum |

<!-- /callsites:auto -->

## Scenarios that use me
<!-- scenarios:auto -->

*Auto-derived from direct references + transitive file-overlap.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

_(none detected — this idiom is either cross-cutting infrastructure or an internal helper pattern)_

<!-- /scenarios:auto -->
## Cross-references

- [[hint-bits-setbufferdirty]] — `SetHintBits`/`SetHintBitsExt` machinery, the WAL-flush precondition.
- [[heap-tuple-freeze]] — how `HEAP_XMIN_FROZEN` gets set and what it means.
- [[combocid-handling]] — cmin/cmax encoding for self-modifying transactions.
- [[heaptuple-update-chain]] — `HeapTupleSatisfiesUpdate` and the `TM_*` result codes.
- [[tuple-locking-modes]] — `HEAP_XMAX_IS_MULTI` and `HeapTupleGetUpdateXid`.
- [[xmin-horizon-management]] — `OldestXmin` computation that drives `HeapTupleSatisfiesVacuum`.
- [[clog-slru]] — `TransactionIdDidCommit` consults this.
- `knowledge/subsystems/access-heap.md` §"Visibility" — subsystem-level view.
