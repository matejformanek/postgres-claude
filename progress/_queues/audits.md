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

## audit-clean rotation (2026-06-20) — anchor bdae2c20e88d, 12 docs re-verified, 0 drift

[pending] knowledge/subsystems/headers-wave3.md verified=2026-06-20 [clean: libpq-be.h Port 128-241/ClientConnectionInfo 86-106/ClientSocket 248-252/FILE_DH2048 265/be_tls_* 287-339 all hold]
[pending] knowledge/idioms/error-handling.md verified=2026-06-20 [clean: elog.h elevel-ladder 26-58/elog macro 242/errstart defaults 108-112/MAKE_SQLSTATE 69-74/pg_unreachable 133-140 all hold]
[pending] knowledge/idioms/fmgr.md verified=2026-06-20 [clean: fmgr.h PGFunction 40/FmgrInfo 56-67/FunctionCallInfoBaseData 85-96/LOCAL_FCINFO 110-118/SizeForFunctionCallInfo 102-104 + fmgr.c fn_oid-last 159 all hold]
[pending] knowledge/idioms/spi.md verified=2026-06-20 [clean: spi.c SPI_connect 94-98/horrible-API 40-47/SPI_finish 183/SPI_prepare 861/SPI_palloc 1339/SPI_result_code_string 1973 all hold]
[pending] knowledge/idioms/catalog-conventions.md verified=2026-06-20 [clean: genbki.h CATALOG/BKI 42-66/CATALOG_VARLEN 148-156/DECLARE_* 68-146 + catversion.h CATALOG_VERSION_NO 60 + transam.h FirstNormalObjectId 195-197 all hold]
[pending] knowledge/idioms/bgworker-and-parallel.md verified=2026-06-20 [clean: bgworker.h BGWORKER_CLASS_PARALLEL 69-75/BgWorkerStartTime 84-89/exit-code 18-23 + bgworker.c lockless-slot 45-86 + parallel.h API 64-72 + parallel.c CreateParallelContext 174/PARALLEL_KEY_* 64-81 + worker_spi.c bgw_extra 151-171 all hold]
[pending] knowledge/idioms/guc-variables.md verified=2026-06-20 [clean: guc_tables.h config_type 22-27 + guc.h GucContext 71-80/config_source 111-127/GUC_* flags 222-228/GUC_CUSTOM_PLACEHOLDER 223 + guc.c MarkGUCPrefixReserved 5186 all hold]
[pending] knowledge/data-structures/heap-tuple-layout.md verified=2026-06-20 [clean: htup_details.h HeapTupleHeaderData 153/t_infomask 188-217/t_infomask2 288-298/284-353 + heapam_visibility.c 13-35 all hold]
[pending] knowledge/data-structures/pgproc-fields.md verified=2026-06-20 [clean: proc.h fastpath-fields 329-335/FastPathLockSlotsPerBackend 101-104/lockGroup 304-306 + lock.c FastPathTransferRelationLocks 2869 all hold]
[pending] knowledge/architecture/mvcc.md verified=2026-06-20 [clean: heapam_visibility.c summary 38-57/non-MVCC-NOTE 13-27/MVCC-NOTE 33-36/SetHintBits 101-125 + htup_details.h t_ctid 86-112/combo-CID 73-84/XMIN flags 204-206 all hold]
[pending] knowledge/architecture/wal.md verified=2026-06-20 [clean: xlog.c header 14-25/GUCs 121-143/wal_level 138/wal_sync_method_options 178-191 + xlog.h wal_level enum 76-78/XLogIsNeeded 112 all hold]
[pending] knowledge/architecture/query-lifecycle.md verified=2026-06-20 [clean: postgres.c PostgresMain 4274/pg_parse_query 616/pg_plan_query 899/exec_simple_query 1029/parse_analyze callsite 699/ReadCommand callsite 4788 + rewriteHandler.c QueryRewrite 4781 all hold]

## anchor-bump (2026-06-14) — e18b0cb7344..da1eff08a5be (20 commits)

[done:d3dfc9b] knowledge/files/contrib/seg/seg.c.md  reason=anchor-bump 2026-06-14:e18b0cb7344..da1eff08a5be verified=2026-06-16
[done:d3dfc9b] knowledge/files/contrib/xml2/xpath.c.md  reason=anchor-bump 2026-06-14:e18b0cb7344..da1eff08a5be verified=2026-06-16
[done:089661b] knowledge/files/src/backend/access/transam/xlog.c.md  reason=anchor-bump 2026-06-14:e18b0cb7344..da1eff08a5be verified=2026-06-24
[done:089661b] knowledge/files/src/backend/access/transam/xlogutils.c.md  reason=anchor-bump 2026-06-14:e18b0cb7344..da1eff08a5be verified=2026-06-24
[done:089661b] knowledge/files/src/backend/catalog/pg_subscription.c.md  reason=anchor-bump 2026-06-14:e18b0cb7344..da1eff08a5be verified=2026-06-24
[done:089661b] knowledge/files/src/backend/commands/subscriptioncmds.c.md  reason=anchor-bump 2026-06-14:e18b0cb7344..da1eff08a5be verified=2026-06-24
[done:089661b] knowledge/files/src/backend/commands/tablecmds.c.md  reason=anchor-bump 2026-06-14:e18b0cb7344..da1eff08a5be verified=2026-06-24
[done:089661b] knowledge/files/src/backend/libpq/crypt.c.md  reason=anchor-bump 2026-06-14:e18b0cb7344..da1eff08a5be verified=2026-06-24
[done:089661b] knowledge/files/src/backend/libpq/pqmq.c.md  reason=anchor-bump 2026-06-14:e18b0cb7344..da1eff08a5be verified=2026-06-24
[done:d3dfc9b] knowledge/files/src/backend/nodes/makefuncs.c.md  reason=anchor-bump 2026-06-14:e18b0cb7344..da1eff08a5be verified=2026-06-16
[done:d3dfc9b] knowledge/files/src/backend/parser/parse_coerce.c.md  reason=anchor-bump 2026-06-14:e18b0cb7344..da1eff08a5be verified=2026-06-16
[done:d3dfc9b] knowledge/files/src/backend/parser/parse_expr.c.md  reason=anchor-bump 2026-06-14:e18b0cb7344..da1eff08a5be verified=2026-06-16
[done:d3dfc9b] knowledge/files/src/backend/parser/parse_func.c.md  reason=anchor-bump 2026-06-14:e18b0cb7344..da1eff08a5be verified=2026-06-16
[done:d3dfc9b] knowledge/files/src/backend/parser/parse_relation.c.md  reason=anchor-bump 2026-06-14:e18b0cb7344..da1eff08a5be verified=2026-06-16
[done:d3dfc9b] knowledge/files/src/backend/parser/parse_target.c.md  reason=anchor-bump 2026-06-14:e18b0cb7344..da1eff08a5be verified=2026-06-16
[done:089661b] knowledge/files/src/backend/replication/logical/relation.c.md  reason=anchor-bump 2026-06-14:e18b0cb7344..da1eff08a5be verified=2026-06-24
[done:089661b] knowledge/files/src/backend/replication/walsender.c.md  reason=anchor-bump 2026-06-14:e18b0cb7344..da1eff08a5be verified=2026-06-24
[done:089661b] knowledge/files/src/backend/utils/adt/ri_triggers.c.md  reason=anchor-bump 2026-06-14:e18b0cb7344..da1eff08a5be verified=2026-06-24
[done:38d62e6] knowledge/files/src/backend/utils/adt/xml.c.md  reason=anchor-bump 2026-06-14:e18b0cb7344..da1eff08a5be re-pinned=f0a4f280b4d3 [drift-fixed: xpath ~4400→4572, XmlTable* ~4750→4933/4978, loc 5167→5169]
[done:d3dfc9b] knowledge/files/src/backend/utils/cache/inval.c.md  reason=anchor-bump 2026-06-14:e18b0cb7344..da1eff08a5be verified=2026-06-16
[done:38d62e6] knowledge/files/src/backend/utils/init/postinit.c.md  reason=anchor-bump 2026-06-14:e18b0cb7344..da1eff08a5be re-pinned=f0a4f280b4d3 [drift-fixed: all InitPostgres-pipeline + public-surface cites shifted +6/+7, loc 1553→1567]
[done:38d62e6] knowledge/files/src/bin/psql/describe.c.md  reason=anchor-bump 2026-06-14:e18b0cb7344..da1eff08a5be re-pinned=f0a4f280b4d3 [clean: file unchanged, exact cites hold; tightened 2 "area" cites to 6823/7089]
[done:38d62e6] knowledge/files/src/include/miscadmin.h.md  reason=anchor-bump 2026-06-14:e18b0cb7344..da1eff08a5be re-pinned=f0a4f280b4d3 [clean: all major cites hold ±2, loc ~553→555]
[done:38d62e6] knowledge/files/src/include/parser/parse_relation.h.md  reason=anchor-bump 2026-06-14:e18b0cb7344..da1eff08a5be re-pinned=f0a4f280b4d3 [clean: all category fn prototypes present, loc ~140→141]
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
[done:38d62e6] knowledge/files/src/include/nodes/nodes.h.md  reason=anchor-bump 2026-06-16:b78cd2bda5b1..e5f94c4808fe (query jumble comment fixes, e5f94c4808fe) re-pinned=f0a4f280b4d3 [clean: enum/macro cites hold ±2, loc 446→444]
[done:38d62e6] knowledge/files/src/include/nodes/parsenodes.h.md  reason=anchor-bump 2026-06-16:b78cd2bda5b1..e5f94c4808fe (query jumble comment fixes, e5f94c4808fe) re-pinned=f0a4f280b4d3 [clean: struct cites hold ±3, loc ~5000→4599]
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
[done:4138954] knowledge/files/src/backend/commands/typecmds.c.md  reason=anchor-bump 2026-06-18:ab3023ad1e68..bdae2c20e88d (Fix ALTER DOMAIN VALIDATE CONSTRAINT locking, 64797ad97d6e) — AUDIT 2026-06-23: clean re-pin (LOC 4757→4747; only cites :3-4/:14-25 top-of-file, unaffected by mid-file −10; re-pinned 031904048aa2)
[done:4138954] knowledge/files/src/backend/replication/logical/slotsync.c.md  reason=anchor-bump 2026-06-18:ab3023ad1e68..bdae2c20e88d (Avoid stale slot access after dropping obsolete synced slots., bdae2c20e88d) — AUDIT 2026-06-23: DRIFT fixed (LOC 2099→2102; documented drop_local_obsolete_slots :535 stale-slot mutex re-validation guard + LockSharedObject(DatabaseRelationId) serialization)
[done:4138954] knowledge/files/src/backend/replication/logical/worker.c.md  reason=anchor-bump 2026-06-18:ab3023ad1e68..bdae2c20e88d (Avoid errors during ALTER SUBSCRIPTION., e5c40584a712) — AUDIT 2026-06-23: clean re-pin (LOC unchanged 6435; all 18 function line-cites verified exact — e5c40584 was line-neutral; re-pinned 031904048aa2)
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

