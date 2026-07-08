# q3c — spherical (celestial ra/dec) spatial indexing with NO custom access method: reduce the 2D-sphere to a 1D bigint the plain B-tree already indexes

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `segasai/q3c` @ branch `master` — Sergey Koposov's Quad Tree Cube
> sky-indexing extension for astronomy (ADASS 2006, ASCL 1905.008). All
> `file:line` cites below point into that repo (not `source/`), since this doc
> characterizes an *external* extension's divergence from core idioms. Cites
> verified against files fetched on 2026-07-08 (see Sources footer). The build
> copies `README.md` → `q3c.md` as the installed doc (`Makefile` `readme`
> target); the C source set is `dump.o q3c.o q3c_poly.o q3cube.o` from
> `Makefile OBJS`.

## Domain & purpose

q3c answers spherical spatial queries over astronomical catalogs: cone searches
("all objects within R degrees of a point"), ellipse and polygon searches, and
positional cross-matches between two catalogs of celestial coordinates
(`README.md:80-143`) `[from-README]`. The coordinates are right ascension /
declination in degrees on the celestial sphere. The whole design turns on one
move: a **quad-tree-cube space-filling curve maps `(ra, dec)` on the sphere to a
single 64-bit integer `ipix`** (`q3c_ang2ipix`), and every higher-level query is
expressed as a set of integer **range predicates** on that scalar. Because the
scalar is an ordinary `bigint`, the acceleration structure is a **plain
functional B-tree index** — `CREATE INDEX ON mytable (q3c_ang2ipix(ra, dec))`
(`README.md:55-57`) `[from-README]`. There is no GiST opclass, no custom index
AM, no new operator strategy set for searching — the sphere problem is reduced to
a 1D-scalar problem the core B-tree already solves.

## How it hooks into PG

- **`PG_MODULE_MAGIC`** at `q3c.c:47`, guarded by `#ifdef` `[verified-by-code]`.
  **No `_PG_init`, no hooks, no GUCs, no shared memory** — grepping the C set
  finds none `[verified-by-code]`. q3c is a `MODULE_big` of four objects
  (`Makefile OBJS`).
- **~30 `PG_FUNCTION_INFO_V1` fmgr entry points** in `q3c.c` (declared
  `q3c.c:56-80`), all `pgq3c_*`. The user-facing SQL names (`q3c_ang2ipix`,
  `q3c_dist`, `q3c_radial_query`, `q3c_join`, …) are wired to them in the install
  SQL `scripts/q3c--2.0.3.sql` `[verified-by-code]`.
- **The load-bearing primitive** is `q3c_ang2ipix(double precision, double
  precision) RETURNS bigint`, declared `IMMUTABLE STRICT PARALLEL SAFE`
  (`q3c--2.0.3.sql:46-49`), C body `pgq3c_ang2ipix` at `q3c.c:208`
  `[verified-by-code]`. Everything else is scaffolding around indexing this.
- **Search predicates are pure SQL functions over the functional index.**
  `q3c_radial_query(ra, dec, cra, cdec, r)` is a `LANGUAGE SQL IMMUTABLE`
  function whose body is a giant disjunction of ~100+ `bigint` range tests of
  the form `q3c_ang2ipix($1,$2) >= q3c_radial_query_it(...) AND
  q3c_ang2ipix($1,$2) < q3c_radial_query_it(...)` (`q3c--2.0.3.sql:277-339+`)
  `[verified-by-code]`. The planner sees indexable `>=`/`<` conditions on the
  indexed expression `q3c_ang2ipix(ra,dec)` and drives a **bitmap index scan** —
  exactly the plan shape the README tells users to check for (`README.md:332-335`)
  `[from-README]`.
- **`q3c_join` for cross-matching** two catalogs is likewise SQL: it expands to
  8 `bigint` range conditions on `q3c_ang2ipix(rightra, rightdec)` (four
  disjoint ipix ranges × 2 bounds, via `q3c_nearby_it`) plus a precise
  `q3c_sindist(...) < sin(R/2)^2` recheck (`q3c--2.0.3.sql:199-210`)
  `[verified-by-code]`. Argument order matters: the indexed table's `ra,dec`
  must be the 3rd/4th args so the index expression matches (`README.md:205-207`)
  `[from-README]`.
