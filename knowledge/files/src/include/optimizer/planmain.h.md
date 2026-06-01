# planmain.h — optimizer/plan/ prototypes

- **Source:** 135 lines · **Last verified commit:** `ef6a95c7c64`

GUC externs `cursor_tuple_fraction` (default 0.1), `enable_self_join_elimination`.

Prototypes for query_planner (planmain.c), make_one_rel (allpaths.c),
remove_useless_joins / reduce_unique_semijoins /
remove_useless_self_joins / innerrel_is_unique (analyzejoins.c),
preprocess_minmax_aggregates (planagg.c), set_plan_references +
SS_make_initplan_from_plan + the dependency-tracking entries (setrefs.c).

Also the `query_pathkeys_callback` typedef used by query_planner.
