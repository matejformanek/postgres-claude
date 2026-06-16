# pathnode.h — pathnode.c + relnode.c prototypes

- **Source:** 390 lines · **Last verified commit:** `ef6a95c7c64`

Every `create_*_path` constructor (one per Path subtype) plus the core
machinery: `add_path`, `add_path_precheck`, `add_partial_path`,
`set_cheapest`, `compare_path_costs`, `get_baserel_parampathinfo`,
`get_joinrel_parampathinfo`. Also the relnode.c API:
`setup_simple_rel_arrays`, `build_simple_rel`, `find_base_rel`,
`build_join_rel`, `min_join_parameterization`.

Hook: `build_simple_rel_hook` for plugins to intervene during baserel
construction. [verified-by-code:20-26]

## Appears in scenarios

<!-- scenarios:auto:begin -->

- [Scenario — Add a new plan node](../../../../scenarios/add-new-plan-node.md)

<!-- scenarios:auto:end -->
