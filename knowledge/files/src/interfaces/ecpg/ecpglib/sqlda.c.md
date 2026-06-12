---
path: src/interfaces/ecpg/ecpglib/sqlda.c
anchor_sha: e18b0cb7344cb4bd28468f6c0aeeb9b9241d30aa
loc: 592
depth: deep
---

# `sqlda.c` — build SQLDA (SQL Descriptor Area) structures from a `PGresult`

## Purpose
Constructs SQLDA descriptor areas — the dynamic-SQL result-metadata-plus-data
blocks that ESQL/C programs read after `EXEC SQL DESCRIBE` / `FETCH ... USING
DESCRIPTOR` — in both the native (`struct sqlda_struct`) and Informix-compat
(`struct sqlda_compat`) layouts, from a libpq `PGresult`. The defining design
choice (file header comment, sqlda.c:1-7) is that a single allocation holds
*both* the metadata (the SQLDA header, the per-column `sqlvar` array, and for
the compat layout the field-name strings) *and* the converted field values for
one row, so the caller can release everything with a plain `free(sqlda)`. Sizing
is done in a first pass (`sqlda_*_total_size`) that walks the columns computing
aligned offsets; building/setting is a second pass that reproduces the exact
same offset walk and fills in `sqldata` pointers that point back into the same
block. The native and compat paths are near-duplicates differing only in the
header/`sqlvar` layout and name storage.

## Public symbols
| Symbol | Site | Notes |
|---|---|---|
| `struct sqlda_compat *ecpg_build_compat_sqlda(int line, PGresult *res, int row, enum COMPAT_MODE compat)` | sqlda.c:204 | Allocates + fills compat metadata (header, sqlvar array, field names); leaves room for one row's values. |
| `void ecpg_set_compat_sqlda(int lineno, struct sqlda_compat **_sqlda, const PGresult *res, int row, enum COMPAT_MODE compat)` | sqlda.c:254 | Second pass: sets `sqldata`/`sqllen`/`sqlind` and converts values for `row`. |
| `struct sqlda_struct *ecpg_build_native_sqlda(int line, PGresult *res, int row, enum COMPAT_MODE compat)` | sqlda.c:411 | Native counterpart of `ecpg_build_compat_sqlda`. |
| `void ecpg_set_native_sqlda(int lineno, struct sqlda_struct **_sqlda, const PGresult *res, int row, enum COMPAT_MODE compat)` | sqlda.c:443 | Native counterpart of `ecpg_set_compat_sqlda`. |

All four are declared in `ecpglib_extern.h` and consumed by `descriptor.c` /
`execute.c`. The five `static` helpers (`ecpg_sqlda_align_add_size`,
`sqlda_compat_empty_size`, `sqlda_common_total_size`, `sqlda_compat_total_size`,
`sqlda_native_empty_size`, `sqlda_native_total_size`) are file-local.

## Internal landmarks

**Alignment primitive — `ecpg_sqlda_align_add_size` (sqlda.c:32-42).** Rounds
`offset` up to `alignment` (`offset += alignment - (offset % alignment)`), writes
the aligned start to `*current`, then adds `size` and writes the end to `*next`.
The single point where all alignment + bump-allocation arithmetic happens, used
identically by both the sizing pass and the fill pass so the two stay in lockstep.

**Empty (metadata-only) size.**
- Compat (sqlda.c:44-62): `sizeof(struct sqlda_compat) + sqld * sizeof(struct
  sqlvar_compat)`, then `+ strlen(fname)+1` for every column's name
  (sqlda.c:55-56), then padded up to `int` alignment for the first value
  (sqlda.c:59).
- Native (sqlda.c:170-183): `sizeof(struct sqlda_struct) + (sqld - 1) *
  sizeof(struct sqlvar_struct)` — the `-1` because `sqlda_struct` already embeds
  one `sqlvar_struct` as a flexible trailer (sqlda.c:177). Names are stored
  inline in `sqlvar.sqlname.data`, so no separate name pass. Same `int`-pad
  (sqlda.c:180).

**Value-area size — `sqlda_common_total_size` (sqlda.c:64-153).** Per-column
`switch` on the ECPG dynamic type (mapped via `sqlda_dynamic_type(PQftype(...),
compat)`, sqlda.c:74); each case calls `ecpg_sqlda_align_add_size` with that
type's natural alignment and storage size, then `offset = next_offset`
(sqlda.c:150). Fixed-width scalars are straightforward. Two special cases:
- **char/string/default (sqlda.c:139-148):** size is `strlen(PQgetvalue)+1`
  (NUL included), aligned to `int`.
- **numeric (sqlda.c:106-129):** two-level. First reserve `sizeof(numeric)`
  aligned to `sizeof(NumericDigit *)` (so the embedded `buf`/`digits` pointers
  are pointer-aligned). Then, if the value is non-null, deconstruct it with
  `PGTYPESnumeric_from_asc` *just to learn the digit-buffer length*
  (`num->digits - num->buf + num->ndigits`), reserve that many bytes aligned to
  `int` from `next_offset` (sqlda.c:126), and `PGTYPESnumeric_free` it. The
  comment at sqlda.c:108-115 flags that numeric must be deconstructed twice
  (once here for sizing, once in the set pass to fill).

**Single-allocation layout & internal pointers — `ecpg_build_compat_sqlda`
(sqlda.c:204-246).** `ecpg_alloc(size, line)` then `memset(...,0,size)`. Carves
the block: `sqlvar = (struct sqlvar_compat *)(sqlda + 1)` (sqlda.c:220),
`fname = (char *)(sqlvar + sqld)` (sqlda.c:222). Stores `sqlda->desc_occ = size`
as a "cheat" to keep the full allocation size around (sqlda.c:226). Field names
are `strcpy`'d into the `fname` region and `fname` is bumped by
`strlen+1` per column (sqlda.c:232-234). Native build (sqlda.c:411-441) writes
the `"SQLDA  "` id tag (sqlda.c:425), sets `sqln=sqld`, computes `sqldabc` (the
metadata byte count, sqlda.c:428), and copies names inline into
`sqlvar[i].sqlname.data` (sqlda.c:437).

