# `src/include/lib/knapsack.h`

- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
- **Lines:** 16

## Role

Discrete-knapsack dynamic-programming solver. Sole core consumer:
the GROUPING SETS planner alongside `bipartite_match.h` — picks
which rollup chains to materialize given a `work_mem`-shaped
budget. [from-comment]
`source/src/include/lib/knapsack.h:13-14`

## Public API

- `DiscreteKnapsack(int max_weight, int num_items, int *item_weights, double *item_values)` → `Bitmapset *`

Result is the indices of chosen items, as a Bitmapset.

## Invariants

- O(num_items * max_weight) memory and time. Caller is the planner,
  which clamps both.

## Trust boundary (Phase D)

None — internal planner DP.

## Cross-refs

- `knowledge/files/src/include/lib/bipartite_match.h.md` — sister
  combinatorial primitive in grouping-set planning

## Issues

None.
