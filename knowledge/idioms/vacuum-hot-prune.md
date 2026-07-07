# HOT-chain pruning — collapse + redirect + LP_DEAD with a deferred-WAL plan

A heap page may accumulate dead row versions: HOT updates leave a chain of
heap-only tuples linked through `t_ctid`, each pointing to the next
version. When the chain ages out, **pruning** collapses the chain in
place. The interface is `heap_page_prune_and_freeze` (`pruneheap.c:1089`),
which is the **single entry point** for both opportunistic prunes (on
heap access) and VACUUM's first pass.

The mechanism mirrors the freeze module's design: **plan outside the
critical section, execute inside.** A `PruneState` accumulates per-page
arrays of changes (`redirected[]`, `nowdead[]`, `nowunused[]`,
`frozen[]`), then `heap_page_prune_execute` + `heap_freeze_prepared_tuples`
apply them inside a single `START_CRIT_SECTION` plus one WAL record
(`XLOG_HEAP2_PRUNE_*`).

This doc walks the HOT chain shape, the three pruning outcomes for a chain
(all-dead → LP_DEAD root, partially-dead → LP_REDIRECT root, all-live →
unchanged), the `heap_prune_chain` per-chain walker, the page-level
critical-section assembly, and the on-access fast path
`heap_page_prune_opt`.

Companion docs:
- [[heap-tuple-freeze]] — the same plan-then-execute split applied to freeze.
- [[vacuum-tid-store]] — where vacuum stashes the LP_DEAD pointers for index cleanup.
- [[vacuum-two-pass-heap]] — vacuumlazy.c's three-pass orchestration that calls this.
- [[heaptuple-update-chain]] — the HOT chain definition (HEAP_ONLY_TUPLE / HEAP_HOT_UPDATED / t_ctid linkage).

## Anchors

- `source/src/backend/access/heap/pruneheap.c:1-13` — banner.
- `source/src/backend/access/heap/pruneheap.c:34-150` — `PruneState` struct.
- `source/src/backend/access/heap/pruneheap.c:269-390` — `heap_page_prune_opt` (the on-access entry).
- `source/src/backend/access/heap/pruneheap.c:1089-1350` — `heap_page_prune_and_freeze` (the unified entry).
- `source/src/backend/access/heap/pruneheap.c:1483-1682` — `heap_prune_chain` (per-HOT-chain walker).
- `source/src/backend/access/heap/pruneheap.c:2064-2224` — `heap_page_prune_execute` (the in-crit-section applier).
- `source/src/backend/access/heap/pruneheap.c:2240-2270` — `page_verify_redirects` (assert-only redirect sanity).
- `source/src/include/storage/itemid.h` — LP_NORMAL / LP_REDIRECT / LP_DEAD / LP_UNUSED line-pointer states.
- `source/src/include/access/heapam_xlog.h` — `XLOG_HEAP2_PRUNE_*` record types.

## Line-pointer states — the prune alphabet

Every item on a heap page is a line pointer (`ItemId`) with 4 possible
states encoded in 2 flag bits:

| State          | Bits | Tuple storage? | Used by                                  |
|----------------|------|----------------|------------------------------------------|
| `LP_UNUSED`    | 00   | no             | available for reuse                       |
| `LP_NORMAL`    | 01   | yes            | regular item with a tuple                 |
| `LP_REDIRECT`  | 10   | no — has offset | HOT chain root after collapse             |
| `LP_DEAD`      | 11   | maybe          | dead but TID may still appear in indexes  |

The four prune transitions:

```
LP_NORMAL (regular root, all dead)            →  LP_DEAD
LP_NORMAL (HOT-chain root, partially dead)    →  LP_REDIRECT(to first live)
LP_NORMAL (heap-only intermediate, removed)   →  LP_UNUSED
LP_REDIRECT → LP_REDIRECT (target updated)    →  re-point to new live tuple
```

