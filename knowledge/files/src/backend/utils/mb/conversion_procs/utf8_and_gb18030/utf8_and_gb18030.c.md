---
path: src/backend/utils/mb/conversion_procs/utf8_and_gb18030/utf8_and_gb18030.c
anchor_sha: e18b0cb7344
loc: 241
depth: read
---

# `utf8_and_gb18030.c` — GB18030 ↔ UTF-8

## Purpose

Conversion proc for the Simplified Chinese **GB18030 ↔ UTF-8** pair.
GB18030 covers all of Unicode (including U+10000 and up) via a
4-byte form, which can't fit in a static lookup table — the file
provides a hand-coded range-based **callback** for the 4-byte
ranges in addition to the standard radix-tree lookup for 1- and
2-byte codepoints. Backs the `gb18030_to_utf8` and `utf8_to_gb18030`
rows in `pg_conversion`. Consumes `gb18030_to_utf8.map` /
`utf8_to_gb18030.map` from `src/backend/utils/mb/Unicode/`.

## Public symbols

| Symbol | Line | Notes |
|---|---:|---|
| `PG_MODULE_MAGIC_EXT(.name = "utf8_and_gb18030", …)` | 20 | Module identity. |
| `PG_FUNCTION_INFO_V1(gb18030_to_utf8)` | 25 | fmgr V1. |
| `PG_FUNCTION_INFO_V1(utf8_to_gb18030)` | 26 | fmgr V1. |
| `gb_linear` (static inline) | 34 | Pack 4-byte GB18030 into a linear code. |
| `gb_unlinear` (static inline) | 46 | Reverse of `gb_linear`. |
| `unicode_to_utf8word` (static inline) | 62 | Pack a UCS code point into a word-formatted UTF-8 byte sequence. |
| `utf8word_to_unicode` (static inline) | 93 | Reverse of `unicode_to_utf8word`. |
| `conv_18030_to_utf8` (static) | 135 | Range-based 4-byte GB18030 → UTF-8 callback. |
| `conv_utf8_to_18030` (static) | 162 | Range-based UTF-8 → 4-byte GB18030 callback. |
| `gb18030_to_utf8` (`Datum`) | 201 | fmgr entry: GB18030 → UTF-8. |
| `utf8_to_gb18030` (`Datum`) | 222 | fmgr entry: UTF-8 → GB18030. |

## Internal landmarks

- Standard 6-arg fmgr unpack in both Datum functions.
- `CHECK_ENCODING_CONVERSION_ARGS(PG_GB18030, PG_UTF8)` (line 210)
  and inverse on line 231.
- `LocalToUtf(..., NULL, 0, conv_18030_to_utf8, PG_GB18030, noError)`
  (lines 212-217) passes a **per-encoding callback** (7th positional
  arg in the `LocalToUtf` / `UtfToLocal` signature) in place of a
  combined-char map. The worker hits the radix tree first for
  1-/2-byte codepoints, falls back to the callback for everything
  not found there.
- The callback uses the `conv18030(minunicode, mincode, maxcode)`
  macro (lines 138-140) to express 13 ranges (lines 142-154) that
  cover all U+0452 – U+10FFFF GB18030 mappings.
- `gb_linear` / `gb_unlinear` (lines 34-55) convert between a 4-byte
  GB18030 code (e.g. `0x8130D330`) and a contiguous integer index
  — the math is `b0 * 12600 + b1 * 1260 + b2 * 10 + b3` minus the
  `0x81 0x30 0x81 0x30` origin.

## Invariants & gotchas

- Loaded via fmgr from `pg_conversion`.
- This is the only conversion proc in the directory that uses the
  range-callback feature of `LocalToUtf` / `UtfToLocal`. The
  combined-char arg is `NULL, 0` — the two features are mutually
  exclusive in practice (you pass either a combined-char map OR a
  callback, never both).
- The range tables (`conv_18030_to_utf8`, `conv_utf8_to_18030`) MUST
  stay synchronized; an asymmetric edit would silently produce
  unrecoverable round-trip data.
- The byte ranges named in the comments (lines 36-37) — first/third
  byte 0x81-0xFE (126 values), second/fourth byte 0x30-0x39 (10
  values) — are also encoded into `gb_linear`'s multipliers (12600,
  1260, 10). Changing one without the other corrupts the linear
  index.
- Invalid input → `ereport(ERROR, ...CHARACTER_NOT_IN_REPERTOIRE)`
  unless `noError = true`.

## Cross-refs

- `knowledge/files/src/backend/utils/mb/conv.c.md` — `LocalToUtf` /
  `UtfToLocal` workers (which invoke the callback).
- `knowledge/files/src/backend/utils/mb/conversion_procs/utf8_and_gbk/utf8_and_gbk.c.md`
  — 2-byte GBK subset sibling.
- `source/src/include/mb/pg_wchar.h` — `PG_GB18030` enum value.
- Comments in this file link to ICU's GB18030 range documentation
  (htmlpreview link, lines 127-131).

## Synthesized by
<!-- backlinks:auto -->
