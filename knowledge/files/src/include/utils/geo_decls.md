# utils/geo_decls.h — Point/Lseg/Path/Line/Box/Polygon/Circle types

Source: `source/src/include/utils/geo_decls.h` (277 lines)
Source pin: `4b0bf0788b066a4ca1d4f959566678e44ec93422`

## Role

Declares the 2D geometric types and the EPSILON-fuzzy floating comparisons (FPeq, FPlt, etc.) used by the geo ops.

## Public API

- **EPSILON = 1.0E-06** (`geo_decls.h:41`).
- **Fuzzy float comparisons**: `FPzero(A)`, `FPeq/FPne/FPlt/FPle/FPgt/FPge` (`geo_decls.h:43-89`).
- **Types** (`geo_decls.h:92-165`):
  - `Point { float8 x, y; }` (line 95-99)
  - `LSEG { Point p[2]; }` (line 105-108)
  - `PATH { vl_len_, npts, closed, dummy, Point p[]; }` (line 114-121) — varlena, contains explicit `dummy` for double-align padding.
  - `LINE { float8 A, B, C; }` (line 127-132) — Ax+By+C=0 general form.
  - `BOX { Point high, low; }` (line 139-143) — corners sorted at construction.
  - `POLYGON { vl_len_, npts, BOX boundbox, Point p[]; }` (line 150-156) — varlena.
  - `CIRCLE { Point center; float8 radius; }` (line 161-165).
- fmgr macros for each (`geo_decls.h:174-275`).

## Invariants

- **INV-EPSILON-not-transitive** [from-comment, `geo_decls.h:30-32`]: "Beware of normal reasoning about the behavior of these comparisons, since for example FPeq does not behave transitively." Equality is `|A-B| <= EPSILON`, so A≈B and B≈C does NOT imply A≈C.
- **INV-FP*-NaN-FALSE** [from-comment, `geo_decls.h:33-34`]: "these functions are not NaN-aware and will give FALSE for any case involving NaN inputs." Differs from float.h's `float8_*` which treats NaN as larger than non-NaN.
- **INV-FP*-Inf-safe** [from-comment, `geo_decls.h:36-39`]: "will give sane answers for infinite inputs" — implementation eliminates equality cases before subtracting to avoid Inf - Inf = NaN.
- **INV-BOX-corners-sorted** [from-comment, `geo_decls.h:136-138`]: BOX struct stores corners sorted (`high.x >= low.x`, `high.y >= low.y`) — saves work at compare time but requires constructors to sort.
- **INV-PATH-dummy-padding** [verified-by-code, `geo_decls.h:119`]: explicit `int32 dummy` field exists solely to make the FLEXIBLE_ARRAY_MEMBER Point start at a double-align boundary. Removing it is an on-disk break.
- **INV-XXX-not-by-numerical-analyst** [from-comment, `geo_decls.h:11-14`]: original author's own self-deprecation; the implementations are not numerically robust under adversarial input.

## Trust-boundary / Phase-D surface

- **Inf - Inf and 0 * Inf in geometric ops** — the FP* helpers avoid Inf-Inf via the equality short-circuit (`geo_decls.h:38-39`), but downstream ops in geo_ops.c that *compute* distances/products can still produce NaN from Inf inputs. Box/Polygon recv must validate that input coordinates are finite (or accept NaN consequences).
- **EPSILON intransitivity → btree/index inconsistency** — using FPeq in an opclass `equal` would break btree's `a=b ∧ b=c ⇒ a=c` requirement. No btree opclass currently uses these for that reason, but the trap is implicit, not enforced.
- **`PATH.dummy` field on disk** — pg_dump of pre-existing tables would carry the value; on-disk compatibility requires keeping it.
- **A7 / A14-class concerns**: `point_recv`, `box_recv`, `polygon_recv`, `path_recv` should validate finiteness (no Inf in coords) and overflow (npts * sizeof(Point) doesn't overflow Size). Header silent.

## Cross-refs

- `source/src/backend/utils/adt/geo_ops.c` — implementations + recv/in.
- A13/A14 NaN findings: `seg`, `cube`, btree_gist float ops have parallel issues.
- `knowledge/files/src/include/utils/float.md` — companion (NaN-aware comparisons).

## Issues

- `[ISSUE-INVARIANT: EPSILON intransitivity is a foot-gun for opclass authors (medium)]` — comment at line 30-32 is the entire warning; new GiST/SP-GiST opclasses on geo types often mis-handle this.
- `[ISSUE-DOC: NaN behavior differs between geo_decls.h and float.h (medium)]` — geo FP* says "FALSE on NaN", float.h `float8_*` says "NaN > everything." Mixing the two in one operator family is a known source of bugs.
- `[ISSUE-INVARIANT: BOX corners-sorted is invariant constructed-only (low)]` — no runtime assert; a malformed BOX (high < low) would silently miscompute area/distance.
