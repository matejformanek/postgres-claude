# `src/backend/lib/knapsack.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~105
- **Source:** `source/src/backend/lib/knapsack.c`

A pseudo-polynomial 0/1 knapsack solver. Single entry point
`DiscreteKnapsack` returns a `Bitmapset` of the chosen item indices.
The implementation is the textbook DP that reuses the `values[]`
array by iterating weights from high to low; it's pseudo-polynomial
in the weight limit `O(nW)`. Used by the planner (extended-statistics
selection) — see `optimizer/path/statsmcv.c` callers.
[verified-by-code]

The interesting trick is `bms_replace_members(sets[j], sets[ow])` to
reuse already-allocated `Bitmapset` storage instead of `bms_copy`-ing
each iteration; the bitmapsets are pre-padded with an unused high bit
at index `num_items` so re-using a smaller set into a larger slot
never needs realloc, then that sentinel bit is `bms_del_member`'d off
before returning. [verified-by-code §knapsack.c:73, 100]

## API / entry points

- `Bitmapset *DiscreteKnapsack(int max_weight, int num_items, int *item_weights, double *item_values)`
  — weights must be `>= 0`, values may be NULL (treated as 1 each).
  Weight-0 items are always included (free items). [from-comment §knapsack.c:6-16]

## Notable invariants / details

- Allocates everything in a dedicated `AllocSetContext` named
  "Knapsack" sized `ALLOCSET_SMALL_SIZES`; deletes the context at
  end. Result `Bitmapset` is `bms_copy`'d back into the parent
  context first. [verified-by-code §knapsack.c:54-57, 102]
- `<=` (not `<`) is used to compare `values[j]` against
  `values[ow] + iv`; ties go to the new item. [verified-by-code §knapsack.c:85]

## Potential issues

- None.
