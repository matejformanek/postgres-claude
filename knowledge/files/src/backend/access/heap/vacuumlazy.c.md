# vacuumlazy.c

- **Source path:** `source/src/backend/access/heap/vacuumlazy.c`
- **Lines:** 3883
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `commands/vacuum.c` (driver / parameter parsing), `commands/vacuumparallel.c` (parallel index vacuum), `pruneheap.c` (per-page work), `visibilitymap.c`, `access/tidstore/*` (the dead-items store).

## Purpose

The lazy ("concurrent", non-blocking) VACUUM driver for heap relations. Drives the three-phase algorithm: phase I scans the heap and prunes/freezes pages, accumulating dead TIDs in a TID store; phase II vacuums every index against that TID store; phase III revisits the heap pages to convert LP_DEAD line pointers to LP_UNUSED. Implements eager freezing, the failsafe (anti-wraparound) bypass, and post-vacuum relation truncation. Updates pg_class stats and the cumulative-stats subsystem. [from-comment, vacuumlazy.c:1-100; verified-by-code]

## Top-of-file comment
> 220-line block (vacuumlazy.c:1-225) — one of the longest in the heap directory. Covers: the three phases, the TID-store fill/drain interleaving, parallel index vacuum reference, FSM update cadence, post-VACUUM truncation; then a long "Relation Scanning" section that explains aggressive vs normal, page-skipping via VM (SKIP_PAGES_THRESHOLD), eager scanning of all-visible-but-not-all-frozen pages, and the MAX_EAGER_FREEZE_SUCCESS_RATE cap. [from-comment, vacuumlazy.c:1-225]

## Public surface (non-static functions)

- `heap_vacuum_rel(Relation, const VacuumParams *, BufferAccessStrategy)` (line 624) — The single public entry point. Sets up `LVRelState`, runs the phases, updates pg_class, frees resources.
- `heap_page_is_all_visible(...)` (line 3550, `USE_ASSERT_CHECKING` only) — Assert helper: re-derive all-visible status from scratch and compare to claim.

## Static spine (selection)

- `lazy_scan_heap` (1279) — phase I driver.
- `heap_vac_scan_next_block` (1648) — read_stream callback supplying the next non-skipped heap block to phase I.
- `find_next_unskippable_block` (1748) — VM-based skip logic with SKIP_PAGES_THRESHOLD; also handles eager-scan accounting.
- `lazy_scan_new_or_empty` (1877) — fast path for empty / new pages: set VM bits without further work.
- `lazy_scan_prune` (2021) — calls `heap_page_prune_and_freeze` for one page; folds returned PruneFreezeResult into vacrel counters.
- `lazy_scan_noprune` (2158) — alternative path when only a shared/exclusive lock is held (no cleanup lock available): can update VM, can record dead items, but cannot do real pruning. Used when cleanup-lock acquisition would block.
- `lazy_vacuum` (2369) — phases II + III dispatcher; checks failsafe; calls index vacuum then heap-reap.
- `lazy_vacuum_all_indexes` (2494), `lazy_cleanup_all_indexes` (2944), `lazy_vacuum_one_index` (3013), `lazy_cleanup_one_index` (3062) — index vacuum / cleanup.
- `lazy_vacuum_heap_rel` (2640), `lazy_vacuum_heap_page` (2758) — phase III: turn LP_DEAD line pointers into LP_UNUSED.
- `vacuum_reap_lp_read_stream_next` (2602) — read_stream callback for phase III.
- `lazy_check_wraparound_failsafe` (2890) — anti-wraparound emergency bypass (skips index vacuum + cleanup if too close to xidStopLimit).
- `lazy_truncate_heap` (3142), `count_nondeletable_pages` (3273), `should_attempt_truncation` (3122) — post-vacuum truncation, including the lock-acquisition retry loop.
- `dead_items_alloc/_add/_reset/_cleanup` (3416, 3481, 3503, 3529) — wrappers over the TID store.
- `heap_vacuum_eager_scan_setup` (497) — initialises the eager-scan state (success cap, region sampling).
- Error-context helpers: `vacuum_error_callback` (3794), `update_vacuum_error_info` (3858), `restore_vacuum_error_info` (3877).

## Key types / structs

- `LVRelState` (defined inside this file; struct begins after the `#include` block) — Holds *everything* about one VACUUM-of-one-relation: relation, indexes, cutoffs, dead-items TID store, scan counters, eager-scan accounting, parallel-context handle, error-context info. The dominant state object.
- `LVSavedErrInfo` — checkpointed copy of error-context info, used when switching between phases that need different error context.

## Key invariants and locking

