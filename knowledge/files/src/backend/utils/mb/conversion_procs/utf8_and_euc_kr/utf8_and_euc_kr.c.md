---
path: src/backend/utils/mb/conversion_procs/utf8_and_euc_kr/utf8_and_euc_kr.c
anchor_sha: e18b0cb7344
loc: 81
depth: read
---

# `utf8_and_euc_kr.c` — EUC_KR ↔ UTF-8

## Purpose

Conversion proc for the Korean **EUC_KR ↔ UTF-8** pair (the KS X
1001 / Wansung subset, *not* the UHC superset which is in
`utf8_and_uhc.c`). Backs the `euc_kr_to_utf8` and `utf8_to_euc_kr`
rows in `pg_conversion`. Consumes `euc_kr_to_utf8.map` /
`utf8_to_euc_kr.map` from `src/backend/utils/mb/Unicode/`.

## Public symbols

| Symbol | Line | Notes |
|---|---:|---|
| `PG_MODULE_MAGIC_EXT(.name = "utf8_and_euc_kr", …)` | 20 | Module identity. |
| `PG_FUNCTION_INFO_V1(euc_kr_to_utf8)` | 25 | fmgr V1 registration. |
| `PG_FUNCTION_INFO_V1(utf8_to_euc_kr)` | 26 | fmgr V1 registration. |
| `euc_kr_to_utf8` (`Datum`) | 42 | EUC_KR → UTF-8 entry point. |
| `utf8_to_euc_kr` (`Datum`) | 63 | UTF-8 → EUC_KR entry point. |

## Internal landmarks

- Standard 6-arg fmgr unpack.
- `CHECK_ENCODING_CONVERSION_ARGS(PG_EUC_KR, PG_UTF8)` (line 50) and
  inverse on line 71.
- Calls `LocalToUtf` / `UtfToLocal` with the radix tree, NULL
  combined-char map, no callback.
- Returns `PG_RETURN_INT32(converted)`.

## Invariants & gotchas

- Loaded via fmgr from `pg_conversion`.
- EUC_KR ↔ Unicode is one-to-one (combined-char map `NULL, 0`).
- EUC_KR is the smaller charset; full modern Hangul coverage requires
  UHC (`utf8_and_uhc.c`). Many web pages tagged "euc-kr" actually
  contain UHC bytes — PG accepts only the strict KS X 1001 subset
  here.
- Invalid input → `ereport(ERROR, ...CHARACTER_NOT_IN_REPERTOIRE)`
  unless `noError = true`.

## Cross-refs

- `knowledge/files/src/backend/utils/mb/conv.c.md` — `LocalToUtf` /
  `UtfToLocal`.
- `knowledge/files/src/backend/utils/mb/conversion_procs/utf8_and_uhc/utf8_and_uhc.c.md`
  — UHC superset sibling.
- `source/src/include/mb/pg_wchar.h` — `PG_EUC_KR` enum value.

## Synthesized by
<!-- backlinks:auto -->
