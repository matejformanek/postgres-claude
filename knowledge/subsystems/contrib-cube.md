# contrib-cube (multidimensional cubes)

- **Source path:** `source/contrib/cube/`
- **Last verified commit:** `e18b0cb7344` (2026-06-13 anchor)
- **Extension version:** `1.5` (per `cube.control`)
- **Trusted:** yes (`trusted = true`)

## 1. Purpose

Data type representing **N-dimensional cubes** — a
generalization of intervals to many dimensions. A cube is two
points in N-space (the "lower-left" and "upper-right" corners
of an axis-aligned box). Operators support overlap,
containment, distance, and GiST indexing for spatial-style
queries on arbitrary-dimensional data.

Use cases:
- Scientific data with multiple measurement axes
  (temperature × pressure × pH).
- Multi-attribute range queries
  (price ∈ [10, 50] × time ∈ [0, 100]).
- Approximate nearest-neighbor via GiST.

For 2D geographic data, **PostGIS** is the proper choice. cube
is for non-geographic N-dimensional ranges.

## 2. The single 1920-LOC file

```
source/contrib/cube/cube.c    1920 LOC
```

[verified-by-code `wc -l`]

All in one file: parser, operators, GiST opclass, distance
functions. Notably the largest single-file contrib by far.

## 3. SQL surface — type construction

```sql
'(0, 0), (1, 1)'::cube                    -- 2D unit square
'(1, 2, 3), (4, 5, 6)'::cube              -- 3D box
cube_a_f8('{1, 2, 3}'::float8[])          -- 3D point from array
cube_a_f8_f8(lower_arr, upper_arr)        -- box from arrays
cube_c_f8(c, x)                           -- append dimension
cube_c_f8_f8(c, l, u)                     -- append dimension w/ range
```

[verified-by-code `cube.c:35-44`]

The text representation: `(lo1, lo2, ..., loN), (up1, up2, ...,
upN)`. For a "point" (zero-volume cube), the two corners
coincide; the text shortcut `(1, 2, 3)` parses as a point.

## 4. SQL surface — accessors

| Function | Returns |
|---|---|
| `cube_dim(cube)` | Dimensionality |
| `cube_ll_coord(cube, n)` | Lower-left N-th coord |
| `cube_ur_coord(cube, n)` | Upper-right N-th coord |
| `cube_subset(cube, int[])` | Project to subset of dimensions |
| `cube_enlarge(cube, r, n)` | Enlarge by r in n dims |
| `cube_distance(c1, c2)` | Euclidean distance between centers |

[verified-by-code `cube.c:44-46`]

## 5. SQL surface — operators

| Op | Meaning |
|---|---|
| `c1 @> c2` | c1 contains c2 |
| `c1 <@ c2` | c2 contains c1 |
| `c1 && c2` | overlap |
| `c1 = c2` | equal |
| `c1 <-> c2` | Euclidean distance (KNN-search-friendly) |
| `c1 <#> c2` | Chebyshev (max-coord) distance |
| `c1 <=> c2` | Taxicab (sum-coord) distance |

The 3 distance operators (`<->`, `<#>`, `<=>`) are designed
for use with `ORDER BY ... LIMIT N` queries — the GiST opclass
supports KNN-style search where the index drives ordering.

## 6. The GiST opclass

`gist_cube_ops` (default for GiST on cube):

- **Internal node**: a "bounding cube" containing all
  descendant cubes.
- **Leaf node**: the actual cube.
- **Picksplit**: at split time, decide which leaf goes left
  vs right — uses a "longest dimension" heuristic.
- **Penalty**: at insert, measure how much each candidate
  internal node would have to grow; pick the smallest.

For KNN search (`ORDER BY c <-> point LIMIT 10`), the opclass
provides a distance-to-cube-from-point function. GiST visits
internal nodes in distance order; the first 10 leaves found
are returned.

## 7. The dimensionality limit

`MAX_CUBE_DIM = 100`. Cubes can have up to 100 dimensions.
Operations on very-high-dim cubes are slow (linear in
dimension); 100 is a practical upper bound for index
performance.

## 8. Production-use guidance

- **For 2D/3D geographic data, use PostGIS.** Much richer
  type system + topology.
- **For sub-100-dim numeric ranges, cube is good.** Index
  scales well.
- **KNN search** (`ORDER BY <->`) is the showcase use case
  — sub-second query on 1M cubes with proper opclass.
- **Trusted extension** — `CREATE EXTENSION cube` doesn't
  require superuser.

## 9. Invariants

- **[INV-1]** Dimensionality limited to `MAX_CUBE_DIM = 100`.
- **[INV-2]** Lower-left coord ≤ upper-right coord per axis;
  normalized on input.
- **[INV-3]** A "point" is a cube where lower-left = upper-
  right; canonical normalized form.
- **[INV-4]** Three distance operators; pick by metric.
- **[INV-5]** Trusted extension (CREATE EXTENSION without
  superuser).

## 10. Useful greps

- The entry points:
  `grep -n 'PG_FUNCTION_INFO_V1' source/contrib/cube/cube.c | head -30`
- The GiST opclass functions:
  `grep -n 'g_cube_' source/contrib/cube/cube.c | head -10`
- The KNN distance operators:
  `grep -n 'cube_distance\|cube_coord_llur\|distance_*chebyshev' source/contrib/cube/cube.c | head -10`

## 11. Cross-references

- `knowledge/subsystems/contrib-seg.md` — companion 1D
  interval type; the 0D-vs-N-D split.
- `knowledge/subsystems/access-method-apis.md` — GiST AM
  contracts.
- `knowledge/subsystems/contrib-btree_gist.md` — sibling
  contrib for scalar types under GiST.
- `.claude/skills/access-method-apis.md` — index-AM
  contracts.
- `source/contrib/cube/cube.c` — implementation.
