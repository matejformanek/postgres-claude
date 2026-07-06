# Queue: pg-quality-auditor — skill-regression side

Format: `[status] <skill-slug> last_passrate=<pct|never>`
Refill rule: list `.claude/skills/*/SKILL.md`; entries whose
last-rerun date in this file is > 30 days old go back to `[pending]`.

## Entries

[done:2026-06-09] locking last_passrate=100% reran=2026-06-09
[done:2026-06-09] memory-contexts last_passrate=100% reran=2026-06-09
[done:2026-06-09] memory-keeping last_passrate=100% reran=2026-06-09
[done:2026-06-09] parser-and-nodes last_passrate=100% reran=2026-06-09
[done:2026-06-09] patch-submission last_passrate=100% reran=2026-06-09
[done:2026-06-09] pg-claude last_passrate=100% reran=2026-06-09
[done:2026-06-09] replication-overview last_passrate=96.3% reran=2026-06-09
[done:2026-06-09] review-checklist last_passrate=100% reran=2026-06-09
[done:2026-06-09] testing last_passrate=100% reran=2026-06-09
[done:2026-06-09] wal-and-xlog last_passrate=100% reran=2026-06-09
[done:2026-07-03] access-method-apis last_passrate=100% reran=2026-07-03 [cites re-verified @b542d5566705: tableamapi.c 37 Assert(routine->), amapi.h callbacks, vacuum.h VACUUM_OPTION_NO_PARALLEL=0, genam.c:58-59 "kinda ugly"]
[done:2026-06-06] build-and-run last_passrate=100% reran=2026-06-06
[done:2026-06-06] catalog-conventions last_passrate=100% reran=2026-06-06
[done:2026-06-06] coding-style last_passrate=100% reran=2026-06-06
[done:2026-06-06] commit-message-style last_passrate=100% reran=2026-06-06
[done:2026-06-06] debugging last_passrate=100% reran=2026-06-06
[done:2026-06-06] error-handling last_passrate=100% reran=2026-06-06
[done:2026-06-06] executor-and-planner last_passrate=100% reran=2026-06-06
[done:2026-06-06] extension-development last_passrate=100% reran=2026-06-06
[done:2026-06-06] fmgr-and-spi last_passrate=100% reran=2026-06-06
[done:2026-06-06] gucs-bgworker-parallel last_passrate=100% reran=2026-06-06 [LEGACY: this slug was split into gucs-config + bgworker-and-extensions + parallel-query; those three are now tracked as separate entries below. Retire this row on next full refill.]

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
