---
path: src/backend/utils/mb/conversion_procs/utf8_and_sjis2004/utf8_and_sjis2004.c
anchor_sha: e18b0cb7344
loc: 81
depth: read
---

# `utf8_and_sjis2004.c` — SHIFT_JIS_2004 ↔ UTF-8

## Purpose

Conversion proc for the Japanese **SHIFT_JIS_2004 ↔ UTF-8** pair (the
JIS X 0213:2004 Shift-JIS variant). Backs the
`shift_jis_2004_to_utf8` and `utf8_to_shift_jis_2004` rows in
`pg_conversion`. Consumes `shift_jis_2004_to_utf8.map` /
`utf8_to_shift_jis_2004.map` plus the JIS-2004 combined-char arrays
from `src/backend/utils/mb/Unicode/`.

## Public symbols

| Symbol | Line | Notes |
|---|---:|---|
| `PG_MODULE_MAGIC_EXT(.name = "utf8_and_sjis2004", …)` | 20 | Module identity. |
| `PG_FUNCTION_INFO_V1(shift_jis_2004_to_utf8)` | 25 | fmgr V1 registration. |
| `PG_FUNCTION_INFO_V1(utf8_to_shift_jis_2004)` | 26 | fmgr V1 registration. |
| `shift_jis_2004_to_utf8` (`Datum`) | 42 | SHIFT_JIS_2004 → UTF-8. |
| `utf8_to_shift_jis_2004` (`Datum`) | 63 | UTF-8 → SHIFT_JIS_2004. |

## Internal landmarks

- Standard 6-arg fmgr unpack.
- `CHECK_ENCODING_CONVERSION_ARGS(PG_SHIFT_JIS_2004, PG_UTF8)` (line 50)
  and inverse on line 71.
- **Combined-character map is non-NULL** — calls into
  `LocalToUtf` / `UtfToLocal` pass `LUmapSHIFT_JIS_2004_combined,
  lengthof(LUmapSHIFT_JIS_2004_combined)` (lines 54, 75). JIS X
  0213:2004 has characters whose Unicode canonical form is a base
  codepoint + combining mark, so the worker needs the second-codepoint
  table.
- Returns `PG_RETURN_INT32(converted)`.

## Invariants & gotchas

- Loaded via fmgr from `pg_conversion`. The 6-arg `conv_proc`
  signature is fixed.
- This file and `utf8_and_euc2004.c` are the only UTF8↔legacy procs
  that ship a combined-char map. The combined arrays
  (`LUmapSHIFT_JIS_2004_combined`, `ULmapSHIFT_JIS_2004_combined`) are
  defined inside the included `.map` headers.
- Invalid input → `ereport(ERROR, ...CHARACTER_NOT_IN_REPERTOIRE)`
  unless `noError = true`.

## Cross-refs

- `knowledge/files/src/backend/utils/mb/conv.c.md` — `LocalToUtf` /
  `UtfToLocal` workers (which dispatch the combined-char fallback).
- `knowledge/files/src/backend/utils/mb/conversion_procs/utf8_and_euc2004/utf8_and_euc2004.c.md`
  — sibling JIS-2004 conversion through EUC.
- `knowledge/files/src/backend/utils/mb/conversion_procs/euc2004_sjis2004/euc2004_sjis2004.c.md`
  — direct EUC_JIS_2004 ↔ SHIFT_JIS_2004 transcoder.
- `source/src/include/mb/pg_wchar.h` — `PG_SHIFT_JIS_2004` enum value.

## Synthesized by
<!-- backlinks:auto -->
