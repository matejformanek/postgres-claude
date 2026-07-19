# contrib/isn/isn.h

**Pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
**LOC:** 33
**Verification depth:** full read

## Role

Public header for the `isn` contrib module — defines the on-disk type
`ean13` (a `uint64`) and the standard PG_GETARG/PG_RETURN macros that
funnel through `INT64`.  All five user-visible types (`ean13`, `isbn`,
`ismn`, `issn`, `upc`) share this representation; the type discriminator
lives in the high-order bits and `isn.c`'s `ean2isn` function.
[verified-by-code] `source/contrib/isn/isn.h:1-32`

## Public API

- `typedef uint64 ean13;` — single internal storage type for ALL five
  user types.
  [verified-by-code] `source/contrib/isn/isn.h:25`
- `PG_GETARG_EAN13(n) → PG_GETARG_INT64(n)`,
  `PG_RETURN_EAN13(x) → PG_RETURN_INT64(x)`.
  [verified-by-code] `source/contrib/isn/isn.h:27-28`
- `extern void initialize(void);` — declared but **not defined** in this
  tree (left over from earlier design? See ISSUE below).
  [verified-by-code] `source/contrib/isn/isn.h:30`

## Notable internals

- `#undef ISN_DEBUG` at line 20 — the module-local `ISN_DEBUG` macro is
  defined inside `isn.c` based on `USE_ASSERT_CHECKING`, not here.
  [verified-by-code] `source/contrib/isn/isn.h:20-21`
- The "invalid check digit" flag lives in the low bit of the ean13
  value (see `is_valid` / `make_valid` in isn.c). So the *real*
  numeric range is 0..(2^63-1), with the low bit reserved.
  [verified-by-code] `source/contrib/isn/isn.c:1100-1120`

## Trust-boundary / Phase-D surface

- All input validation lives in `isn.c`. This header is just data.
- **ISSUE-D1 (low, hygiene)**: `extern void initialize(void);` is
  declared but no matching definition exists in the source tree.
  Dead declaration — would be silently ignored at link time, but a
  reader can be misled.
  [inferred] from grep for `^initialize\|^isn_initialize` (no result).

## Cross-refs

- `source/contrib/isn/isn.c` — implementation.
- `source/contrib/isn/{EAN13,ISBN,ISMN,ISSN,UPC}.h` — registration
  prefix tables (see `isn_data_headers.md`).

## Issues raised

- **ISSUE-D1 (low)** — orphan `extern void initialize(void);`
  declaration.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/contrib-isn.md](../../../subsystems/contrib-isn.md)