## anchor-bump 2026-06-19: bdae2c20e88d..dc5116780846 (11 commits, pg-anchor-refresh)

[done:6b2dde1] knowledge/files/src/bin/pg_dump/pg_dump.c.md  reason=anchor-bump 2026-06-19:bdae2c20e88d..dc5116780846 (Revert non-text output formats for pg_dumpall, 7ca548f23a60) — AUDIT 2026-06-22: clean, re-pinned to f25a07b2d94c (revert restored file to doc state; LOC 21102 unchanged, 7 cites spot-checked)
[done:6b2dde1] knowledge/files/src/bin/pg_dump/pg_dumpall.c.md  reason=anchor-bump 2026-06-19:bdae2c20e88d..dc5116780846 (Revert non-text output formats for pg_dumpall, 7ca548f23a60) — AUDIT 2026-06-22: MAJOR drift fixed (revert removed all archive-output: −549 LOC 2441→1892; full rewrite to text-only, dropped parseDumpFormat/archDumpFormat/createDumpId/check_for_invalid_global_names/toc.glo/map.dat)
[done:6b2dde1] knowledge/files/src/bin/pg_dump/pg_restore.c.md  reason=anchor-bump 2026-06-19:bdae2c20e88d..dc5116780846 (Revert non-text output formats for pg_dumpall, 7ca548f23a60) — AUDIT 2026-06-22: MAJOR drift fixed (revert removed dumpall-archive restore: −622 LOC 1331→709; full rewrite to single-archive driver, dropped restore_all_databases/restore_global_objects/get_dbname_oid_list_from_mfile/--exclude-database/--globals-only)
[done:6b2dde1] knowledge/files/src/bin/pg_dump/pg_backup_archiver.h.md  reason=anchor-bump 2026-06-19:bdae2c20e88d..dc5116780846 (Revert non-text output formats for pg_dumpall, 7ca548f23a60) — AUDIT 2026-06-22: clean, re-pinned (LOC 477→476 cosmetic; K_VERS/structs/worker-codes all hold)
[done:6b2dde1] knowledge/files/src/bin/pg_dump/pg_backup.h.md  reason=anchor-bump 2026-06-19:bdae2c20e88d..dc5116780846 (Revert non-text output formats for pg_dumpall, 7ca548f23a60) — AUDIT 2026-06-22: clean, re-pinned (public header untouched, LOC 347)
[done:6b2dde1] knowledge/files/src/bin/pg_dump/pg_backup_tar.c.md  reason=anchor-bump 2026-06-19:bdae2c20e88d..dc5116780846 (Revert non-text output formats for pg_dumpall, 7ca548f23a60) — AUDIT 2026-06-22: clean, re-pinned (tar module untouched, LOC 1197)
[done:6b2dde1] knowledge/files/src/bin/pg_dump/parallel.c.md  reason=anchor-bump 2026-06-19:bdae2c20e88d..dc5116780846 (Revert non-text output formats for pg_dumpall, 7ca548f23a60) — AUDIT 2026-06-22: DRIFT fixed (revert removed replace_on_exit_close_archive helper @old:345 → uniform −14 shift after that line; phantom-symbol cite removed; ~30 cites re-pinned; LOC 1817→1803)
[done:468743e] knowledge/files/src/backend/storage/ipc/procarray.c.md  reason=anchor-bump 2026-06-19:bdae2c20e88d..dc5116780846 (Make GetSnapshotData() more resilient on out-of-memory errors, 29fb598b9cad) — AUDIT 2026-06-21: DRIFT fixed (OOM guard +8 in GetSnapshotData interior, +1 reuse helpers; ~20 cites re-pinned; stale :339 lastOverflowedXid cite corrected)
[done:468743e] knowledge/files/src/backend/postmaster/autovacuum.c.md  reason=anchor-bump 2026-06-19:bdae2c20e88d..dc5116780846 (Avoid division-by-zero when calculating autovacuum MXID score, 1f2297b54879) — AUDIT 2026-06-21: DRIFT fixed (tail shmem symbols +5: AutoVacuumingActive 3459->3464, ShmemRequest/Init 3530/3553->3535/3558)
[done:468743e] knowledge/files/src/backend/optimizer/util/clauses.c.md  reason=anchor-bump 2026-06-19:bdae2c20e88d..dc5116780846 (Silence "may be used uninitialized" compiler warning, f04781df5daf) — AUDIT 2026-06-21: DRIFT fixed (bottom-half table wrong AT CREATION vs ef6a95c7c64, not drift: is_parallel_safe 1151->766 etc.; top half +1; whole table re-pinned + re-sorted)
[done:468743e] knowledge/files/src/backend/jit/llvm/llvmjit_deform.c.md  reason=anchor-bump 2026-06-19:bdae2c20e88d..dc5116780846 (Update JIT tuple deforming code for virtual generated columns, dc5116780846) — AUDIT 2026-06-21: DRIFT fixed (+12, 3 zones; all landmarks re-pinned + SEMANTIC change captured: guaranteed-present now excludes ATTRIBUTE_GENERATED_VIRTUAL + always NULL-checks virtual gencols)
[done:468743e] knowledge/files/src/backend/postmaster/datachecksum_state.c.md  reason=anchor-bump 2026-06-19:bdae2c20e88d..dc5116780846 (Fix comments on data checksum cost settings, 8d22f5232458) — AUDIT 2026-06-21: SUBSTANTIVE drift fixed (cost params read UNDER DataChecksumsWorkerLock not lock-free; dynamic cost params now supported; derived ISSUE-undocumented-invariant marked RESOLVED; 10 entry cites + cluster re-pinned)
[done:468743e] knowledge/files/contrib/hstore_plperl/hstore_plperl.c.md  reason=anchor-bump 2026-06-19:bdae2c20e88d..dc5116780846 (hstore_plperl: Add CHECK_FOR_INTERRUPTS() in reference-unwinding loop, c0f17b04d906) — AUDIT 2026-06-21: DRIFT fixed (+9; entry+leak cites re-pinned; new CHECK_FOR_INTERRUPTS in SvROK loop :121 documented)

## anchor-bump 2026-06-20: dc5116780846..f25a07b2d94c (1 commit, pg-anchor-refresh)

[done:6b2dde1] knowledge/files/src/port/pgmkdirp.c.md  reason=anchor-bump 2026-06-20:dc5116780846..f25a07b2d94c (Make pg_mkdir_p() tolerant of a concurrent directory creation, f25a07b2d94c) — AUDIT 2026-06-22: SEMANTIC drift fixed (LOC 148→169; component walk restructured stat-first → mkdir-first-tolerate-EEXIST; new WIN32 GetFileAttributes probe documented; concurrent-creation tolerance added to gotchas)

## anchor-bump 2026-06-21: f25a07b2d94c..031904048aa2 (4 commits, pg-anchor-refresh)

[done:4138954] knowledge/files/src/backend/replication/logical/sequencesync.c.md  reason=anchor-bump 2026-06-21:f25a07b2d94c..031904048aa2 (Fix misreporting of publisher sequence permissions during sync, d4a657b0a4db) — AUDIT 2026-06-23: DRIFT fixed (LOC 776→815; REMOTE_SEQ_COL_COUNT 10→11; CopySeqResult INSUFFICIENT_PERM split into SUBSCRIBER/PUBLISHER variants; ProcessSequencesForSync :96→:97; re-pinned 031904048aa2)
[done:4138954] knowledge/files/src/backend/utils/cache/typcache.c.md  reason=anchor-bump 2026-06-21:f25a07b2d94c..031904048aa2 (Make type cache initialization more resilient on re-entry after OOM, 73dab12719ee) — AUDIT 2026-06-23: DRIFT fixed (LOC 3226→3228; uniform +2 shift on all cites after lookup_type_cache@389; documented new in_progress_list OOM-resilient lazy init)
[done:4138954] knowledge/files/src/backend/storage/ipc/standby.c.md  reason=anchor-bump 2026-06-21:f25a07b2d94c..031904048aa2 (Make StandbyAcquireAccessExclusiveLock() more resilent with OOMs, b85f9c00fb88) — AUDIT 2026-06-23: DRIFT fixed (LOC unchanged 1528; stale cross-ref LockAcquireExtended(reportMemoryError=false) corrected to throwing LockAcquire; entries-before-lock OOM reorder documented :1008-1029)

## anchor-bump 2026-06-22: 031904048aa2..9a60f295bcb1 (2 commits, pg-anchor-refresh)

[pending] knowledge/files/src/backend/optimizer/plan/analyzejoins.c.md  reason=anchor-bump 2026-06-22:031904048aa2..9a60f295bcb1 (Strip removed-relation references from PlaceHolderVars at join removal, 9a60f295bcb1)

## anchor-bump 2026-06-23: 9a60f295bcb1..f0a4f280b4d3 (3 commits, pg-anchor-refresh)

[pending] knowledge/files/src/backend/utils/resowner/resowner.c.md  reason=anchor-bump 2026-06-23:9a60f295bcb1..f0a4f280b4d3 (Fix unsafe order of operations in ResourceOwnerReleaseAll(), ef01ca6dbca5)

## anchor-bump 2026-06-24: f0a4f280b4d3..419ce13b7019 (8 commits, pg-anchor-refresh)

