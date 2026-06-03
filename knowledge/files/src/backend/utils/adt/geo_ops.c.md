# geo_ops.c — geometric type I/O and operators

## Purpose

Implements `point`, `line`, `lseg`, `box`, `path`, `polygon`, `circle` types and the dozens of operators among them: distance, intersection, containment, overlap, area. Plus the `<->` distance operator powering kNN GiST/SP-GiST searches over geometry.

Source: `source/src/backend/utils/adt/geo_ops.c` (5713 lines).

## Indexed surface

- Type I/O (start of file, ~line 100-550):
  - `point_in`/`_out`/`_recv`/`_send`
  - `lseg_in`/`_out`
  - `line_in`/`_out` (line at xml.c:1131 — `isinf(m)` check on slope)
  - `box_in`/`_out`/`_recv`/`_send` — lines 423-555
  - `path_in`/`_out`
  - `poly_in`/`_out`
  - `circle_in`/`_out`
- Operators (lines 555-3000+):
  - Box: `box_overlap`, `box_left`, `box_right`, `box_below`, `box_above`, `box_contained`, `box_contain`, `box_distance`, `box_area`, `box_intersect`
  - Line: line/line `line_interpt`, `line_parallel`, `line_perp`
  - Distance: `dist_*` family — point-point, point-line, point-box, etc.
  - kNN: `dist_ppoly_internal` at line 2712
  - Polygon: `poly_overlap`, `poly_contain`, `points_box` at line 4310

## NaN / infinity discipline

The file is defensive about IEEE-754 hazards:

- `isnan(l1->A) || isnan(l1->B) || isnan(l1->C)` checks at lines 1248-1249 in line-intersection. [verified-by-code]
- `isnan(pt1->x) || isnan(pt1->y)` checks at lines 2031-2032. [verified-by-code]
- `isinf(m)` check at line 1131 (vertical-line slope). [verified-by-code]
- `get_float8_infinity()` returned in degenerate cases at 1285, 1297, 2088, 2106. [verified-by-code]
- `FPzero`, `FPeq`, `FPlt`, etc. — epsilon-comparison macros (defined in `geo_decls.h`); used throughout. NOTE: epsilon comparisons are scale-dependent and known to give surprising results for very large coordinates. [from-comment]

## Phase D notes

- **Float-to-integer overflow**: most operators stay in `float8`; box dimensions are floats. No int32 narrowing seen in hot paths. [inferred from spot-check]
- **Quadratic algorithms**: polygon-polygon overlap is O(n*m); poly-contains is O(n). For pathological polygons (thousands of vertices) these are slow but not exponential. No DoS gate.
- **Polygon vertex-count cap**: a polygon's vertex count is stored in `npts` (int32), capped by varlena size. A polygon of 100 MB worth of points is allowable but the operators will be slow. [inferred]
- **Epsilon comparisons (FPeq, FPlt, ...)** use a fixed `EPSILON` (1e-6 typically). For coordinates near 1e10 this is many ULPs smaller than the representable precision, leading to FPeq returning true for clearly distinct points. Documented limitation, often surfaces on bug list. [from-comment, geo_decls.h]
- **Circle radius can be negative** if parsed loosely — circle_in checks for r >= 0. [inferred from box_diagonal area]

## Potential issues

- `[ISSUE-correctness: epsilon-based FPeq/FPlt comparisons in geo_ops are scale-blind; large-coordinate inputs can violate transitivity (e.g. a == b and b == c but a != c). Documented limitation. (medium; long-standing)]`.
- `[ISSUE-dos: polygon ops are O(n*m); a 1M-vertex polygon overlap test can run for many minutes without yielding (CHECK_FOR_INTERRUPTS not visible in the inner loops — would need targeted audit) (maybe)]`.
- `[ISSUE-correctness: box_in accepts swapped corners and swaps them silently; a NaN coordinate in one corner can survive the swap if the comparison is NaN-tainted (would need targeted audit) (maybe)]`.
- `[ISSUE-undocumented-invariant: many *_internal helpers assume both operands have been validated by *_in; if a caller bypasses input validation (e.g. binary recv with malformed body), the *_internal can divide by zero (low — recv functions exist and do validate)]`.
- `[ISSUE-stale-todo: many geo functions predate the float8 NaN/Inf cleanup of PG 12; some still return surprising results on Inf inputs rather than ereport (low)]`.

Confidence: function indexing `[verified-by-code]`; quadratic / epsilon concerns `[inferred]`.
