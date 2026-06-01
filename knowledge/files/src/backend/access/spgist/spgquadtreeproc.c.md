# spgquadtreeproc.c

- **Source path:** `source/src/backend/access/spgist/spgquadtreeproc.c` (473 lines)
- **Last verified commit:** `ef6a95c7c64`

## Purpose

Built-in **quadtree** opclass over `point`: `quad_point_ops`. Each inner tuple's prefix is a centroid; children are the 4 quadrants relative to it (4 nodes always, no AddNode needed). [from-comment, spgquadtreeproc.c:1-13]

## Procs

- `spg_quad_config` — prefix = point, label = void, nNodes=4.
- `spg_quad_choose` — descend into the quadrant containing the point.
- `spg_quad_picksplit` — pick centroid (median of x and y), allocate 4 children.
- `spg_quad_inner_consistent` — prune quadrants outside the query.
- `spg_quad_leaf_consistent` — point comparison.

Tags: [from-comment].

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
