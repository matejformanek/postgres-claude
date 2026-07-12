# Queue: pg-quality-auditor — skill-regression side

Format: `[status] <skill-slug> last_passrate=<pct|never>`
Refill rule: list `.claude/skills/*/SKILL.md`; entries whose
last-rerun date in this file is > 30 days old go back to `[pending]`.

## Entries

[done:2026-07-09] locking last_passrate=100% reran=2026-07-09 [4/4 cites re-verified @4c75cc786301: lockdefs.h:33-48 8 lockmodes, port/atomics.h:25-26 use-higher-level, buf_internals.h:33-86 64-bit state bit-layout, port/atomics.h:107-112 u64 spinlock fallback — all hold]
[done:2026-07-12] memory-contexts last_passrate=100% reran=2026-07-12 [cites re-verified @54cd6fc83176: memutils.h:40-49 — MaxAllocSize ((Size)0x3fffffff) + MaxAllocHugeSize (SIZE_MAX/2) both hold at cited lines]
[pending] memory-keeping last_passrate=100% [refill 2026-07-12: reran 2026-06-09 > 30d stale; zero source-cites — future SKILL run reconfirms structure/format by construction]
[done:2026-07-09] parser-and-nodes last_passrate=100% reran=2026-07-09 [cites re-verified @4c75cc786301: nodes.h:228 copyObject/typeof_unqual, copyfuncs.c:177/:185 copyObjectImpl+check_stack_depth, nodeFuncs.h:22-34 QTW_* + :155 expression_tree_walker macro, nodes.h:43/:124 pg_node_attr, analyze.c transformStmt@335/stmt_requires_parse_analysis@470/analyze_requires_snapshot@514 — all within ±1 line]
[pending] patch-submission last_passrate=100% [refill 2026-07-12: reran 2026-06-09 > 30d stale; zero source-cites — future SKILL run reconfirms structure/format by construction]
[pending] pg-claude last_passrate=100% [refill 2026-07-12: reran 2026-06-09 > 30d stale; zero source-cites — future SKILL run reconfirms structure/format by construction]
[done:2026-07-09] replication-overview last_passrate=100% reran=2026-07-09 [cites re-verified @4c75cc786301: guc_tables.c:525 wal_level_options exact, effective_wal_level 649→650 off-by-1 (tolerated); slot.h:43 ReplicationSlotPersistency + :58 ReplicationSlotInvalidationCause; output_plugin.h:36 LogicalOutputPluginInit. NOTE: guc_tables.c refactored to 811 lines — GUC arrays moved to guc_tables.inc.c include; both cited symbols still resolve. Prior 96.3% eval-fail unrelated to cites]
[pending] review-checklist last_passrate=100% [refill 2026-07-12: reran 2026-06-09 > 30d stale; zero source-cites — future SKILL run reconfirms structure/format by construction]
[pending] testing last_passrate=100% [refill 2026-07-12: reran 2026-06-09 > 30d stale; zero source-cites — future SKILL run reconfirms structure/format by construction]
[done:2026-07-09] wal-and-xlog last_passrate=100% reran=2026-07-09 [11/11 cites re-verified @4c75cc786301: rmgr.c:97/:107 RegisterCustomRmgr, rmgr.h:35 RM_MIN_CUSTOM_ID=128, xlog_internal.h:351 RmgrData, xloginsert.h:28/:31 XLR_NORMAL_MAX_BLOCK_ID+flags, xlogutils.h:74 BLK_NEEDS_REDO, generic_xlog.h:23 MAX_GENERIC_XLOG_PAGES, twophase.c:12-19 NOTES, decode.c:116 rm_decode — all hold]
[done:2026-07-03] access-method-apis last_passrate=100% reran=2026-07-03 [cites re-verified @b542d5566705: tableamapi.c 37 Assert(routine->), amapi.h callbacks, vacuum.h VACUUM_OPTION_NO_PARALLEL=0, genam.c:58-59 "kinda ugly"]
[pending] build-and-run last_passrate=100% [refill 2026-07-12: reran 2026-06-06 > 30d stale; zero source-cites — future SKILL run reconfirms structure/format by construction]
[done:2026-07-12] catalog-conventions last_passrate=100% reran=2026-07-12 [cite re-verified @54cd6fc83176: transam.h:160-197 OID-assignment comment block (1-9999 manual / 8000-9999 dev / 10000-11999 genbki / 12000-16383 initdb / 16384+ normal) + FirstGenbkiObjectId=10000 / FirstUnpinnedObjectId=12000 / FirstNormalObjectId=16384 defines — holds]
[done:2026-07-12] coding-style last_passrate=100% reran=2026-07-12 [cite re-verified @54cd6fc83176: elog.h:179 = `extern int errcode_for_file_access(void);` — holds exactly]
[pending] commit-message-style last_passrate=100% [refill 2026-07-12: reran 2026-06-06 > 30d stale; zero source-cites — future SKILL run reconfirms structure/format by construction]
[done:2026-07-12] debugging last_passrate=100% reran=2026-07-12 [3/3 cites re-verified @54cd6fc83176: elog.h:53 `#define ERROR 21`; xlog.c:7707/7724 deliberate `pg_usleep(10000L)` delay-loops (line-exact — but eval prose labels these "WAL recovery" retry loops; they're actually CreateCheckPoint DELAY_CHKPT_START/COMPLETE loops = eval-answer imprecision, not SKILL.md drift); 007_pre_auth.pl:38 injection_points 'wait' waitpoint — all hold]
[done:2026-07-12] error-handling last_passrate=100% reran=2026-07-12 [4/4 cites re-verified @54cd6fc83176: elog.c:154 `#define ERRORDATA_STACK_SIZE 5`; ipc.h:47 `PG_ENSURE_ERROR_CLEANUP` macro; fd.h:177 `extern int OpenTransientFile(...)`; fd.h:36 transient-fd/AllocateDir comment region (ResourceOwner-cleanup semantics) — all hold]
[done:2026-07-09] executor-and-planner last_passrate=92% reran=2026-07-09 [DRIFT FIXED: grouping_planner cited planner.c:1775 now at 1704 (−71, from qual-pushdown refactor 44fb59fc) — corrected in ascii tree + Where-to-look range. Other cites hold @4c75cc786301 within ±5: planner@328/standard_planner@346/subquery_planner@770, set_rel_pathlist@520, standard_join_search@3952, add_path@459/create_seqscan_path@1026, create_plan@339, ExecutorStart@124, ExprContext@281, RelOptInfo@1009]
[done:2026-07-09] extension-development last_passrate=100% reran=2026-07-09 [3/3 cites re-verified @4c75cc786301: extension.c:77 Extension_control_path GUC, fmgr.h:430 _PG_init decl, guc.h:358-421 DefineCustomBoolVariable@359..MarkGUCPrefixReserved@419 — all hold]
[done:2026-07-09] fmgr-and-spi last_passrate=100% reran=2026-07-09 [31 cites re-verified @4c75cc786301: spi.c SPI_connect_ext@101/SPI_finish@182/AtEOSubXact_SPI@482/SPI_prepare@861/SPI_keepplan@977/SPI_copytuple@1048/SPI_cursor_open@1446/SPI_result_code_string@1973; fmgr.c DirectFunctionCall1Coll@794/OidFunctionCall0Coll@1403/InputFunctionCall@1531; funcapi.c@100/112; 11 fmgr.h + 4 funcapi.h + spi.h:82 headers — all hold]
[retired:2026-07-12] gucs-bgworker-parallel [LEGACY split into gucs-config + bgworker-and-extensions + parallel-query, all three tracked separately above; row retired per its own 2026-06-06 note]

## Refill 2026-07-06 (pg-quality-auditor SKILL mode)

10 skills had a SKILL.md + iter-1/iter-2 eval suite but were never in
this queue (the `gucs-bgworker-parallel` split created 3 of them; the
2-iteration campaign never back-filled the process/planner skills). Added
below. SKILL-mode reverification @anchor e0ff7fd9aa2e: cite-heavy skills
had every source cite re-fetched and confirmed; process skills carry zero
source cites (their evals assert format/structure) so cite-reverification
is N/A and their FINAL.md iter-2 pass-rate is preserved by construction.

[done:2026-07-06] gucs-config last_passrate=100% reran=2026-07-06 [5/5 cites re-verified @e0ff7fd9aa2e: guc.h GucContext enum :71-80, flag bits GUC_LIST_INPUT… :214-242, DefineCustomBoolVariable :359, MarkGUCPrefixReserved :421 (header) + guc.c :5185 (body)]
[done:2026-07-06] bgworker-and-extensions last_passrate=100% reran=2026-07-06 [7/7 cites re-verified @e0ff7fd9aa2e: bgworker.h restart-code comment :14-27, BGWORKER_* flags :50-75, BgWorkerStartTime enum :84-89; dfmgr.c _PG_init dlsym :297; planner.h planner_hook :28; postgres.c die :3023; interrupt.c SignalHandlerForConfigReload :60-65]
[done:2026-07-06] parallel-query last_passrate=100% reran=2026-07-06 [cites re-verified @e0ff7fd9aa2e: parallel.h ParallelContext :33; parallel.c PARALLEL_KEY_* :67-81, PARALLEL_KEY_GUC :70, lock-group-leader :594, BecomeLockGroupMember/deadlock :1401; pg_proc.h proparallel :79; lock.c LockCheckConflicts :1591; condition_variable.h :32; execParallel.c keys :60]
[done:2026-07-06] pg-feature-plan last_passrate=100% reran=2026-07-06 [SKILL cites hold @e0ff7fd9aa2e: lockfuncs.c advisory-lock section :605, catversion.h bump-rule :26-29 + CATALOG_VERSION_NO :60, lock.h GetLockStatusData :422, kwlist.h ASCII-order note :24. NOTE: eval answers.md:205 places MERGE/METHOD neighborhood "around kwlist.h:27" but merge/method are at 283-285 (line 27 = "abort") — worked-example imprecision in the eval, not SKILL.md content; never accurate, not anchor drift; semantic claim "between MERGE and METHOD" holds]
[done:2026-07-06] psql last_passrate=100% reran=2026-07-06 [live SKILL.md accurate @e0ff7fd9aa2e: :101-102 column set {name,ident,type,level,path,total_bytes,total_nblocks,free_bytes,free_chunks,used_bytes} matches pg_get_backend_memory_contexts proargnames pg_proc.dat:8728 exactly. NOTE: eval answers.md cite pg_proc.dat:8713 is stale (SRF relocated to 8728, ~+15 lines) — eval-artifact drift, not SKILL.md regression]
[done:2026-07-06] pg-patch-review last_passrate=100% reran=2026-07-06 [zero source cites; evals assert review-process/format; cite-reverification N/A; FINAL.md iter-2 32/32 preserved]
[done:2026-07-06] pg-feature-brainstorm last_passrate=100% reran=2026-07-06 [zero source cites; evals assert brainstorm structure/DECISION-question shape; cite-reverification N/A; FINAL.md iter-2 preserved]
[done:2026-07-06] pg-implement last_passrate=100% reran=2026-07-06 [zero source cites; evals assert R1-R15 discipline/phase-commit shape; cite-reverification N/A; FINAL.md iter-2 31/31 preserved]
[done:2026-07-06] pg-shadow-implement last_passrate=100% reran=2026-07-06 [zero source cites; evals assert shadow-diff/parity process; cite-reverification N/A; FINAL.md iter-2 32/32 preserved]
[done:2026-07-06] meta-commit-style last_passrate=100% reran=2026-07-06 [zero source cites; evals assert commit-format/trailer rules; cite-reverification N/A; FINAL.md iter-2 31/31 preserved]
