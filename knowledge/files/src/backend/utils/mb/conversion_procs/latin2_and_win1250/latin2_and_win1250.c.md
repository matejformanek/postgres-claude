---
path: src/backend/utils/mb/conversion_procs/latin2_and_win1250/latin2_and_win1250.c
anchor_sha: e18b0cb7344
loc: 113
depth: read
---

# `latin2_and_win1250.c` — LATIN2 ↔ WIN1250 (direct, no UTF-8 hop)

## Purpose

Conversion proc for the **Central European pair ISO-8859-2 (LATIN2)
↔ Windows-1250** without round-tripping through UTF-8. Both are
single-byte encodings; the high half (bytes 0x80-0xFF) is reshuffled
between them. The module ships two hand-curated 128-byte tables and
dispatches via `local2local()` (from `source/src/backend/utils/mb/conv.c:33`)
which does a direct byte-by-byte substitution.

This is the canonical "direct legacy↔legacy pair" shape; compare
the larger `cyrillic/cyrillic.c` (4 encodings, 12 procs, 491 LOC)
and the JP-pair modules (`euc_jp_and_sjis/`,
`euc2004_sjis2004/`) which use the same `local2local`-style direct
substitution at higher fan-out.

## Public symbols

| Symbol | Line | Notes |
|---|---:|---|
| `latin2_to_win1250` (`Datum`, fmgr V1) | 81 | LATIN2 → WIN1250. |
| `win1250_to_latin2` (`Datum`, fmgr V1) | 98 | WIN1250 → LATIN2. |
| `PG_MODULE_MAGIC_EXT(.name = "latin2_and_win1250", .version = PG_VERSION)` | 18 | |
| `PG_FUNCTION_INFO_V1(latin2_to_win1250)` | 23 | fmgr V1 registration. |
| `PG_FUNCTION_INFO_V1(win1250_to_latin2)` | 24 | fmgr V1 registration. |

## Internal landmarks

- `static const unsigned char win1250_2_iso88592[128]` (lines 41-58) —
  hand-maintained table mapping the high half of WIN1250 to LATIN2.
  Entries of `0x00` mark codepoints that exist in WIN1250 but have
  no LATIN2 equivalent (e.g. WIN1250's curly quotes at 0x91-0x94,
  the bullet at 0x95, etc.).
- `static const unsigned char iso88592_2_win1250[128]` (lines 61-78)
  — reverse table.
- The two `Datum` functions are 16 lines each; both call
  `CHECK_ENCODING_CONVERSION_ARGS(PG_LATIN2, PG_WIN1250)` /
  `(PG_WIN1250, PG_LATIN2)` and then dispatch into `local2local(src,
  dest, len, srcenc, dstenc, table, noError)` from `conv.c`.
- The table indexing inside `local2local` (in `conv.c`) is implicitly
  `table[byte - 0x80]`, so the 128-entry table covers byte values
  0x80-0xFF; the ASCII half (< 0x80) is passed through unchanged.

## Invariants

- Both tables are exactly 128 entries (0x80-0xFF). Adding/removing
  rows would silently corrupt all conversions; there's no length
  assertion in the C code (only a `lengthof`-style check in the
  helper would catch it, and `local2local` doesn't do one).
- Table entries of `0x00` are the sentinel for "no equivalent". The
  `local2local` helper recognises 0 as untranslatable and either
  raises (`noError = false`) or returns the short byte count
  (`noError = true`).
- The two tables MUST be exact inverses *modulo* the unmappable
  entries: applying `latin2_to_win1250` then `win1250_to_latin2` to
  a fully-mappable LATIN2 string must yield the original.
  Verifying this by hand is the only safety net; there is no
  generated cross-check.
- `CHECK_ENCODING_CONVERSION_ARGS(PG_LATIN2, PG_WIN1250)` is a
  *constant* macro call (no wildcards), so this proc only handles
  the exact LATIN2 ↔ WIN1250 pair — `pg_conversion` rows pointing at
  it for any other pair would `ereport(ERRCODE_INTERNAL_ERROR)`.

## Potential issues

- **Tables are hand-maintained** — no `Unicode/` generator scripts
  produce them. The `.map` headers don't apply here because the
  conversion sidesteps Unicode entirely. Updating either table
  requires careful audit against the authoritative
  WIN1250/ISO-8859-2 charts; a one-byte typo could swap two
  unrelated letters at large scale.
- **Asymmetric coverage.** WIN1250 has more printable characters in
  its high half than LATIN2; ~12 entries in `win1250_2_iso88592`
  legitimately map to `0x00` (untranslatable). This is *expected*
  but means the round-trip is *lossy* in the WIN1250→LATIN2→WIN1250
  direction. Documented behavior; not a bug.
- **No combined-character map.** Both encodings are strict
  single-byte; multi-codepoint Unicode sequences (e.g. base + combining
  accent) are inaccessible from these tables. A user with composed
  characters that survive only via UTF-8 must route through one of
  the `utf8_and_*` modules instead.
- The "WIN1250 0x88" entry maps to LATIN2 0x88 (line 43 column 1),
  which is in the C1 control range in both encodings — technically
  defined as "undefined" in WIN1250. The mapping is identity-passthrough
  to avoid losing such bytes, but a stricter validator might prefer
  `0x00` here. Conservative call; not flagging as a bug.

## Cross-refs

- `knowledge/files/src/backend/utils/mb/conversion_procs/README.md` —
  directory overview; lists this as the canonical direct-pair shape.
- `knowledge/files/src/backend/utils/mb/conv.c.md` — `local2local`
  helper at line 33.
- `source/src/include/mb/pg_wchar.h` — `PG_LATIN2` and `PG_WIN1250`
  enum values, `CHECK_ENCODING_CONVERSION_ARGS` macro.
- Sibling modules using the same `local2local` shape:
  `cyrillic/cyrillic.c`, `euc_jp_and_sjis/euc_jp_and_sjis.c`,
  `euc2004_sjis2004/euc2004_sjis2004.c`, `euc_tw_and_big5/big5.c`.

## Synthesized by
<!-- backlinks:auto -->
