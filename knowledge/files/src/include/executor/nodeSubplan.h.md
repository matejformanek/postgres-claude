# nodeSubplan.h

- **Source:** `source/src/include/executor/nodeSubplan.h` (~35 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## API

- `ExecInitSubPlan(SubPlan*, parent)` — init.
- `ExecSubPlan(SubPlanState*, econtext, &isNull)` — evaluate an
  expression-tree SubPlan reference.
- `ExecSetParamPlan(SubPlanState*, econtext)` — run an InitPlan once,
  stash outputs in PARAM_EXEC slots.
- `ExecSetParamPlanMulti(const Bitmapset*, econtext)` — run multiple
  InitPlans in batch (used at ExecutorRun start to evaluate all
  plan-startup InitPlans before plan execution begins).
- `ExecReScanSetParamPlan(node, parent)` — rerun an InitPlan when its
  driving outer params change.
- `EstimateSubplanHashTableSpace(nentries, tupleWidth, unknownEqFalse)` —
  for the planner to estimate ANY/ALL hash-subplan memory.

## Tags

- [verified-by-code] full surface.
