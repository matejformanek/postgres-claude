# pruneheap.c

- **Source path:** `source/src/backend/access/heap/pruneheap.c`
- **Lines:** 2735
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `README.HOT` (the design doc), `heapam.h` (`PruneFreezeParams`/`PruneFreezeResult`), `heapam_xlog.c` (`heap_xlog_prune_freeze`), `vacuumlazy.c` (primary caller).

## Purpose

Implements heap page pruning and HOT-chain management: on-access pruning (`heap_page_prune_opt`) and the unified VACUUM pruning + freezing + VM-setting (`heap_page_prune_and_freeze`). Pruning removes dead HOT tuples within a single page, turns root line pointers into LP_REDIRECT, and marks fully-dead line pointers LP_DEAD (or LP_UNUSED if no index points to them). The unified entry point also computes freeze plans, sets VM bits, and emits a single combined WAL record. [from-comment, README.HOT; verified-by-code, pruneheap.c top]

## Top-of-file comment
> "heap page pruning and HOT-chain management code" [from-comment, pruneheap.c:1-12]

## Public surface (non-static functions)

- `heap_page_prune_opt(Relation, Buffer, Buffer *vmbuffer, bool rel_read_only)` (line 271) — Opportunistic on-access pruning. Called from scan paths; cheap check for whether to bother, then prunes with a cleanup lock if there's enough win.
- `heap_page_prune_and_freeze(PruneFreezeParams *params, PruneFreezeResult *presult, OffsetNumber *off_loc, TransactionId *new_relfrozen_xid, MultiXactId *new_relmin_mxid)` (line 1090) — The big one. Used by VACUUM and (with FREEZE option off) by `heap_page_prune_opt`. Produces a `PruneFreezeResult` and updates relfrozenxid trackers.
- `heap_page_prune_execute(Buffer, bool lp_truncate_only, OffsetNumber *redirected, int nredirected, OffsetNumber *nowdead, int ndead, OffsetNumber *nowunused, int nunused)` (line 2065) — Apply the pre-computed offset arrays to the page. Used both by the live emitter and by redo.
- `heap_get_root_tuples(Page page, OffsetNumber *root_offsets)` (line 2289) — For each offset, find the root of its HOT chain. Used by VACUUM to map index TIDs back to roots.
- `log_heap_prune_and_freeze(Relation, Buffer, Buffer vmbuffer, uint8 vmflags, TransactionId conflict_xid, bool cleanup_lock, PruneReason, frozen, nfrozen, redirected, nredirected, dead, ndead, unused, nunused)` (line 2561) — Emit the WAL record matching the just-applied modifications.

## Static helpers (selection)

- `prune_freeze_setup` (400), `prune_freeze_plan` (531), `prune_freeze_fast_path` (1007) — split-out phases of the unified pruning code path.
- `heap_page_will_freeze` (734), `heap_page_will_set_vm` (950), `heap_page_fix_vm_corruption` (852) — predicates the planner uses.
- `heap_prune_chain` (1483) — walks a HOT chain starting from a root LP and decides what to do with each member.
- `heap_prune_satisfies_vacuum` (1401) + `htsv_get_valid_status` (1444) — wrappers around `HeapTupleSatisfiesVacuum` that share state across chain walking.
- `heap_prune_record_*` family (1686-2040) — accumulators that record planned redirects, dead lp's, unused lp's, freeze plans.
- `heap_log_freeze_*` (2400, 2416, 2462, 2482) — group identical freeze plans for compact WAL.
- `page_verify_redirects` (2241) — assertion-only consistency check on a freshly-pruned page.

## Key types / structs

- `PruneState` (pruneheap.c:~74, struct begins at line 520 in the listing; the comment block starts at line 520 in the visible head) — Working state for one page. Carries vistest, cutoffs, arrays of planned changes (redirected[MaxHeapTuplesPerPage*2], nowdead[], nowunused[], frozen[]), and accumulators `set_all_visible`/`set_all_frozen`, `latest_xid_removed`. Sized for the maximum number of items per page so no allocation happens per-page. [verified-by-code]

## Key invariants and locking

