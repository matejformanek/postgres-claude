---
path: src/backend/utils/mb/conversion_procs/utf8_and_sjis/utf8_and_sjis.c
anchor_sha: e18b0cb7344
loc: 81
depth: read
---

# `utf8_and_sjis.c` — SJIS ↔ UTF-8

## Purpose

Conversion proc for the Japanese **SJIS ↔ UTF-8** pair (Shift_JIS,
the JIS X 0208 / CP932 variant — *not* JIS X 0213:2004 which is
`utf8_and_sjis2004.c`). Backs the `sjis_to_utf8` and `utf8_to_sjis`
rows in `pg_conversion`. Consumes `sjis_to_utf8.map` /
`utf8_to_sjis.map` from `src/backend/utils/mb/Unicode/`.

## Public symbols

| Symbol | Line | Notes |
|---|---:|---|
| `PG_MODULE_MAGIC_EXT(.name = "utf8_and_sjis", …)` | 20 | Module identity. |
| `PG_FUNCTION_INFO_V1(sjis_to_utf8)` | 25 | fmgr V1 registration. |
| `PG_FUNCTION_INFO_V1(utf8_to_sjis)` | 26 | fmgr V1 registration. |
| `sjis_to_utf8` (`Datum`) | 42 | SJIS → UTF-8 entry point. |
| `utf8_to_sjis` (`Datum`) | 63 | UTF-8 → SJIS entry point. |

## Internal landmarks

- Standard 6-arg fmgr unpack.
- `CHECK_ENCODING_CONVERSION_ARGS(PG_SJIS, PG_UTF8)` (line 50) and
  inverse on line 71.
- Calls `LocalToUtf` / `UtfToLocal` with the radix tree, NULL
  combined-char map, and no per-encoding callback.
- Returns `PG_RETURN_INT32(converted)`.

## Invariants & gotchas

- Loaded via fmgr from `pg_conversion`.
- SJIS (CP932 baseline) → Unicode is one-to-one — combined-char map is
  `NULL, 0`. The 2004 revision DOES require a combined-char map; that
  is handled by the sibling `utf8_and_sjis2004.c`.
- The SJIS-to-EUC_JP transcode lives in
  `euc_jp_and_sjis/euc_jp_and_sjis.c` and predates the UTF-8 path.
- Invalid input → `ereport(ERROR, ...CHARACTER_NOT_IN_REPERTOIRE)`
  unless `noError = true`.

## Cross-refs

- `knowledge/files/src/backend/utils/mb/conv.c.md` — `LocalToUtf` /
  `UtfToLocal`.
- `knowledge/files/src/backend/utils/mb/conversion_procs/utf8_and_sjis2004/utf8_and_sjis2004.c.md`
  — JIS X 0213:2004 sibling.
- `knowledge/files/src/backend/utils/mb/conversion_procs/euc_jp_and_sjis/euc_jp_and_sjis.c.md`
  — direct SJIS ↔ EUC_JP transcoder.
- `source/src/include/mb/pg_wchar.h` — `PG_SJIS` enum value.

## Synthesized by
<!-- backlinks:auto -->