`LP_DEAD` exists because the TID may still be referenced by an index entry
that VACUUM hasn't reached yet. Removing the line pointer outright would
turn the index entry into a dangling pointer to a recycled slot. The
sequence is: pruning sets `LP_DEAD` (heap pass 1) → VACUUM cleans
indexes → VACUUM converts `LP_DEAD` to `LP_UNUSED` (heap pass 2). See
[[vacuum-two-pass-heap]] for the orchestration.

## HOT chains — the shape being collapsed

A HOT (Heap-Only Tuple) chain is a sequence of row versions on the **same
page** linked by `t_ctid`:

```
LP_NORMAL [root: HEAP_HOT_UPDATED, t_ctid=offset2] → tuple v1
LP_NORMAL [offset2: HEAP_ONLY_TUPLE | HEAP_HOT_UPDATED, t_ctid=offset3] → tuple v2
LP_NORMAL [offset3: HEAP_ONLY_TUPLE, t_ctid=self] → tuple v3 (current)
```

Only the **root** is referenced by indexes — the heap-only intermediates
(`HEAP_ONLY_TUPLE` set) are invisible to index scans. This is why HOT
update was added: an update that doesn't modify any indexed column can
extend the chain without touching every index. See
[[heaptuple-update-chain]] for the data model.

Pruning the chain (`heap_prune_chain`, `pruneheap.c:1483`) walks the
chain following `t_ctid` and classifies each tuple via
`HeapTupleSatisfiesVacuum` (cached as `htsv[]` to avoid recomputing per
visit). Three outcomes:

1. **Entire chain `HEAPTUPLE_DEAD`** → mark root `LP_DEAD`, mark every
   intermediate `LP_UNUSED`. The root retains its position because an
   index entry may still point at it. (`pruneheap.c:1656-1665`).
2. **Some prefix dead, suffix live** → set root to `LP_REDIRECT` pointing
   at the first non-dead chain member; mark dead intermediates
   `LP_UNUSED`. The redirect collapses the chain so subsequent index
   scans land directly on the live version. (`pruneheap.c:1666-1681`).
3. **Entirely live (or only `RECENTLY_DEAD`)** → leave alone.
   (`pruneheap.c:1640-1655`).

The walker tracks `ndeadchain = index of last DEAD seen + 1`. The
"prefix DEAD then RECENTLY_DEAD" case treats RECENTLY_DEAD as dead-enough
**only if followed by a hard DEAD** — RECENTLY_DEAD by itself stays live
to honor possible older snapshots. The comment is explicit: "We don't need
to advance the conflict horizon for RECENTLY_DEAD tuples, even if we are
removing them. … the DEAD tuple must have been inserted by a newer
transaction." [from-comment] (`pruneheap.c:1576-1594`).

The walk stops on:
- `HEAPTUPLE_LIVE` / `_INSERT_IN_PROGRESS` / `_DELETE_IN_PROGRESS` — chain
  continues but we can't prune it.
- `priorXmax != current xmin` — chain broken (xact aborted or wrong
  chain).
- A normal-tuple-not-HOT-updated — end of chain.
- An offset already processed — must not be the same chain.

[verified-by-code] (`pruneheap.c:1505-1622`).

## The plan struct — PruneState arrays

```c
/* pruneheap.c:34-150 (abridged) */
typedef struct {
    GlobalVisState   *vistest;        /* visibility horizon */
    bool              mark_unused_now;
    bool              attempt_freeze;
    bool              attempt_set_vm;
    VacuumCutoffs    *cutoffs;        /* freeze cutoffs */

    BlockNumber       block;
    Buffer            buffer;
    Page              page;

    TransactionId     new_prune_xid;        /* lowest soon-prunable XID */
    TransactionId     latest_xid_removed;   /* for replay conflict horizon */
    int               nredirected, ndead, nunused, nfrozen;
    OffsetNumber      redirected[MaxHeapTuplesPerPage * 2];  /* pairs: from,to */
    OffsetNumber      nowdead[MaxHeapTuplesPerPage];
    OffsetNumber      nowunused[MaxHeapTuplesPerPage];
    HeapTupleFreeze   frozen[MaxHeapTuplesPerPage];

    bool              set_all_visible, set_all_frozen;
    bool              processed[MaxHeapTuplesPerPage + 1];
    int8              htsv[MaxHeapTuplesPerPage + 1];   /* cached vacuum status */
    /* ... HOT-chain working state ... */
} PruneState;
```