[in-progress:cloud/pg-quality-auditor/2026-06-28] knowledge/files/src/backend/parser/parse_func.c.md  reason=anchor-bump 2026-06-24:f0a4f280b4d3..419ce13b7019 (Refine error reporting for null treatment on non-window functions, 419ce13b7019; prior re-anchored [in-progress] 2026-06-19 follows the same parse_func_call null-treatment path) — AUDIT 2026-06-28: clean re-pin to 419ce13b7019 (no line cites; null-treatment errmsg :357-359 confirmed; LOC 2816→2821)
[in-progress:cloud/pg-quality-auditor/2026-06-28] knowledge/files/src/pl/plperl/plperl.c.md  reason=anchor-bump 2026-06-24:f0a4f280b4d3..419ce13b7019 (plperl: Fix NULL pointer dereference for forged array object, 4015abe14bb0) — AUDIT 2026-06-28: re-anchored line-neutral (LOC 4254); documented forged-array NULL-deref hardening in get_perl_array_ref :1144 (4015abe14bb0); fixed stale plperl_init_interp cite 606-650→710; ~12 cites sampled in-tolerance, full re-pin deferred
[in-progress:cloud/pg-quality-auditor/2026-06-28] knowledge/files/src/backend/commands/explain.c.md  reason=anchor-bump 2026-06-24:f0a4f280b4d3..419ce13b7019 (Re-index ModifyTable FDW arrays when pruning result relations, b43f8aa4cb30) — AUDIT 2026-06-28: clean re-pin (b43f8aa4cb30 line-neutral; LOC 5324 unchanged; entry points intact)
[in-progress:cloud/pg-quality-auditor/2026-06-28] knowledge/files/src/backend/executor/nodeModifyTable.c.md  reason=anchor-bump 2026-06-24:f0a4f280b4d3..419ce13b7019 (Re-index ModifyTable FDW arrays when pruning result relations, b43f8aa4cb30) — AUDIT 2026-06-28: MAJOR drift fixed (pinned ef6a95c7c64; all ~17 fn cites re-pinned −13/+2; documented b43f8aa4cb30 FDW-array re-index in ExecInitModifyTable :5123-5223; LOC ≈5500→5951)
[in-progress:cloud/pg-quality-auditor/2026-06-28] knowledge/files/src/include/nodes/execnodes.h.md  reason=anchor-bump 2026-06-24:f0a4f280b4d3..419ce13b7019 (Re-index ModifyTable FDW arrays when pruning result relations, b43f8aa4cb30) — AUDIT 2026-06-28: DRIFT fixed (+1 on structs past :500: ResultRelInfo/EState/ExecRowMark/TupleHash*; LOC ~3500→2816; noted ModifyTableState :1440 FDW re-index)
[in-progress:cloud/pg-quality-auditor/2026-06-28] knowledge/files/src/backend/utils/cache/catcache.c.md  reason=anchor-bump 2026-06-24:f0a4f280b4d3..419ce13b7019 (Nail pg_parameter_acl in relcache, 4cc02b80774e) — AUDIT 2026-06-28: DRIFT fixed (cumulative ef6a95c7c64 delta; +2 below SearchCatCache :1374, +1 at ResetCatalogCache :754; all fn + interior-comment cites re-pinned; LOC 2500→2502)
[in-progress:cloud/pg-quality-auditor/2026-06-28] knowledge/files/src/backend/utils/cache/relcache.c.md  reason=anchor-bump 2026-06-24:f0a4f280b4d3..419ce13b7019 (Nail pg_parameter_acl in relcache, 4cc02b80774e) — AUDIT 2026-06-28: MAJOR drift fixed (4cc02b80774e nailed pg_parameter_acl in Phase3; +2 above ~:4250, +9/+10 below; full ~40-cite re-pin; header include :59 + Desc_pg_parameter_acl :124 documented; LOC 7021→7030)
[in-progress:cloud/pg-quality-auditor/2026-06-28] knowledge/files/src/include/catalog/pg_parameter_acl.h.md  reason=anchor-bump 2026-06-24:f0a4f280b4d3..419ce13b7019 (Nail pg_parameter_acl in relcache, 4cc02b80774e) — AUDIT 2026-06-28: clean re-pin (4cc02b80774e changed relcache.c not this header; all 11 cites hold exact)
[in-progress:cloud/pg-quality-auditor/2026-06-28] knowledge/files/src/include/catalog/catversion.h.md  reason=anchor-bump 2026-06-24:f0a4f280b4d3..419ce13b7019 (2 catversion bumps: pg_parameter_acl relcache-nailing 4cc02b80774e + variadic pg_get_*_ddl() declaration fix 2af70e937478) — AUDIT 2026-06-28: value drift fixed (CATALOG_VERSION_NO 202605131→202606232 via 2 catversion bumps 4cc02b80+2af70e93)
[in-progress:cloud/pg-quality-auditor/2026-06-28] knowledge/files/src/include/fe_utils/psqlscan_int.h.md  reason=anchor-bump 2026-06-24:f0a4f280b4d3..419ce13b7019 (psql: Tighten heuristics for BEGIN/END within CREATE SCHEMA, 049b742daad0) — AUDIT 2026-06-28: SEMANTIC drift fixed (049b742daad0 renamed identifier_count/identifiers[4] → init_idents[4] :122 + added sub_idents[4] :125 for CREATE SCHEMA; rewrote BEGIN/END heuristic + ISSUE; symbol table re-pinned +3; LOC 155→158)
[pending] knowledge/files/src/backend/catalog/objectaddress.c.md  reason=anchor-bump 2026-06-24:f0a4f280b4d3..419ce13b7019 (Readable identity strings for property graph objects, 2a7e95b659df)

## anchor-bump 2026-06-25: 419ce13b7019..4abf411e2328 (8 commits, pg-anchor-refresh)

