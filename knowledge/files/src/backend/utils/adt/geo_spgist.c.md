# geo_spgist.c — SP-GiST opclass for box and point

## Purpose

SP-GiST (Space-Partitioned GiST) opclasses for `box` and `point`. Uses a 4-d "quad-tree on box centers" split: each inner node has up to 4 (point) or 16 (box) children based on which quadrant the centroid lies in. The interesting half of the file is `spg_quad_inner_consistent` which prunes branches based on the search bounding box.

Source: `source/src/backend/utils/adt/geo_spgist.c` (885 lines).

## Key functions

- `spg_box_quad_config` (line 400) — declares prefix/label types and "longValuesOK = false". [verified-by-code]
- `spg_box_quad_choose` (line 416) — descends an inner node, picks child quadrant by box-center comparison. [verified-by-code]
- `spg_box_quad_picksplit` (line 440) — chooses the centroid of input boxes as the new inner-node center. [verified-by-code]
- `spg_box_quad_inner_consistent` (line 552) — the pruning core. Given a search box `q`, determines which of the 16 child quadrants can contain matches. Uses centroid-based bounding-box logic. [verified-by-code]
- `spg_box_quad_leaf_consistent` (line 740) — final check at leaf; applies the actual operator. [verified-by-code]
- `spg_point_quad_*` (lines 858, 875) — analogous for points; simpler since points have no extent. [verified-by-code]

## Phase D notes

- **Iterative tree walk** — no C-stack recursion; SP-GiST machinery in `src/backend/access/spgist/` drives the descent. No stack-depth concern here.
- **Centroid-as-prefix design**: the bounding-box pruning is sensitive to input distribution; pathological inputs (millions of identical centroids) degrade to a chain. Documented SP-GiST tradeoff. [from-README, src/backend/access/spgist/README]
- **`longValuesOK = false`**: a single leaf datum must fit in one page. Boxes always fit. Polygons don't have an SP-GiST opclass — that's GiST.

## Potential issues

- `[ISSUE-dos: pathologically clustered input boxes (all sharing the same centroid) degrade SP-GiST to a long chain; no explicit cap or balance recovery (low — same as any SP-GiST opclass)]`.
- `[ISSUE-correctness: inner_consistent prunes via centroid-vs-query-box comparisons using FPlt/FPgt epsilon math; for very large coordinates the same scale issue as geo_ops can produce false negatives (would need targeted audit) (maybe)]`.

Confidence: `[verified-by-code]` for function map.

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `utils-adt`](../../../../../issues/utils-adt.md)
<!-- issues:auto:end -->
