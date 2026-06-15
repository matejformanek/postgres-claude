---
path: src/backend/utils/mb/conversion_procs/utf8_and_euc_tw/utf8_and_euc_tw.c
anchor_sha: e18b0cb7344
loc: 81
depth: read
---

# `utf8_and_euc_tw.c` — EUC_TW ↔ UTF-8

## Purpose

Conversion proc for the Traditional Chinese **EUC_TW ↔ UTF-8** pair
(CNS 11643-based EUC variant for Taiwan).
Backs the `euc_tw_to_utf8` and `utf8_to_euc_tw` rows in `pg_conversion`.
Consumes `euc_tw_to_utf8.map` / `utf8_to_euc_tw.map` from
`src/backend/utils/mb/Unicode/` (built by `UCS_to_EUC_TW.pl`).

## Public symbols

| Symbol | Line | Notes |
|---|---:|---|
| `PG_MODULE_MAGIC_EXT(.name = "utf8_and_euc_tw", …)` | 20 | Module identity. |
| `PG_FUNCTION_INFO_V1(euc_tw_to_utf8)` | 25 | fmgr V1 registration. |
| `PG_FUNCTION_INFO_V1(utf8_to_euc_tw)` | 26 | fmgr V1 registration. |
| `euc_tw_to_utf8` (`Datum`) | 42 | EUC_TW → UTF-8 entry point. |
| `utf8_to_euc_tw` (`Datum`) | 63 | UTF-8 → EUC_TW entry point. |

## Internal landmarks

- Standard 6-arg fmgr unpack identical to all trivial UTF8↔CJK procs.
- `CHECK_ENCODING_CONVERSION_ARGS(PG_EUC_TW, PG_UTF8)` (line 50) and
  inverse on line 71.
- Calls `LocalToUtf` / `UtfToLocal` (in `src/backend/utils/mb/conv.c`)
  with the radix tree, NULL combined-char map, and no callback.
- Returns `PG_RETURN_INT32(converted)`.

## Invariants & gotchas

- Loaded via fmgr from `pg_conversion`. The 6-arg `conv_proc`
  signature is fixed.
- EUC_TW ↔ Unicode is one-to-one in the PG mapping (no combined-char
  map). Note that EUC_TW ↔ BIG5 *is* lossy and is handled by a
  different conversion proc, `euc_tw_and_big5/big5.c`.
- Invalid input → `ereport(ERROR, ...CHARACTER_NOT_IN_REPERTOIRE)`
  unless `noError = true`.

## Cross-refs

- `knowledge/files/src/backend/utils/mb/conv.c.md` — `LocalToUtf` /
  `UtfToLocal`.
- `knowledge/files/src/backend/utils/mb/conversion_procs/utf8_and_big5/utf8_and_big5.c.md`
  — canonical sibling.
- `knowledge/files/src/backend/utils/mb/conversion_procs/euc_tw_and_big5/big5.c.md`
  — the lossy EUC_TW ↔ BIG5 transcoder.
- `source/src/include/mb/pg_wchar.h` — `PG_EUC_TW` enum value.

## Synthesized by
<!-- backlinks:auto -->