`redirected[]` is twice the max because each redirect is a `(from, to)`
pair: from = root offset, to = first live tuple offset.
`MaxHeapTuplesPerPage` is the per-page cap on tuples — depends on
`BLCKSZ`/`sizeof(HeapTupleHeader)` but typically ~300 at 8 KiB.
[verified-by-code] (`pruneheap.c:72-75`).

`htsv[]` is the cached `HTSV_Result` per offset. Pruning visits each
chain root, but a HOT chain may be walked from multiple roots if not
careful — `processed[]` is the bitmap that prevents revisiting. The
cache means we call `HeapTupleSatisfiesVacuum` once per tuple even when
the chain is walked.

## The top-level orchestration

`heap_page_prune_and_freeze` (`pruneheap.c:1089`) is the linear sequence:

```
prune_freeze_setup           — fill PruneState from params
heap_page_fix_vm_corruption  — if VM bit set but PD_ALL_VISIBLE off, fix

if PRUNE_ALLOW_FAST_PATH and (all-frozen or (all-visible and !attempt_freeze)):
    prune_freeze_fast_path; return

prune_freeze_plan            — populate the arrays:
    for each unprocessed offset on page:
        if has tuple: heap_prune_chain(...)
        if attempt_freeze: heap_prepare_freeze_tuple → frozen[nfrozen++]

# After planning:
clear set_all_visible if newest_live_xid still in any snapshot's running set
do_prune       = nredirected || ndead || nunused
do_hint_prune  = pd_prune_xid changed or PageIsFull
do_freeze      = heap_page_will_freeze(...)
do_set_vm      = heap_page_will_set_vm(...)

# Snapshot conflict horizon = max(vm.newest_live_xid, freeze.conflict_xid, prune.latest_xid_removed)

if do_set_vm: lock vmbuffer EXCLUSIVE        # before crit section
START_CRIT_SECTION();

if do_hint_prune:
    page.pd_prune_xid = new_prune_xid
    PageClearFull(page)
    if !do_freeze && !do_prune && !do_set_vm:
        MarkBufferDirtyHint(buffer, true)    # hint-only path, no full WAL

if do_prune || do_freeze || do_set_vm:
    if do_prune:  heap_page_prune_execute(buffer, false, redirected, ...,
                                          nowdead, ..., nowunused, ...)
    if do_freeze: heap_freeze_prepared_tuples(buffer, frozen, nfrozen)
    if do_set_vm: PageSetAllVisible; visibilitymap_set(...)
    MarkBufferDirty(buffer)
    if RelationNeedsWAL:
        log_heap_prune_and_freeze(... → XLOG_HEAP2_PRUNE_*)

END_CRIT_SECTION();
if do_set_vm: unlock vmbuffer
```

[verified-by-code] (`pruneheap.c:1089-1350`).

The split is the same fingerprint as freeze: the plan can fail (set
`set_all_visible = false`, decide not to freeze), but the in-crit-section
work is a deterministic apply of accumulated arrays. WAL replay can run
the same applier from the record's encoded arrays.

The `heap_page_fix_vm_corruption` step at entry is a corruption recovery:
if the VM bit is set but `PD_ALL_VISIBLE` is clear (a known crash-fallout
state), repair them to a consistent state before the regular logic runs.

## The applier — heap_page_prune_execute

