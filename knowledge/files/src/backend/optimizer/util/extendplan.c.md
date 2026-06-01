# extendplan.c — planner extension state hooks

- **Source:** 177 lines · **Last verified commit:** `ef6a95c7c64`
- **Depth:** read

Loadable modules can attach private per-PlannerGlobal / PlannerInfo /
RelOptInfo state. Lets `set_join_pathlist_hook`-style extensions cache
per-joinrel intermediate results across calls. [from-comment:7-15]

- `GetPlannerExtensionId(name)` (40) — assign or look up a slot id.
- `SetPlannerGlobalExtensionState` / `SetPlannerInfoExtensionState` /
  `SetRelOptInfoExtensionState` — setters at lines 76, 112, 146.

Used by core: GEQO itself registers under the name `"geqo"`.
[verified-by-code, geqo_main.c:104-105]

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
