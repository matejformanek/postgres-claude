---
source_url: https://www.postgresql.org/docs/current/earthdistance.html
fetched_at: 2026-07-14T20:57:00Z
anchor_sha: 1863452a4bfe
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
section: "F.13 earthdistance — calculate great-circle distances"
maps_to_skill: [access-method-apis, type-cache]
---

# Docs distilled — earthdistance (great-circle distance; the cube KNN payoff)

Two ways to compute great-circle distance. The interesting one is the
**cube-based** path: it layers a `earth` domain over `cube` and turns a
proximity query into a `cube` bounding-box `@>` index scan — the concrete
application that motivates `cube`'s GiST opclass.

## Non-obvious claims

- **Depends on `cube`** — install `cube` first, or `CREATE EXTENSION
  earthdistance CASCADE`. Both should live in the **same trusted schema**; an
  untrusted object in earthdistance's schema is an install-time security hazard.
  [from-docs]
- **A lat/lon point is stored as a 3-D `cube` coordinate on the sphere surface**
  — `(x,y,z)` distance from Earth's center. The `earth` domain over `cube`
  carries the validity constraint. This 3-D-on-sphere encoding is what dodges
  the pole / ±180°-longitude singularities the point-based path suffers.
  [from-docs]
- **`earth() → float8` is the single tunable constant** — the assumed Earth
  radius **in meters**. Redefining that one function re-bases *all* cube-path
  distances into other units/radii. [from-docs]
- **The index trick: `earth_box(earth, radius) → cube`** returns a bounding cube
  usable with the `cube` `@>` operator (hence a `gist_cube_ops` index) to
  pre-filter candidate locations; the box is a *superset*, so a secondary
  `earth_distance(...) < radius` recheck is required. This is the canonical
  "GiST bounding box + exact recheck" nearest-location pattern. [from-docs]
- **Core functions**: `ll_to_earth(lat, lon)`, `latitude(earth)`/
  `longitude(earth)`, `earth_distance(earth, earth)`, `earth_box`,
  `sec_to_gc`/`gc_to_sec` (secant↔great-circle). [from-docs]
- **Point-based path is the lesser one**: `point <@> point → float8` returns
  distance in **statute miles**, with **hardwired units** (`earth()` does *not*
  affect it) and pole/antimeridian edge-case problems. Prefer the cube path.
  [from-docs]

## Links into corpus

- `[[docs-distilled/cube.md]]` — earthdistance is the *why* behind
  `gist_cube_ops`: `earth_box` + `@>` + exact recheck is the applied form of
  cube's boolean/KNN GiST support. Read the two together.
- `access-method-apis` skill — textbook "lossy bounding-box index filter +
  precise recheck" flow (same shape as `[[docs-distilled/intarray.md]]`'s lossy
  `gist__intbig_ops` recheck).
- `gucs-config` / function-as-constant: `earth()` is the "tune behavior by
  redefining a SQL function" idiom rather than a GUC.