```c
/* pruneheap.c:2064-2224 */
void heap_page_prune_execute(Buffer buffer, bool lp_truncate_only,
                             OffsetNumber *redirected, int nredirected,
                             OffsetNumber *nowdead, int ndead,
                             OffsetNumber *nowunused, int nunused)
{
    /* Three independent loops, applied in order */
    for (i = 0; i < nredirected; i++)
        ItemIdSetRedirect(itemid_at(redirected[2i]), redirected[2i+1]);

    for (i = 0; i < ndead; i++)
        ItemIdSetDead(itemid_at(nowdead[i]));

    for (i = 0; i < nunused; i++)
        ItemIdSetUnused(itemid_at(nowunused[i]));

    if (lp_truncate_only)
        PageTruncateLinePointerArray(page);   /* vacuum's second pass */
    else {
        PageRepairFragmentation(page);
        page_verify_redirects(page);          /* assert-only */
    }
}
```

This is also called from replay (decoded arrays come from the WAL record)
and from VACUUM's second pass to convert `LP_DEAD` → `LP_UNUSED` (the
`lp_truncate_only = true` mode, which skips fragmentation repair because
no tuple storage moved). [verified-by-code] (`pruneheap.c:2064-2078`).

`PageRepairFragmentation` compacts tuple data by sliding live tuples toward
the higher-address end of the page and rebuilding the line-pointer array
to match. Free space coalesces in the middle. The line-pointer offsets in
`redirected[]` survive because line pointers are stable across
fragmentation repair — only tuple-data positions change.

## Why LP_REDIRECT stays after the chain collapses

The "must keep around an LP_REDIRECT" rule is one of the more subtle
invariants:

> We need to keep around an LP_REDIRECT item (after original non-heap-only
> root tuple gets pruned away) so that it's always possible for VACUUM to
> easily figure out what TID to delete from indexes when an entire HOT
> chain becomes dead. A heap-only tuple can never become LP_DEAD; an
> LP_REDIRECT item or a regular heap tuple can.

[from-comment] (`pruneheap.c:2117-2122`).

Index entries point at the **root TID**. When the entire chain dies, the
root must become `LP_DEAD` (not `LP_UNUSED`) so VACUUM's index cleanup
can find the right entries to delete. If the root were `LP_UNUSED`, a
later heap insert could reuse the slot for an unrelated row, and the
stale index entry would now point to a wrong tuple.

So pruning transitions follow this asymmetry:
- Heap-only intermediate dies → `LP_UNUSED` (no index references it).
- Chain root dies → `LP_DEAD` (indexes reference it; await VACUUM pass 2).
- Chain partially dies → root becomes `LP_REDIRECT` to first live; index
  scans following the redirect still land on the live tuple.

## The on-access entry — heap_page_prune_opt

`heap_page_prune_opt` (`pruneheap.c:269`) is the **opportunistic** pruner
called from `heap_fetch_next_buffer` and similar hot paths. It's
short-circuit-heavy:

```c
void heap_page_prune_opt(Relation rel, Buffer buffer, Buffer *vmbuffer,
                         bool rel_read_only) {
    if (RecoveryInProgress()) return;                            /* can't WAL */
    if (!TransactionIdIsValid(PageGetPruneXid(page))) return;    /* no pending dead */
    if (!GlobalVisTestIsRemovableXid(vistest, prune_xid, true))  /* none removable yet */
        return;

    minfree = max(RelationGetTargetPageFreeSpace(rel, FILLFACTOR), BLCKSZ/10);
    if (PageIsFull(page) || PageGetHeapFreeSpace(page) < minfree) {
        if (!ConditionalLockBufferForCleanup(buffer)) return;    /* don't block */
        if (PageIsFull(page) || PageGetHeapFreeSpace(page) < minfree) {
            heap_page_prune_and_freeze(... PRUNE_ON_ACCESS ...
                                       PRUNE_ALLOW_FAST_PATH +
                                       (rel_read_only ? PRUNE_SET_VM : 0));
            ...
        }
        LockBuffer(buffer, BUFFER_LOCK_UNLOCK);
    }
}
```

Three guard gates:
1. **Not in recovery** — opportunistic pruning can't run when WAL is
   read-only.
2. **`pd_prune_xid` set** — a per-page hint XID written by inserters/
   updaters when a tuple "might soon be prunable" (deleted, aborted,
   or HOT-updated). Zero means nothing to do without consulting CLOG.
