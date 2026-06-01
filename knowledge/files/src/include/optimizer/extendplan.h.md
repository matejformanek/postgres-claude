# extendplan.h

- **Source:** 72 lines · **Last verified commit:** `ef6a95c7c64`

`GetPlannerExtensionId(name)` + the three setters/getters for
PlannerGlobal / PlannerInfo / RelOptInfo extension state, used by GEQO
and by external planner extensions to cache per-rel data.
