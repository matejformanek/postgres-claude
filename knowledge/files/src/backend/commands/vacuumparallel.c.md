# `src/backend/commands/vacuumparallel.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~1367
- **Source:** `source/src/backend/commands/vacuumparallel.c`

Parallel index bulk-deletion and index cleanup for both `VACUUM` and
autovacuum. The leader (heap-scanning vacuum process) hands off a set
of indexes to parallel workers; each worker `index_bulk_delete`s or
`index_cleanup`s one index at a time. Workers share a `TidStore` of
dead tuple TIDs allocated in DSA. PG18 extended this with
`PVSharedCostParams` for autovacuum, so cost-delay tweaks during a
`pg_reload_conf` propagate from the leader to its workers via a
generation counter. [verified-by-code]

## API / entry points

- `parallel_vacuum_init(rel, indrels, nindexes, nrequested_workers,
  vac_work_mem, elevel, bstrategy)` — set up the parallel context,
  estimate DSM, register `parallel_vacuum_main` as the worker entry,
  create the shared TidStore. Returns NULL if parallel vacuum was
  not feasible (e.g. all indexes unsuitable). [verified-by-code]
- `parallel_vacuum_end(pvs, istats)` — copy out per-index
  `IndexBulkDeleteResult` stats, destroy parallel context.
  [verified-by-code]
- `parallel_vacuum_get_dead_items(pvs, dead_items_info_p)` /
  `parallel_vacuum_reset_dead_items(pvs)` — access and reset the
  shared TidStore between bulk-delete passes. [verified-by-code]
- `parallel_vacuum_bulkdel_all_indexes(pvs, num_table_tuples,
  num_index_scans, wstats)` — launch workers for one bulk-delete
  pass. [verified-by-code]
- `parallel_vacuum_cleanup_all_indexes(pvs, num_table_tuples,
  num_index_scans, estimated_count, wstats)` — same for cleanup.
  [verified-by-code]
- `parallel_vacuum_main(seg, toc)` — worker entry. Loops indexes
  whose `idx` counter atomic-increment hands it. Sets up error
  callback (`parallel_vacuum_error_callback`) with the per-index
  name. [verified-by-code]
- `parallel_vacuum_update_shared_delay_params(void)` — worker-side
  polled refresher: checks `cost_params.generation` atomically; if
  newer than worker's local copy, re-reads the spinlock-protected
  values. [from-comment]
- `parallel_vacuum_propagate_shared_delay_params(void)` —
  leader-side autovacuum-only: re-publish cost-delay values into
  the shared struct and bump generation. [from-comment]

## Notable invariants / details

- DSM keys (lines 57-61): SHARED=1, QUERY_TEXT=2, BUFFER_USAGE=3,
  WAL_USAGE=4, INDEX_STATS=5. Distinct from plan_node_id keys so
  small integers are safe. [from-comment]
- `PVShared` struct (line 94) holds: `relid`, log `elevel`,
  `queryid`, total `reltuples`, `estimated_count`,
  per-worker `maintenance_work_mem_worker`, BAS `ring_nbuffers`,
  atomic `cost_balance`, atomic `active_nworkers`, atomic `idx`
  (the next-index assignment counter), DSA handle of dead_items
  TidStore, `dead_items_info`, `is_autovacuum` flag, and the
  embedded `PVSharedCostParams`. [verified-by-code]
- `PVSharedCostParams` (line 67) — generation counter (atomic) +
  spinlock protecting `cost_delay`, `cost_limit`,
  `cost_page_{dirty,hit,miss}`. Generation starts at 1; workers
  initialize their local copy to 0, guaranteeing the first poll
  takes the fast path. [from-comment]
- Per-index parallel safety: `parallel_vacuum_index_is_parallel_safe`
  decides whether each index can be touched by workers; unsafe ones
  are processed by the leader in `parallel_vacuum_process_unsafe_indexes`.
  Safety depends on the index AM's
  `amparallelvacuumoptions` mask + the current pass (bulkdel vs
  cleanup vs cond-cleanup) + size threshold
  (`min_parallel_index_scan_size`).
- Worker assignment: `pg_atomic_fetch_add_u32(&shared->idx, 1)`
  inside the worker loop (in `parallel_vacuum_process_safe_indexes`).
- Error reporting: `parallel_vacuum_error_callback` switches on the
  per-index `status` (`PARALLEL_INDVAC_STATUS_NEED_BULKDELETE` vs
  `NEED_CLEANUP`) and prepends `errcontext` with
  `"while {vacuuming,cleaning up} index ..."`. The leader sets the
  callback only for the per-index call window. [verified-by-code]
- Lock-group: workers belong to the leader's lock group, so heavy
  locks held by the leader on the heap don't block them.

## Potential issues

- Lines 117-123. "Not sure the spinlock is needed here" — same
  hedging phrasing also seen in `repack_worker.c`. Different
  problem (shared cost params), but the language is identical and
  suggests both authors were uncertain about the established
  shared-memory ordering rules. [ISSUE-doc-drift: spinlock
  uncertainty comment (nit)] (NB: this issue applies to the
  PVSharedCostParams setup path, not the cost-tracking path.)
- `pv_shared_cost_params` is a file-scope static. Set when the
  worker attaches; not cleared on detach. Stale pointer after
  worker exit is harmless because the worker process exits, but if
  the same backend somehow ran two parallel-vacuums (it can't,
  in practice) you'd carry over the old pointer. [unverified]
- Memory-context for the worker is the executor's per-query
  context; index AMs may palloc into it. Resets between passes
  rely on `parallel_vacuum_reset_dead_items` destroying the
  TidStore + creating a new one with the same `max_bytes`. DSA
  segments are returned to the OS. [from-comment]

## Synthesized by
<!-- backlinks:auto -->
