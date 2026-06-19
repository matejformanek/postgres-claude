# Queue: pg-quality-auditor — audit (long-form doc) side

Format: `[status] <doc-path> verified=<YYYY-MM-DD|never> [reason=<tag>]`
Refill rule: re-walk `knowledge/{architecture,subsystems,idioms,data-structures}/*.md`;
any doc whose `verified` annotation is > 30 days old (or `never`) goes
back to `[pending]`.

**Added 2026-06-12 (pg-anchor-refresh):** `pg-anchor-refresh` (11th routine,
schedule 03:37) also enqueues `knowledge/files/<path>.md` entries with
`reason=anchor-bump <old>..<new>` whenever upstream master moves and the
touched paths have an existing per-file doc. These are higher-priority
than the periodic 30-day refresh: process them first.

## Entries

[pending] knowledge/subsystems/headers-wave3.md verified=2026-06-10
[pending] knowledge/idioms/catalog-conventions.md verified=2026-06-11
[pending] knowledge/idioms/error-handling.md verified=2026-06-11
[pending] knowledge/idioms/fmgr.md verified=2026-06-11
[pending] knowledge/idioms/spi.md verified=2026-06-11
[pending] knowledge/idioms/parser-pipeline.md verified=2026-06-12
[pending] knowledge/idioms/node-types-and-lists.md verified=2026-06-12
[pending] knowledge/idioms/bgworker-and-parallel.md verified=2026-06-12
[pending] knowledge/idioms/guc-variables.md verified=2026-06-12
[pending] knowledge/data-structures/heap-tuple-layout.md verified=2026-06-12
[pending] knowledge/data-structures/pgproc-fields.md verified=2026-06-12
[pending] knowledge/architecture/mvcc.md verified=2026-06-13
[pending] knowledge/architecture/wal.md verified=2026-06-13
[pending] knowledge/architecture/planner.md verified=2026-06-13
[pending] knowledge/architecture/query-lifecycle.md verified=2026-06-13
[pending] knowledge/data-structures/snapshot-lifecycle.md verified=2026-06-13 [drift-fixed: heapam_visibility.c cite 177-191→13-35]
[pending] knowledge/architecture/executor.md verified=2026-06-13 [drift-fixed: nodeModifyTable.c §8a cites +13 lines]
[pending] knowledge/architecture/overview.md verified=2026-06-14
[pending] knowledge/architecture/access-methods.md verified=2026-06-14
[pending] knowledge/architecture/process-model.md verified=2026-06-14
[pending] knowledge/architecture/replication.md verified=2026-06-14
[pending] knowledge/subsystems/access-heap.md verified=2026-06-14
[pending] knowledge/subsystems/access-transam.md verified=2026-06-14
[pending] knowledge/subsystems/executor.md verified=2026-06-14 [drift-fixed: execExpr.c §3.1/§3.2 cites −20/−33 + phantom ExecInitExprWithContext removed; nodeModifyTable.c §9 cites −13]
[pending] knowledge/subsystems/storage-ipc.md verified=2026-06-15
[pending] knowledge/subsystems/storage-lmgr.md verified=2026-06-15
[pending] knowledge/subsystems/utils-cache.md verified=2026-06-15
[pending] knowledge/subsystems/utils-mmgr.md verified=2026-06-15
[pending] knowledge/subsystems/storage-buffer.md verified=2026-06-15
[pending] knowledge/subsystems/jit.md verified=2026-06-15
[pending] knowledge/subsystems/optimizer.md verified=2026-06-15 [drift-fixed: subselect.c SS_process_ctes 883→886, SS_process_sublinks 2206→2209]
[pending] knowledge/subsystems/partitioning.md verified=2026-06-15 [drift-fixed: PartitionRangeBound 50-71→65-71, partition_hbound_cmp 3770-3778→3580-3588]

## anchor-bump (2026-06-14) — e18b0cb7344..da1eff08a5be (20 commits)

