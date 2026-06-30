# contrib/earthdistance/earthdistance.c

Source pin: `4b0bf0788b066a4ca1d4f959566678e44ec93422`.

## Role

Provides `geo_distance(point, point) → float8` — great-circle distance
in **statute miles** between two `point`s whose `x` is longitude (°)
and `y` is latitude (°). The companion `earthdistance--1.1.sql` exposes
the cube-based "earth ball" representation (different angle, different
units). This C file is the v1.0 plain-`point` implementation.
[verified-by-code] `source/contrib/earthdistance/earthdistance.c:99-108`.

## Public API

- `geo_distance(point, point) → float8` — `:99-108`. [verified-by-code]

Internal:
- `degtorad(degrees)` — `:33-37`.
- `geo_distance_internal(pt1, pt2)` — haversine formula, `:52-81`.

## Constants

- `EARTH_RADIUS = 3958.747716` miles (`:20`). [verified-by-code]
- `TWO_PI = 2.0 * M_PI` (`:21`).
- `M_PI` falls back to a literal if not provided by `<math.h>`
  (`:10-12`).

## Invariants

- Result is in **statute miles** — units not asserted in the function
  contract beyond a header comment (`:48-49`). Caller cannot tell
  miles vs km from the type. [from-comment]
- No domain check on lat/lon — values outside `[-180,180]` /
  `[-90,90]` are silently accepted; `degtorad` then `sin`/`cos` give
  numerically valid but geometrically meaningless results.
  [verified-by-code]
- `longdiff` is normalized to `<= PI` by `longdiff = TWO_PI -
  longdiff` if it exceeds PI (`:71-73`). This is correct for inputs
  in `[-2pi,2pi]` only — outside that, the normalization is incomplete.
  [inferred]
- `sino` is clamped to `<= 1` (`:77-78`) to defend against
  floating-point round-off pushing the haversine result just over 1,
  which would make `asin` return NaN. [verified-by-code, from-comment]

## Trust-boundary / Phase-D surface

- **No lat/lon range check.** A user passing `point(1e10, 1e10)` gets
  a result without error. Not a security bug — just precision waste
  — but worth flagging for the documentation gap. [ISSUE-documentation]
- **NaN/Inf input** — `Point` carries float8 `x`/`y`; if either is
  NaN/Inf, `degtorad` propagates NaN/Inf, `sin`/`cos` give NaN, and
  the result is NaN. PostgreSQL float math allows this. No crash;
  result is just NaN. [verified-by-code]
- **EARTH_RADIUS precision** — 3958.747716 mi corresponds to roughly
  6371.0089 km, close to the mean Earth radius. The header comment
  notes "earth's radius" but doesn't specify the precision class
  (the actual Earth is oblate, ~6378 km equatorial vs 6357 km polar
  → up to 0.3% error). [ISSUE-documentation]

## Cross-refs

- `source/contrib/cube/cube.c` — earthdistance v1.1's SQL layer
  delegates spherical distance to cube. This C file is v1.0 only.
- `source/utils/adt/geo_ops.c` — defines `Point`.

<!-- issues:auto:begin -->
- [Issue register — `earthdistance`](../../../issues/earthdistance.md)
<!-- issues:auto:end -->

## Issues

- `[ISSUE-documentation: EARTH_RADIUS precision class undocumented;
  spherical-earth assumption introduces up to ~0.3% error vs WGS84]
  (low)` — `source/contrib/earthdistance/earthdistance.c:19-20`
- `[ISSUE-documentation: no lat/lon range check; out-of-range inputs
  silently give nonsense distance instead of ERROR] (low)` —
  `source/contrib/earthdistance/earthdistance.c:52-81`
- `[ISSUE-robustness: longdiff > 2pi not normalized; if caller passes
  longitude in radians instead of degrees the math silently degrades]
  (low)` — `source/contrib/earthdistance/earthdistance.c:71-73`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/contrib-earthdistance.md](../../../subsystems/contrib-earthdistance.md)
