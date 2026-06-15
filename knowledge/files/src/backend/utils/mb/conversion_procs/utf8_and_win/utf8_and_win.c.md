---
path: src/backend/utils/mb/conversion_procs/utf8_and_win/utf8_and_win.c
anchor_sha: e18b0cb7344
loc: 153
depth: read
---

# `utf8_and_win.c` — Windows codepages ↔ UTF-8

## Purpose

Conversion proc for **eleven Windows codepages ↔ UTF-8** in a single
module: WIN866, WIN874, WIN1250, WIN1251, WIN1252, WIN1253, WIN1254,
WIN1255, WIN1256, WIN1257, WIN1258. Backs two `pg_conversion` rows
that dispatch on the source/dest encoding ID at runtime:
`win_to_utf8`, `utf8_to_win`. Consumes 22 `.map` headers (one
`winXXX_to_utf8.map` and one `utf8_to_winXXX.map` per codepage) from
`src/backend/utils/mb/Unicode/`.

## Public symbols

| Symbol | Line | Notes |
|---|---:|---|
| `PG_MODULE_MAGIC_EXT(.name = "utf8_and_win", …)` | 40 | Module identity. |
| `PG_FUNCTION_INFO_V1(win_to_utf8)` | 45 | fmgr V1. |
| `PG_FUNCTION_INFO_V1(utf8_to_win)` | 46 | fmgr V1. |
| `maps[]` (static `pg_conv_map` array) | 69 | Table mapping `pg_enc` → radix-tree pair. |
| `win_to_utf8` (`Datum`) | 83 | WINxxxx → UTF-8 dispatcher. |
| `utf8_to_win` (`Datum`) | 119 | UTF-8 → WINxxxx dispatcher. |

## Internal landmarks

- The `pg_conv_map` struct (lines 62-67) bundles `{encoding, map1
  (to-UTF8), map2 (from-UTF8)}`. The static `maps[]` (lines 69-81)
  is an 11-row table covering the eleven supported WIN codepages.
- `win_to_utf8` (line 83): pulls the **source encoding** out of fmgr
  arg 0 (`PG_GETARG_INT32(0)`), passes `-1` as the source-side check
  to `CHECK_ENCODING_CONVERSION_ARGS(-1, PG_UTF8)` (line 93) since the
  source varies, then linear-scans `maps[]` to find the matching
  radix tree and delegates to `LocalToUtf`.
- `utf8_to_win` (line 119): mirror image — pulls the **dest encoding**
  out of fmgr arg 1, passes `-1` as the dest-side check, scans
  `maps[]`, delegates to `UtfToLocal`.
- If the encoding ID doesn't appear in `maps[]`, both functions raise
  `ereport(ERROR, errcode(ERRCODE_INTERNAL_ERROR), errmsg("unexpected
  encoding ID %d for WIN character sets", encoding))` (lines 111-114,
  147-150).

## Invariants & gotchas

- Loaded via fmgr from `pg_conversion`. Multiple `pg_conversion` rows
  point at these same two SQL-callable functions — the dispatch
  happens inside via the encoding-ID arg, an exception to the
  "one proc per direction per pair" pattern of every other file in
  this directory.
- All eleven Windows codepages are single-byte → Unicode is one-to-one
  (combined-char map `NULL, 0`).
- The `CHECK_ENCODING_CONVERSION_ARGS(-1, ...)` form signals to the
  shared macro "skip the source-side / dest-side encoding-ID equality
  check"; the per-row consistency is then re-validated by the linear
  scan over `maps[]`.
- Invalid input inside the worker → `ereport(ERROR,
  ...CHARACTER_NOT_IN_REPERTOIRE)` unless `noError = true`.

## Cross-refs

- `knowledge/files/src/backend/utils/mb/conv.c.md` — `LocalToUtf` /
  `UtfToLocal`.
- `knowledge/files/src/backend/utils/mb/conversion_procs/cyrillic/cyrillic.c.md`
  — sibling that covers WIN866/WIN1251 in the non-UTF8 dimension.
- `source/src/include/mb/pg_wchar.h` — the `PG_WIN866` … `PG_WIN1258`
  enum values used to key `maps[]`.

## Synthesized by
<!-- backlinks:auto -->