[in-progress:cloud/pg-quality-auditor/2026-06-29] knowledge/files/src/backend/utils/activity/pgstat_io.c.md  reason=anchor-bump 2026-06-25:419ce13b7019..4abf411e2328 (pg_stat_io: Don't flag extends by autovacuum launcher, 4abf411e2328, Melanie Plageman) — AUDIT 2026-06-29: clean prose re-pin @4abf411e2328; documented autovac-launcher validation refinement (:460/:463); LOC ~540→~558
[in-progress:cloud/pg-quality-auditor/2026-06-29] knowledge/files/src/bin/psql/tab-complete.in.c.md  reason=anchor-bump 2026-06-25:419ce13b7019..4abf411e2328 (psql: Add tab completion for subscription wal_receiver_timeout, 56b2792cf84f, Fujii Masao) — AUDIT 2026-06-29: re-pinned from 4b0bf0788b0; +2/+3 region drift fixed (requote 6926→6928, exec_query 7041→7043, encodings 6793→6797); wal_receiver_timeout add @:2384/:3970; LOC 7341→7343
[in-progress:cloud/pg-quality-auditor/2026-06-29] knowledge/files/src/backend/postmaster/datachecksum_state.c.md  reason=anchor-bump 2026-06-25:419ce13b7019..4abf411e2328 (datachecksum_state.[ch] cleanup cluster: distinguish worker invocations a4f02cab4b97 + check-result cleanup c48e7b2c8bd0 + worker_pid reset c008b7ea10a5 + misc cleanup 0edbf72f7683, all Heikki Linnakangas) — AUDIT 2026-06-29: MAJOR drift fixed (cleanup-cluster +~40 shift; ~20 cites re-pinned; CHECK_FOR_ABORT_REQUEST split→LAUNCHER/WORKER :401/:410; LOC 1723→1789)
[in-progress:cloud/pg-quality-auditor/2026-06-29] knowledge/files/src/include/postmaster/datachecksum_state.h.md  reason=anchor-bump 2026-06-25:419ce13b7019..4abf411e2328 (Misc cleanup in datachecksums_state.[ch], 0edbf72f7683, Heikki Linnakangas) — AUDIT 2026-06-29: MAJOR drift fixed (header gutted ~54→28; 2 enums + StartDataChecksumsWorkerLauncher moved to .c; API section rewritten)
[in-progress:cloud/pg-quality-auditor/2026-06-29] knowledge/files/src/backend/access/transam/xact.c.md  reason=anchor-bump 2026-06-25:419ce13b7019..4abf411e2328 (Fix set of typos and grammar mistakes, b3a95566fc25, Michael Paquier — comment-only) — AUDIT 2026-06-29: clean re-pin (all cites exact; LOC 6503)
[in-progress:cloud/pg-quality-auditor/2026-06-29] knowledge/files/src/backend/access/transam/xlogprefetcher.c.md  reason=anchor-bump 2026-06-25:419ce13b7019..4abf411e2328 (Fix set of typos and grammar mistakes, b3a95566fc25, Michael Paquier — comment-only) — AUDIT 2026-06-29: DRIFT fixed (+1 below ~500: ReadRecord 986→987/BeginRead 967→968/pg_stat 829→830; stale struct cite :962→:127; LOC 1106→1107)
[in-progress:cloud/pg-quality-auditor/2026-06-29] knowledge/files/src/backend/postmaster/startup.c.md  reason=anchor-bump 2026-06-25:419ce13b7019..4abf411e2328 (Fix set of typos and grammar mistakes, b3a95566fc25, Michael Paquier — comment-only) — AUDIT 2026-06-29: clean re-pin (decl/return-type cites hold)
[in-progress:cloud/pg-quality-auditor/2026-06-29] knowledge/files/src/backend/utils/activity/pgstat_relation.c.md  reason=anchor-bump 2026-06-25:419ce13b7019..4abf411e2328 (Fix set of typos and grammar mistakes, b3a95566fc25, Michael Paquier — comment-only) — AUDIT 2026-06-29: clean re-pin (prose; symbols present; LOC ~1000→~1013)
[in-progress:cloud/pg-quality-auditor/2026-06-29] knowledge/files/src/backend/utils/activity/pgstat_slru.c.md  reason=anchor-bump 2026-06-25:419ce13b7019..4abf411e2328 (Fix set of typos and grammar mistakes, b3a95566fc25, Michael Paquier — comment-only) — AUDIT 2026-06-29: clean re-pin (prose; LOC ~220→~241)
[in-progress:cloud/pg-quality-auditor/2026-06-29] knowledge/files/src/backend/utils/adt/float.c.md  reason=anchor-bump 2026-06-25:419ce13b7019..4abf411e2328 (Fix set of typos and grammar mistakes, b3a95566fc25, Michael Paquier — comment-only) — AUDIT 2026-06-29: DRIFT fixed (check_float8_array :3015→def :2974/accum call :3100; LOC 4321→4389)
[in-progress:cloud/pg-quality-auditor/2026-06-29] knowledge/files/src/backend/utils/adt/pg_dependencies.c.md  reason=anchor-bump 2026-06-25:419ce13b7019..4abf411e2328 (Fix set of typos and grammar mistakes, b3a95566fc25, Michael Paquier — comment-only) — AUDIT 2026-06-29: DRIFT fixed (build_mvdependencies ~680→647/dup-check→702-720/serialize→725; LOC 873→872)
[in-progress:cloud/pg-quality-auditor/2026-06-29] knowledge/files/src/include/tsearch/ts_type.h.md  reason=anchor-bump 2026-06-25:419ce13b7019..4abf411e2328 (Fix set of typos and grammar mistakes, b3a95566fc25, Michael Paquier — comment-only) — AUDIT 2026-06-29: clean re-pin (bitfield/prose, no line cites)
[in-progress:cloud/pg-quality-auditor/2026-06-29] knowledge/files/src/port/pqsignal.c.md  reason=anchor-bump 2026-06-25:419ce13b7019..4abf411e2328 (Fix set of typos and grammar mistakes, b3a95566fc25, Michael Paquier — comment-only) — AUDIT 2026-06-29: clean re-pin (all cites hold; loc 220)
[in-progress:cloud/pg-quality-auditor/2026-06-29] knowledge/files/contrib/pg_stash_advice/stashfuncs.c.md  reason=anchor-bump 2026-06-25:419ce13b7019..4abf411e2328 (Fix set of typos and grammar mistakes, b3a95566fc25, Michael Paquier — comment-only) — AUDIT 2026-06-29: clean re-pin (6 SRF ranges hold exact)

## anchor-bump 2026-06-28: 4abf411e2328..02f699c14163 (18 commits, pg-anchor-refresh)

[pending] knowledge/files/contrib/pg_prewarm/autoprewarm.c.md  reason=anchor-bump 2026-06-28:4abf411e2328..02f699c14163 (Fix out-of-bounds access in autoprewarm worker, dac36601fd77, Tomas Vondra)
[pending] knowledge/files/src/backend/commands/copyfrom.c.md  reason=anchor-bump 2026-06-28:4abf411e2328..02f699c14163 (Reject child partition FDWs in FOR PORTION OF, a40fdf658862, Peter Eisentraut)
[pending] knowledge/files/src/backend/commands/copyto.c.md  reason=anchor-bump 2026-06-28:4abf411e2328..02f699c14163 (COPY TO FORMAT JSON: respect column list order, effb923d9dec + pgindent fix 02f699c14163, Andrew Dunstan)
[pending] knowledge/files/src/backend/commands/tablecmds.c.md  reason=anchor-bump 2026-06-28:4abf411e2328..02f699c14163 (Prevent inherited CHECK constraints from being weakened, 0cd17fdd3c00, Andrew Dunstan + Take into account default_tablespace during MERGE/SPLIT PARTITION(S), cdae794af31b, Alexander Korotkov)
[pending] knowledge/files/src/backend/executor/execMain.c.md  reason=anchor-bump 2026-06-28:4abf411e2328..02f699c14163 (Reject child partition FDWs in FOR PORTION OF, a40fdf658862, Peter Eisentraut)
[pending] knowledge/files/src/backend/executor/execPartition.c.md  reason=anchor-bump 2026-06-28:4abf411e2328..02f699c14163 (Reject child partition FDWs in FOR PORTION OF, a40fdf658862, Peter Eisentraut)
[pending] knowledge/files/src/backend/executor/nodeModifyTable.c.md  reason=anchor-bump 2026-06-28:4abf411e2328..02f699c14163 (Reject child partition FDWs in FOR PORTION OF, a40fdf658862, Peter Eisentraut — prior [in-progress] 06-24 row covers the unrelated b43f8aa4cb30 FDW-array re-index)
[pending] knowledge/files/src/backend/optimizer/plan/planner.c.md  reason=anchor-bump 2026-06-28:4abf411e2328..02f699c14163 (Move FOR PORTION OF volatile check into planner, a272a58b9424, Peter Eisentraut)
[pending] knowledge/files/src/backend/parser/analyze.c.md  reason=anchor-bump 2026-06-28:4abf411e2328..02f699c14163 (Reject child partition FDWs in FOR PORTION OF, a40fdf658862 + Move FOR PORTION OF volatile check into planner, a272a58b9424, Peter Eisentraut)
[pending] knowledge/files/src/bin/pg_test_timing/pg_test_timing.c.md  reason=anchor-bump 2026-06-28:4abf411e2328..02f699c14163 (Fix options listing of pg_test_timing --cutoff, 3277e69b8eb0, Peter Eisentraut)
[pending] knowledge/files/src/bin/pg_upgrade/check.c.md  reason=anchor-bump 2026-06-28:4abf411e2328..02f699c14163 (Message and comment wording fixes, cae90d747969, Peter Eisentraut)
[pending] knowledge/files/src/bin/psql/crosstabview.c.md  reason=anchor-bump 2026-06-28:4abf411e2328..02f699c14163 (Make crosstabview honor boolean/null display settings, 4df5fe3833a8, Álvaro Herrera)
[pending] knowledge/files/src/include/catalog/catversion.h.md  reason=anchor-bump 2026-06-28:4abf411e2328..02f699c14163 (catversion bump: Mark uuid-to-bytea cast as leakproof, 6468f7a853c3, Masahiko Sawada)
[pending] knowledge/files/src/include/executor/executor.h.md  reason=anchor-bump 2026-06-28:4abf411e2328..02f699c14163 (Reject child partition FDWs in FOR PORTION OF, a40fdf658862, Peter Eisentraut)
[pending] knowledge/files/src/interfaces/ecpg/preproc/type.c.md  reason=anchor-bump 2026-06-28:4abf411e2328..02f699c14163 (Fix null-pointer crash in ECPG compiler, 7f5e0b22e5ea, Tom Lane)
[pending] knowledge/files/contrib/hstore_plpython/hstore_plpython.c.md  reason=anchor-bump 2026-06-29:02f699c14163..b7e4e3e7fa73 (plpython: Fix NULL pointer dereferences for broken sequence and mapping, 8612f0b7ce09, Richard Guo)
[pending] knowledge/files/src/backend/access/transam/xact.c.md  reason=anchor-bump 2026-06-29:02f699c14163..b7e4e3e7fa73 (Hardwire RI fast-path end-of-xact cleanup into xact.c, 6f4bac854fb7, Amit Langote)
[pending] knowledge/files/src/backend/utils/adt/ddlutils.c.md  reason=anchor-bump 2026-06-29:02f699c14163..b7e4e3e7fa73 (Use named boolean parameters for pg_get_*_ddl option arguments, d6ed87d19890, Andrew Dunstan)
[pending] knowledge/files/src/backend/utils/adt/ri_triggers.c.md  reason=anchor-bump 2026-06-29:02f699c14163..b7e4e3e7fa73 (Hardwire RI fast-path end-of-xact cleanup into xact.c, 6f4bac854fb7, Amit Langote)
[pending] knowledge/files/src/backend/utils/adt/selfuncs.c.md  reason=anchor-bump 2026-06-29:02f699c14163..b7e4e3e7fa73 (Avoid collation lookup failure when considering a "char" column, b574fec00f27, Tom Lane)
[pending] knowledge/files/src/include/commands/trigger.h.md  reason=anchor-bump 2026-06-29:02f699c14163..b7e4e3e7fa73 (Hardwire RI fast-path end-of-xact cleanup into xact.c, 6f4bac854fb7, Amit Langote)
[done:fb47271] knowledge/files/src/backend/storage/lmgr/proc.c.md  reason=anchor-bump 2026-06-30:b7e4e3e7fa73..c776550e4662 (Change stat_lock.wait_time to double precision, c776550e4662, Michael Paquier) — AUDIT 2026-07-02: DRIFT fixed (LOC 2139→2140; uniform +1 below :1613 where c776550e4662 added the μs pgstat_count_lock_waits call; ~12 §2/§4/§5 cites re-pinned incl. deadlock partition-lock canonical statement 1856-1939→1857-1940)
[done:fb47271] knowledge/files/src/backend/utils/activity/pgstat_lock.c.md  reason=anchor-bump 2026-06-30:b7e4e3e7fa73..c776550e4662 (Change stat_lock.wait_time to double precision, c776550e4662, Michael Paquier) — AUDIT 2026-07-02: DRIFT fixed (pgstat_count_lock_waits signature long msecs→PgStat_Counter usecs, ms→μs; stale ":147 cast" ISSUE corrected; wait_time is int64 μs internally, SQL-exposed as double)
[done:fb47271] knowledge/files/src/backend/utils/adt/pgstatfuncs.c.md  reason=anchor-bump 2026-06-30:b7e4e3e7fa73..c776550e4662 (Change stat_lock.wait_time to double precision, c776550e4662, Michael Paquier) — AUDIT 2026-07-02: clean (all cites hold ±1, LOC ~2360→2363; doc doesn't cover pg_stat_get_lock :1741 where wait_time now returns via Float8GetDatum(pg_stat_us_to_ms) :1764 — noted + anchor header added)
[done:fb47271] knowledge/files/src/include/pgstat.h.md  reason=anchor-bump 2026-06-30:b7e4e3e7fa73..c776550e4662 (Change stat_lock.wait_time to double precision, c776550e4662, Michael Paquier) — AUDIT 2026-07-02: clean re-pin (all region cites hold ±1, LOC ~881→882; added PgStat_LockEntry :349-354 wait_time=int64 μs / SQL double note)
[pending] knowledge/files/src/fe_utils/string_utils.c.md  reason=anchor-bump 2026-06-30:b7e4e3e7fa73..c776550e4662 (Restore comment at appendShellString(), cfa573cf8cbd, Noah Misch)
[done:fb47271] knowledge/files/src/backend/storage/buffer/bufmgr.c.md  reason=anchor-bump 2026-06-30:b7e4e3e7fa73..c776550e4662 (bufmgr: Fix race in LockBufferForCleanup(), 8d85cb889a39, Andres Freund) — AUDIT 2026-07-02: DRIFT fixed (LOC 8967→8993; §3.11 rewritten for the missed-wakeup race fix: publish BM_PIN_COUNT_WAITER via pg_atomic_fetch_or_u64 under header lock then recheck refcount before sleeping; LockBufferForCleanup 6678→6679, ConditionalLock 6852→6878, WakePinCountWaiter 3428→3429, FlushBuffer XLogFlush 4553-4569→4569-4571; broader month-old drift noted in header)
[pending] knowledge/files/src/backend/parser/parse_func.c.md  reason=anchor-bump 2026-06-30:b7e4e3e7fa73..c776550e4662 (Remove stray blank line in ParseFuncOrColumn(), d8113095c488, Tom Lane)
[done:fb47271] knowledge/files/src/backend/access/hash/hash_xlog.c.md  reason=anchor-bump 2026-06-30:b7e4e3e7fa73..c776550e4662 (Fix unlogged sequence corruption after standby promotion, 8e684ce11dda, Heikki Linnakangas) — AUDIT 2026-07-02: re-pinned (LOC 1154→1131 −23; INIT handlers now call XLogFlushBufferForRedoIfInit ×3 @:43/:71/:92; record-table + README cites unaffected; banner :1-13 holds)
[done:fb47271] knowledge/files/src/backend/access/transam/xlogutils.c.md  reason=anchor-bump 2026-06-30:b7e4e3e7fa73..c776550e4662 (Fix unlogged sequence corruption after standby promotion, 8e684ce11dda, Heikki Linnakangas) — AUDIT 2026-07-02: DRIFT fixed (LOC 1046→1070; new XLogFlushBufferForRedoIfInit :334 documented; +24 shift below it, ~11 function cites re-pinned CreateFakeRelcacheEntry 571→595 … WALReadRaiseError 1023→1047)
[done:fb47271] knowledge/files/src/include/access/xlogutils.h.md  reason=anchor-bump 2026-06-30:b7e4e3e7fa73..c776550e4662 (Fix unlogged sequence corruption after standby promotion, 8e684ce11dda, Heikki Linnakangas) — AUDIT 2026-07-02: DRIFT fixed (LOC 121→123; new XLogFlushBufferForRedoIfInit proto :90-91 added to redo-helpers with full mechanism note; +2 shift CreateFakeRelcacheEntry 99→101, WALReadRaiseError 119→121)
[done:fb47271] knowledge/files/src/backend/commands/sequence_xlog.c.md  reason=anchor-bump 2026-06-30:b7e4e3e7fa73..c776550e4662 (Fix unlogged sequence corruption after standby promotion, 8e684ce11dda, Heikki Linnakangas) — AUDIT 2026-07-02: re-pinned (LOC ~80→81; seq_redo now calls XLogFlushBufferForRedoIfInit :65 documented — init-fork flush so unlogged-seq reinit survives promotion)
[pending] knowledge/files/src/backend/statistics/stat_utils.c.md  reason=anchor-bump 2026-06-30:b7e4e3e7fa73..c776550e4662 (Simplify some stats restore code with InputFunctionCallSafe(), efa59a500457, Michael Paquier)
[pending] knowledge/files/src/bin/pg_combinebackup/reconstruct.c.md  reason=anchor-bump 2026-06-30:b7e4e3e7fa73..c776550e4662 (Fix handling of copy_file_range() return value, 994f770a0fd5, Tomas Vondra)
[pending] knowledge/files/src/backend/executor/spi.c.md  reason=anchor-bump 2026-07-01:c776550e4662..b542d5566705 (Make SPI_prepare argtypes argument const + const Datum * fixes, b1c41398e48c+cd3ad3bc0356, Peter Eisentraut)
[pending] knowledge/files/src/include/executor/spi_priv.h.md  reason=anchor-bump 2026-07-01:c776550e4662..b542d5566705 (Make SPI_prepare argtypes argument const, b1c41398e48c, Peter Eisentraut)
[pending] knowledge/files/src/include/utils/plancache.h.md  reason=anchor-bump 2026-07-01:c776550e4662..b542d5566705 (Make SPI_prepare argtypes argument const, b1c41398e48c, Peter Eisentraut)
[pending] knowledge/files/src/backend/utils/cache/plancache.c.md  reason=anchor-bump 2026-07-01:c776550e4662..b542d5566705 (Make SPI_prepare argtypes argument const, b1c41398e48c, Peter Eisentraut)
[pending] knowledge/files/src/backend/utils/activity/pgstat_backend.c.md  reason=anchor-bump 2026-07-01:c776550e4662..b542d5566705 (Add backend-level lock statistics, 8c579bdc366d, Michael Paquier)
[pending] knowledge/files/src/backend/utils/adt/multixactfuncs.c.md  reason=anchor-bump 2026-07-01:c776550e4662..b542d5566705 (Avoid useless calls in pg_get_multixact_stats(), b542d5566705, Michael Paquier)
[pending] knowledge/files/src/backend/postmaster/autovacuum.c.md  reason=anchor-bump 2026-07-01:c776550e4662..b542d5566705 (Use placeholders and not GUC names in error message, 7905416eef9b, Michael Paquier)
[pending] knowledge/files/src/common/d2s.c.md  reason=anchor-bump 2026-07-01:c776550e4662..b542d5566705 (Clean up inconsistencies in CPU-identification macros, 2ef57e636fc9, Tom Lane)
[pending] knowledge/files/src/include/c.h.md  reason=anchor-bump 2026-07-01:c776550e4662..b542d5566705 (Clean up inconsistencies in CPU-identification macros, 2ef57e636fc9, Tom Lane)
[pending] knowledge/files/src/include/port/atomics/arch-x86.h.md  reason=anchor-bump 2026-07-01:c776550e4662..b542d5566705 (CPU-macro cleanup + Remove pg_spin_delay(), 2ef57e636fc9+ae27a41e0c7f, Tom Lane+Nathan Bossart)
[pending] knowledge/files/src/include/port/atomics/generic.h.md  reason=anchor-bump 2026-07-01:c776550e4662..b542d5566705 (Remove pg_spin_delay(), ae27a41e0c7f, Nathan Bossart)
[pending] knowledge/files/src/include/portability/instr_time.h.md  reason=anchor-bump 2026-07-01:c776550e4662..b542d5566705 (Clean up inconsistencies in CPU-identification macros, 2ef57e636fc9, Tom Lane)
[pending] knowledge/files/src/include/storage/s_lock.h.md  reason=anchor-bump 2026-07-01:c776550e4662..b542d5566705 (Clean up inconsistencies in CPU-identification macros, 2ef57e636fc9, Tom Lane)
[pending] knowledge/files/src/port/pg_cpu_x86.c.md  reason=anchor-bump 2026-07-01:c776550e4662..b542d5566705 (Clean up inconsistencies in CPU-identification macros, 2ef57e636fc9, Tom Lane)
[pending] knowledge/files/src/bin/initdb/initdb.c.md  reason=anchor-bump 2026-07-01:c776550e4662..b542d5566705 (Remove radius from initdb authentication methods, a78f7390bf19, Thomas Munro)

<!-- anchor-refresh 2026-07-02: b542d5566705..6b41bd1a459c, 19 commits, 85 new + 11 already-pending -->
[pending] knowledge/files/contrib/btree_gist/btree_float4.c.md  reason=anchor-bump 2026-07-02:b542d5566705..6b41bd1a459c (btree_gist: fix NaN handling in float4/float8 opclasses, 7d3448961da3, Tom Lane)
[pending] knowledge/files/contrib/btree_gist/btree_float8.c.md  reason=anchor-bump 2026-07-02:b542d5566705..6b41bd1a459c (btree_gist: fix NaN handling in float4/float8 opclasses, 7d3448961da3, Tom Lane)
[pending] knowledge/files/contrib/btree_gist/btree_utils_num.h.md  reason=anchor-bump 2026-07-02:b542d5566705..6b41bd1a459c (btree_gist: fix NaN handling in float4/float8 opclasses, 7d3448961da3, Tom Lane)
[pending] knowledge/files/contrib/oid2name/oid2name.c.md  reason=anchor-bump 2026-07-02:b542d5566705..6b41bd1a459c (Fix mismatched deallocation functions, 30652b356d20, Peter Eisentraut)
[pending] knowledge/files/src/backend/backup/basebackup.c.md  reason=anchor-bump 2026-07-02:b542d5566705..6b41bd1a459c (Clear base backup progress on backup failure, 55f0a13e96be, Fujii Masao)
[pending] knowledge/files/src/backend/backup/basebackup_progress.c.md  reason=anchor-bump 2026-07-02:b542d5566705..6b41bd1a459c (Clear base backup progress on backup failure, 55f0a13e96be, Fujii Masao)
[pending] knowledge/files/src/backend/backup/basebackup_server.c.md  reason=anchor-bump 2026-07-02:b542d5566705..6b41bd1a459c (Don't cast off_t to 32-bit type for output, bug fix, e8f851d61727, Peter Eisentraut)
[pending] knowledge/files/src/backend/catalog/aclchk.c.md  reason=anchor-bump 2026-07-02:b542d5566705..6b41bd1a459c (Allow logical replication conflicts to be logged to a table, a5918fddf10d, Amit Kapila)
[pending] knowledge/files/src/backend/catalog/catalog.c.md  reason=anchor-bump 2026-07-02:b542d5566705..6b41bd1a459c (Allow logical replication conflicts to be logged to a table, a5918fddf10d, Amit Kapila)
[pending] knowledge/files/src/backend/catalog/pg_publication.c.md  reason=anchor-bump 2026-07-02:b542d5566705..6b41bd1a459c (Allow logical replication conflicts to be logged to a table, a5918fddf10d, Amit Kapila)
[pending] knowledge/files/src/backend/catalog/pg_subscription.c.md  reason=anchor-bump 2026-07-02:b542d5566705..6b41bd1a459c (Allow logical replication conflicts to be logged to a table, a5918fddf10d, Amit Kapila)
[pending] knowledge/files/src/backend/commands/indexcmds.c.md  reason=anchor-bump 2026-07-02:b542d5566705..6b41bd1a459c (Improve the names generated for indexes on expressions, 181b6185c79e, Tom Lane)
[pending] knowledge/files/src/backend/commands/lockcmds.c.md  reason=anchor-bump 2026-07-02:b542d5566705..6b41bd1a459c (Allow logical replication conflicts to be logged to a table, a5918fddf10d, Amit Kapila)
[pending] knowledge/files/src/backend/commands/policy.c.md  reason=anchor-bump 2026-07-02:b542d5566705..6b41bd1a459c (Allow logical replication conflicts to be logged to a table, a5918fddf10d, Amit Kapila)
[pending] knowledge/files/src/backend/commands/statscmds.c.md  reason=anchor-bump 2026-07-02:b542d5566705..6b41bd1a459c (Allow logical replication conflicts to be logged to a table, a5918fddf10d, Amit Kapila)
[pending] knowledge/files/src/backend/commands/subscriptioncmds.c.md  reason=anchor-bump 2026-07-02:b542d5566705..6b41bd1a459c (Allow logical replication conflicts to be logged to a table, a5918fddf10d, Amit Kapila)
[pending] knowledge/files/src/backend/commands/trigger.c.md  reason=anchor-bump 2026-07-02:b542d5566705..6b41bd1a459c (Allow logical replication conflicts to be logged to a table, a5918fddf10d, Amit Kapila)
[pending] knowledge/files/src/backend/libpq/auth.c.md  reason=anchor-bump 2026-07-02:b542d5566705..6b41bd1a459c (Warn on password auth with MD5-encrypted passwords, f6fdc2a4a737, Fujii Masao)
[pending] knowledge/files/src/backend/libpq/crypt.c.md  reason=anchor-bump 2026-07-02:b542d5566705..6b41bd1a459c (Warn on password auth with MD5-encrypted passwords, f6fdc2a4a737, Fujii Masao)
[pending] knowledge/files/src/backend/optimizer/prep/prepunion.c.md  reason=anchor-bump 2026-07-02:b542d5566705..6b41bd1a459c (Improve UNION's output row count estimate, be69a5ff1fd9, Richard Guo)
[pending] knowledge/files/src/backend/parser/parse_target.c.md  reason=anchor-bump 2026-07-02:b542d5566705..6b41bd1a459c (Improve the names generated for indexes on expressions, 181b6185c79e, Tom Lane)
[pending] knowledge/files/src/backend/parser/parse_utilcmd.c.md  reason=anchor-bump 2026-07-02:b542d5566705..6b41bd1a459c (Improve the names generated for indexes on expressions, 181b6185c79e, Tom Lane)
[pending] knowledge/files/src/backend/replication/logical/conflict.c.md  reason=anchor-bump 2026-07-02:b542d5566705..6b41bd1a459c (Allow logical replication conflicts to be logged to a table, a5918fddf10d, Amit Kapila; pgindent fix for commit a5918fddf1, fdad19e1cfe4, Amit Kapila)
[pending] knowledge/files/src/backend/replication/logical/slotsync.c.md  reason=anchor-bump 2026-07-02:b542d5566705..6b41bd1a459c (Expand comment on the slot recheck in drop_local_obsolete_slots(), 6b41bd1a459c, Amit Kapila)
[pending] knowledge/files/src/backend/rewrite/rewriteDefine.c.md  reason=anchor-bump 2026-07-02:b542d5566705..6b41bd1a459c (Allow logical replication conflicts to be logged to a table, a5918fddf10d, Amit Kapila)
[pending] knowledge/files/src/backend/utils/adt/jsonpath_exec.c.md  reason=anchor-bump 2026-07-02:b542d5566705..6b41bd1a459c (Fix jsonpath .decimal() to honor silent mode, 7b12ae729e6a, Michael Paquier)
[pending] knowledge/files/src/backend/utils/adt/numeric.c.md  reason=anchor-bump 2026-07-02:b542d5566705..6b41bd1a459c (Fix jsonpath .decimal() to honor silent mode, 7b12ae729e6a, Michael Paquier)
[pending] knowledge/files/src/backend/utils/adt/uuid.c.md  reason=anchor-bump 2026-07-02:b542d5566705..6b41bd1a459c (Add min() and max() aggregate support for uuid, 2e606d75c0bf, Masahiko Sawada)
[pending] knowledge/files/src/bin/initdb/findtimezone.c.md  reason=anchor-bump 2026-07-02:b542d5566705..6b41bd1a459c (Sync our copy of the timezone library with IANA release tzcode2026b, aeb07c55fab5, Tom Lane)
[pending] knowledge/files/src/bin/pg_archivecleanup/pg_archivecleanup.c.md  reason=anchor-bump 2026-07-02:b542d5566705..6b41bd1a459c (Split dry-run messages into primary and detail, e3b5817c8b89, Peter Eisentraut)
[pending] knowledge/files/src/bin/pg_basebackup/pg_basebackup.c.md  reason=anchor-bump 2026-07-02:b542d5566705..6b41bd1a459c (Fix mismatched deallocation functions, 30652b356d20, Peter Eisentraut)
[pending] knowledge/files/src/bin/pg_basebackup/pg_createsubscriber.c.md  reason=anchor-bump 2026-07-02:b542d5566705..6b41bd1a459c (Split dry-run messages into primary and detail, e3b5817c8b89, Peter Eisentraut; Fix mismatched deallocation functions, 30652b356d20, Peter Eisentraut)
[pending] knowledge/files/src/bin/pg_basebackup/streamutil.c.md  reason=anchor-bump 2026-07-02:b542d5566705..6b41bd1a459c (Fix mismatched deallocation functions, 30652b356d20, Peter Eisentraut)
[pending] knowledge/files/src/bin/pg_combinebackup/load_manifest.c.md  reason=anchor-bump 2026-07-02:b542d5566705..6b41bd1a459c (Fix mismatched deallocation functions, 30652b356d20, Peter Eisentraut)
[pending] knowledge/files/src/bin/pg_combinebackup/pg_combinebackup.c.md  reason=anchor-bump 2026-07-02:b542d5566705..6b41bd1a459c (Split dry-run messages into primary and detail, e3b5817c8b89, Peter Eisentraut; Fix mismatched deallocation functions, 30652b356d20, Peter Eisentraut)
[pending] knowledge/files/src/bin/pg_ctl/pg_ctl.c.md  reason=anchor-bump 2026-07-02:b542d5566705..6b41bd1a459c (Fix mismatched deallocation functions, 30652b356d20, Peter Eisentraut)
[pending] knowledge/files/src/bin/pg_dump/compress_gzip.c.md  reason=anchor-bump 2026-07-02:b542d5566705..6b41bd1a459c (Fix mismatched deallocation functions, 30652b356d20, Peter Eisentraut)
[pending] knowledge/files/src/bin/pg_dump/compress_lz4.c.md  reason=anchor-bump 2026-07-02:b542d5566705..6b41bd1a459c (Fix mismatched deallocation functions, 30652b356d20, Peter Eisentraut)
[pending] knowledge/files/src/bin/pg_dump/compress_none.c.md  reason=anchor-bump 2026-07-02:b542d5566705..6b41bd1a459c (Fix mismatched deallocation functions, 30652b356d20, Peter Eisentraut)
[pending] knowledge/files/src/bin/pg_dump/connectdb.c.md  reason=anchor-bump 2026-07-02:b542d5566705..6b41bd1a459c (Fix mismatched deallocation functions, 30652b356d20, Peter Eisentraut)
[pending] knowledge/files/src/bin/pg_dump/dumputils.c.md  reason=anchor-bump 2026-07-02:b542d5566705..6b41bd1a459c (Fix mismatched deallocation functions, 30652b356d20, Peter Eisentraut)
[pending] knowledge/files/src/bin/pg_dump/parallel.c.md  reason=anchor-bump 2026-07-02:b542d5566705..6b41bd1a459c (Fix mismatched deallocation functions, 30652b356d20, Peter Eisentraut)
[pending] knowledge/files/src/bin/pg_dump/pg_backup_custom.c.md  reason=anchor-bump 2026-07-02:b542d5566705..6b41bd1a459c (Fix mismatched deallocation functions, 30652b356d20, Peter Eisentraut)
[pending] knowledge/files/src/bin/pg_dump/pg_backup_db.c.md  reason=anchor-bump 2026-07-02:b542d5566705..6b41bd1a459c (Fix mismatched deallocation functions, 30652b356d20, Peter Eisentraut)
[pending] knowledge/files/src/bin/pg_dump/pg_backup_directory.c.md  reason=anchor-bump 2026-07-02:b542d5566705..6b41bd1a459c (Fix mismatched deallocation functions, 30652b356d20, Peter Eisentraut)
[pending] knowledge/files/src/bin/pg_dump/pg_backup_tar.c.md  reason=anchor-bump 2026-07-02:b542d5566705..6b41bd1a459c (Fix mismatched deallocation functions, 30652b356d20, Peter Eisentraut)
[pending] knowledge/files/src/bin/pg_dump/pg_dump.c.md  reason=anchor-bump 2026-07-02:b542d5566705..6b41bd1a459c (Fix mismatched deallocation functions, 30652b356d20, Peter Eisentraut)
[pending] knowledge/files/src/bin/pg_dump/pg_dump_sort.c.md  reason=anchor-bump 2026-07-02:b542d5566705..6b41bd1a459c (Fix mismatched deallocation functions, 30652b356d20, Peter Eisentraut)
[pending] knowledge/files/src/bin/pg_dump/pg_dumpall.c.md  reason=anchor-bump 2026-07-02:b542d5566705..6b41bd1a459c (Fix mismatched deallocation functions, 30652b356d20, Peter Eisentraut)
[pending] knowledge/files/src/bin/pg_rewind/pg_rewind.c.md  reason=anchor-bump 2026-07-02:b542d5566705..6b41bd1a459c (Split dry-run messages into primary and detail, e3b5817c8b89, Peter Eisentraut)
[pending] knowledge/files/src/bin/pg_upgrade/function.c.md  reason=anchor-bump 2026-07-02:b542d5566705..6b41bd1a459c (Fix mismatched deallocation functions, 30652b356d20, Peter Eisentraut)
[pending] knowledge/files/src/bin/pg_verifybackup/pg_verifybackup.c.md  reason=anchor-bump 2026-07-02:b542d5566705..6b41bd1a459c (Fix mismatched deallocation functions, 30652b356d20, Peter Eisentraut)
[pending] knowledge/files/src/bin/pgbench/pgbench.c.md  reason=anchor-bump 2026-07-02:b542d5566705..6b41bd1a459c (Fix mismatched deallocation functions, 30652b356d20, Peter Eisentraut)
[pending] knowledge/files/src/bin/psql/command.c.md  reason=anchor-bump 2026-07-02:b542d5566705..6b41bd1a459c (Fix mismatched deallocation functions, 30652b356d20, Peter Eisentraut)
[pending] knowledge/files/src/bin/psql/common.c.md  reason=anchor-bump 2026-07-02:b542d5566705..6b41bd1a459c (Fix mismatched deallocation functions, 30652b356d20, Peter Eisentraut)
[pending] knowledge/files/src/bin/psql/describe.c.md  reason=anchor-bump 2026-07-02:b542d5566705..6b41bd1a459c (Fix mismatched deallocation functions, 30652b356d20, Peter Eisentraut)
[pending] knowledge/files/src/bin/psql/help.c.md  reason=anchor-bump 2026-07-02:b542d5566705..6b41bd1a459c (Fix mismatched deallocation functions, 30652b356d20, Peter Eisentraut)
[pending] knowledge/files/src/bin/psql/input.c.md  reason=anchor-bump 2026-07-02:b542d5566705..6b41bd1a459c (Fix mismatched deallocation functions, 30652b356d20, Peter Eisentraut)
[pending] knowledge/files/src/bin/psql/large_obj.c.md  reason=anchor-bump 2026-07-02:b542d5566705..6b41bd1a459c (Fix mismatched deallocation functions, 30652b356d20, Peter Eisentraut)
[pending] knowledge/files/src/bin/psql/mainloop.c.md  reason=anchor-bump 2026-07-02:b542d5566705..6b41bd1a459c (Fix mismatched deallocation functions, 30652b356d20, Peter Eisentraut)
[pending] knowledge/files/src/bin/psql/prompt.c.md  reason=anchor-bump 2026-07-02:b542d5566705..6b41bd1a459c (Fix mismatched deallocation functions, 30652b356d20, Peter Eisentraut)
[pending] knowledge/files/src/bin/psql/startup.c.md  reason=anchor-bump 2026-07-02:b542d5566705..6b41bd1a459c (Fix mismatched deallocation functions, 30652b356d20, Peter Eisentraut)
[pending] knowledge/files/src/bin/psql/stringutils.c.md  reason=anchor-bump 2026-07-02:b542d5566705..6b41bd1a459c (Fix mismatched deallocation functions, 30652b356d20, Peter Eisentraut)
[pending] knowledge/files/src/bin/psql/tab-complete.in.c.md  reason=anchor-bump 2026-07-02:b542d5566705..6b41bd1a459c (Fix mismatched deallocation functions, 30652b356d20, Peter Eisentraut; Allow logical replication conflicts to be logged to a table, a5918fddf10d, Amit Kapila)
[pending] knowledge/files/src/bin/scripts/vacuumdb.c.md  reason=anchor-bump 2026-07-02:b542d5566705..6b41bd1a459c (Split dry-run messages into primary and detail, e3b5817c8b89, Peter Eisentraut)
[pending] knowledge/files/src/common/logging.c.md  reason=anchor-bump 2026-07-02:b542d5566705..6b41bd1a459c (Fix mismatched deallocation functions, 30652b356d20, Peter Eisentraut)
[pending] knowledge/files/src/fe_utils/print.c.md  reason=anchor-bump 2026-07-02:b542d5566705..6b41bd1a459c (Fix mismatched deallocation functions, 30652b356d20, Peter Eisentraut)
[pending] knowledge/files/src/include/backup/basebackup_sink.h.md  reason=anchor-bump 2026-07-02:b542d5566705..6b41bd1a459c (Clear base backup progress on backup failure, 55f0a13e96be, Fujii Masao)
[pending] knowledge/files/src/include/catalog/catalog.h.md  reason=anchor-bump 2026-07-02:b542d5566705..6b41bd1a459c (Allow logical replication conflicts to be logged to a table, a5918fddf10d, Amit Kapila)
[pending] knowledge/files/src/include/nodes/parsenodes.h.md  reason=anchor-bump 2026-07-02:b542d5566705..6b41bd1a459c (Improve the names generated for indexes on expressions, 181b6185c79e, Tom Lane)
[pending] knowledge/files/src/include/parser/parse_target.h.md  reason=anchor-bump 2026-07-02:b542d5566705..6b41bd1a459c (Improve the names generated for indexes on expressions, 181b6185c79e, Tom Lane)
[pending] knowledge/files/src/include/replication/conflict.h.md  reason=anchor-bump 2026-07-02:b542d5566705..6b41bd1a459c (Allow logical replication conflicts to be logged to a table, a5918fddf10d, Amit Kapila)
[pending] knowledge/files/src/interfaces/ecpg/test/pg_regress_ecpg.c.md  reason=anchor-bump 2026-07-02:b542d5566705..6b41bd1a459c (Fix mismatched deallocation functions, 30652b356d20, Peter Eisentraut)
[pending] knowledge/files/src/port/pg_crc32c_armv8.c.md  reason=anchor-bump 2026-07-02:b542d5566705..6b41bd1a459c (Use C11 alignas instead of pg_attribute_aligned, 8061bfd15abe, Peter Eisentraut)
[pending] knowledge/files/src/test/isolation/isolation_main.c.md  reason=anchor-bump 2026-07-02:b542d5566705..6b41bd1a459c (Fix mismatched deallocation functions, 30652b356d20, Peter Eisentraut)
[pending] knowledge/files/src/test/isolation/isolationtester.c.md  reason=anchor-bump 2026-07-02:b542d5566705..6b41bd1a459c (Fix mismatched deallocation functions, 30652b356d20, Peter Eisentraut)
[pending] knowledge/files/src/test/modules/libpq_pipeline/libpq_pipeline.c.md  reason=anchor-bump 2026-07-02:b542d5566705..6b41bd1a459c (Fix mismatched deallocation functions, 30652b356d20, Peter Eisentraut)
[pending] knowledge/files/src/test/regress/pg_regress_main.c.md  reason=anchor-bump 2026-07-02:b542d5566705..6b41bd1a459c (Fix mismatched deallocation functions, 30652b356d20, Peter Eisentraut)
[pending] knowledge/files/src/timezone/localtime.c.md  reason=anchor-bump 2026-07-02:b542d5566705..6b41bd1a459c (Sync our copy of the timezone library with IANA release tzcode2026b, aeb07c55fab5, Tom Lane)
[pending] knowledge/files/src/timezone/pgtz.c.md  reason=anchor-bump 2026-07-02:b542d5566705..6b41bd1a459c (Sync our copy of the timezone library with IANA release tzcode2026b, aeb07c55fab5, Tom Lane)
[pending] knowledge/files/src/timezone/pgtz.h.md  reason=anchor-bump 2026-07-02:b542d5566705..6b41bd1a459c (Sync our copy of the timezone library with IANA release tzcode2026b, aeb07c55fab5, Tom Lane)
[pending] knowledge/files/src/timezone/private.h.md  reason=anchor-bump 2026-07-02:b542d5566705..6b41bd1a459c (Sync our copy of the timezone library with IANA release tzcode2026b, aeb07c55fab5, Tom Lane; Fix macro-redefinition warning introduced by aeb07c55f, 85656c1bef4a, Tom Lane)
[pending] knowledge/files/src/timezone/strftime.c.md  reason=anchor-bump 2026-07-02:b542d5566705..6b41bd1a459c (Sync our copy of the timezone library with IANA release tzcode2026b, aeb07c55fab5, Tom Lane)
[pending] knowledge/files/src/timezone/tzfile.h.md  reason=anchor-bump 2026-07-02:b542d5566705..6b41bd1a459c (Sync our copy of the timezone library with IANA release tzcode2026b, aeb07c55fab5, Tom Lane)
[pending] knowledge/files/src/timezone/zic.c.md  reason=anchor-bump 2026-07-02:b542d5566705..6b41bd1a459c (Sync our copy of the timezone library with IANA release tzcode2026b, aeb07c55fab5, Tom Lane)

[pending] knowledge/files/contrib/pg_plan_advice/pgpa_scan.c.md  reason=anchor-bump 2026-07-03:6b41bd1a459c..a5422fe3bd7e (pg_plan_advice: Don't generate FOREIGN_JOIN advice for a single relation, 53e6f51eef55, Robert Haas)
[pending] knowledge/files/src/backend/access/nbtree/nbtcompare.c.md  reason=anchor-bump 2026-07-03:6b41bd1a459c..a5422fe3bd7e (Use ssup_datum_*_cmp in more places, 51cd5d6f0523, John Naylor)
[pending] knowledge/files/src/backend/access/transam/multixact.c.md  reason=anchor-bump 2026-07-03:6b41bd1a459c..a5422fe3bd7e (Remove replication slot advice from MultiXact wraparound hints, 084734ff5a42, Fujii Masao)
[pending] knowledge/files/src/backend/commands/vacuum.c.md  reason=anchor-bump 2026-07-03:6b41bd1a459c..a5422fe3bd7e (Remove replication slot advice from MultiXact wraparound hints, 084734ff5a42, Fujii Masao)
[pending] knowledge/files/src/backend/tcop/postgres.c.md  reason=anchor-bump 2026-07-03:6b41bd1a459c..a5422fe3bd7e (Add log_statement_max_length GUC to limit logged statement text, c8bd8387c27a, Fujii Masao)
[pending] knowledge/files/src/backend/utils/adt/pgstatfuncs.c.md  reason=anchor-bump 2026-07-03:6b41bd1a459c..a5422fe3bd7e (Fix loss of precision in pg_stat_us_to_ms(), 3eca140531f1, John Naylor; Fix typo in pg_stat_us_to_ms(), 71fa15af591a, Michael Paquier)
[pending] knowledge/files/src/backend/utils/misc/guc_tables.c.md  reason=anchor-bump 2026-07-03:6b41bd1a459c..a5422fe3bd7e (Add log_statement_max_length GUC to limit logged statement text, c8bd8387c27a, Fujii Masao)
[pending] knowledge/files/src/bin/pg_upgrade/controldata.c.md  reason=anchor-bump 2026-07-03:6b41bd1a459c..a5422fe3bd7e (Remove pg_upgrade support for upgrading from pre-v10 servers, 14d841808307, Nathan Bossart)
[pending] knowledge/files/src/bin/pg_upgrade/exec.c.md  reason=anchor-bump 2026-07-03:6b41bd1a459c..a5422fe3bd7e (Remove pg_upgrade support for upgrading from pre-v10 servers, 14d841808307, Nathan Bossart)
[pending] knowledge/files/src/bin/pg_upgrade/file.c.md  reason=anchor-bump 2026-07-03:6b41bd1a459c..a5422fe3bd7e (Remove pg_upgrade support for upgrading from pre-v10 servers, 14d841808307, Nathan Bossart)
[pending] knowledge/files/src/bin/pg_upgrade/multixact_rewrite.c.md  reason=anchor-bump 2026-07-03:6b41bd1a459c..a5422fe3bd7e (Remove pg_upgrade support for upgrading from pre-v10 servers, 14d841808307, Nathan Bossart)
[pending] knowledge/files/src/bin/pg_upgrade/pg_upgrade.c.md  reason=anchor-bump 2026-07-03:6b41bd1a459c..a5422fe3bd7e (Remove pg_upgrade support for upgrading from pre-v10 servers, 14d841808307, Nathan Bossart)
[pending] knowledge/files/src/bin/pg_upgrade/pg_upgrade.h.md  reason=anchor-bump 2026-07-03:6b41bd1a459c..a5422fe3bd7e (Remove pg_upgrade support for upgrading from pre-v10 servers, 14d841808307, Nathan Bossart)
[pending] knowledge/files/src/bin/pg_upgrade/relfilenumber.c.md  reason=anchor-bump 2026-07-03:6b41bd1a459c..a5422fe3bd7e (Remove pg_upgrade support for upgrading from pre-v10 servers, 14d841808307, Nathan Bossart)
[pending] knowledge/files/src/bin/pg_upgrade/server.c.md  reason=anchor-bump 2026-07-03:6b41bd1a459c..a5422fe3bd7e (Remove pg_upgrade support for upgrading from pre-v10 servers, 14d841808307, Nathan Bossart)
[pending] knowledge/files/src/bin/pg_upgrade/version.c.md  reason=anchor-bump 2026-07-03:6b41bd1a459c..a5422fe3bd7e (Remove pg_upgrade support for upgrading from pre-v10 servers, 14d841808307, Nathan Bossart)
[pending] knowledge/files/src/include/storage/buf_internals.h.md  reason=anchor-bump 2026-07-03:6b41bd1a459c..a5422fe3bd7e (Switch Get[Local]BufferDescriptor() to use a signed value in input, ba4134075a82, Michael Paquier)
[pending] knowledge/files/src/include/utils/guc.h.md  reason=anchor-bump 2026-07-03:6b41bd1a459c..a5422fe3bd7e (Add log_statement_max_length GUC to limit logged statement text, c8bd8387c27a, Fujii Masao)
[pending] knowledge/files/src/test/modules/test_custom_stats/test_custom_fixed_stats.c.md  reason=anchor-bump 2026-07-03:6b41bd1a459c..a5422fe3bd7e (test_custom_stats: Fail if loading module outside shared_preload_libraries, 5045d9ff3b5a, Michael Paquier)

## anchor-bump 2026-07-04: a5422fe3bd7e..e0ff7fd9aa2e (17 commits, pg-anchor-refresh)

[pending] knowledge/files/contrib/btree_gist/btree_bit.c.md  reason=anchor-bump 2026-07-04:a5422fe3bd7e..e0ff7fd9aa2e (Remove btree_gist's useless logic for encoding-aware truncation, b82d69abf64f, Tom Lane)
[pending] knowledge/files/contrib/btree_gist/btree_bool.c.md  reason=anchor-bump 2026-07-04:a5422fe3bd7e..e0ff7fd9aa2e (Sync signatures of gbt_var_consistent() and gbt_num_consistent(), 4b808ed77cd9, Tom Lane)
[pending] knowledge/files/contrib/btree_gist/btree_bytea.c.md  reason=anchor-bump 2026-07-04:a5422fe3bd7e..e0ff7fd9aa2e (Remove btree_gist's useless logic for encoding-aware truncation, b82d69abf64f, Tom Lane)
[pending] knowledge/files/contrib/btree_gist/btree_cash.c.md  reason=anchor-bump 2026-07-04:a5422fe3bd7e..e0ff7fd9aa2e (Sync signatures of gbt_var_consistent() and gbt_num_consistent(), 4b808ed77cd9, Tom Lane)
[pending] knowledge/files/contrib/btree_gist/btree_date.c.md  reason=anchor-bump 2026-07-04:a5422fe3bd7e..e0ff7fd9aa2e (Sync signatures of gbt_var_consistent() and gbt_num_consistent(), 4b808ed77cd9, Tom Lane)
[pending] knowledge/files/contrib/btree_gist/btree_enum.c.md  reason=anchor-bump 2026-07-04:a5422fe3bd7e..e0ff7fd9aa2e (Sync signatures of gbt_var_consistent() and gbt_num_consistent(), 4b808ed77cd9, Tom Lane)
[pending] knowledge/files/contrib/btree_gist/btree_inet.c.md  reason=anchor-bump 2026-07-04:a5422fe3bd7e..e0ff7fd9aa2e (Sync signatures of gbt_var_consistent() and gbt_num_consistent(), 4b808ed77cd9, Tom Lane)
[pending] knowledge/files/contrib/btree_gist/btree_int2.c.md  reason=anchor-bump 2026-07-04:a5422fe3bd7e..e0ff7fd9aa2e (Sync signatures of gbt_var_consistent() and gbt_num_consistent(), 4b808ed77cd9, Tom Lane)
[pending] knowledge/files/contrib/btree_gist/btree_int4.c.md  reason=anchor-bump 2026-07-04:a5422fe3bd7e..e0ff7fd9aa2e (Sync signatures of gbt_var_consistent() and gbt_num_consistent(), 4b808ed77cd9, Tom Lane)
[pending] knowledge/files/contrib/btree_gist/btree_int8.c.md  reason=anchor-bump 2026-07-04:a5422fe3bd7e..e0ff7fd9aa2e (Sync signatures of gbt_var_consistent() and gbt_num_consistent(), 4b808ed77cd9, Tom Lane)
[pending] knowledge/files/contrib/btree_gist/btree_interval.c.md  reason=anchor-bump 2026-07-04:a5422fe3bd7e..e0ff7fd9aa2e (Sync signatures of gbt_var_consistent() and gbt_num_consistent(), 4b808ed77cd9, Tom Lane)
[pending] knowledge/files/contrib/btree_gist/btree_macaddr.c.md  reason=anchor-bump 2026-07-04:a5422fe3bd7e..e0ff7fd9aa2e (Sync signatures of gbt_var_consistent() and gbt_num_consistent(), 4b808ed77cd9, Tom Lane)
[pending] knowledge/files/contrib/btree_gist/btree_macaddr8.c.md  reason=anchor-bump 2026-07-04:a5422fe3bd7e..e0ff7fd9aa2e (Sync signatures of gbt_var_consistent() and gbt_num_consistent(), 4b808ed77cd9, Tom Lane)
[pending] knowledge/files/contrib/btree_gist/btree_numeric.c.md  reason=anchor-bump 2026-07-04:a5422fe3bd7e..e0ff7fd9aa2e (Remove btree_gist's useless logic for encoding-aware truncation, b82d69abf64f, Tom Lane)
[pending] knowledge/files/contrib/btree_gist/btree_oid.c.md  reason=anchor-bump 2026-07-04:a5422fe3bd7e..e0ff7fd9aa2e (Sync signatures of gbt_var_consistent() and gbt_num_consistent(), 4b808ed77cd9, Tom Lane)
[pending] knowledge/files/contrib/btree_gist/btree_text.c.md  reason=anchor-bump 2026-07-04:a5422fe3bd7e..e0ff7fd9aa2e (Remove btree_gist's useless logic for encoding-aware truncation, b82d69abf64f, Tom Lane)
[pending] knowledge/files/contrib/btree_gist/btree_time.c.md  reason=anchor-bump 2026-07-04:a5422fe3bd7e..e0ff7fd9aa2e (Sync signatures of gbt_var_consistent() and gbt_num_consistent(), 4b808ed77cd9, Tom Lane)
[pending] knowledge/files/contrib/btree_gist/btree_ts.c.md  reason=anchor-bump 2026-07-04:a5422fe3bd7e..e0ff7fd9aa2e (Sync signatures of gbt_var_consistent() and gbt_num_consistent(), 4b808ed77cd9, Tom Lane)
[pending] knowledge/files/contrib/btree_gist/btree_utils_num.c.md  reason=anchor-bump 2026-07-04:a5422fe3bd7e..e0ff7fd9aa2e (Tighten up btree_gist's handling of truncated bounds, fea9c1884b20, Tom Lane)
[pending] knowledge/files/contrib/btree_gist/btree_utils_var.c.md  reason=anchor-bump 2026-07-04:a5422fe3bd7e..e0ff7fd9aa2e (Remove btree_gist's useless logic for encoding-aware truncation, b82d69abf64f, Tom Lane)
[pending] knowledge/files/contrib/btree_gist/btree_utils_var.h.md  reason=anchor-bump 2026-07-04:a5422fe3bd7e..e0ff7fd9aa2e (Remove btree_gist's useless logic for encoding-aware truncation, b82d69abf64f, Tom Lane)
[pending] knowledge/files/contrib/btree_gist/btree_uuid.c.md  reason=anchor-bump 2026-07-04:a5422fe3bd7e..e0ff7fd9aa2e (Sync signatures of gbt_var_consistent() and gbt_num_consistent(), 4b808ed77cd9, Tom Lane)
[pending] knowledge/files/src/backend/commands/propgraphcmds.c.md  reason=anchor-bump 2026-07-04:a5422fe3bd7e..e0ff7fd9aa2e (Fix handling of dropping a property not associated with the given label, 96418a6da9d0, Peter Eisentraut)
[pending] knowledge/files/src/backend/parser/parse_clause.c.md  reason=anchor-bump 2026-07-04:a5422fe3bd7e..e0ff7fd9aa2e (Resolve unknown-type literals in GRAPH_TABLE COLUMNS, efd7d8d7d495, Peter Eisentraut)
[pending] knowledge/files/src/backend/storage/buffer/bufmgr.c.md  reason=anchor-bump 2026-07-04:a5422fe3bd7e..e0ff7fd9aa2e (Prevent access to other sessions' empty temp tables, c40819ebf954, Alexander Korotkov) — prior [done:fb47271] row (06-30 anchor-bump, 8d85cb889a39 LockBufferForCleanup race) audited 2026-07-02; re-touched here
[pending] knowledge/files/src/bin/psql/tab-complete.in.c.md  reason=anchor-bump 2026-07-04:a5422fe3bd7e..e0ff7fd9aa2e (psql: Fix \df tab completion for procedures, 6d4ca6de9777, Fujii Masao) — prior [in-progress:cloud/pg-quality-auditor/2026-06-29] row (06-25 anchor-bump) still open; re-touched here
[pending] knowledge/files/src/interfaces/libpq/fe-trace.c.md  reason=anchor-bump 2026-07-04:a5422fe3bd7e..e0ff7fd9aa2e (Fix tracing of BackendKeyData and CancelRequest, b22b619056e8, Heikki Linnakangas)
[pending] knowledge/subsystems/contrib-btree_gist.md  reason=anchor-bump 2026-07-04:a5422fe3bd7e..e0ff7fd9aa2e (25 impacted btree_gist files — encoding-aware-truncation removal b82d69abf64f + truncated-bounds tightening fea9c1884b20 + signature sync 4b808ed77cd9 + NotEqual internal-page crash fix eef644e57c38, Tom Lane); >=5-impacted-file subsystem threshold

## audit-clean/drift rotation (2026-07-05, pg-quality-auditor) — AUDIT mode, 8 long-form docs re-verified @a5422fe3bd7e (4 clean, 4 drift-fixed)

[pending] knowledge/idioms/parser-pipeline.md verified=2026-07-05 [clean: 10 cites hold @a5422fe3bd7e — parser.c:35-42/scan.l:13-22/gram.y:13629-13631+13649-13706/analyze.c:127+334-433+8-14+74/parse_node.c:38-50; tightened parsenodes.h Query typedef 117→120]
[pending] knowledge/idioms/node-types-and-lists.md verified=2026-07-05 [clean: 19 cites exact — nodes.h/pg_list.h/value.h/gen_node_support.pl/nodes-README all hold]
[pending] knowledge/data-structures/snapshot-lifecycle.md verified=2026-07-05 [clean: 9 cites hold — snapmgr.c 785-787/898-902/937-955/499/554-577/1862-1868 + heapam_visibility.c 13-35 all exact]
[pending] knowledge/architecture/access-methods.md verified=2026-07-05 [clean: no file:line cites (bare filenames + symbol/commit refs only) — vacuously clean]
[pending] knowledge/architecture/overview.md verified=2026-07-05 [drift-fixed: postgres.c dispatch switch 4838+→4933 (switch(firstchar)); postinit.c InitPostgres 716→722, ClientAuthentication call 262→268; nav path optimizer/planner.c→optimizer/plan/planner.c]
[pending] knowledge/architecture/planner.md verified=2026-07-05 [drift-fixed: analyzejoins.c reduce_unique_semijoins 874-895→961-974 + comment 862-873→961-972, remove_useless_self_joins 2539-2553→2603-2639 (~+90/+100 shift); planner.c/pathnode.c/costsize.c/setrefs.c/allpaths.c cites all hold]
[pending] knowledge/architecture/executor.md verified=2026-07-05 [drift-fixed: execGrouping.c §7b additionalsize mechanism refactored — pad-bytes-after-TupleHashEntryData (502 / (char*)entry+MAXALIGN) → co-located-with-MinimalTuple via ExecCopySlotMinimalTupleExtra:585-586 + TupleHashEntryGetAdditional (executor.h:193); 58/59 other cites exact incl. 2026-06-13 nodeModifyTable §8a]
[pending] knowledge/architecture/process-model.md verified=2026-07-05 [drift-fixed: procsignal_sigusr1_handler misattributed to tcop/postgres.c → defined procsignal.c:696, registered postgres.c:4427; 27/28 other cites hold @a5422fe3bd7e]
