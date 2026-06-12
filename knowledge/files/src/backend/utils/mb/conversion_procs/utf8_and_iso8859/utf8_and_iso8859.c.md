---
path: src/backend/utils/mb/conversion_procs/utf8_and_iso8859/utf8_and_iso8859.c
anchor_sha: e18b0cb7344
loc: 172
depth: read
---

# `utf8_and_iso8859.c` — UTF8 ↔ 13 ISO-8859-* encodings

## Purpose

Single conversion module servicing the **13 ISO-8859-N variants
collectively** (ISO-8859-2 through ISO-8859-16, minus the
LATIN1-only `_1` one which is hand-coded in
`utf8_and_iso8859_1/`). Instead of one .so per variant, a single
`pg_conv_map[]` array dispatches at call time on the runtime
`encoding` argument. The resulting binary holds 26 radix trees (one
to/from pair per variant) statically linked from the generated
headers under `Unicode/`.

This is the multi-encoding module pattern (compare `utf8_and_win.c`,
`utf8_and_cyrillic.c`); the other modules in the directory hard-code
exactly one pair of encoding IDs.

## Public symbols

| Symbol | Line | Notes |
|---|---:|---|
| `iso8859_to_utf8` (`Datum`, fmgr V1) | 103 | `<iso8859-N>` → UTF-8. Source encoding ID is read from `PG_GETARG_INT32(0)`. |
| `utf8_to_iso8859` (`Datum`, fmgr V1) | 139 | UTF-8 → `<iso8859-N>`. Destination encoding ID is read from `PG_GETARG_INT32(1)`. |
| `PG_MODULE_MAGIC_EXT(.name = "utf8_and_iso8859", .version = PG_VERSION)` | 44 | Required since PG 18. |
| `PG_FUNCTION_INFO_V1(iso8859_to_utf8)` | 49 | fmgr V1 registration. |
| `PG_FUNCTION_INFO_V1(utf8_to_iso8859)` | 50 | fmgr V1 registration. |

## Internal landmarks

- `typedef struct { pg_enc encoding; const pg_mb_radix_tree *map1;
  const pg_mb_radix_tree *map2; } pg_conv_map;` (lines 66-71) — the
  dispatch row type. `map1` is the to-UTF8 tree (used by
  `iso8859_to_utf8`), `map2` is the from-UTF8 tree (used by
  `utf8_to_iso8859`).
- `static const pg_conv_map maps[] = { ... };` (lines 73-100) — the
  9-element table covering LATIN2, LATIN3, LATIN4, LATIN5 (alias for
  ISO-8859-9), LATIN6 (ISO-8859-10), LATIN7 (ISO-8859-13), LATIN8
  (ISO-8859-14), LATIN9 (ISO-8859-15), LATIN10 (ISO-8859-16),
  ISO_8859_5, ISO_8859_6, ISO_8859_7, ISO_8859_8. The PG_ enum names
  expose the LATIN-N aliases that appear in `pg_enc`. ISO-8859-1 is
  intentionally absent — see Potential issues.
- 25 `#include "../../Unicode/<...>.map"` lines (17-42) pull in the
  radix-tree definitions; each `.map` is a generated C source declaring
  a `pg_mb_radix_tree` named `iso8859_N_to_unicode_tree` /
  `iso8859_N_from_unicode_tree`.
- Both functions call `LocalToUtf` / `UtfToLocal` from `conv.c` (lines
  120-125 and 156-161). The 4th-5th args (`NULL, 0`) say "no
  combined-character map needed", which is correct for single-byte
  encodings like ISO-8859.

## Invariants

- The `maps[]` table is searched linearly; with only 13 entries the
  cost is negligible. Order is not significance — any permutation is
  legal as long as encoding IDs are unique.
- If `PG_GETARG_INT32(0)` (or `(1)` for the reverse direction)
  doesn't match any row, the code falls through to the
  `ERRCODE_INTERNAL_ERROR` `ereport` at line 130 / 166 — this is a
  "the catalog is lying to us" condition, not a user error.
- `CHECK_ENCODING_CONVERSION_ARGS(-1, PG_UTF8)` at line 112 (and
  `(PG_UTF8, -1)` at line 148) — the `-1` wildcards out the variable
  side. The macro still enforces that the *other* side is UTF8.
- `noError` propagation: passed through unchanged to
  `LocalToUtf`/`UtfToLocal` — that helper is responsible for honoring
  the "truncate instead of raise" contract.

## Potential issues

- **ISO-8859-1 is intentionally elsewhere.** The 9-entry `maps[]`
  array covers LATIN2-LATIN10 and ISO_8859_5/6/7/8, *not* LATIN1. A
  reader trying to extend the module to cover LATIN1 would find that
  it doesn't work because `pg_conversion` routes LATIN1 to the
  `utf8_and_iso8859_1` proc instead (which uses an open-coded loop,
  no radix tree, because LATIN1 is a direct subset of U+0000-U+00FF
  and benefits from skipping the tree lookup).
- **Adding a new ISO-8859-* row is a two-step change.** Need to (a)
  add the generator entry under `src/backend/utils/mb/Unicode/`, (b)
  add both `iso8859_N_to_unicode_tree` and
  `iso8859_N_from_unicode_tree` `#include`s and a `maps[]` row here,
  (c) bump catversion if a new `pg_conversion` row appears.
- The fall-through `PG_RETURN_INT32(0)` after `ereport(ERROR, ...)`
  at lines 135 and 171 is dead code (ereport longjmps) but is
  conventional in PG to satisfy compilers warning about
  non-returning paths in `Datum`-returning functions.

## Cross-refs

- `knowledge/files/src/backend/utils/mb/conversion_procs/README.md` —
  directory-wide overview.
- `knowledge/files/src/backend/utils/mb/conv.c.md` — `LocalToUtf`
  / `UtfToLocal` shared helpers.
- `source/src/include/mb/pg_wchar.h` — `pg_enc` IDs (PG_LATIN2, ...,
  PG_LATIN10, PG_ISO_8859_5, ...), `pg_mb_radix_tree` layout,
  `CHECK_ENCODING_CONVERSION_ARGS` macro.
- `source/src/backend/utils/mb/Unicode/UCS_to_8859.pl` — generator
  for these `.map` headers.

## Synthesized by
<!-- backlinks:auto -->
