---
path: src/backend/utils/mb/conversion_procs/utf8_and_euc_jp/utf8_and_euc_jp.c
anchor_sha: e18b0cb7344
loc: 81
depth: read
---

# `utf8_and_euc_jp.c` — EUC_JP ↔ UTF-8

## Purpose

Conversion proc for the Japanese **EUC_JP ↔ UTF-8** pair (the JIS X
0208-based EUC variant — *not* JIS X 0213:2004 which is
`utf8_and_euc2004.c`). Backs the `euc_jp_to_utf8` and
`utf8_to_euc_jp` rows in `pg_conversion`. Consumes
`euc_jp_to_utf8.map` / `utf8_to_euc_jp.map` from
`src/backend/utils/mb/Unicode/`.

## Public symbols

| Symbol | Line | Notes |
|---|---:|---|
| `PG_MODULE_MAGIC_EXT(.name = "utf8_and_euc_jp", …)` | 20 | Module identity. |
| `PG_FUNCTION_INFO_V1(euc_jp_to_utf8)` | 25 | fmgr V1 registration. |
| `PG_FUNCTION_INFO_V1(utf8_to_euc_jp)` | 26 | fmgr V1 registration. |
| `euc_jp_to_utf8` (`Datum`) | 42 | EUC_JP → UTF-8 entry point. |
| `utf8_to_euc_jp` (`Datum`) | 63 | UTF-8 → EUC_JP entry point. |

## Internal landmarks

- Standard 6-arg fmgr unpack.
- `CHECK_ENCODING_CONVERSION_ARGS(PG_EUC_JP, PG_UTF8)` (line 50) and
  inverse on line 71.
- Calls `LocalToUtf` / `UtfToLocal` with the radix tree, NULL
  combined-char map, no callback.
- Returns `PG_RETURN_INT32(converted)`.

## Invariants & gotchas

- Loaded via fmgr from `pg_conversion`.
- Baseline EUC_JP ↔ Unicode is one-to-one (combined-char map `NULL,
  0`). The 2004 revision adds combining-form codepoints — handled by
  the sibling `utf8_and_euc2004.c`. See `README.euc_jp` next to this
  source file for the encoding details.
- EUC_JP ↔ SJIS is a separate transcoder
  (`euc_jp_and_sjis/euc_jp_and_sjis.c`).
- Invalid input → `ereport(ERROR, ...CHARACTER_NOT_IN_REPERTOIRE)`
  unless `noError = true`.

## Cross-refs

- `knowledge/files/src/backend/utils/mb/conv.c.md` — `LocalToUtf` /
  `UtfToLocal`.
- `knowledge/files/src/backend/utils/mb/conversion_procs/utf8_and_euc2004/utf8_and_euc2004.c.md`
  — JIS X 0213:2004 sibling.
- `knowledge/files/src/backend/utils/mb/conversion_procs/euc_jp_and_sjis/euc_jp_and_sjis.c.md`
  — direct EUC_JP ↔ SJIS transcoder.
- `source/src/backend/utils/mb/conversion_procs/README.euc_jp` —
  encoding background notes.
- `source/src/include/mb/pg_wchar.h` — `PG_EUC_JP` enum value.

## Synthesized by
<!-- backlinks:auto -->
