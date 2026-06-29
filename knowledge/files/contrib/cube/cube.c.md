# contrib/cube/cube.c

Source pin: `4b0bf0788b066a4ca1d4f959566678e44ec93422`.

## Role

Implements the `cube` data type — a variable-length N-dimensional
axis-aligned box of `double` coordinates, plus btree/R-tree/GiST
opclass support and KNN distance operators. The "cube" can also be a
"point" (lower-left == upper-right; only one set of coords stored;
indicated by a header bit). [verified-by-code]
`source/contrib/cube/cube.c:120-244` (input), `:394-660` (GiST),
`:1262-1404` (distance), `:1652-1708` (cube_coord_llur).

## Public API (SQL-callable)

- I/O: `cube_in`, `cube_out`, `cube_send`, `cube_recv`,
  `cube_a_f8_f8`, `cube_a_f8`, `cube_f8`, `cube_f8_f8`, `cube_c_f8`,
  `cube_c_f8_f8`, `cube_subset` — `:121,296,334,356,143,210,1777,
  1795,1829,1876,247`.
- Btree: `cube_eq/ne/lt/gt/le/ge/cmp` — `:1039,1054,1069,1084,1099,
  1114,1024`.
- R-tree: `cube_contains/contained/overlap/union/inter/size` —
  `:1169,1185,1240,813,828,904`.
- GiST: `g_cube_consistent/compress/decompress/penalty/picksplit/
  union/same/distance` — `:395,462,468,491,516,430,666,1407`.
- Misc: `distance_taxicab/chebyshev`, `cube_distance`,
  `cube_is_point`, `cube_enlarge`, `cube_dim`, `cube_ll_coord`,
  `cube_ur_coord`, `cube_coord`, `cube_coord_llur` —
  `:1311,1355,1262,1528,1712,1563,1574,1591,1612,1653`.

## Invariants

- `CUBE_MAX_DIM = 100` (`cubedata.h:7`). Checked at every constructor
  path: `cube_a_f8_f8` (`:161`), `cube_a_f8` (`:225`), `cube_subset`
  (`:265`), `cube_recv` (`:366`), `cube_c_f8` (`:1837`),
  `cube_c_f8_f8` (`:1885`), `cube_enlarge` clamps `n` to MAX_DIM
  (`:1723`). Parser checks in 4 productions in `cubeparse.y:61,91,
  110,129`. [verified-by-code]
- `NDBOX` header: bits 0-7 = dim (max 100), bit 31 = point flag, bits
  8-30 must be 0 (`cubedata.h:14-27`). Not validated in `cube_recv`
  beyond stripping `POINT_BIT` and `DIM_MASK`. [ISSUE: see Phase-D]
- Point representation: `IS_POINT(cube)` → upper-right coords aren't
  stored, `UR_COORD` returns `LL_COORD`. Stored size is `POINT_SIZE`
  vs `CUBE_SIZE` (half). [verified-by-code]
- Comparison normalizes per-axis with `Min(LL, UR)` / `Max(LL, UR)`
  so `((2,1),(1,2))` and `((1,1),(2,2))` compare equal — see comments
  at `:1629-1651`. [verified-by-code, from-comment]

## Notable internals

- `cube_recv` (`:356-381`) allocates exactly `offsetof + sizeof(double)
  * nitems` bytes after rejecting `nitems > CUBE_MAX_DIM`. With
  `POINT_BIT` clear, `nitems` is doubled (`:373`). The CUBE_MAX_DIM
  check is **before** the doubling, so at most 200 doubles allocated
  — fine. [verified-by-code]
- `g_cube_picksplit` (`:516-660`) uses Guttman's quadratic split:
  O(N²) seed selection by maximum-wasted-space, then O(N) assignment.
  This is the classic R-tree split and can blow up: for N=300 entries
  per page that's 45 000 union+intersection computations. Each
  involves `cube_union_v0` which palloc's a fresh CUBE_SIZE — so
  ~45 000 palloc's of ~1.6 KB each on a single page split.
  [verified-by-code, observation]
- `cube_union_v0` (`:752-810`) palloc's the union and never frees
  intermediate unions during the GiST union fold (`g_cube_union`
  `:430-454`). For an N-entry vector, that's N palloc's during a
  single union — typical R-tree memory cost. [verified-by-code]
- `cube_subset` (`:247-293`) validates each `dx[i]` is `1..DIM(c)`
  (`:282-285`). Negative or zero index → `ERRCODE_ARRAY_ELEMENT_ERROR`.
  [verified-by-code]
- `cube_coord` (`:1612`) validates `coord` in `[1, 2*DIM(cube)]`
  (`:1617`). For points it returns `cube->x[(coord-1) % DIM]` (`:1623`)
  — so `coord = DIM+1` on a point reads `x[0]`, deliberately mirroring
  point semantics. [verified-by-code]
- `cube_coord_llur` and `g_cube_distance` both raise on `coord == 0`
  (`:1661, :1425`). Negative coords are inverted (`:1666-1670, :1431-
  1434`), so `INT32_MIN` would overflow on `coord = -coord`. [ISSUE]
