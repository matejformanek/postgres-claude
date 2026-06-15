---
path: src/backend/utils/mb/conversion_procs/cyrillic/cyrillic.c
anchor_sha: e18b0cb7344
loc: 491
depth: read
---

# `cyrillic.c` — KOI8-R / WIN1251 / WIN866 / ISO-8859-5 pairwise transcoders

## Purpose

Conversion proc for **pairwise Cyrillic transcodings that do not
involve UTF-8**: KOI8-R, ISO-8859-5, Windows-1251 (CP1251), and
Windows-866 (CP866). Backs twelve `pg_conversion` rows (every
ordered pair among the four). All transcoding is via small static
**byte→byte translation tables** (single-byte encodings, no
multi-byte handling required); the file is dominated by these
tables.

## Public symbols

| Symbol | Line | Notes |
|---|---:|---|
| `PG_MODULE_MAGIC_EXT(.name = "cyrillic", …)` | 18 | Module identity. |
| `PG_FUNCTION_INFO_V1(koi8r_to_win1251)` | 23 | fmgr V1. |
| `PG_FUNCTION_INFO_V1(win1251_to_koi8r)` | 24 | fmgr V1. |
| `PG_FUNCTION_INFO_V1(koi8r_to_win866)` | 25 | fmgr V1. |
| `PG_FUNCTION_INFO_V1(win866_to_koi8r)` | 26 | fmgr V1. |
| `PG_FUNCTION_INFO_V1(win866_to_win1251)` | 27 | fmgr V1. |
| `PG_FUNCTION_INFO_V1(win1251_to_win866)` | 28 | fmgr V1. |
| `PG_FUNCTION_INFO_V1(iso_to_koi8r)` | 29 | fmgr V1. |
| `PG_FUNCTION_INFO_V1(koi8r_to_iso)` | 30 | fmgr V1. |
| `PG_FUNCTION_INFO_V1(iso_to_win1251)` | 31 | fmgr V1. |
| `PG_FUNCTION_INFO_V1(win1251_to_iso)` | 32 | fmgr V1. |
| `PG_FUNCTION_INFO_V1(iso_to_win866)` | 33 | fmgr V1. |
| `PG_FUNCTION_INFO_V1(win866_to_iso)` | 34 | fmgr V1. |
| Static tables `iso2koi`, `iso2win1251`, `iso2win866`, `win12512koi`, `koi2win1251`, `koi2win866`, `win8662koi`, `win8662win1251`, `win12512win866`, and reverse maps | 61+ | 128-byte tables (one entry per high-bit byte). |
| `koi8r_to_win1251` (`Datum`) | 301 | First fmgr entry. |
| ... twelve Datums, one per pair direction ... | 301, 317, 333, 349, 365, 381, 397, 413, 429, 445, 461, 477 | Standard 6-arg fmgr unpack each. |

## Internal landmarks

- Tables (lines 61+) are 128-byte `static const unsigned char[]`
  arrays mapping the upper half (`0x80`–`0xFF`) of one encoding to
  the corresponding byte in the target encoding; a `0x00` entry
  marks an untranslatable code point.
- Each Datum function (lines 301-491, every 16 lines) follows the
  same shape: 6-arg fmgr unpack →
  `CHECK_ENCODING_CONVERSION_ARGS(<src>, <dst>)` → call
  `local2local(src, dest, len, <src>, <dst>, table, noError)` →
  `PG_RETURN_INT32(converted)`.
- `local2local` (declared in `mb/pg_wchar.h`, defined in
  `src/backend/utils/mb/conv.c`) is the shared single-byte-to-single-byte
  walker: for each high-bit-set source byte, look up
  `table[byte - 0x80]`; if zero, raise (or break on `noError`); else
  store the mapped byte.
- ASCII bytes (high bit clear) are copied verbatim by `local2local`
  — the tables only cover high-bit codepoints.

## Invariants & gotchas

- Loaded via fmgr from `pg_conversion`. Twelve `pg_conversion` rows
  point at this single shared object.
- Single-byte encodings only — no length validation beyond "src
  bytes have a 0x80-mapped table entry or not". `noError = true`
  returns the partial byte count; otherwise an untranslatable byte
  raises `ereport(ERROR, ...UNTRANSLATABLE_CHARACTER)`.
- The pairwise tables MUST be symmetric (e.g. `koi2win1251[c-0x80]`
  must be inverted by `win12512koi`); historical drift would silently
  break round-trip preservation. There is no automated test that
  verifies symmetry — the regression test `conversion.sql` exercises
  end-to-end SQL conversion.
- Each table has gaps (`0x00`) where the source codepoint has no
  representation in the target — that is the "untranslatable" signal
  to `local2local`.
- KOI8 ↔ UTF-8 transcoders are NOT here; they live in
  `utf8_and_cyrillic/utf8_and_cyrillic.c`.

## Cross-refs

- `knowledge/files/src/backend/utils/mb/conv.c.md` — `local2local`
  worker.
- `knowledge/files/src/backend/utils/mb/conversion_procs/utf8_and_cyrillic/utf8_and_cyrillic.c.md`
  — UTF-8 sibling.
- `knowledge/files/src/backend/utils/mb/conversion_procs/utf8_and_win/utf8_and_win.c.md`
  — broader Windows codepage dispatcher (covers WIN1251 / WIN866
  in the UTF-8 dimension).
- `source/src/include/mb/pg_wchar.h` — `PG_KOI8R`, `PG_WIN1251`,
  `PG_WIN866`, `PG_ISO_8859_5` enum values.

## Synthesized by
<!-- backlinks:auto -->
