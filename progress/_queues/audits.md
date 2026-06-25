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

[pending] knowledge/idioms/parser-pipeline.md verified=2026-06-12
[pending] knowledge/idioms/node-types-and-lists.md verified=2026-06-12
[pending] knowledge/architecture/planner.md verified=2026-06-13
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
[in-progress:cloud/pg-quality-auditor/2026-06-25] knowledge/files/src/backend/utils/adt/xml.c.md  reason=anchor-bump 2026-06-14:e18b0cb7344..da1eff08a5be re-pinned=f0a4f280b4d3 [drift-fixed: xpath ~4400→4572, XmlTable* ~4750→4933/4978, loc 5167→5169]
[done:d3dfc9b] knowledge/files/src/backend/utils/cache/inval.c.md  reason=anchor-bump 2026-06-14:e18b0cb7344..da1eff08a5be verified=2026-06-16
[in-progress:cloud/pg-quality-auditor/2026-06-25] knowledge/files/src/backend/utils/init/postinit.c.md  reason=anchor-bump 2026-06-14:e18b0cb7344..da1eff08a5be re-pinned=f0a4f280b4d3 [drift-fixed: all InitPostgres-pipeline + public-surface cites shifted +6/+7, loc 1553→1567]
[in-progress:cloud/pg-quality-auditor/2026-06-25] knowledge/files/src/bin/psql/describe.c.md  reason=anchor-bump 2026-06-14:e18b0cb7344..da1eff08a5be re-pinned=f0a4f280b4d3 [clean: file unchanged, exact cites hold; tightened 2 "area" cites to 6823/7089]
[in-progress:cloud/pg-quality-auditor/2026-06-25] knowledge/files/src/include/miscadmin.h.md  reason=anchor-bump 2026-06-14:e18b0cb7344..da1eff08a5be re-pinned=f0a4f280b4d3 [clean: all major cites hold ±2, loc ~553→555]
[in-progress:cloud/pg-quality-auditor/2026-06-25] knowledge/files/src/include/parser/parse_relation.h.md  reason=anchor-bump 2026-06-14:e18b0cb7344..da1eff08a5be re-pinned=f0a4f280b4d3 [clean: all category fn prototypes present, loc ~140→141]
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
[in-progress:cloud/pg-quality-auditor/2026-06-25] knowledge/files/src/include/nodes/nodes.h.md  reason=anchor-bump 2026-06-16:b78cd2bda5b1..e5f94c4808fe (query jumble comment fixes, e5f94c4808fe) re-pinned=f0a4f280b4d3 [clean: enum/macro cites hold ±2, loc 446→444]
[in-progress:cloud/pg-quality-auditor/2026-06-25] knowledge/files/src/include/nodes/parsenodes.h.md  reason=anchor-bump 2026-06-16:b78cd2bda5b1..e5f94c4808fe (query jumble comment fixes, e5f94c4808fe) re-pinned=f0a4f280b4d3 [clean: struct cites hold ±3, loc ~5000→4599]
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