[done:d3dfc9b] knowledge/files/contrib/seg/seg.c.md  reason=anchor-bump 2026-06-14:e18b0cb7344..da1eff08a5be verified=2026-06-16
[done:d3dfc9b] knowledge/files/contrib/xml2/xpath.c.md  reason=anchor-bump 2026-06-14:e18b0cb7344..da1eff08a5be verified=2026-06-16
[pending] knowledge/files/src/backend/access/transam/xlog.c.md  reason=anchor-bump 2026-06-14:e18b0cb7344..da1eff08a5be
[pending] knowledge/files/src/backend/access/transam/xlogutils.c.md  reason=anchor-bump 2026-06-14:e18b0cb7344..da1eff08a5be
[pending] knowledge/files/src/backend/catalog/pg_subscription.c.md  reason=anchor-bump 2026-06-14:e18b0cb7344..da1eff08a5be
[pending] knowledge/files/src/backend/commands/subscriptioncmds.c.md  reason=anchor-bump 2026-06-14:e18b0cb7344..da1eff08a5be
[pending] knowledge/files/src/backend/commands/tablecmds.c.md  reason=anchor-bump 2026-06-14:e18b0cb7344..da1eff08a5be
[pending] knowledge/files/src/backend/libpq/crypt.c.md  reason=anchor-bump 2026-06-14:e18b0cb7344..da1eff08a5be
[pending] knowledge/files/src/backend/libpq/pqmq.c.md  reason=anchor-bump 2026-06-14:e18b0cb7344..da1eff08a5be
[done:d3dfc9b] knowledge/files/src/backend/nodes/makefuncs.c.md  reason=anchor-bump 2026-06-14:e18b0cb7344..da1eff08a5be verified=2026-06-16
[done:d3dfc9b] knowledge/files/src/backend/parser/parse_coerce.c.md  reason=anchor-bump 2026-06-14:e18b0cb7344..da1eff08a5be verified=2026-06-16
[done:d3dfc9b] knowledge/files/src/backend/parser/parse_expr.c.md  reason=anchor-bump 2026-06-14:e18b0cb7344..da1eff08a5be verified=2026-06-16
[done:d3dfc9b] knowledge/files/src/backend/parser/parse_func.c.md  reason=anchor-bump 2026-06-14:e18b0cb7344..da1eff08a5be verified=2026-06-16
[done:d3dfc9b] knowledge/files/src/backend/parser/parse_relation.c.md  reason=anchor-bump 2026-06-14:e18b0cb7344..da1eff08a5be verified=2026-06-16
[done:d3dfc9b] knowledge/files/src/backend/parser/parse_target.c.md  reason=anchor-bump 2026-06-14:e18b0cb7344..da1eff08a5be verified=2026-06-16
[pending] knowledge/files/src/backend/replication/logical/relation.c.md  reason=anchor-bump 2026-06-14:e18b0cb7344..da1eff08a5be
[pending] knowledge/files/src/backend/replication/walsender.c.md  reason=anchor-bump 2026-06-14:e18b0cb7344..da1eff08a5be
[pending] knowledge/files/src/backend/utils/adt/ri_triggers.c.md  reason=anchor-bump 2026-06-14:e18b0cb7344..da1eff08a5be
[pending] knowledge/files/src/backend/utils/adt/xml.c.md  reason=anchor-bump 2026-06-14:e18b0cb7344..da1eff08a5be
[done:d3dfc9b] knowledge/files/src/backend/utils/cache/inval.c.md  reason=anchor-bump 2026-06-14:e18b0cb7344..da1eff08a5be verified=2026-06-16
[pending] knowledge/files/src/backend/utils/init/postinit.c.md  reason=anchor-bump 2026-06-14:e18b0cb7344..da1eff08a5be
[pending] knowledge/files/src/bin/psql/describe.c.md  reason=anchor-bump 2026-06-14:e18b0cb7344..da1eff08a5be
[pending] knowledge/files/src/include/miscadmin.h.md  reason=anchor-bump 2026-06-14:e18b0cb7344..da1eff08a5be
[pending] knowledge/files/src/include/parser/parse_relation.h.md  reason=anchor-bump 2026-06-14:e18b0cb7344..da1eff08a5be
[pending] knowledge/subsystems/parser-and-rewrite.md  reason=anchor-bump 2026-06-14:e18b0cb7344..da1eff08a5be (6 impacted parser files)
[pending] knowledge/files/contrib/postgres_fdw/postgres_fdw.c.md  reason=anchor-bump 2026-06-15:da1eff08a5be..b78cd2bda5b1
[in-progress:cloud/pg-quality-auditor/2026-06-17] knowledge/files/src/backend/replication/libpqwalreceiver/libpqwalreceiver.c.md  reason=upstream-delta 2026-06-15:b78cd2bda5b1..a75bd485b5ea (sig change + escaping rewrite)
[in-progress:cloud/pg-quality-auditor/2026-06-17] knowledge/files/src/backend/replication/repl_scanner.l.md  reason=upstream-delta 2026-06-15:b78cd2bda5b1..a75bd485b5ea (new <xd>{xddouble} rule)
[in-progress:cloud/pg-quality-auditor/2026-06-17] knowledge/files/src/backend/commands/subscriptioncmds.c.md  reason=upstream-delta 2026-06-15:b78cd2bda5b1..a75bd485b5ea (appendQuotedString helper; already queued for 06-14 anchor-bump)
[in-progress:cloud/pg-quality-auditor/2026-06-17] knowledge/files/src/bin/pg_basebackup/pg_recvlogical.c.md  reason=upstream-delta 2026-06-15:b78cd2bda5b1..a75bd485b5ea
[in-progress:cloud/pg-quality-auditor/2026-06-17] knowledge/files/src/bin/pg_basebackup/receivelog.c.md  reason=upstream-delta 2026-06-15:b78cd2bda5b1..a75bd485b5ea (stack buf -> PQExpBuffer)
[in-progress:cloud/pg-quality-auditor/2026-06-17] knowledge/files/src/bin/pg_basebackup/streamutil.c.md  reason=upstream-delta 2026-06-15:b78cd2bda5b1..a75bd485b5ea
[in-progress:cloud/pg-quality-auditor/2026-06-17] knowledge/files/src/bin/pg_basebackup/streamutil.h.md  reason=upstream-delta 2026-06-15:b78cd2bda5b1..a75bd485b5ea
[in-progress:cloud/pg-quality-auditor/2026-06-17] knowledge/files/src/interfaces/libpq/fe-protocol3.c.md  reason=upstream-delta 2026-06-15:b78cd2bda5b1..e0511883cae2 (VALID_LONG_MESSAGE_TYPE += ParameterDescription)
[pending] knowledge/files/src/bin/pg_dump/pg_backup_archiver.c.md  reason=anchor-bump 2026-06-16:b78cd2bda5b1..e5f94c4808fe (pg_restore --statistics[-only] inconsistency fix, 0dd93de69e80)
[pending] knowledge/files/src/include/nodes/nodes.h.md  reason=anchor-bump 2026-06-16:b78cd2bda5b1..e5f94c4808fe (query jumble comment fixes, e5f94c4808fe)
[pending] knowledge/files/src/include/nodes/parsenodes.h.md  reason=anchor-bump 2026-06-16:b78cd2bda5b1..e5f94c4808fe (query jumble comment fixes, e5f94c4808fe)
[pending] knowledge/files/src/include/nodes/primnodes.h.md  reason=anchor-bump 2026-06-16:b78cd2bda5b1..e5f94c4808fe (query jumble comment fixes, e5f94c4808fe)
[pending] knowledge/subsystems/replication.md  reason=anchor-bump 2026-06-16:b78cd2bda5b1..e5f94c4808fe (7 impacted files via a75bd485 replication-command quoting; Owners/Invariants may need refresh)

