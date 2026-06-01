# clauses.h

- **Source:** 59 lines · **Last verified commit:** `ef6a95c7c64`

Subset of clauses.c's API exposed to other planner modules: contain_*
probes, eval_const_expressions, expression_planner, inline_function /
inline_set_returning_function, replace_outer_grouping etc. The full
public API for non-planner consumers is in `optimizer.h`.
