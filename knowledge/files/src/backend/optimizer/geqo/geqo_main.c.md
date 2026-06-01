# geqo_main.c — Genetic Query Optimization driver

- **Source:** `source/src/backend/optimizer/geqo/geqo_main.c` (367 lines)
- **Header:** `source/src/include/optimizer/geqo.h`
- **Last verified commit:** `ef6a95c7c64`

## 1. Purpose

Top-level driver of the Genetic Algorithm (GA) join-order search, used by
`allpaths.c:standard_join_search` when the number of base relations exceeds
`geqo_threshold` (default 12). The join-order problem is treated as a
constrained Traveling Salesman Problem (TSP). [from-comment, geqo_main.c:70-72]

## 2. Entry point

`RelOptInfo *geqo(PlannerInfo *root, int number_of_rels, List *initial_rels)`
at `geqo_main.c:74`. [verified-by-code]

## 3. Algorithm shape

1. `geqo_set_seed` — seed PRNG from `Geqo_seed` GUC.
2. `gimme_pool_size`, `gimme_number_generations` — derive GA params from
   `Geqo_effort` (1..10).
3. `alloc_pool` + `random_init_pool` + `sort_pool` — fitness = cheapest
   `total_cost` of resulting RelOptInfo, computed by `geqo_eval()` from
   `geqo_eval.c`.
4. Main loop (lines ~189-…): per generation pick `momma`/`daddy` via
   `linear_rand` (geqo_selection.c), apply the recombination operator
   (default ERX, compile-time selectable: PMX/CX/PX/OX1/OX2), insert into
   pool via `spread_chromo`. [verified-by-code]
5. Return best `RelOptInfo` from the cheapest tour. [verified-by-code]

## 4. Important detail

`root->assumeReplanning = true` is set at line 112 — tells the core planner
that intermediate Path lists may be discarded between candidate join orders.
[verified-by-code]

GEQO is registered as an "in-core planner extension" via
`Geqo_planner_extension_id = GetPlannerExtensionId("geqo")` (line 104-105);
per-call state lives in `GeqoPrivateData` attached to PlannerInfo. [verified-by-code]

## 5. GUCs

`geqo`, `geqo_threshold`, `geqo_effort`, `geqo_pool_size`,
`geqo_generations`, `geqo_selection_bias`, `geqo_seed`. [verified-by-code, lines 45-49]

## 6. Tags
`[verified-by-code]` ×6, `[from-comment]` ×1
