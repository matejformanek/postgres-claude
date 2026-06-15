---
path: src/backend/utils/mb/conversion_procs/euc_tw_and_big5/euc_tw_and_big5.c
anchor_sha: e18b0cb7344
loc: 229
depth: read
---

# `euc_tw_and_big5.c` — EUC_TW ↔ BIG5

## Purpose

Direct (no UTF-8 trip) conversion proc for the Traditional Chinese
**EUC_TW ↔ BIG5** pair. Backs the `euc_tw_to_big5` and
`big5_to_euc_tw` rows in `pg_conversion`. The transcoding uses
range-based BIG5↔CNS 11643 tables defined in the sibling file
`big5.c` (which is linked into the same shared object); EUC_TW
itself is a CNS-11643-based EUC variant, so the worker converts
EUC_TW → CNS → BIG5 (and vice versa) inline.

## Public symbols

| Symbol | Line | Notes |
|---|---:|---|
| `PG_MODULE_MAGIC_EXT(.name = "euc_tw_and_big5", …)` | 18 | Module identity. |
| `PG_FUNCTION_INFO_V1(euc_tw_to_big5)` | 23 | fmgr V1. |
| `PG_FUNCTION_INFO_V1(big5_to_euc_tw)` | 24 | fmgr V1. |
| `euc_tw2big5` (static, fwd decl) | 40 | EUC_TW → BIG5 worker. |
| `big52euc_tw` (static, fwd decl) | 41 | BIG5 → EUC_TW worker. |
| `euc_tw_to_big5` (`Datum`) | 43 | fmgr entry. |
| `big5_to_euc_tw` (`Datum`) | 59 | fmgr entry. |

## Internal landmarks

- Standard 6-arg fmgr unpack in both Datum functions.
- `CHECK_ENCODING_CONVERSION_ARGS(PG_EUC_TW, PG_BIG5)` (line 52) and
  inverse on line 68.
- Each Datum function delegates to the local worker; the worker
  loops byte-by-byte, calling `pg_encoding_verifymbchar(PG_EUC_TW,
  ...)` to size each input character, branching on the `SS2`
  shift-marker for plane-2 EUC_TW characters, and consulting the
  `big5.c` lookup tables to translate plane/code pairs into BIG5
  bytes.
- Returns `PG_RETURN_INT32(converted)`.

## Invariants & gotchas

- Loaded via fmgr from `pg_conversion`.
- This is one of two "direct CJK transcoder" pairs in the directory
  (the others are `euc_jp_and_sjis` and `euc2004_sjis2004`). They
  bypass UTF-8 entirely — useful for users who maintain databases in
  legacy CJK encodings and want to convert client output without a
  round-trip.
- BIG5↔CNS is lossy because the two character repertoires don't
  perfectly overlap. Untranslatable input → `ereport(ERROR,
  ...UNTRANSLATABLE_CHARACTER)` unless `noError = true`.
- The shift-byte handling (`c1 == SS2`, line 99) is the EUC_TW
  marker for "the next two bytes are plane-2 CNS"; without it the
  worker would mis-decode multi-plane input.
- `pg_encoding_verifymbchar` may return `-1` for malformed EUC_TW —
  in that case the worker reports `report_invalid_encoding` (or
  breaks out on `noError`).

## Cross-refs

- `knowledge/files/src/backend/utils/mb/conversion_procs/euc_tw_and_big5/big5.c.md`
  — sibling file with the BIG5↔CNS range tables this worker consumes.
- `knowledge/files/src/backend/utils/mb/conv.c.md` — shared helpers
  (`pg_encoding_verifymbchar`, `report_invalid_encoding`,
  `report_untranslatable_char`).
- `knowledge/files/src/backend/utils/mb/conversion_procs/utf8_and_euc_tw/utf8_and_euc_tw.c.md`
  — UTF-8 sibling for EUC_TW (one-to-one, table-driven).
- `knowledge/files/src/backend/utils/mb/conversion_procs/utf8_and_big5/utf8_and_big5.c.md`
  — UTF-8 sibling for BIG5.
- `source/src/include/mb/pg_wchar.h` — `PG_EUC_TW`, `PG_BIG5`,
  `SS2` macro.

## Synthesized by
<!-- backlinks:auto -->
