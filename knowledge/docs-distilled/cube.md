---
source_url: https://www.postgresql.org/docs/current/cube.html
fetched_at: 2026-07-14T20:52:00Z
anchor_sha: 1863452a4bfe
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
section: "F.11 cube — multidimensional cube data type"
maps_to_skill: [access-method-apis, type-cache]
---

# Docs distilled — cube (N-dimensional cube type + KNN-GiST opclass)

A multidimensional interval/box type. The canonical **KNN-GiST** worked
example: its `gist_cube_ops` opclass supports *ordering* by a metric operator
in `ORDER BY`, not just boolean `WHERE` predicates — the feature that makes
`ORDER BY … <-> point LIMIT k` an index scan.

## Non-obvious claims

- **Dimension limit is a hard compile-time 100:** `#define CUBE_MAX_DIM (100)`
  [[cubedata.h:6]]. [verified-by-code @ 1863452a4bfe]
- **On-disk `NDBOX` packs dimensionality + an is-point flag into one `header`
  word.** Struct: `{ int32 vl_len_; unsigned int header; double
  x[FLEXIBLE_ARRAY_MEMBER] }` [[cubedata.h:8]]. Bits 0–7 = dim count, bit 31 =
  point flag: `POINT_BIT 0x80000000`, `DIM_MASK 0x7fffffff`,
  `IS_POINT(cube)`/`DIM(cube)` macros [[cubedata.h:31]].
  [verified-by-code @ 1863452a4bfe]
- **Space-saving point encoding:** when the lower-left and upper-right corners
  coincide, `cube` stores **only one corner** plus the is-point flag (the flag
  is exactly `POINT_BIT` above), halving the `double` array. [from-docs] +
  [verified-by-code @ 1863452a4bfe]
- **Coordinates are always normalized to "lower-left → upper-right".** The cube
  functions **auto-swap** endpoints so the internal box is canonical; you
  cannot store an inverted box. [from-docs]
- **Coordinates are 64-bit `double`** → values beyond ~16 significant digits
  truncate. [from-docs] (matches the `double x[]` array above.)
- **`gist_cube_ops` supports three distinct index roles:**
  1. **Boolean `WHERE`**: `=`, `&&` (overlap), `@>` (contains), `<@`
     (contained-by).
  2. **KNN `ORDER BY`** by a *metric*: `<->` (Euclidean/L2), `<#>` (taxicab/L1),
     `<=>` (Chebyshev/L∞) — nearest-neighbour returned in index order.
  3. **KNN `ORDER BY` by a coordinate**: `~> k` extracts the k-th bound
     (`n=2k-1` → lower bound of dim k, `n=2k` → upper bound), so
     `ORDER BY c ~> 1 LIMIT 5` returns the 5 rows with smallest first-dim
     lower bound via the index. [from-docs]
- **Mixed-dimensionality operands**: the lower-dimensional cube is treated as a
  Cartesian projection with **implicit zeros** in the missing coordinates.
  [from-docs]
- **Key functions**: `cube_dim`, `cube_ll_coord`/`cube_ur_coord`,
  `cube_is_point`, `cube_distance`, `cube_subset` (project/reorder dims),
  `cube_union`/`cube_inter`, `cube_enlarge(cube, r, n)` (grow/shrink by radius).
  [from-docs]

## Links into corpus

- `access-method-apis` skill — `gist_cube_ops` is the reference for the
  **`distance` GiST support function (KNN)** and the `ORDER BY` index path;
  contrast `[[docs-distilled/seg.md]]` (R-tree-over-GiST, boolean only) and
  `[[docs-distilled/hstore.md]]` (signature, boolean only).
- `[[docs-distilled/gist.md]]` — the GiST support-function set (`consistent`,
  `penalty`, `picksplit`, `distance`) `gist_cube_ops` implements.
- `earthdistance` contrib builds directly on `cube` (point-on-sphere → 3-D
  cube); note that link when documenting geospatial contribs.