- **One — and only one — C-level planner touchpoint: a fake operator that exists
  solely to carry a selectivity estimator.** The install SQL declares a dummy
  composite type `q3c_type`, a dummy operator `==<<>>==` whose procedure
  `q3c_seloper` **always returns `true`** (`q3c.c:103-107`), and attaches
  `RESTRICT = q3c_sel`, `JOIN = q3c_seljoin` (`q3c--2.0.3.sql:4-34`)
  `[verified-by-code]`. Each search/join SQL body ANDs in a
  `radius ==<<>>== (ra,dec,...)::q3c_type` term (e.g. `q3c--2.0.3.sql:209`) whose
  only purpose is to give the planner a handle with a real selectivity function.
- **Install SQL is the catalog surface**: `CREATE TYPE`, `CREATE OPERATOR`,
  `CREATE FUNCTION ... LANGUAGE C`, and the SQL-bodied search wrappers. The
  `.control` is `relocatable = true`, `default_version = '2.0.3'`
  (`q3c.control`).

## Where it diverges from core idioms

- **The whole point: no new access method.** Where PostGIS adds a GiST opclass,
  pgvector adds a whole new AM (HNSW/IVFFlat), and smlar reuses core GiST+GIN via
  bit-signatures, q3c adds **nothing** to the AM layer. It lowers a hard 2D
  spherical-range problem to a **1D scalar B-tree range** problem by choosing a
  space-filling curve (`q3c_ang2ipix`) such that spherical neighborhoods map to a
  bounded union of `ipix` intervals. This is the extreme "reduce, don't extend"
  end of the spatial-indexing spectrum. `[inferred]` from the absence of any
  `CREATE ACCESS METHOD` / `CREATE OPERATOR CLASS ... USING` in the install SQL
  and the functional-index instructions in `README.md:55-57`.
- **Selectivity via a decoy operator.** Core PG has no way to attach a
  `RESTRICT`/`JOIN` selectivity function to a bare SQL function call, so q3c
  fabricates an always-true operator `==<<>>==` purely as a vehicle for
  `q3c_sel` / `q3c_seljoin` (`q3c.c:112-195`). Those estimators compute the
  fraction of sky the search circle covers: `ratio = 3.14 * rad * rad / 41252.`
  (π·r² over 41252.96 sq-deg whole-sky), then `CLAMP_PROBABILITY`
  (`q3c.c:143-149`) `[verified-by-code]`. This is a genuinely unusual pattern —
  a no-op operator that carries planner metadata rather than semantics.
- **Function-static memoization instead of per-call recomputation.** The SQL
  bodies call `q3c_radial_query_it($3,$4,$5,N,1)` up to ~100 times with the same
  `(ra,dec,radius)` and only a varying iteration index `N`. Recomputing the
  range set each time would be catastrophic, so the C iterators cache the last
  invocation's parameters and its computed range array in **`static` locals**
  and just index into the buffer when `(ra,dec,radius)` are unchanged
  (`pgq3c_radial_query_it` `q3c.c:769-813`; `pgq3c_nearby_it` `q3c.c:505-560`;
  even `pgq3c_ang2ipix` keeps a 1-entry `static` cache `q3c.c:214-244`)
  `[verified-by-code]`. The `invocation` flag is deliberately set to 1 only
  *after* the buffers are populated, with a comment noting crash/cancel safety
  (`q3c.c:527-532`) `[from-comment]`. This leans on backend-per-connection
  process isolation: the statics are private to one backend and the functions
  are `IMMUTABLE`, so the cache is safe but is a divergence from the stateless
  fmgr-function norm.
- **Precomputed lookup tables as a build artifact.** The bit-interleaving arrays
  (`xbits`/`ybits`/`xbits1`/`ybits1`) and `nside` live in a `const struct
  q3c_prm hprm` that is *code-generated at build time* by a standalone `prepare`
  binary into `dump.c` (`Makefile` `dump.c: prepare readme` rule; every entry
  point does `extern struct q3c_prm hprm;` e.g. `q3c.c:211`) `[verified-by-code]`.
  The extension ships a generated C file rather than computing tables in
  `_PG_init`.
