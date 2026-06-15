---
path: src/backend/utils/mb/conversion_procs/utf8_and_uhc/utf8_and_uhc.c
anchor_sha: e18b0cb7344
loc: 81
depth: read
---

# `utf8_and_uhc.c` — UHC ↔ UTF-8

## Purpose

Conversion proc for the Korean **UHC ↔ UTF-8** pair (Unified Hangul
Code, Microsoft CP949, the EUC-KR superset that covers all 11,172
modern Hangul syllables). Backs the `uhc_to_utf8` and `utf8_to_uhc`
rows in `pg_conversion`. Consumes `uhc_to_utf8.map` /
`utf8_to_uhc.map` from `src/backend/utils/mb/Unicode/`.

## Public symbols

| Symbol | Line | Notes |
|---|---:|---|
| `PG_MODULE_MAGIC_EXT(.name = "utf8_and_uhc", …)` | 20 | Module identity. |
| `PG_FUNCTION_INFO_V1(uhc_to_utf8)` | 25 | fmgr V1 registration. |
| `PG_FUNCTION_INFO_V1(utf8_to_uhc)` | 26 | fmgr V1 registration. |
| `uhc_to_utf8` (`Datum`) | 42 | UHC → UTF-8 entry point. |
| `utf8_to_uhc` (`Datum`) | 63 | UTF-8 → UHC entry point. |

## Internal landmarks

- Standard 6-arg fmgr unpack identical to the trivial UTF8↔CJK procs.
- `CHECK_ENCODING_CONVERSION_ARGS(PG_UHC, PG_UTF8)` (line 50) and
  inverse on line 71.
- Calls `LocalToUtf` / `UtfToLocal` with the radix tree, NULL
  combined-char map, no callback.
- Returns `PG_RETURN_INT32(converted)`.

## Invariants & gotchas

- Loaded via fmgr from `pg_conversion`. The 6-arg `conv_proc`
  signature is fixed.
- UHC ↔ Unicode is one-to-one in the PG mapping — combined-char map
  is `NULL, 0`. UHC's precomposed Hangul syllables map directly to
  the U+AC00-U+D7AF Unicode block.
- Invalid input → `ereport(ERROR, ...CHARACTER_NOT_IN_REPERTOIRE)`
  unless `noError = true`.

## Cross-refs

- `knowledge/files/src/backend/utils/mb/conv.c.md` — `LocalToUtf` /
  `UtfToLocal`.
- `knowledge/files/src/backend/utils/mb/conversion_procs/utf8_and_big5/utf8_and_big5.c.md`
  — canonical sibling.
- `knowledge/files/src/backend/utils/mb/conversion_procs/utf8_and_euc_kr/utf8_and_euc_kr.c.md`
  — Korean sibling (smaller charset).
- `source/src/include/mb/pg_wchar.h` — `PG_UHC` enum value.

## Synthesized by
<!-- backlinks:auto -->