**Fill pass — `ecpg_set_compat_sqlda` / `ecpg_set_native_sqlda`
(sqlda.c:254-409, 443-592).** Re-derives the first-value offset from
`sqlda_*_empty_size(res)` (sqlda.c:266, 455) and re-runs the identical per-column
offset walk, this time setting `sqlvar[i].sqldata = (char *) sqlda + offset` and
`sqllen`. Numeric (sqlda.c:323-362, 512-551) sets `set_data = false`, `memcpy`s
the `numeric` struct into place, and if `num->buf` is present copies the digit
bytes into the reserved tail and rewrites the embedded `buf`/`digits` pointers to
point into the block (sqlda.c:350-357, 539-546). Null handling: `sqlind` points
at static `value_is_null`/`value_is_not_null` int16s (sqlda.c:251-252, 393, 580);
non-null non-numeric values are converted by `ecpg_get_data` (sqlda.c:399, 584);
nulls call `ECPGset_noind_null` (sqlda.c:405). Compat-only: a value longer than
32768 bytes also gets mirrored into `sqlilongdata` (sqlda.c:386-387).

## Invariants & gotchas

- **The two passes MUST walk offsets identically.** `sqlda_common_total_size`
  (sizing) and the `set_*` functions (filling) duplicate the same per-type
  `switch` with the same alignment/size arguments. Any divergence — a type added
  to one switch but not the other, or different alignment — makes the fill pass
  write outside the bytes the sizing pass reserved. This is the central
  must-not-break property and the reason the duplication is tolerated rather than
  refactored. [verified-by-code sqlda.c:64-153 vs 277-389, 466-576]

- **Single free contract.** Everything (header, sqlvars, names, values, numeric
  digit buffers) lives in one `ecpg_alloc` block; callers `free(sqlda)` once
  (sqlda.c:1-7). Therefore every internal pointer (`sqlvar`, `sqlname`,
  `sqldata`, numeric `buf`/`digits`) must point *inside* that block — they are
  offsets from `sqlda`, never independent allocations. [from-comment sqlda.c:4-6]

- **Numeric `buf`/`digits` pointer arithmetic (sqlda.c:355-356, 544-545):**
  `(NumericDigit *) sqlda + offset`. Because `NumericDigit` is `unsigned char`
  (`pgtypes_numeric.h:17`, size 1), the pointer scaling degenerates to a byte
  add, so this is correct *only by virtue of that typedef*. If `NumericDigit`
  were ever widened, this arithmetic would silently scale `offset` by the element
  size and corrupt the pointers. [verified-by-code; NumericDigit size from
  pgtypes_numeric.h:17]

- **Numeric is parsed twice** (sqlda.c:108-115 comment): once for sizing, once
  for fill. The two `PGTYPESnumeric_from_asc` calls must agree on digit-buffer
  length or the reserved tail won't match what's copied. Both guard `if
  (num->buf)` before touching the digit region.

- **NUL terminator space** for char/string is included via `strlen+1`
  (sqlda.c:144, 382, 571) in both passes — consistent, so no off-by-one between
  reserve and fill.

- **Numeric NULL path** in the size pass `break`s out of the inner block on a
  failed/NULL parse *before* reserving digit-tail space (sqlda.c:117-128); the
  fill pass mirrors this with `ECPGset_noind_null` and an early `break`
  (sqlda.c:334-346). Kept symmetric.

- **`row < 0` means metadata-only**: both `sqlda_*_total_size` and the `set_*`
  functions short-circuit (sqlda.c:163-164, 192, 262-263, 451-452), producing a
  descriptor with no value area. Callers must not read `sqldata` in that mode.

## Cross-refs
- [[descriptor.c]], [[execute.c]], [[data.c]]
- `ecpg_get_data` (in data.c) does the actual text-to-binary value conversion.
- `sqlda-compat.h`, `sqlda-native.h`, `ecpglib_extern.h` define the structs and
  declare the four public builders.

## Potential issues

- **[ISSUE-OVERFLOW: size pass uses signed `long`, no overflow guard]**
  `sqlda.c:47,65,159,173,188` — all offset/size accumulation is in signed `long`
  with no saturation check before `ecpg_alloc`. With very many columns and/or
  very wide values (e.g. large char columns whose `strlen+1` per column sums
  high, or numeric digit buffers), the running `offset` could in principle
  overflow `long` and wrap negative; `ecpg_alloc` would then receive a bogus
  (possibly small or negative) size while the fill pass walks the real, larger
  offsets — a heap overflow. In practice column counts and libpq value sizes are
  bounded by available memory, so this is low-likelihood, but there is no
  explicit guard. Severity: low (hard to trigger; requires pathological result
  width). [inferred]

- **[ISSUE-ROBUSTNESS: silent size/fill divergence on numeric parse mismatch]**
  `sqlda.c:122-126 vs 341-352` — sizing and filling independently call
  `PGTYPESnumeric_from_asc` on the same text. If the two parses ever disagreed on
  `num->digits - num->buf + num->ndigits` (they shouldn't for identical input,
  but they are not asserted equal), the fill `memcpy` at sqlda.c:353/542 could
  exceed the reserved tail. No assertion ties the two together. Severity: low
  (deterministic parser makes divergence unlikely). [inferred]