- **IMMUTABLE / PARALLEL SAFE discipline is essential, not incidental.** The
  functional index is only legal because `q3c_ang2ipix` is `IMMUTABLE`
  (`q3c--2.0.3.sql:49`). Distance/PM functions that accept NULL proper motions
  are deliberately marked **not** `STRICT` (`q3c--2.0.3.sql:109-135`)
  `[from-comment]`, because a strict function would collapse a NULL-pm row to
  NULL and drop it from a cross-match.
- **Non-finite inputs guarded, no `ereport` niceties.** `pgq3c_ang2ipix` returns
  SQL NULL for non-finite `ra`/`dec` (`q3c.c:233-236`); iterators `elog(ERROR,
  ...)` on NaN/out-of-range declination rather than using SQLSTATE-tagged
  `ereport` (`q3c.c:522-524`, `q3c.c:784`) `[verified-by-code]` — a lighter error
  idiom than core PG's `errcode(...)` convention.

## Notable design decisions

- **Cube-face projection + bit interleaving = the ipix.** `q3c_ang2ipix_xy`
  picks one of 6 cube faces from `(ra,dec)`, gnomonically projects onto that
  face's `[0,1]²` square, quantizes to integer `xi,yi`, and interleaves their
  bits into the final scalar (`q3cube.c:175-273`) `[verified-by-code]`. The
  interleave itself is `q3c_xiyi2ipix`: `face * nside² + xbits[xi..] +
  ybits[yi..]` (`q3cube.c:981-990`) `[verified-by-code]` — a Morton/Z-order-style
  quad-tree address within each cube face.
- **`ipix` is `int64`** (`typedef int64 q3c_ipix_t`, `common.h:50`) with
  `Q3C_MAX_IPIX` up to ~`2^62` (`common.h:60`) `[verified-by-code]`, so it fits
  PostgreSQL `bigint` exactly and B-tree-orders naturally.
- **Range set split into "fulls" and "partials".** `q3c_radial_query`
  (`q3cube.c:2472`) fills two arrays: `fulls` = ipix ranges fully inside the
  circle (no per-row recheck needed) and `partials` = ranges straddling the
  boundary (need the exact `q3c_sindist` recheck). Both capped at
  `Q3C_NPARTIALS = Q3C_NFULLS = 50` pairs (`common.h:177-180`), which is why the
  SQL body emits ~100 OR'd range clauses per query (`q3c--2.0.3.sql:281-339+`)
  `[verified-by-code]`.
- **Exact recheck always ANDed after the index ranges.** Cone search ANDs
  `q3c_sindist(...) < POW(SIN(RADIANS(r)/2),2)` (`q3c--2.0.3.sql:208`), ellipse
  ANDs `q3c_in_ellipse(...)` (`q3c--2.0.3.sql:273`) — the ipix ranges are a
  conservative *filter*; correctness comes from the recheck `[verified-by-code]`.
- **Proper-motion cross-match** (`q3c_join_pm`, `q3c--2.0.3.sql:229-259`) folds
  epoch + proper motion into the ipix range computation (`q3c_nearby_pm_it`) so
  moving-source matching still rides the same B-tree `[verified-by-code]`.
- **Polygon search** lives in `q3c_poly.c` (`q3c_check_sphere_point_in_poly`
  `q3c_poly.c:334`, cover-check `q3c_poly_cover_check:248`) and is exposed as
  `q3c_poly_query_it`, again emitting ipix ranges over the same functional index
  `[verified-by-code]`. `q3c_in_poly` is the index-*less* exact test
  (`README.md:140-141`) `[from-README]`.
- **Nearest-neighbour is not a special operator** — it is `q3c_join` inside a
  `LATERAL` subquery `ORDER BY q3c_dist(...) LIMIT 1` (`README.md:273-307`),
  i.e. composed from the range-join primitive rather than a `<->` KNN operator
  as pgvector does `[from-README]`.
- **Pure-SQL helpers via bit-shift.** `q3c_ipixcenter` is a one-line SQL
  expression doing `>> << +` arithmetic on the ipix — no C at all
  (`q3c--2.0.3.sql:74-79`) `[verified-by-code]`.

## Links into corpus

