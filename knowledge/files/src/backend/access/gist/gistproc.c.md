# gistproc.c

- **Source path:** `source/src/backend/access/gist/gistproc.c` (1763 lines)
- **Last verified commit:** `ef6a95c7c64`

## Purpose

Built-in opclass support functions for **2-D geometry**: box, polygon, circle, point. Implements R-tree behavior using **Guttman's polynomial-time picksplit** algorithm. The largest in-tree opclass; mostly arithmetic. [from-comment, gistproc.c:1-16]

## What it implements

For each geometric type, the GiST opclass needs (procnums 1-9):
1. `consistent` — `key OP query` test at each node.
2. `union` — bounding box of N keys.
3. `compress` — leaf storage compression (e.g. polygon → bounding box).
4. `decompress` — inverse (often a no-op).
5. `penalty` — area enlargement metric for choosing subtree.
6. `picksplit` — Guttman's R-tree split into two halves.
7. `same` — bitwise-equal test.
8. `distance` — KNN distance from query (optional, makes opclass `amcanorderbyop`).
9. `fetch` — leaf-key reconstruction for index-only scans (optional).

For `box_ops`, `poly_ops`, `circle_ops`, `point_ops` — each gets its own `consistent`/`union`/`penalty`/`picksplit`/`same`/`distance`. Sortsupport (procnum 11) is provided for **point** to enable the sorted-build path. [verified-by-code, function list]

## Guttman picksplit (`gist_box_picksplit` ~line 800+)

1. Compute the bounding box.
2. Choose two seed entries that would produce the largest "waste" if combined.
3. Distribute remaining entries one by one to whichever side enlarges less.

Time: O(n²) in entries-per-page (n ≤ a few hundred). Quality: good enough for low-dim R-tree; less good for high-dim, hence the alternative "double sorting" split in `gist_box_double_sorting_split` (more recent addition).

Tags: [from-comment]; [verified-by-code for function-list mapping].

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
