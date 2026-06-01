# execMain.c

- **Source:** `source/src/backend/executor/execMain.c` (3268 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** deep-read (top-level executor lifecycle + EvalPlanQual)

## Purpose

The top-level executor interface. Owns the four-call lifecycle
`ExecutorStart / ExecutorRun / ExecutorFinish / ExecutorEnd` that every
PG query plan executor invocation goes through, plus the EvalPlanQual
machinery for READ COMMITTED row recheck. [from-comment] `:1-37`

The file header lays out the contract verbatim: `ExecutorStart` must be
called once, `ExecutorRun` may be called multiple times (or never, for
EXPLAIN), `ExecutorFinish` runs AFTER triggers and must precede
`ExecutorEnd` (except in EXPLAIN-only mode), `ExecutorEnd` tears down.
[from-comment] `:6-28`

## Plugin hooks `:69-76`

Each of the four entry points checks a global hook pointer and falls
back to the `standard_*` implementation. Plugins (`auto_explain`,
`pg_stat_statements`, …) install themselves here. There is also
`ExecutorCheckPerms_hook` used by `ExecCheckPermissions`.

## Entry points

| Function | File:line | Role |
|---|---|---|
| `ExecutorStart` | `:124` | Hook dispatcher → `standard_ExecutorStart` |
| `standard_ExecutorStart` | `:143` | Set up EState + per-query memory context, call `InitPlan` |
| `ExecutorRun` | `:308` | Hook dispatcher → `standard_ExecutorRun` |
| `standard_ExecutorRun` | `:318` | rStartup the dest, call `ExecutePlan`, rShutdown |
| `ExecutorFinish` | `:417` | Hook dispatcher |
| `standard_ExecutorFinish` | `:426` | `ExecPostprocessPlan` + `AfterTriggerEndQuery` |
| `ExecutorEnd` | `:477` | Hook dispatcher |
| `standard_ExecutorEnd` | `:486` | `ExecEndPlan` + `UnregisterSnapshot` + `FreeExecutorState` |
| `ExecutorRewind` | `:547` | `ExecReScan` from the top (SELECT only) |
| `InitPlan` | `:847` | Set up range table, row marks, initPlans/subPlans, then `ExecInitNode` on root |
| `ExecPostprocessPlan` | `:1519` | Drain `es_auxmodifytables` so secondary ModifyTable nodes complete |
| `ExecEndPlan` | `:1565` | `ExecEndNode(root)` + `ExecEndNode` over `es_subplanstates` + close rels |
| `ExecutePlan` | `:1685` | The `for(;;)` loop that pulls tuples from the root planstate |
| `EvalPlanQual` | `:2678` | Public EPQ recheck entry — re-run quals against an updated row version |
| `EvalPlanQualInit` | `:2747` | Init EPQState at plan-state node creation |
| `EvalPlanQualBegin` | `:2960` | Lazy materialization of the EPQ recheck plan tree |
| `EvalPlanQualNext` | `:2944` | Run one EPQ ExecProcNode |
| `EvalPlanQualStart` | `:3027` | Build the parallel EPQ EState + planstate tree |
| `EvalPlanQualEnd` | `:3208` | Tear down EPQ recheck state |

## InitPlan walkthrough `:847`

Order of operations is load-bearing — the file is the canonical
reference for "what happens before tuples flow":

1. `ExecCheckPermissions(rangeTable, permInfos)` — ACL pass on all RTEs. `:862`
2. `ExecInitRangeTable` — install RT into EState, allocate parallel
   `es_relations / es_rowmarks / es_result_relations` arrays. `:867`
3. `ExecDoInitialPruning` — run-time partition pruning for `Append /
   MergeAppend` so unused child subplans are never inited. `:882`
4. Build `ExecRowMark[]` for FOR UPDATE/SHARE/KEY SHARE/REFERENCE/COPY
   marks; `ROW_MARK_COPY` is the only one that doesn't open a relation. `:887-960`
5. `subplans` loop: for every PlannedStmt-level subplan (these are the
   shared CTEs, init/sub plans hoisted to the top), call `ExecInitNode`
   in a fresh `es_subplan_index`-th slot. `:991`
6. `ExecInitNode(plan, estate, eflags)` on the root — recurses through
   the whole plan tree. `:1002`
7. Build the JunkFilter for SELECT if any TLIST entry has `resjunk`. `:1013-1042`

The result tuple descriptor is then stored on the QueryDesc.

## InitPlan / ExecEndPlan and the subplan list

`PlannedStmt.subplans` (planner output) is the flat array of all
SubPlan trees referenced by `$n` Param expressions; `InitPlan` iterates
it into `estate->es_subplanstates`. Per-PlanState `initPlan` lists are
handled in `execProcnode.c`'s `ExecInitNode`, not here — see that file's
doc. `ExecEndPlan :1565` symmetrically calls `ExecEndNode` on root +
every entry of `es_subplanstates`.

## ExecutePlan loop `:1685`

The hot loop is small and shape-stable: `ResetPerTupleExprContext` →
`ExecProcNode(planstate)` → optional `ExecFilterJunk` → `dest->receiveSlot`
→ count + check `numberTuples` limit + loop. `:1728-1787`

After the loop, if `!(es_top_eflags & EXEC_FLAG_BACKWARD)`, calls
`ExecShutdownNode` to release resources eagerly (parallel workers,
foreign scan handles, hash table memory). `:1793`

Parallel mode is entered/exited around the loop, but is suppressed if
`already_executed || numberTuples != 0` (i.e. partial execution forces
serial). `:1715-1723`, `:1796`

## EvalPlanQual entry `:2678`

The READ COMMITTED row-recheck protocol. When a `table_tuple_update /
delete / lock` returns `TM_Updated`, the caller (typically
`ExecUpdate`/`ExecDelete` in nodeModifyTable, or `ExecLockRows`) must:

1. Lock the latest row version (typically with
   `TUPLE_LOCK_FLAG_FIND_LAST_VERSION`).
2. Pass the locked slot into `EvalPlanQual(epqstate, rel, rti, slot)`.
3. EvalPlanQual runs a *parallel* mini-plan (built by
   `EvalPlanQualStart` `:3027`) that re-tests the row against the
   query's quals using the new version, and returns the slot if it
   still qualifies, else NULL (skip).

Key detail: each EPQState has `relsubs_done[]` / `relsubs_blocked[]`
parallel to the range table — only the rti being rechecked has a tuple
available; all other result relations are marked `blocked` so they
return EOS. `:2700-2728`

EPQ state is lazy: `EvalPlanQualInit` is cheap, the mini-EState +
planstate tree are only built on first `EvalPlanQualBegin`. See the
executor README EvalPlanQual section for the conceptual model — this
file is the runtime mechanism.

## Invariants

- `EState->es_snapshot` must be the `ActiveSnapshot` before
  `standard_ExecutorStart` / `Run` — checked by Asserts at `:153, 336`. [verified-by-code]
- Parallel mode requires complete execution: any `numberTuples != 0`
  or repeat `ExecutorRun` call forces serial. `:1715` [verified-by-code]
- `ExecutorFinish` must have run before `ExecutorEnd`, except in
  EXPLAIN-only mode. Assert at `:507`. [verified-by-code]
- `ExecEndPlan` only closes relations + drops pins — it does NOT free
  per-node memory. That comes from `FreeExecutorState` which destroys
  the per-query memory context. [from-comment] `:1556-1561`
- Read-only / parallel-mode write check at `ExecCheckXactReadOnly` runs
  in `standard_ExecutorStart` before InitPlan. [verified-by-code]

## Cross-refs

- `knowledge/architecture/executor.md` — high-level model that frames
  this file's role.
- `knowledge/files/src/backend/executor/execProcnode.c.md` — the dispatch
  layer that `InitPlan` / `ExecEndPlan` recurse through.
- `knowledge/files/src/backend/executor/nodeModifyTable.c.md` — the
  primary caller of `EvalPlanQual`.
- `knowledge/idioms/memory-contexts.md` — `estate->es_query_cxt` is the
  per-query AllocSet rooted at the caller's CurrentMemoryContext.
- `source/src/backend/executor/README` — EvalPlanQual conceptual model.

## Tags

- [verified-by-code] every entry point + line citation above.
- [from-comment] the four-call lifecycle contract and EPQ behavior
  narratives, both quoted from the top-of-file and the function-prologue
  comments.
- [from-README] the conceptual framing for EvalPlanQual.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/executor.md](../../../../subsystems/executor.md)
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
