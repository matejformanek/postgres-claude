---
path: src/backend/utils/mb/conversion_procs/utf8_and_johab/utf8_and_johab.c
anchor_sha: e18b0cb7344
loc: 81
depth: read
---

# `utf8_and_johab.c` — JOHAB ↔ UTF-8

## Purpose

Conversion proc for the Korean **JOHAB ↔ UTF-8** pair.
Backs the `johab_to_utf8` and `utf8_to_johab` rows in `pg_conversion`.
Consumes the generated radix-tree headers `johab_to_utf8.map` and
`utf8_to_johab.map` from `src/backend/utils/mb/Unicode/` (built by
`UCS_to_JOHAB.pl`).

## Public symbols

| Symbol | Line | Notes |
|---|---:|---|
| `PG_MODULE_MAGIC_EXT(.name = "utf8_and_johab", …)` | 20 | Module identity. |
| `PG_FUNCTION_INFO_V1(johab_to_utf8)` | 25 | fmgr V1 registration. |
| `PG_FUNCTION_INFO_V1(utf8_to_johab)` | 26 | fmgr V1 registration. |
| `johab_to_utf8` (`Datum`) | 42 | JOHAB → UTF-8 entry point. |
| `utf8_to_johab` (`Datum`) | 63 | UTF-8 → JOHAB entry point. |

## Internal landmarks

- Standard 6-arg fmgr unpack: `PG_GETARG_CSTRING(2/3)` for src/dest,
  `PG_GETARG_INT32(4)` for `len`, `PG_GETARG_BOOL(5)` for `noError`.
- `CHECK_ENCODING_CONVERSION_ARGS(PG_JOHAB, PG_UTF8)` (line 50) and
  inverse on line 71.
- Each Datum function calls `LocalToUtf` / `UtfToLocal` (in
  `src/backend/utils/mb/conv.c`) with the matching radix tree, NULL
  combined-char map, and no per-encoding helper callback.
- Returns `PG_RETURN_INT32(converted)`.

## Invariants & gotchas

- Loaded via fmgr from `pg_conversion`. The 6-arg `conv_proc`
  signature is fixed.
- Despite the Korean Hangul-syllable model that JOHAB encodes, the
  PG mapping is byte-for-codepoint via the radix tree alone — the
  combined-char args are still `NULL, 0`. JOHAB → Unicode does not
  require canonical decomposition because the Unicode side stores
  precomposed Hangul syllables in the BMP. Compare GB18030 and the
  JIS-2004 family which require a real combined-char map.
- Invalid input → `ereport(ERROR, ...CHARACTER_NOT_IN_REPERTOIRE)`
  via the worker, unless `noError = true`, in which case the partial
  byte count is returned.

## Cross-refs

- `knowledge/files/src/backend/utils/mb/conv.c.md` — the `LocalToUtf` /
  `UtfToLocal` workers.
- `knowledge/files/src/backend/utils/mb/conversion_procs/utf8_and_big5/utf8_and_big5.c.md`
  — the canonical "trivial UTF8↔CJK" sibling.
- `source/src/include/mb/pg_wchar.h` — `PG_JOHAB` enum value.
- `source/src/backend/utils/mb/Unicode/UCS_to_JOHAB.pl` — generator.

## Synthesized by
<!-- backlinks:auto -->