- **Cleanup-lock vs exclusive-lock split.** Pruning that moves tuple data (redirect creation, LP_DEAD assignment of an item containing a tuple) requires a **buffer cleanup lock**. Freeze-only or "mark already-LP_DEAD lp unused" can run under an ordinary exclusive lock. The XLHP_CLEANUP_LOCK WAL flag encodes which one redo needs. [from-comment, heapam_xlog.h:302-310]
- **HOT chain rules** (enforced by `heap_prune_chain`): chain begins at a non-HOT-only root LP; subsequent members have HEAP_ONLY_TUPLE; chain ends at a member whose t_ctid points to itself, or whose xmin is aborted, or whose t_ctid points outside the page. Index entries reference only roots. [from-readme, README.HOT]
- **Redirecting LP** is created when the root is dead but the chain continues with live or recently-dead members; the root LP is set to LP_REDIRECT pointing to the live member's offset. Indexes keep working because they hit the redirect and follow it forward. [from-readme, README.HOT]
- **VM bit setting** is bundled into the same WAL record as the prune. Setting `PD_ALL_VISIBLE` requires that the page-level check pass AND the cutoff `OldestXmin` rule pass. `heap_page_will_set_vm` (line 950) is the predicate. [verified-by-code]
- **VM corruption repair.** `heap_page_fix_vm_corruption` (line 852) handles the case where the VM bit was set but the page has tuples that should not be visible (e.g., from a long-ago bug or pg_upgrade artefact). It clears the bad VM bit *and* logs a warning. [verified-by-code, from-comment near line 852]
- **Freeze planning vs execution.** `prune_freeze_plan` only *plans* freezing into the `frozen[]` array; execution (modifying tuple headers) happens inside `heap_page_prune_and_freeze` after entering the critical section, just before `heap_page_prune_execute`. The pre-checks (`heap_pre_freeze_checks` in heapam.c) verify xmin-committed / xmax-aborted invariants before any header is touched. [verified-by-code]
- **`PRUNE_VACUUM_CLEANUP`** is the second-pass mode used for `lazy_vacuum_heap_page` — converts LP_DEAD → LP_UNUSED for offsets in the dead-items TID store. Does not move tuple data and so can run under an exclusive lock. [from-comment in heapam_xlog.h]

## Functions of note (deep-read selection)

1. **`heap_page_prune_opt`** (line 271) — Returns immediately if the page is on a read-only relation or has no candidate prunable hint. Otherwise opportunistically attempts a cleanup lock (`ConditionalLockBufferForCleanup`); if it fails, does nothing. The fast-path version (no freeze, no VM-set) is used here. [verified-by-code]

2. **`heap_page_prune_and_freeze`** (line 1090) — Multi-stage:
   1. `prune_freeze_setup` — initialise PruneState from params.
   2. Loop over all line pointers; for each unprocessed root, call `heap_prune_chain`.
   3. After chain walking, compute final VM bit setting via `heap_page_will_set_vm`.
   4. Enter critical section, call `heap_page_prune_execute` to apply offsets, execute freeze plans (`heap_freeze_prepared_tuples`), set VM bits if applicable.
   5. Call `log_heap_prune_and_freeze` to emit the combined WAL.
   6. Return `PruneFreezeResult` to caller (used by vacuumlazy to update stats and decide truncation safety). [verified-by-code]

3. **`heap_prune_chain`** (line 1483) — Recursive HOT-chain walker. For each chain member: determine HTSV status, follow t_ctid forward, decide whether the member can be reclaimed / kept / converted to redirect. The state machine here is **the core of HOT semantics** — getting it wrong means index corruption. The function is well-commented but conceptually dense. [verified-by-code, from-readme]

4. **`heap_page_prune_execute`** (line 2065) — Mechanical: for each offset in redirected[], set the LP to LP_REDIRECT with the new target; for nowdead[], set LP_DEAD; for nowunused[], set LP_UNUSED. Called identically from emit and redo paths — that shared call site is the guarantee that emit and redo stay in sync. [verified-by-code]

5. **`log_heap_prune_and_freeze`** (line 2561) — Variable-length WAL construction: groups identical freeze plans, packs the optional sub-records in the order documented in heapam_xlog.h:250-286, attaches the buffer reference. Records `XLOG_HEAP2_PRUNE_ON_ACCESS` vs `_VACUUM_SCAN` vs `_VACUUM_CLEANUP` based on the `reason` param. [verified-by-code]

## Cross-references

- **Callers:** `heap_page_prune_opt` is called from `heapam.c::heap_page_prune_opt`-adjacent scan paths (sequential scan, index scan, bitmap heap scan via `heap_fetch_next_buffer`-ish); `heap_page_prune_and_freeze` is called by `vacuumlazy.c::lazy_scan_prune` (with `PRUNE_VACUUM_SCAN`) and again from `lazy_vacuum_heap_page` (with `PRUNE_VACUUM_CLEANUP`). `heap_get_root_tuples` is called by VACUUM's TID-store reconciliation. `heap_page_prune_execute` is also called by `heapam_xlog.c::heap_xlog_prune_freeze` during redo. [verified-by-code]
- **Calls into:** `heapam_visibility.c` (`HeapTupleSatisfiesVacuumHorizon`, `HeapTupleIsSurelyDead`), `heapam.c` (`heap_prepare_freeze_tuple`, `heap_freeze_prepared_tuples`, `heap_pre_freeze_checks`), `visibilitymap.c` (pin/set), `bufmgr.c`, `xloginsert.c`.

## Open questions

- The exact criteria in `heap_page_will_freeze` for when "eager freezing" by a normal (non-aggressive) VACUUM is profitable — heuristic. [unverified]
- Behaviour when an LP_REDIRECT's target offset itself becomes LP_DEAD — the chain walker handles this but I did not enumerate every transition. [unverified]
- Performance impact of the per-page `PruneState` size (MaxHeapTuplesPerPage * a few arrays = several KB on the stack). [unverified]

## Confidence tag tally
`[verified-by-code]=18 [from-comment]=4 [from-readme]=4 [inferred]=0 [unverified]=3`
