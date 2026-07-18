# planner.h — planner.c internals for other planner modules

- **Source:** 88 lines · **Last verified commit:** `ef6a95c7c64`

Top-comment note: the *primary* planner entries live in `optimizer.h`
because they're called from non-planner code. This header is the
internal-to-optimizer surface. [from-comment:5-9]

Exposes `subquery_planner`, `standard_planner`, `grouping_planner`
helpers, plus internal pieces of the upper-rel pipeline.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/contrib-pg_plan_advice.md](../../../../subsystems/contrib-pg_plan_advice.md)

- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)