## anchor-bump (2026-06-17) — e5f94c4808fe..ab3023ad1e68 (10 commits)

[in-progress:cloud/pg-quality-auditor/2026-06-19] knowledge/files/src/backend/parser/parse_func.c.md  reason=anchor-bump 2026-06-17:e5f94c4808fe..ab3023ad1e68 (null-treatment reject for non-window funcs 4e5920e6 + error-message typo ab3023ad; prior [done:d3dfc9b] re-anchors) — AUDIT 2026-06-19: clean, re-anchored to ab3023ad (no line cites; 5 entry points intact)
[pending] knowledge/files/src/backend/replication/logical/reorderbuffer.c.md  reason=anchor-bump 2026-06-17:e5f94c4808fe..ab3023ad1e68 (free speculative-insertion change tuple, f50c329f)
[pending] knowledge/files/src/backend/commands/repack.c.md  reason=anchor-bump 2026-06-17:e5f94c4808fe..ab3023ad1e68 (concurrent repack: reject leftover toast attribs, e2a8cabc)
[pending] knowledge/files/src/backend/statistics/extended_stats_funcs.c.md  reason=anchor-bump 2026-06-17:e5f94c4808fe..ab3023ad1e68 (reject oversized MCV lists in pg_restore_extended_stats, f6e4ec0a)
[in-progress:cloud/pg-quality-auditor/2026-06-19] knowledge/files/contrib/ltree/ltree.h.md  reason=anchor-bump 2026-06-17:e5f94c4808fe..ab3023ad1e68 (int32 overflow fix in ltree_compare, 3f328049) — AUDIT 2026-06-19: DRIFT fixed (new ltree_compare_distance decl @ltree.h:209 shifted decls +1; ltree_op.c cross-refs re-pinned)
[in-progress:cloud/pg-quality-auditor/2026-06-19] knowledge/files/contrib/ltree/ltree_gist.c.md  reason=anchor-bump 2026-06-17:e5f94c4808fe..ab3023ad1e68 (int32 overflow fix in ltree_compare, 3f328049) — AUDIT 2026-06-19: DRIFT fixed (ltree_penalty now calls ltree_compare_distance, not ltree_compare)
[in-progress:cloud/pg-quality-auditor/2026-06-19] knowledge/files/contrib/ltree/ltree_op.c.md  reason=anchor-bump 2026-06-17:e5f94c4808fe..ab3023ad1e68 (int32 overflow fix in ltree_compare, 3f328049) — AUDIT 2026-06-19: DRIFT fixed (full re-cite; ltree_compare/ltree_compare_distance split; +ltree issue register row resolved)

