# repack.c

- **Source path:** `source/src/backend/commands/repack.c`
- **Lines:** 3954
- **Last verified commit:** `d774576f6f0`
- **Companion files:** `commands/repack_worker.c` (the bgworker that decodes WAL during CONCURRENT mode), `commands/repack_internal.h`, `commands/cluster.c` is **GONE** — its functionality lives here now ("formerly known as CLUSTER"). VACUUM FULL also routes here.

## Purpose

"REPACK a table; formerly known as CLUSTER. VACUUM FULL also uses parts of this code." Two modes: **non-concurrent** (take `AccessExclusiveLock`, copy tuples to a new heap, swap relfilenodes, drop old heap — the historical CLUSTER/VACUUM-FULL behaviour) and **concurrent** (PG 18+, `ShareUpdateExclusiveLock` only; logical-decoding bgworker captures concurrent changes during the initial copy and replays them on the new heap before a brief lock upgrade for the swap). [from-comment, repack.c:3-22]

## Why this file replaced cluster.c

Before PG 18, `cluster.c` had the CLUSTER + VACUUM FULL machinery and rewrote tuples via a custom code path. PG 18 unified them as REPACK with two modes and added the **concurrent** variant whose much-shorter strong-lock window addresses the "VACUUM FULL kills production" complaint. Old `CLUSTER tbl USING idx` is now `REPACK tbl USING idx`; the grammar still accepts CLUSTER as an alias.

## Public surface

- `ExecRepack` (250) — entry from `ProcessUtility`. Parses options (`CONCURRENTLY`, `VERBOSE`, `ANALYZE`, `USING idx`), determines lock level via `RepackLockLevel` (449), loops over the relations (`get_tables_to_repack` 2102 for "all tables that can be clustered"), and calls `process_single_relation` (2390) → `cluster_rel` (482).
- `cluster_rel` (482) — per-relation driver. Validates that the chosen clustering index is OK (`check_index_is_clusterable` 732), calls `rebuild_relation`.
- `rebuild_relation` (970) — **non-concurrent path**. Calls `make_new_heap` (1124) to create the transient relation in the chosen access method/tablespace, `copy_table_data` (1253) to scan + sort + insert, `finish_heap_swap` (1881) to swap relfilenodes and drop the old heap.
- `rebuild_relation_finish_concurrent` (3181) — **concurrent path** finisher; runs after the initial copy and after `apply_concurrent_changes` has caught up. Upgrades to `AccessExclusiveLock`, replays final WAL slice, swaps relfilenodes, builds indexes on the new heap.
- `make_new_heap` (1124) — creates a transient empty heap with the new pg_class entry but linked so `finish_heap_swap` can flip relfilenodes in pg_class.
- `copy_table_data` (1253) — heap copy loop; supports either an index scan (in clustering-index order) or a seq scan + tuplesort.
- `swap_relation_files` (1499) — the catalog swap: swap `relfilenode`, `reltablespace`, `relam`, plus toast relations' OIDs and indexes. Also updates `relfrozenxid` and `relminmxid` to those of the new heap.
- `finish_heap_swap` (1881) — swap + drop transient + rebuild indexes + reset pg_statistic.
- **Concurrent-mode helpers:**
  - `start_repack_decoding_worker` (3601) / `stop_repack_decoding_worker` (3691) — launch/stop the bgworker.
  - `apply_concurrent_changes` (2542) — read spilled WAL changes from the BufFile written by the worker and replay them on the new heap as `apply_concurrent_insert` (2668) / `apply_concurrent_update` (2689) / `apply_concurrent_delete` (2731). Each change is deserialized by `restore_tuple` (2765), which reconstructs any separately-stored external attributes and errors out (`elog(ERROR, ...)`, repack.c:2823 / 2828) if the count of leftover toast attributes doesn't match what was spilled — the `natt_ext != 0` reject guard (upstream commit e2a8cabc). [verified-by-code]
  - `find_target_tuple` (2873) — locate the row in the new heap by replica-identity columns (because the new heap has different TIDs than the old one).
  - `identity_key_equal` (2926) — replica-identity comparison.
  - `process_concurrent_changes` (2963) — pump loop: keep pulling decoded changes until LSN reaches the lock-upgrade target.
- **Multi-table / partitioned table support:**
  - `get_tables_to_repack` (2102), `get_tables_to_repack_partitioned` (2219) — discover candidate relations.
  - `check_concurrent_repack_requirements` (858) — concurrent mode requires the relation to have a replica identity: either an explicit `REPLICA IDENTITY USING INDEX` or a non-deferrable PK. `REPLICA IDENTITY FULL` and `REPLICA IDENTITY NOTHING` are explicitly **rejected** as not-yet-supported (repack.c:906-916), as are catalog/TOAST/non-permanent relations and `wal_level < replica`.

## Concurrent REPACK protocol [HIGH-RISK]

The top-of-file comment is the authoritative description (repack.c:7-22): [from-comment]

1. Take `ShareUpdateExclusiveLock`. Create transient heap.
2. `start_repack_decoding_worker` — bgworker creates a logical replication slot at the current LSN. **As long as that slot exists, WAL cannot be removed even if the standby falls behind** (important operational gotcha).
3. Initial copy of old heap → new heap proceeds while the worker accumulates concurrent INSERT/UPDATE/DELETE changes into a `BufFile` (no in-memory bound).
4. When copy completes, the main backend reads the BufFile, calls `apply_concurrent_*` per change. Loops until the worker's apply LSN approaches the current insert LSN.
5. **Lock upgrade** from `ShareUpdateExclusive` → `AccessExclusiveLock`. Final WAL drain. Swap relfilenodes. Drop slot. Drop old heap.

**Failure modes documented in source:** if the lock upgrade deadlocks with a long-running reader, the concurrent REPACK aborts and the transient heap + slot are cleaned up. The bgworker has `stop_repack_decoding_worker_cb` (3736) registered as an on-exit hook to release the slot even on crash. [verified-by-code]

## Tests

- `src/test/regress/sql/cluster.sql` (still uses the old name as alias) + `src/test/regress/sql/repack.sql`.
- TAP tests for concurrent mode under `src/test/recovery/` exercise the slot/WAL boundary.

## Open questions

- Behaviour when a row's replica identity has changed (RI USING INDEX with the index dropped) between initial copy and apply phase. [unverified]
- Interaction between concurrent REPACK and a concurrent CIC on the same table — both take ShareUpdateExclusive; the order matters for what the new heap's indexes see. [unverified]
- TOAST table handling during concurrent mode (the toast pointers need rewriting in `adjust_toast_pointers` 2838) — the exact correctness argument was not deep-read. [unverified]

## Confidence tag tally

`[verified-by-code]=9 [from-comment]=2 [unverified]=3`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