Spatial / GIS-astronomy sibling cluster: [[postgis]] (adds a GiST opclass),
[[pgvector]] (adds a whole new AM for KNN), [[smlar]] (reuses core GiST+GIN via
bit-signatures), [[pointcloud]] (typmod-driven compressed blobs). q3c is the
"no new AM at all" endpoint of that spectrum. Core cube/earthdistance analogues
live at [[contrib-cube]] and [[contrib-earthdistance]] (see
`knowledge/subsystems/contrib-cube.md`, `contrib-earthdistance.md`).

Relevant idioms: [[fmgr]] (`knowledge/idioms/fmgr.md`) for the
`PG_FUNCTION_INFO_V1` / `PG_GETARG_*` entry points; [[guc-variables]] — notable
here for its *absence*. Subsystems: `knowledge/subsystems/access-nbtree.md`
(the B-tree that actually does the work), `knowledge/subsystems/optimizer.md`
(where `RESTRICT`/`JOIN` selectivity functions are consumed). Architecture:
`knowledge/architecture/access-methods.md` (q3c is the counter-example — it
extends *nothing* in the AM layer), `knowledge/architecture/planner.md`.

## Sources

Fetched 2026-07-08, branch `master`. Note: the repo's `README.md` was served
correctly on a retry; a first fetch returned an unrelated cached body
(`pg_plan_advsr`) through the proxy — the cites here are against the verified
`README.md` (`# Q3C`, author S. Koposov).

- `https://raw.githubusercontent.com/segasai/q3c/master/README.md` @ 2026-07-08 → HTTP 200 (343 lines) — functions, usage, plan-shape guidance `[from-README]`. (First attempt returned wrong cached content; retry clean.)
- `https://raw.githubusercontent.com/segasai/q3c/master/q3c.control` @ 2026-07-08 → HTTP 200 — `relocatable`, `default_version = '2.0.3'`.
- `https://raw.githubusercontent.com/segasai/q3c/master/Makefile` @ 2026-07-08 → HTTP 200 — `MODULE_big`, `OBJS`, generated `dump.c` / `prepare` build rules, `readme` copy step.
- `https://raw.githubusercontent.com/segasai/q3c/master/common.h` @ 2026-07-08 → HTTP 200 (376 lines) — `q3c_ipix_t = int64`, `Q3C_MAX_IPIX`, `Q3C_NPARTIALS`/`Q3C_NFULLS`, interleave constants.
- `https://raw.githubusercontent.com/segasai/q3c/master/q3c.c` @ 2026-07-08 → HTTP 200 (1357 lines; needed 2 retries past HTTP 429) — fmgr glue: `pgq3c_ang2ipix`, `pgq3c_seloper`/`pgq3c_sel`/`pgq3c_seljoin`, `pgq3c_nearby_it`, `pgq3c_radial_query_it`, static memoization.
- `https://raw.githubusercontent.com/segasai/q3c/master/q3cube.c` @ 2026-07-08 → HTTP 200 (3067 lines; 1 retry past 429) — core algorithm: `q3c_ang2ipix_xy`, `q3c_xiyi2ipix`, `q3c_radial_query`, `q3c_get_nearby`, `q3c_ipix2ang`.
- `https://raw.githubusercontent.com/segasai/q3c/master/q3c_poly.c` @ 2026-07-08 → HTTP 200 (438 lines) — spherical polygon cover/point-in-poly.
- `https://raw.githubusercontent.com/segasai/q3c/master/scripts/q3c--2.0.3.sql` @ 2026-07-08 → HTTP 200 (1046 lines; retries past 429) — the catalog surface: `q3c_type`, `==<<>>==` operator, C-function decls, SQL-bodied search/join wrappers.

Gaps: `q3c.h` → HTTP 404 (header is `common.h`, not `q3c.h`; resolved). `dump.c`
→ HTTP 404 (it is a *generated* build artifact, not committed — confirmed by the
`Makefile dump.c:` rule). All `file:line` cites into `.c`/`.h`/`.sql` are
`[verified-by-code]` against the fetched copies; README-only narration is
`[from-README]`; the "no custom AM anywhere" and crash-safety-of-static-cache
claims are `[inferred]`/`[from-comment]` as tagged inline.
