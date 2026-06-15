---
path: src/backend/utils/mb/conversion_procs/utf8_and_euc_cn/utf8_and_euc_cn.c
anchor_sha: e18b0cb7344
loc: 81
depth: read
---

# `utf8_and_euc_cn.c` — EUC_CN ↔ UTF-8

## Purpose

Conversion proc for the Simplified Chinese **EUC_CN ↔ UTF-8** pair.
Backs the `euc_cn_to_utf8` and `utf8_to_euc_cn` rows in `pg_conversion`.
Consumes the generated radix-tree headers `euc_cn_to_utf8.map` and
`utf8_to_euc_cn.map` from `src/backend/utils/mb/Unicode/` (built by
`UCS_to_EUC_CN.pl`).

## Public symbols

| Symbol | Line | Notes |
|---|---:|---|
| `PG_MODULE_MAGIC_EXT(.name = "utf8_and_euc_cn", …)` | 20 | Module identity. |
| `PG_FUNCTION_INFO_V1(euc_cn_to_utf8)` | 25 | fmgr V1 registration. |
| `PG_FUNCTION_INFO_V1(utf8_to_euc_cn)` | 26 | fmgr V1 registration. |
| `euc_cn_to_utf8` (`Datum`) | 42 | EUC_CN → UTF-8 entry point. |
| `utf8_to_euc_cn` (`Datum`) | 63 | UTF-8 → EUC_CN entry point. |

## Internal landmarks

- Standard 6-arg fmgr unpack: `PG_GETARG_CSTRING(2/3)` for src/dest,
  `PG_GETARG_INT32(4)` for `len`, `PG_GETARG_BOOL(5)` for `noError`.
- `CHECK_ENCODING_CONVERSION_ARGS(PG_EUC_CN, PG_UTF8)` (line 50) and
  inverse on line 71 — consistency-check the fmgr arg0/arg1 against
  the expected pair.
- Each Datum function calls `LocalToUtf` / `UtfToLocal` (in
  `src/backend/utils/mb/conv.c`) with the matching radix tree, NULL
  combined-char map (EUC_CN ↔ Unicode is one-to-one), and no
  per-encoding helper callback.
- Returns `PG_RETURN_INT32(converted)` — byte count successfully
  converted before any failure point.

## Invariants & gotchas

- Loaded via fmgr from `pg_conversion`; never called from C
  directly. The 6-arg `conv_proc` signature is fixed across all
  conversion procs in this directory.
- EUC_CN ↔ Unicode has no multi-codepoint canonical form, so the 4th-5th
  args to `LocalToUtf` / `UtfToLocal` are `NULL, 0`. Compare GB18030,
  JOHAB, and the JIS-2004 family which DO pass a combined-char map.
- Invalid input → `ereport(ERROR, errcode(ERRCODE_CHARACTER_NOT_IN_REPERTOIRE))`
  via `report_invalid_encoding` / `report_untranslatable_char` inside
  the worker, unless `noError = true`, in which case the partial
  byte count is returned.

## Cross-refs

- `knowledge/files/src/backend/utils/mb/conv.c.md` — the `LocalToUtf` /
  `UtfToLocal` workers.
- `knowledge/files/src/backend/utils/mb/conversion_procs/utf8_and_big5/utf8_and_big5.c.md`
  — the canonical "trivial UTF8↔CJK" sibling.
- `source/src/include/mb/pg_wchar.h` — `PG_EUC_CN` enum value,
  `pg_mb_radix_tree` layout.
- `source/src/backend/utils/mb/Unicode/UCS_to_EUC_CN.pl` — generator
  for the `.map` headers.

## Synthesized by
<!-- backlinks:auto -->
