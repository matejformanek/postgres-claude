---
path: src/backend/utils/mb/conversion_procs/euc_jp_and_sjis/euc_jp_and_sjis.c
anchor_sha: e18b0cb7344
loc: 329
depth: read
---

# `euc_jp_and_sjis.c` — EUC_JP ↔ SJIS (no UTF-8 trip)

## Purpose

Direct conversion proc for the Japanese **EUC_JP ↔ SJIS** pair
without involving UTF-8. Backs the `euc_jp_to_sjis` and
`sjis_to_euc_jp` rows in `pg_conversion`. The transcoding is
mostly algorithmic (the JIS X 0208 → Shift-JIS bit-rearrangement),
with a small `sjis.map` lookup table covering the "user-defined
character" range (IBM kanji) that doesn't fit the algorithm.

## Public symbols

| Symbol | Line | Notes |
|---|---:|---|
| `PG_MODULE_MAGIC_EXT(.name = "euc_jp_and_sjis", …)` | 30 | Module identity. |
| `PG_FUNCTION_INFO_V1(euc_jp_to_sjis)` | 35 | fmgr V1. |
| `PG_FUNCTION_INFO_V1(sjis_to_euc_jp)` | 36 | fmgr V1. |
| `PGSJISALTCODE` (macro) | 22 | SJIS replacement char `0x81ac`. |
| `PGEUCALTCODE` (macro) | 23 | EUC_JP replacement char `0xa2ae`. |
| `sjis.map` (included header) | 28 | Static lookup table for the IBM-kanji UDC range. |
| `euc_jp2sjis` (static, fwd decl) | 52 | EUC_JP → SJIS worker. |
| `sjis2euc_jp` (static, fwd decl) | 53 | SJIS → EUC_JP worker. |
| `euc_jp_to_sjis` (`Datum`) | 55 | fmgr entry. |
| `sjis_to_euc_jp` (`Datum`) | 71 | fmgr entry. |

## Internal landmarks

- Standard 6-arg fmgr unpack in both Datum functions.
- `CHECK_ENCODING_CONVERSION_ARGS(PG_EUC_JP, PG_SJIS)` (line 64) and
  inverse on line 80.
- The Datum entry points delegate to `euc_jp2sjis` / `sjis2euc_jp`,
  which iterate byte-by-byte, branch on `SS2`/`SS3` shift markers for
  EUC_JP plane-2/3 input, and run the JIS X 0208 ↔ Shift-JIS
  bit-rearrangement inline.
- The `sjis.map` table covers the IBM-kanji UDC (user-defined
  character) range — those bytes can't be derived algorithmically
  and have to be looked up.
- When a codepoint has no mapping, the worker substitutes
  `PGSJISALTCODE` / `PGEUCALTCODE` (the "alternate code") if
  `noError = true`, otherwise reports
  `report_untranslatable_char(...)`.
- Returns `PG_RETURN_INT32(converted)`.

## Invariants & gotchas

- Loaded via fmgr from `pg_conversion`.
- The substitution-on-failure behaviour with `PGSJISALTCODE` /
  `PGEUCALTCODE` is **unique to this conversion proc** — most others
  bail out (or break on `noError`) without writing replacement
  bytes. The `noError` branch here still writes the alt-code, so
  the caller can keep accumulating output.
- The Shift-JIS encoding does not represent the full JIS X 0212 set
  ("supplementary" kanji); attempting to convert EUC_JP plane-3
  characters to SJIS hits the alt-code path.
- JIS X 0213:2004 needs a different transcoder
  (`euc2004_sjis2004/euc2004_sjis2004.c`).
- UTF-8 paths use `utf8_and_euc_jp.c` and `utf8_and_sjis.c`
  separately.
- Invalid input → `ereport(ERROR, ...CHARACTER_NOT_IN_REPERTOIRE)`
  unless `noError = true`.

## Cross-refs

- `knowledge/files/src/backend/utils/mb/conv.c.md` — shared helpers
  (`pg_encoding_verifymbchar`, `report_invalid_encoding`).
- `knowledge/files/src/backend/utils/mb/conversion_procs/utf8_and_euc_jp/utf8_and_euc_jp.c.md`
  — UTF-8 sibling for EUC_JP.
- `knowledge/files/src/backend/utils/mb/conversion_procs/utf8_and_sjis/utf8_and_sjis.c.md`
  — UTF-8 sibling for SJIS.
- `knowledge/files/src/backend/utils/mb/conversion_procs/euc2004_sjis2004/euc2004_sjis2004.c.md`
  — analogous JIS X 0213:2004 direct transcoder.
- `source/src/backend/utils/mb/conversion_procs/euc_jp_and_sjis/sjis.map`
  — the IBM-kanji UDC lookup table consumed via `#include`.
- `source/src/include/mb/pg_wchar.h` — `PG_EUC_JP`, `PG_SJIS`,
  `SS2`, `SS3`.

## Synthesized by
<!-- backlinks:auto -->
