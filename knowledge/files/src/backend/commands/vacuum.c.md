# vacuum.c

- **Source path:** `source/src/backend/commands/vacuum.c`
- **Lines:** 2715
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `vacuum.h`, `access/heap/vacuumlazy.c` (heap AM's VACUUM body — page scan/prune/freeze loop), `commands/vacuumparallel.c` (parallel index workers), `commands/analyze.c`, `commands/repack.c` (VACUUM FULL == REPACK), `postmaster/autovacuum.c`.

## Purpose

"The postgres vacuum cleaner. This file includes (a) control and dispatch code for VACUUM and ANALYZE commands, (b) code to compute various vacuum thresholds, and (c) index vacuum code. VACUUM for heap AM is implemented in vacuumlazy.c, parallel vacuum in vacuumparallel.c, ANALYZE in analyze.c, and **VACUUM FULL is a variant of REPACK**, handled in repack.c." [from-comment, vacuum.c:3-12]

## Driver / worker split

- **Driver (this file):** parses options, expands the relation list (handles `VACUUM` with no args = all tables in the database; `VACUUM tbl` = one relation; partitioned table = list its leaves), opens each relation under the right lock, decides per-table whether to ANALYZE only / VACUUM only / both, computes freeze cutoffs, and **calls back into the table AM** via `table_relation_vacuum()`. For heap, that lands in `vacuumlazy.c:heap_vacuum_rel`.
- **Worker (vacuumlazy.c, vacuumparallel.c):** the actual page-by-page prune/freeze/vacuum loop; the dead-tid collection (now via `TidStore` in `access/common/tidstore.c`); the index-vacuum dispatch; the relation-truncation step.

This file additionally owns **index-vacuum convenience wrappers** (`vac_bulkdel_one_index` 2663, `vac_cleanup_one_index` 2684) and the `vac_tid_reaped` (2710) callback used by `IndexBulkDelete` to test "is this TID dead?".

## Public surface

- `ExecVacuum` (163) — parse `VacuumStmt`, build `VacuumParams`, set up `BufferAccessStrategy` (BAS_VACUUM ring, default 256 KB; user-overridable with `BUFFER_USAGE_LIMIT`), then call `vacuum`.
- `vacuum` (494) — **internal entry**, also used by autovacuum (which constructs a synthetic `VacuumParams`). Decides whether to use the caller's transaction or own xacts (`use_own_xacts = relations==NIL || multiple relations`), then loops calling `vacuum_rel` and `analyze_rel`.
- `vacuum_is_permitted_for_relation` (720) — ACL check including the per-table-owner shortcut, MAINTAIN role, and the autovacuum bypass. Returns false silently for skipped tables to avoid noisy logs.
- `vacuum_open_relation` (772) — open with the right lock (`ShareUpdateExclusiveLock` for lazy VACUUM; `AccessExclusiveLock` for VACUUM FULL via REPACK), with handling for missing relations and shared catalogs.
- `vacuum_get_cutoffs` (1106) — **the heart of freeze policy.** Computes `VacuumCutoffs` (OldestXmin, FreezeLimit, MultiXactCutoff, relfrozenxid_pre, relminmxid_pre). The Freeze Limit is `OldestXmin - vacuum_freeze_min_age`. The "aggressive" mode kicks in when `pg_class.relfrozenxid` is older than `vacuum_freeze_table_age` xacts behind current — then we scan ALL pages, not just those flagged not-all-frozen in the VM.
- `vacuum_xid_failsafe_check` (1274) — emergency mode: when `relfrozenxid` is within `vacuum_failsafe_age` (default 1.6 B) of wrap-around, **cost-delay is disabled and index-vacuum is skipped** to finish freezing as fast as possible. Same logic for multixact (`vacuum_multixact_failsafe_age`).
- `vac_estimate_reltuples` (1336) — when only a subset of pages was scanned, blend the scanned-pages density with the prior `reltuples` estimate weighted by scanned/total fraction. Comment explains the rationale (avoid wild swings).
- `vac_update_relstats` (1432) — write `pg_class` (`relpages`, `reltuples`, `relallvisible`, `relfrozenxid`, `relminmxid`) via `heap_inplace_update_and_unlock` (so the change doesn't generate a new HOT chain and survives concurrent VACUUMs).
- `vac_update_datfrozenxid` (1614) — recompute `pg_database.datfrozenxid` as the min of all relfrozenxids in this DB; called at end of each VACUUM.
- `vac_truncate_clog` (1835) — once per VACUUM, recompute cluster-wide oldest xid via `MinimumActiveBackendXmin` etc. and call `TruncateCLOG` / `TruncateCommitTs` / `TruncateMultiXact` to delete pg_xact files older than that.
- `vacuum_rel` (2012) — per-relation entry: open, sanity checks, `table_relation_vacuum` callback, then handle TOAST table.
- `vac_open_indexes` (2374), `vac_close_indexes` (2417) — open/close all indexes of a heap relation with a single lock cycle.
- `vacuum_delay_point` (2438) — the cost-delay sleep called from inside the heap-vacuum loop. Reads `VacuumCostBalance` accumulated by the buffer manager and sleeps if it exceeds `vacuum_cost_limit`. Honours the failsafe-disable flag.
- `compute_parallel_delay` (2608) — split the cost-delay budget across parallel workers so the per-relation throttle is honoured cluster-wide.

## VACUUM transaction-block rule

`VACUUM` (with the VACUUM bit) calls `PreventInTransactionBlock` and runs in its own xact-per-relation. `ANALYZE` (alone) does NOT — it can run inside a user xact, but it then can't use multi-xact bookkeeping for cutoffs. [verified-by-code, vacuum.c:502-516]

## What this file is NOT

- It does NOT contain the heap page-scan loop (that's `vacuumlazy.c:lazy_scan_heap`).
- It does NOT contain the dead-tuple collection structure (now `TidStore` in PG 17+; previously a flat array — `access/common/tidstore.c`).
- It does NOT do parallel-worker launch (`vacuumparallel.c`).
- It does NOT do VACUUM FULL's data copy (`repack.c`).

## Confidence tag tally

`[verified-by-code]=8 [from-comment]=2`
