# contrib-earthdistance (great-circle distance on Earth)

- **Source path:** `source/contrib/earthdistance/`
- **Last verified commit:** `e18b0cb7344` (2026-06-13 anchor)
- **Extension version:** `1.2` (per `earthdistance.control`)
- **Trusted:** no (depends on `cube`)
- **Requires:** `cube`

## 1. Purpose

Compute **great-circle distances** between points on Earth's
surface and **bounding-box queries** for "find points within
distance D of (lat, lon)." Two SQL-level interfaces:

- **Point-based** (`Point` data type, statute miles) — simple,
  no index support.
- **Cube-based** (using `contrib-cube` types) — supports GiST
  indexing for fast "within distance D" queries.

The cube-based form is the workhorse. The point-based form is
~100 LOC of `earthdistance.c` and exists for legacy reasons.

## 2. Two implementations in one extension

The SQL surface installs TWO sets of functions:

### Set 1: Point-based (statute miles)

```sql
SELECT '(40.7128, -74.0060)'::point <@>
       '(48.8566, 2.3522)'::point;
-- → distance in statute miles between NYC and Paris
```

`@<>` operator computes great-circle distance using
spherical-law-of-cosines on `Point` arguments. Output is
statute miles. Implemented in the 108-LOC C file
[verified-by-code `wc -l earthdistance.c`].

### Set 2: Cube-based (meters; GiST-indexable)

The bulk of earthdistance — implemented in SQL on top of
`cube`:

```sql
SELECT earth_distance(ll_to_earth(40.7128, -74.0060),
                       ll_to_earth(48.8566, 2.3522));
-- → distance in meters

-- Indexed lookup:
CREATE INDEX gis_idx ON places
   USING gist (ll_to_earth(lat, lon));

SELECT * FROM places
   WHERE earth_box(ll_to_earth(40, -74), 50000)
         @> ll_to_earth(lat, lon)
   AND earth_distance(ll_to_earth(lat, lon),
                      ll_to_earth(40, -74)) < 50000;
```

[the canonical "within 50km" query pattern]

## 3. The earth_box trick

`earth_box(point, distance)` returns a **3D cube** that
bounds all points within `distance` meters of `point`.
Because the cube can be GiST-indexed, the WHERE clause
`earth_box(...) @> ll_to_earth(lat, lon)` is an indexed
containment check.

The cube is a **bounding box, not the exact great-circle
ring** — so the followup `earth_distance(...) < distance`
clause filters false positives. The combination:

1. **Index scan**: use `earth_box @>` to prune to candidate
   rows.
2. **Recheck**: use `earth_distance <` to filter exact matches.

This pattern is the canonical "indexed great-circle distance"
query. Without it, every distance computation requires a
table scan.

## 4. The conversion functions

| Function | Returns |
|---|---|
| `ll_to_earth(lat, lon)` | A 3D cube point on Earth's surface |
| `latitude(earth)` | Reverse: extract latitude |
| `longitude(earth)` | Reverse: extract longitude |
| `earth_distance(e1, e2)` | Distance in meters |
| `earth_box(e, radius)` | Bounding 3D cube |
| `gc_to_sec(distance_meters)` | Convert to angular distance (radians) |
| `sec_to_gc(angle_radians)` | Reverse |

The lat/lon → cube conversion places the point on a unit
sphere scaled by Earth's radius. Two cube points'
3D-Euclidean-distance is approximately their great-circle
arc length.

## 5. Why not PostGIS?

PostGIS handles geographic data properly:
- True spheroidal Earth model (not just sphere).
- Polygons + lines + arbitrary shapes, not just points.
- Many coordinate systems.
- Per-feature SRID tagging.

earthdistance is a lightweight alternative when:
- You only need point-to-point distance.
- You don't need polygon operations.
- You don't want PostGIS as a dependency.

For real geographic apps, use PostGIS.

## 6. The spherical-vs-ellipsoidal accuracy gap

Earth is an oblate spheroid, not a sphere. Great-circle on a
sphere approximation introduces up to ~0.5% error at extreme
latitudes. For most apps this is fine; for navigation /
precision-engineering, use PostGIS's geodetic types.

## 7. Production-use guidance

- **For "within distance" queries**, use the cube-based
  form with GiST index.
- **For one-off distance computations**, the point-based
  form is fine.
- **earth_box + earth_distance pair** is the indexed-query
  idiom; both clauses required.
- **CREATE EXTENSION cube FIRST** — earthdistance won't
  install without it.

## 8. Invariants

- **[INV-1]** Spherical model; 0.5% accuracy ceiling.
- **[INV-2]** Cube-based form is GiST-indexable; point form
  is not.
- **[INV-3]** Returns meters (cube form) or statute miles
  (point form); don't mix.
- **[INV-4]** Requires `cube` extension as dependency.
- **[INV-5]** earth_box is a bounding box, not exact;
  combine with earth_distance < D for exact filter.

## 9. Useful greps

- The single C function:
  `cat source/contrib/earthdistance/earthdistance.c`
- The SQL-level implementations:
  `head -100 source/contrib/earthdistance/earthdistance--1.0.sql`

## 10. Cross-references

- `knowledge/subsystems/contrib-cube.md` — the underlying
  N-dimensional cube type earthdistance builds on.
- `knowledge/subsystems/access-method-apis.md` — GiST AM
  contracts for cube indexes.
- `knowledge/subsystems/contrib-pg_trgm.md` — sibling
  similarity contrib (different domain).
- `source/contrib/earthdistance/earthdistance.c` — the point-
  based C implementation (108 LOC).
- `source/contrib/earthdistance/earthdistance--1.0.sql` —
  the cube-based SQL implementation.

## Files owned
<!-- files-owned:auto -->

*Files under this subsystem's owned paths (by slug derivation + include-header filters). Auto-refreshed by `scripts/populate-subsystem-files.py`.*

**1 files.**

| File |
|---|
| [`contrib/earthdistance/earthdistance.c`](../files/contrib/earthdistance/earthdistance.c.md) |

<!-- /files-owned:auto -->
