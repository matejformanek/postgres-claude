---
path: src/backend/utils/mb/conversion_procs/utf8_and_gbk/utf8_and_gbk.c
anchor_sha: e18b0cb7344
loc: 81
depth: read
---

# `utf8_and_gbk.c` — GBK ↔ UTF-8

## Purpose

Conversion proc for the Simplified Chinese **GBK ↔ UTF-8** pair
(Microsoft CP936 superset of GB2312).
Backs the `gbk_to_utf8` and `utf8_to_gbk` rows in `pg_conversion`.
Consumes `gbk_to_utf8.map` / `utf8_to_gbk.map` from
`src/backend/utils/mb/Unicode/` (built by `UCS_to_GBK.pl`).

## Public symbols

| Symbol | Line | Notes |
|---|---:|---|
| `PG_MODULE_MAGIC_EXT(.name = "utf8_and_gbk", …)` | 20 | Module identity. |
| `PG_FUNCTION_INFO_V1(gbk_to_utf8)` | 25 | fmgr V1 registration. |
| `PG_FUNCTION_INFO_V1(utf8_to_gbk)` | 26 | fmgr V1 registration. |
| `gbk_to_utf8` (`Datum`) | 42 | GBK → UTF-8 entry point. |
| `utf8_to_gbk` (`Datum`) | 63 | UTF-8 → GBK entry point. |

## Internal landmarks

- Standard 6-arg fmgr unpack identical to all trivial UTF8↔CJK procs.
- `CHECK_ENCODING_CONVERSION_ARGS(PG_GBK, PG_UTF8)` (line 50) and
  inverse on line 71.
- Calls `LocalToUtf` / `UtfToLocal` (in `src/backend/utils/mb/conv.c`)
  with the radix tree, NULL combined-char map, and no callback.
- Returns `PG_RETURN_INT32(converted)`.

## Invariants & gotchas

- Loaded via fmgr from `pg_conversion`. The 6-arg `conv_proc`
  signature is fixed.
- GBK is the 2-byte subset; the 4-byte extension is GB18030, handled
  by `utf8_and_gb18030.c` (which uses a callback for ranges outside
  the table). GBK ↔ Unicode is one-to-one — no combined-char map.
- Invalid input → `ereport(ERROR, ...CHARACTER_NOT_IN_REPERTOIRE)`
  unless `noError = true`.

## Cross-refs

- `knowledge/files/src/backend/utils/mb/conv.c.md` — `LocalToUtf` /
  `UtfToLocal`.
- `knowledge/files/src/backend/utils/mb/conversion_procs/utf8_and_big5/utf8_and_big5.c.md`
  — canonical sibling.
- `knowledge/files/src/backend/utils/mb/conversion_procs/utf8_and_gb18030/utf8_and_gb18030.c.md`
  — sibling for the 4-byte extension.
- `source/src/include/mb/pg_wchar.h` — `PG_GBK` enum value.

## Synthesized by
<!-- backlinks:auto -->