3. **`GlobalVisTestIsRemovableXid(prune_xid)`** — quick check that some
   transaction younger than `prune_xid` has committed.

The space gate uses `RelationGetTargetPageFreeSpace` (fillfactor target,
default 100% = 0 free) clamped to at least `BLCKSZ / 10`. The "questionable
without buffer lock" comment notes the page-fullness read is racy but
acceptable: "Avoiding taking a lock seems more important than sometimes
getting a wrong answer in what is after all just a heuristic estimate."
[from-comment] (`pruneheap.c:312-316`).

The **`ConditionalLockBufferForCleanup`** is critical: we MUST NOT block.
A regular reader that hits a stuck prune would propagate the wait to its
caller. If the cleanup lock isn't available immediately, return silently
and let a later visitor try. The fact that this lock is *cleanup* (not
just exclusive) means we wait for all pin holders to drain — a HOT
prune that moves tuples around can't run while another backend holds a
pointer into the page.

`PRUNE_ALLOW_FAST_PATH` is the opt-in for skipping work on
already-all-frozen or already-all-visible pages (no need to scan tuples
again). [verified-by-code] (`pruneheap.c:1127-1133`).

Importantly, `heap_page_prune_opt` doesn't update FSM after pruning:
"We avoid reuse of any free space created on the page by unrelated
UPDATEs/INSERTs by opting to not update the FSM at this point. The free
space should be reused by UPDATEs to *this* page." [from-comment]
(`pruneheap.c:384-387`).

## Snapshot conflict horizons

The WAL record's `conflict_xid` field is the **most conservative**
(newest) XID across all three transformations:

```c
/* pruneheap.c:1217-1223 */
conflict_xid = InvalidTransactionId;
if (do_set_vm)
    conflict_xid = prstate.newest_live_xid;
if (do_freeze && ... FreezePageConflictXid > conflict_xid)
    conflict_xid = prstate.pagefrz.FreezePageConflictXid;
if (do_prune && prstate.latest_xid_removed > conflict_xid)
    conflict_xid = prstate.latest_xid_removed;
```

On a hot standby, replaying this WAL record waits for any snapshot
that might still see this XID as running. The three sources contribute:
- Setting VM all-visible: newest live xmin on the page.
- Freezing: the `FreezePageConflictXid` from
  [[heap-tuple-freeze]] — newest xmin being removed from visibility.
- Pruning: the dead-tuple chain horizons, accumulated via
  `HeapTupleHeaderAdvanceConflictHorizon`.

[verified-by-code] (`pruneheap.c:1217-1223`).

## Invariants and races

1. **Cleanup lock required** for the main `heap_page_prune_execute` mode
   (`lp_truncate_only = false`). The fragmentation-repair step moves
   tuple data; concurrent pin holders would see torn reads.
   [from-comment] (`pruneheap.c:2058-2062`).
2. **`lp_truncate_only` mode requires only ordinary exclusive lock** —
   used by VACUUM's second pass to flip `LP_DEAD` to `LP_UNUSED`. No
   data motion, just line-pointer bits. [from-comment] (`pruneheap.c:2060-2062`).
3. **Pruning is opportunistic; failure is silent.** `heap_page_prune_opt`
   returns without complaint if cleanup lock unavailable or page
   genuinely doesn't need pruning. [verified-by-code]
   (`pruneheap.c:325-326`).
4. **`LP_DEAD` is the bridge state between heap pass 1 and pass 2.** The
   line-pointer survives index cleanup so the TID is preserved for
   index lookups to find and delete. Only then does pass 2 set
   `LP_UNUSED`. [from-comment] (`pruneheap.c:2117-2122`).
5. **`heap-only tuple → LP_DEAD` is forbidden** — heap-only tuples are
   not referenced from indexes, so they go straight to `LP_UNUSED`.
   The assertion at `pruneheap.c:2153-2158` enforces this.
