# paths.h — optimizer/path/ prototypes

- **Source:** 289 lines · **Last verified commit:** `ef6a95c7c64`

Aggregates prototypes from allpaths.c, equivclass.c, pathkeys.c,
joinrels.c, joinpath.c, indxpath.c, tidpath.c, clausesel.c.

Notable GUC externs: `enable_geqo`, `enable_eager_aggregate`,
`geqo_threshold`, plus path-method enable flags. Also exposes
`add_paths_to_joinrel`, `make_join_rel`, `join_search_one_level`,
`generate_useful_gather_paths`, hook typedefs (`set_rel_pathlist_hook`,
`set_join_pathlist_hook`).

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
