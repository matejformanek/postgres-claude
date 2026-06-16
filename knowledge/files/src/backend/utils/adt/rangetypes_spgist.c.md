# `src/backend/utils/adt/rangetypes_spgist.c`

- **File:** `source/src/backend/utils/adt/rangetypes_spgist.c` (1000 lines)
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422` (2026-06-03)

## Purpose

The **SP-GiST opclass** for range types. Maps each range to a 2D point
`(lower_bound, upper_bound)` and builds a **quad tree** over those
points. Each inner node has a centroid that partitions its 2D region
into four quadrants; a fifth quadrant on the root holds empty ranges
which can't be 2D-mapped (`:14-22` [from-comment]).

This implementation only depends on the element type's `cmp` proc, so
it works for any range type without per-type configuration.

## Key concepts

- Inner nodes either (a) carry a centroid and have 4 children
  (quadrants) or (b) carry no centroid and have just 2 children (one
  for empty ranges, one for non-empty) — used at the root and
  empty-only branches. [from-comment]
- Picksplit uses **medians along each axis** as the centroid; this is
  computed in `spg_range_quad_picksplit`. [from-comment]

## Key functions

- `spg_range_quad_config(PG_FUNCTION_ARGS)` — declares the SP-GiST
  config: prefix type = void, label type = void (no labels), can-be-null
  flags.
- `spg_range_quad_choose(PG_FUNCTION_ARGS)` — picks the child to
  descend into during insert. Computes which quadrant the new range's
  2D point falls into vs the centroid; if no centroid (root in
  empty-segregating mode), routes by emptiness.
- `spg_range_quad_picksplit(PG_FUNCTION_ARGS)` — computes the centroid
  as the median over both axes; partitions input tuples into the four
  quadrants (or two when emptiness is the split criterion).
- `spg_range_quad_inner_consistent(PG_FUNCTION_ARGS)` — given a query
  range and strategy, prunes quadrants. For `<<` (strictly left),
  only the quadrants whose `upper < query.lower` need scanning, etc.
- `spg_range_quad_leaf_consistent(PG_FUNCTION_ARGS)` — final
  per-tuple test using the appropriate range operator.

## Phase D notes

- No I/O on this path that consumes attacker bytes; consumes
  canonicalized `RangeType` Datums from the heap. [inferred]
- The "no-centroid, two-child" inner node shape is the subtle
  representation invariant; misinterpretation would route inserts to
  the wrong subtree, but cannot corrupt heap pages. [from-comment]

## Potential issues

- [ISSUE-undocumented-invariant: the centroid-vs-no-centroid inner
  node shape is encoded implicitly via the prefix Datum; a future
  refactor risks confusing the two (low)]
- [ISSUE-correctness: median-based centroid can degenerate for
  heavily-skewed bound distributions (e.g. all ranges share lower
  bound), leading to deep trees; same risk as any quad-tree
  implementation (info)]

## Cross-references

- `source/src/include/access/spgist.h` — `spgConfigOut`,
  `spgChooseOut`, `spgPickSplitOut`, `spgInnerConsistentOut`,
  `spgLeafConsistentOut`.
- `source/src/backend/access/spgist/` — engine that calls these
  callbacks.
- `source/src/backend/utils/adt/rangetypes.c` — bound comparison and
  range operators consumed here.

<!-- issues:auto:begin -->
- [Issue register — `utils-adt`](../../../../../issues/utils-adt.md)
<!-- issues:auto:end -->

## Confidence tag tally
- `[from-comment]` × 4
- `[inferred]` × 1
- `[verified-by-code]` × 0 (callbacks read only at signature level)