6. **`pd_prune_xid` is a page-level hint** updated under the buffer
   content lock but written without WAL. `heap_page_prune_opt` consults
   it as a fast cheap "anything to do?" check. [from-comment]
   (`pruneheap.c:286-295`).
7. **`page_verify_redirects` runs only in assert builds** but encodes
   the redirect-must-target-heap-only invariant. A redirect pointing at a
   non-heap-only tuple, or at an `LP_UNUSED`, is a corruption bug.
   [from-comment] (`pruneheap.c:2227-2238`).

## Useful greps

```bash
# Every entry into pruning:
grep -rn "heap_page_prune_and_freeze\|heap_page_prune_opt\|heap_page_prune_execute" \
       source/src/backend/access/heap/

# The cleanup-lock requirement:
grep -rn "LockBufferForCleanup\|ConditionalLockBufferForCleanup" source/src/backend/

# HOT-chain link semantics:
grep -nE "HEAP_HOT_UPDATED|HEAP_ONLY_TUPLE|HeapTupleHeaderIsHotUpdated" \
       source/src/include/access/htup_details.h

# WAL record format for prune:
grep -n "XLOG_HEAP2_PRUNE\|xl_heap_prune\b" \
       source/src/include/access/heapam_xlog.h \
       source/src/backend/access/heap/pruneheap.c

# pd_prune_xid hint mechanics:
grep -rn "PageSetPrunable\|PageGetPruneXid\|pd_prune_xid" source/src/backend/
```



## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/access/heap/pruneheap.c`](../files/src/backend/access/heap/pruneheap.c.md) | 1 | banner |
| [`src/backend/access/heap/pruneheap.c`](../files/src/backend/access/heap/pruneheap.c.md) | 34 | PruneState struct |
| [`src/backend/access/heap/pruneheap.c`](../files/src/backend/access/heap/pruneheap.c.md) | 269 | heap_page_prune_opt (the on-access entry) |
| [`src/backend/access/heap/pruneheap.c`](../files/src/backend/access/heap/pruneheap.c.md) | 1089 | heap_page_prune_and_freeze (the unified entry) |
| [`src/backend/access/heap/pruneheap.c`](../files/src/backend/access/heap/pruneheap.c.md) | 1483 | heap_prune_chain (per-HOT-chain walker) |
| [`src/backend/access/heap/pruneheap.c`](../files/src/backend/access/heap/pruneheap.c.md) | 2064 | heap_page_prune_execute (the in-crit-section applier) |
| [`src/backend/access/heap/pruneheap.c`](../files/src/backend/access/heap/pruneheap.c.md) | 2240 | page_verify_redirects (assert-only redirect sanity) |
| [`src/include/access/heapam_xlog.h`](../files/src/include/access/heapam_xlog.h.md) | — | XLOG_HEAP2_PRUNE_ record types |
| [`src/include/storage/itemid.h`](../files/src/include/storage/itemid.h.md) | — | LP_NORMAL / LP_REDIRECT / LP_DEAD / LP_UNUSED line-pointer states |

<!-- /callsites:auto -->

## Cross-references

- [[heap-tuple-freeze]] — same plan-then-execute model, applied in the same critical section.
- [[heaptuple-update-chain]] — HOT chain structure (HEAP_ONLY_TUPLE / HEAP_HOT_UPDATED).
- [[vacuum-tid-store]] — LP_DEAD offsets get fed into the dead-TID radix tree.
- [[vacuum-two-pass-heap]] — the orchestration that calls this for VACUUM's first pass.
- [[heap-tuple-visibility-mvcc]] — the visibility verdicts (`HEAPTUPLE_DEAD` / `_RECENTLY_DEAD` / `_LIVE` / `_*_IN_PROGRESS`) that drive chain classification.
- [[hint-bits-setbufferdirty]] — `MarkBufferDirtyHint` for the hint-only `pd_prune_xid` update path.
- [[visibility-map-update]] — the VM all-visible/all-frozen bits set by this same WAL record.
- `knowledge/subsystems/access-heap.md` §"HOT pruning" — subsystem-level view.
