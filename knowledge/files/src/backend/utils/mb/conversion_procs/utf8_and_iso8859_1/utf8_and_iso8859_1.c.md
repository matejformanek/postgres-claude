---
path: src/backend/utils/mb/conversion_procs/utf8_and_iso8859_1/utf8_and_iso8859_1.c
anchor_sha: e18b0cb7344
loc: 142
depth: read
---

# `utf8_and_iso8859_1.c` — ISO-8859-1 (LATIN1) ↔ UTF-8

## Purpose

Conversion proc for **ISO-8859-1 ↔ UTF-8**. Because ISO-8859-1
maps directly onto Unicode U+0000–U+00FF, this proc skips the
generic radix-tree machinery and uses a hand-rolled inline byte
loop. Backs the `iso8859_1_to_utf8` and `utf8_to_iso8859_1` rows in
`pg_conversion`. **Does NOT include any `.map` header.**

## Public symbols

| Symbol | Line | Notes |
|---|---:|---|
| `PG_MODULE_MAGIC_EXT(.name = "utf8_and_iso8859_1", …)` | 18 | Module identity. |
| `PG_FUNCTION_INFO_V1(iso8859_1_to_utf8)` | 23 | fmgr V1. |
| `PG_FUNCTION_INFO_V1(utf8_to_iso8859_1)` | 24 | fmgr V1. |
| `iso8859_1_to_utf8` (`Datum`) | 40 | LATIN1 → UTF-8 inline loop. |
| `utf8_to_iso8859_1` (`Datum`) | 76 | UTF-8 → LATIN1 inline loop. |

## Internal landmarks

- Standard 6-arg fmgr unpack.
- `CHECK_ENCODING_CONVERSION_ARGS(PG_LATIN1, PG_UTF8)` (line 50) and
  inverse on line 87.
- `iso8859_1_to_utf8` (line 40): bytewise loop. ASCII subset
  (`!IS_HIGHBIT_SET(c)`) → single-byte copy. High-bit set → emit
  the standard 2-byte UTF-8 sequence `(c >> 6) | 0xC0`,
  `(c & 0x3f) | HIGHBIT`. A null byte aborts with
  `report_invalid_encoding(PG_LATIN1, ...)` unless `noError`.
- `utf8_to_iso8859_1` (line 76): ASCII fast path; otherwise call
  `pg_utf_mblen(src)` to get the UTF-8 sequence length and
  `pg_utf8_islegal(src, l)` to validate. If `l != 2` (i.e. the
  Unicode codepoint is outside U+0080–U+07FF), report
  `report_untranslatable_char(PG_UTF8, PG_LATIN1, ...)` unless
  `noError`. The 2-byte case decodes via
  `c = ((c & 0x1f) << 6) | (src[1] & 0x3f)` and verifies the
  result is in 0x80–0xFF before storing one byte.
- Both functions terminate `*dest = '\0'` after the loop and
  return `PG_RETURN_INT32(src - start)`.

## Invariants & gotchas

- Loaded via fmgr from `pg_conversion`.
- This is the only file in the directory that does NOT call
  `LocalToUtf` / `UtfToLocal`. Hot path performance (ISO-8859-1 ↔ UTF-8
  is by far the most common conversion in PG installations) justifies
  the open-coded loop and avoids the radix-tree allocation entirely.
- The "no map" property means there is no `Unicode/<...>.map`
  generator for this pair — the math IS the spec.
- Embedded NUL handling: an unexpected `\0` in the source is treated
  as an invalid input error (lines 55-60, 92-97) rather than
  truncating the string. That matches the contract of all the other
  conv_procs even though they get NUL handling for free from the
  radix-tree worker.
- Invalid UTF-8 (illegal byte sequence or untranslatable codepoint
  outside 0x80–0xFF) → `ereport(ERROR, ...UNTRANSLATABLE_CHARACTER)`
  unless `noError = true`.

## Cross-refs

- `knowledge/files/src/backend/utils/mb/conv.c.md` — sibling
  helpers `report_invalid_encoding`, `report_untranslatable_char`,
  `pg_utf_mblen`, `pg_utf8_islegal`.
- `knowledge/files/src/backend/utils/mb/conversion_procs/utf8_and_iso8859/`
  — the broader ISO-8859 family (LATIN2..LATIN10), table-driven via
  the generic worker.
- `source/src/include/mb/pg_wchar.h` — `PG_LATIN1`, `IS_HIGHBIT_SET`,
  `HIGHBIT`.

## Synthesized by
<!-- backlinks:auto -->