- **Phase ordering.** Phase I cannot revisit a page once it has been scanned (the TID store holds dead-TIDs and phase III revisits only those pages). [from-comment, vacuumlazy.c:1-100]
- **Cleanup-lock attempt order.** Phase I tries `ConditionalLockBufferForCleanup`; on failure falls through to `lazy_scan_noprune`, which can still set VM bits and record LP_DEAD items but cannot prune. [verified-by-code, lazy_scan_prune vs lazy_scan_noprune]
- **VM bit setting.** Only pages where every tuple is provably visible to every snapshot may be marked `ALL_VISIBLE`. Similar but stricter rule for `ALL_FROZEN`. The PD_ALL_VISIBLE bit on the heap page is kept in sync. [from-comment, visibilitymap.c]
- **Aggressive vacuum** must scan every unfrozen page (cannot skip even all-visible pages that are not all-frozen). [from-comment, vacuumlazy.c:692-696]
- **Eager scanning** is capped at MAX_EAGER_FREEZE_SUCCESS_RATE of all-visible-not-all-frozen pages; once the cap is hit, eager scanning is disabled for the remainder. [from-comment, vacuumlazy.c:713-722]
- **Failsafe bypass** triggered by `lazy_check_wraparound_failsafe` skips phases II and III and continues phase I scanning to advance relfrozenxid as fast as possible. [from-comment + verified-by-code at line 2890]
- **TID store memory cap.** When the TID store hits `maintenance_work_mem`, phase I pauses, phases II + III drain the dead items, then phase I resumes. [from-comment, vacuumlazy.c:21-23]
- **Truncation.** `lazy_truncate_heap` requires AccessExclusiveLock; it gets it with a retry loop and gives up if `count_nondeletable_pages` discovers data added during the lock wait. [verified-by-code]

## Functions of note (deep-read selection)

1. **`heap_vacuum_rel`** (line 624) — Entry sequence: compute cutoffs (`vacuum_get_cutoffs`), open indexes, allocate `LVRelState`, allocate dead-items TID store (`dead_items_alloc`), set up eager-scan state, set up error context, call `lazy_scan_heap`, finalise (`update_relstats_all_indexes`, `vac_update_relstats`, `pgstat_report_vacuum`). [verified-by-code]

2. **`lazy_scan_heap`** (line 1279) — Phase I main loop. Drives the heap read stream (`heap_vac_scan_next_block` → `find_next_unskippable_block`); for each page either fast-paths via `lazy_scan_new_or_empty`, tries `ConditionalLockBufferForCleanup` and calls `lazy_scan_prune`, or falls back to `lazy_scan_noprune`. Checks `lazy_check_wraparound_failsafe` periodically. Calls `lazy_vacuum` when the dead-items store is full or scan completes. Maintains FSM updates every `VACUUM_FSM_EVERY_PAGES` pages. [verified-by-code]

3. **`lazy_scan_prune`** (line 2021) — Per-page work under cleanup lock. Sets up `PruneFreezeParams` (with `HEAP_PAGE_PRUNE_FREEZE | _SET_VM` and the relation's `vistest`), calls `heap_page_prune_and_freeze`, then: appends any LP_DEAD offsets to the dead-items TID store, updates relfrozenxid/relminmxid trackers, updates the eager-scan accounting (page newly all-frozen → success). [verified-by-code]

4. **`lazy_vacuum_heap_page`** (line 2758) — Phase III per-page work. Re-reads the page, takes exclusive lock (NOT cleanup), calls `heap_page_prune_and_freeze` with `PRUNE_VACUUM_CLEANUP` reason (no actual freeze attempts here — the heap_page_prune machinery just turns LP_DEAD into LP_UNUSED based on the TID-store offsets for this block). Re-records FSM space. [verified-by-code]

5. **`lazy_truncate_heap`** (line 3142) — Acquire `AccessExclusiveLock`; call `count_nondeletable_pages` (which may release/reacquire if it sees lock waiters); call `RelationTruncate`; emit pg_class update. The retry-on-lock-waiter behaviour is intentional to avoid blocking other queries unnecessarily. [verified-by-code]

6. **`heap_vac_scan_next_block`** (line 1648) — Read-stream callback. Returns blocks in order, skipping ranges marked all-visible (or all-frozen, for non-aggressive vacuums) per the VM. Cooperates with `find_next_unskippable_block` to encode SKIP_PAGES_THRESHOLD: skip only if there's a sufficiently long run of skippable pages (otherwise we lose read-ahead). [from-comment + verified-by-code]

## Cross-references

- Called by: `commands/vacuum.c::table_relation_vacuum` (via the tableam callback installed in `heapam_handler.c` at line ~624's `heap_vacuum_rel`).
- Calls into: `pruneheap.c::heap_page_prune_and_freeze`, `visibilitymap.c` (pin/get/set), `tidstore` (the dead-items store), `bufmgr.c`, `freespace.c`, `commands/vacuumparallel.c` (parallel index vacuum), `commands/progress.h` (progress reporting), `pgstat.c`.

## Open questions

- The exact heuristics tying `MAX_EAGER_FREEZE_SUCCESS_RATE`, the `success_cap`, and the per-region eager-scan state are intricate; the comment explains the philosophy but the formula details were not deep-read. [unverified]
- Interaction between `lazy_scan_noprune`'s ability to update VM bits and the cleanup-lock requirement claimed elsewhere — I'm fairly sure noprune only sets ALL_FROZEN if it can do so without moving any data, but did not verify each branch. [unverified — important for correctness]
- `dead_items_alloc` parallel path: when `nworkers > 0`, the TID store is allocated in shared memory; the semantics of how phase III dispatches reap work across workers were not traced. [unverified]

## Confidence tag tally
`[verified-by-code]=17 [from-comment]=10 [from-readme]=0 [inferred]=0 [unverified]=3`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/access-heap.md](../../../../../subsystems/access-heap.md)
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
- [idioms/heap-tuple-freeze.md](../../../../../idioms/heap-tuple-freeze.md)
- [idioms/vacuum-skip-pages.md](../../../../../idioms/vacuum-skip-pages.md)
- [idioms/vacuum-truncate-relation.md](../../../../../idioms/vacuum-truncate-relation.md)
- [idioms/vacuum-two-pass-heap.md](../../../../../idioms/vacuum-two-pass-heap.md)