- KNN strategy decode in `g_cube_distance` (`:1407-1509`) — falls
  through to `elog(ERROR, "unrecognized cube strategy")` for
  unknowns. [verified-by-code]

## Trust-boundary / Phase-D surface

- **CUBE_MAX_DIM = 100 cap is well-enforced.** All entry points
  check, including `cube_recv` (`:366`). The parser checks before
  building the in-memory cube. [verified-by-code]
- **cube_in via flex/bison** — `cubescan.l` accepts floats, `infinity`,
  `NaN`. The scan buffer is allocated by `yy_scan_bytes(str, slen)`
  (`cubescan.l:112`), so input length is bounded by what reaches
  `cube_in`. The `list` production (`cubeparse.y:154-166`) builds a
  comma-joined string via `strcat` into a buffer of size
  `scanbuflen + 1` — so total accumulated dim values are bounded by
  the input length. Pre-dim-cap an attacker could send a 100-MB
  string with one float per byte; `palloc(scanbuflen+1)` would
  succeed up to `MaxAllocSize` (1 GB). The CUBE_MAX_DIM check then
  rejects, but the allocation already happened. [ISSUE-DoS]
- **NaN coordinates** — `float8in_internal` accepts NaN. `cube_cmp_v0`
  uses `<` / `>` on doubles; NaN propagates unordered semantics →
  same hazard as `seg`. `cube_contains_v0` uses `>` and `<` on
  Min/Max; NaN compares false-on-both, so a NaN coord makes
  `cube_contains_v0` return true on bogus inputs. [ISSUE-correctness]
- **Infinity coordinates** — `rt_cube_size` multiplies axis widths
  (`:933`); `Inf * 0 = NaN`, propagating into `g_cube_penalty` which
  picks splits by penalty. NaN penalty → unpredictable split choices.
  [ISSUE-correctness]
- **g_cube_picksplit O(N²)** — under adversarial workloads with very
  many overlapping cubes per page, split is expensive. R-tree wisdom,
  not a fresh bug. [ISSUE-DoS-low]
- **`-coord` overflow on INT32_MIN** — `g_cube_distance:1431-1434`
  and `cube_coord_llur:1666-1671` do `coord = -coord`. If `coord ==
  INT32_MIN` that's undefined behavior in C / wraps to itself.
  Triggered by user passing `cube ~> -2147483648`. [ISSUE-UB-low]
- **`cube_recv` doesn't validate unused header bits (8-30)** — the
  comment in `cubedata.h:20` says "unused, initialize to zero". On
  `cube_recv` (`:376`) the header is stored verbatim without masking
  off unused bits. Doesn't immediately corrupt anything, but breaks
  the invariant declared in the header struct and might confuse a
  future version that uses those bits. [ISSUE-robustness]
- **`cube_inter` may return a "non-null intersection for
  non-overlapping boxes"** — explicit FIXME in comment at `:897-898`.
  Not a security issue, but reflects fuzziness in semantics that
  matters for index correctness. [from-comment]

## Cross-refs

- `source/contrib/cube/cubedata.h` — struct + macros.
- `source/contrib/cube/cubeparse.y`, `cubescan.l` — input parser.
- `source/contrib/earthdistance/earthdistance.c` — earthdistance v1.1
  wraps cube to provide spherical distance with GiST.
- A13 `btree_gist` float — same NaN comparison hazard.
- A7 `jsonapi` — comparable recursive-parser DoS family.

<!-- issues:auto:begin -->
- [Issue register — `cube`](../../../issues/cube.md)
<!-- issues:auto:end -->

## Issues

- `[ISSUE-correctness: NaN coordinates make cube_cmp_v0 / cube_contains_v0
  / cube_overlap_v0 return semantically-bogus results — duplicates can
  defeat EXCLUDE USING gist (val WITH =)] (medium)` —
  `source/contrib/cube/cube.c:944-1021,1131-1166,1201-1236`
- `[ISSUE-correctness: Infinity coords produce Inf*0=NaN in
  rt_cube_size; g_cube_penalty selects splits by NaN penalty → poor
  GiST tree shape] (medium)` — `source/contrib/cube/cube.c:914-937,
  491-507`
- `[ISSUE-DoS: cube_in / cubeparse list-builder allocates scanbuflen+1
  bytes BEFORE the CUBE_MAX_DIM check; ~MaxAllocSize text input gets
  fully palloc'd before rejection] (medium)` —
  `source/contrib/cube/cubeparse.y:154-166`, scan size unbounded at
  `cubescan.l:17` (`YY_READ_BUF_SIZE 16777216`)
- `[ISSUE-UB-low: g_cube_distance + cube_coord_llur do `coord = -coord`
  without guarding against INT32_MIN] (low)` —
  `source/contrib/cube/cube.c:1431-1434, 1666-1671`
- `[ISSUE-robustness: cube_recv accepts header with bits 8-30 set
  (cubedata.h says "unused, initialize to zero")] (low)` —
  `source/contrib/cube/cube.c:374-378`
- `[ISSUE-robustness: g_cube_picksplit is Guttman O(N²) — DoS surface
  on pathological GiST page splits with many cubes] (low)` —
  `source/contrib/cube/cube.c:516-660`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/contrib-cube.md](../../../subsystems/contrib-cube.md)
