# nbtsort.c

- **Source path:** `source/src/backend/access/nbtree/nbtsort.c` (1971 lines)
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `utils/sort/tuplesort.c` (the sort engine), `storage/bulk_write.c` (the bulk WAL-efficient writer used for build), `nbtree.c` (`btbuild` is the IndexAmRoutine entry).

## Purpose

Build a btree index from scratch by **sorting input tuples then sequentially loading leaf pages**. Supports **parallel index build** via a leader/worker design with shared `BTShared` state in DSM and per-worker `BTSpool` + `Tuplesortstate`. Bypasses the buffer cache during the load phase using `storage/bulk_write.c` for efficiency. [from-comment, nbtsort.c:1-39]

## Top-of-file design summary

> "We use tuplesort.c to sort the given index tuples into order. Then we scan the index tuples in order and build the btree pages for each level." Leaf fillfactor = `BTREE_DEFAULT_FILLFACTOR` (90% by default, user-adjustable); upper levels always use `BTREE_NONLEAF_FILLFACTOR` (70%). [from-comment, nbtsort.c:6-24]

## Function map

- `btbuild` (299) — IndexAmRoutine entry. Calls `_bt_spools_heapscan` (which decides serial vs parallel and runs the heap scan), `_bt_leafbuild` (does the sort and load), then either `_bt_end_parallel` or just cleans up.
- `_bt_spools_heapscan` (369) — set up one or two `BTSpool`s (two if unique with `nulls_not_distinct=false`, so dead tuples can go to a second spool to skip the uniqueness check), call `_bt_begin_parallel` if requested, run `table_index_build_scan`.
- `_bt_build_callback` (583) — per-tuple callback that splits live vs dead tuples between spool and spool2.
- `_bt_leafbuild` (542) — call `tuplesort_performsort` then `_bt_load` for the actual page-building.
- `_bt_load` (1139) — main load loop. Pulls tuples in order, feeds them to `_bt_buildadd`. Handles deduplication during build (if `btm_allequalimage` allows it).
- `_bt_buildadd` (789) — append a tuple to the current per-level `BTPageState.btps_buf`; if the page is full, finalize it (truncate suffix, set high key, write via bulk_write), allocate next page, recurse to insert downlink in the upper level (creating a new level if needed).
- `_bt_pagestate` (652) — allocate a `BTPageState` for a level.
- `_bt_blnewpage` (612) — allocate a new bulk-write buffer for a level.
- `_bt_blwritepage` (641) — hand a finalized page to `bulk_write`.
- `_bt_slideleft` (689) — final pass on rightmost page of each level: move the unused high-key slot at item 1 down so item 1 is the first data item (rightmost pages have no high key).
- `_bt_uppershutdown` (1067) — flush each level's last page, build the new metapage pointing at the actual root.

### Parallel build

- `_bt_begin_parallel` (1399) — `CreateParallelContext`, allocate DSM space for `BTShared` (with the parallel table scan descriptor appended), initialize the `Sharedsort` and (if unique) `Sharedsort2`, launch workers.
- `_bt_end_parallel` (1611) — `DestroyParallelContext` after collecting `WalUsage`/`BufferUsage`.
- `_bt_parallel_heapscan` (1657) — wait on `BTShared.workersdonecv` for all workers to finish their per-worker tuplesort.
- `_bt_leader_participate_as_worker` (1691) — leader joins as a worker if `DISABLE_LEADER_PARTICIPATION` isn't defined.
- `_bt_parallel_build_main` (1744, exported) — entry point for each parallel worker: attach to DSM, reconstruct `BTSpool`, run `_bt_parallel_scan_and_sort`.
- `_bt_parallel_scan_and_sort` (1869) — the per-worker heapscan + tuplesort feeding.

## Key types

- `BTShared` (97-157) — DSM-resident leader/worker state. Holds the cv, the slock-protected counters (`nparticipantsdone`, `reltuples`, `havedead`, `indtuples`, `brokenhotchain`), and a flexible-tail parallel-table-scan descriptor.
- `BTLeader` (171-200) — local-only state held by the leader (parallel context + convenience pointers to DSM).
- `BTBuildState` (208-229) — per-participant build state (spool + spool2 + indtuples + optional leader).
- `BTPageState` (235-245) — per-level state during build: the current bulk-write buffer, last-loaded offset, level number, "full" threshold.
- `BTWriteState` (250-257) — overall writing-phase state, holds the `BulkWriteState`.

## Key invariants

- **No buffer-cache traffic during load** — pages go through `storage/bulk_write.c` which writes them directly and WAL-logs them efficiently via `XLOG_FPI_FOR_HINT`-like records. [from-comment, nbtsort.c:26-28]
- **Upper-level pages are 70% full**, leaf pages are user-fillfactor% full. [from-comment, nbtsort.c:18-24]
- **The build never produces an empty index** — even a zero-input build still emits a metapage; the root is whatever the leaf level ends up being (or stays as a single empty leaf root for zero tuples). [verified-by-code]
- Parallel workers each produce one sorted run; the leader's tuplesort merges them in `_bt_load`. [from-comment]
- `nulls_not_distinct=false` unique-index builds use **two spools** so that dead tuples are spilled to the second spool and don't participate in the uniqueness check that happens during the merge. [from-comment, nbtsort.c:79-89]

## Cross-references

- **Called by:** `commands/indexcmds.c` via `index_build` (which calls `IndexAmRoutine.ambuild`).
- **Calls into:** `utils/sort/tuplesort.c` (entire sort lifecycle), `storage/bulk_write.c` (`smgr_bulk_*`), `access/table/tableam.c` (`table_index_build_scan`), `access/parallel.c` (parallel infrastructure), `nbtutils.c` (`_bt_truncate`, `_bt_check_third_page`, `_bt_allequalimage`), `nbtdedup.c` (build-time dedup via `_bt_dedup_start_pending`/`_bt_dedup_save_htid`/`_bt_dedup_finish_pending`).

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
- [subsystems/access-nbtree.md](../../../../../subsystems/access-nbtree.md)