## anchor-bump 2026-06-18: ab3023ad1e68..bdae2c20e88d (16 commits, pg-anchor-refresh)

[pending] knowledge/files/contrib/jsonb_plperl/jsonb_plperl.c.md  reason=anchor-bump 2026-06-18:ab3023ad1e68..bdae2c20e88d (jsonb_plperl, jsonb_plpython: Fix unguarded recursion and loops., da82fbb8f9a3)
[pending] knowledge/files/contrib/jsonb_plpython/jsonb_plpython.c.md  reason=anchor-bump 2026-06-18:ab3023ad1e68..bdae2c20e88d (jsonb_plperl, jsonb_plpython: Fix unguarded recursion and loops., da82fbb8f9a3)
[pending] knowledge/files/src/backend/access/transam/xlogreader.c.md  reason=anchor-bump 2026-06-18:ab3023ad1e68..bdae2c20e88d (Fix pgstat_count_io_op_time() calls passing incorrect information, 3048e81308f9)
[pending] knowledge/files/src/backend/access/transam/xlogrecovery.c.md  reason=anchor-bump 2026-06-18:ab3023ad1e68..bdae2c20e88d (Fix pgstat_count_io_op_time() calls passing incorrect information, 3048e81308f9)
[pending] knowledge/files/src/backend/commands/typecmds.c.md  reason=anchor-bump 2026-06-18:ab3023ad1e68..bdae2c20e88d (Fix ALTER DOMAIN VALIDATE CONSTRAINT locking, 64797ad97d6e)
[pending] knowledge/files/src/backend/replication/logical/slotsync.c.md  reason=anchor-bump 2026-06-18:ab3023ad1e68..bdae2c20e88d (Avoid stale slot access after dropping obsolete synced slots., bdae2c20e88d)
[pending] knowledge/files/src/backend/replication/logical/worker.c.md  reason=anchor-bump 2026-06-18:ab3023ad1e68..bdae2c20e88d (Avoid errors during ALTER SUBSCRIPTION., e5c40584a712)
[pending] knowledge/files/src/backend/replication/walreceiver.c.md  reason=anchor-bump 2026-06-18:ab3023ad1e68..bdae2c20e88d (Fix pgstat_count_io_op_time() calls passing incorrect information, 3048e81308f9)
[pending] knowledge/files/src/backend/utils/activity/pgstat.c.md  reason=anchor-bump 2026-06-18:ab3023ad1e68..bdae2c20e88d (Fix PANIC with track_functions due to concurrent drop of pgstats entries, 850b9218c8e4)
[pending] knowledge/files/src/backend/utils/activity/pgstat_function.c.md  reason=anchor-bump 2026-06-18:ab3023ad1e68..bdae2c20e88d (Fix PANIC with track_functions due to concurrent drop of pgstats entries, 850b9218c8e4)
[pending] knowledge/files/src/backend/utils/activity/pgstat_replslot.c.md  reason=anchor-bump 2026-06-18:ab3023ad1e68..bdae2c20e88d (Fix PANIC with track_functions due to concurrent drop of pgstats entries, 850b9218c8e4)
[pending] knowledge/files/src/backend/utils/activity/pgstat_shmem.c.md  reason=anchor-bump 2026-06-18:ab3023ad1e68..bdae2c20e88d (Fix PANIC with track_functions due to concurrent drop of pgstats entries, 850b9218c8e4)
[pending] knowledge/files/src/backend/utils/activity/pgstat_xact.c.md  reason=anchor-bump 2026-06-18:ab3023ad1e68..bdae2c20e88d (Fix PANIC with track_functions due to concurrent drop of pgstats entries, 850b9218c8e4)
[pending] knowledge/files/src/bin/scripts/vacuuming.c.md  reason=anchor-bump 2026-06-18:ab3023ad1e68..bdae2c20e88d (vacuumdb: Fix --missing-stats-only for partitioned indexes., d2cea63065b3)
[pending] knowledge/files/src/include/catalog/pg_subscription.h.md  reason=anchor-bump 2026-06-18:ab3023ad1e68..bdae2c20e88d (Avoid errors during ALTER SUBSCRIPTION., e5c40584a712)
[pending] knowledge/files/src/interfaces/libpq-oauth/oauth-curl.c.md  reason=anchor-bump 2026-06-18:ab3023ad1e68..bdae2c20e88d (libpq-oauth: Print libcurl version with OAUTHDEBUG_UNSAFE_TRACE, 4bd477dcc619)
[pending] knowledge/files/src/test/modules/test_custom_stats/test_custom_var_stats.c.md  reason=anchor-bump 2026-06-18:ab3023ad1e68..bdae2c20e88d (Fix PANIC with track_functions due to concurrent drop of pgstats entries, 850b9218c8e4)
[pending] knowledge/files/src/test/regress/pg_regress.c.md  reason=anchor-bump 2026-06-18:ab3023ad1e68..bdae2c20e88d (Silence uninitialized variable warning with some compiler versions, f29299c42b0b)
[pending] knowledge/files/src/test/regress/regress.c.md  reason=anchor-bump 2026-06-18:ab3023ad1e68..bdae2c20e88d (Avoid errors during ALTER SUBSCRIPTION., e5c40584a712)

## audit-clean rotation (2026-06-19, pg-quality-auditor) — re-verified at anchor ab3023ad1e68

[pending] knowledge/subsystems/foreign.md verified=2026-06-19
[pending] knowledge/subsystems/libpq-backend.md verified=2026-06-19
[pending] knowledge/subsystems/main.md verified=2026-06-19
[pending] knowledge/subsystems/port.md verified=2026-06-19
[pending] knowledge/idioms/locking-overview.md verified=2026-06-19
[pending] knowledge/idioms/memory-contexts.md verified=2026-06-19
[pending] knowledge/data-structures/bufferdesc-state.md verified=2026-06-19
