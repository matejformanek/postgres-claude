# contrib/bloom/blcost.c

**Pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
**LOC:** 45
**Verification depth:** full read

## Role

`blcostestimate` — the AM's cost-estimate callback. Bloom *always*
visits every index tuple (the AM is whole-index-scan), so cost
modeling is trivial: feed `numIndexTuples = index->tuples` and
`numNonLeafPages = 1` (only the metapage) to the generic estimator.
[verified-by-code] `source/contrib/bloom/blcost.c:1-44`

## Public API

- `blcostestimate(root, path, loop_count, &indexStartupCost,
  &indexTotalCost, &indexSelectivity, &indexCorrelation, &indexPages)`
  — wraps `genericcostestimate`.
  [verified-by-code] `source/contrib/bloom/blcost.c:21-44`

## Invariants

- INV-1: `numIndexTuples = index->tuples` — every tuple of the index
  is visited.
  [verified-by-code] `source/contrib/bloom/blcost.c:30-31`
- INV-2: `numNonLeafPages = 1` — only the metapage acts as "non-leaf".
  Mirrors `btcostestimate`'s treatment of the btree metapage.
  [verified-by-code] `source/contrib/bloom/blcost.c:33-34`

## Trust-boundary / Phase-D surface

- Planner-only path. No user-controllable side effects beyond plan
  shape changes. Mis-costing produces slow plans, not data leaks.
- The "always visit every tuple" assumption means bloom indexes are
  almost always cost-dominated by a seqscan on any but the largest
  relations — which is correct: bloom only wins when seqscan is more
  expensive than scanning the entire index + heap recheck for the
  hits.

## Cross-refs

- `source/src/backend/utils/adt/selfuncs.c` — `genericcostestimate`.
- `source/src/backend/access/nbtree/nbtutils.c` — `btcostestimate`
  parallel.

## Issues raised

None — minimal wrapper.
