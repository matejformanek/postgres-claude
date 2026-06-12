---
path: src/backend/utils/mb/conversion_procs/utf8_and_big5/utf8_and_big5.c
anchor_sha: e18b0cb7344
loc: 81
depth: read
---

# `utf8_and_big5.c` — UTF-8 ↔ BIG5

## Purpose

Conversion proc for the Traditional Chinese **BIG5 ↔ UTF-8** pair.
This is the *canonical* "trivial UTF8↔CJK" module in
`conversion_procs/`: at 81 LOC, it is byte-identical in shape to
`utf8_and_euc_cn.c`, `utf8_and_euc_jp.c`, `utf8_and_euc_kr.c`,
`utf8_and_euc_tw.c`, `utf8_and_gbk.c`, `utf8_and_johab.c`,
`utf8_and_sjis.c`, `utf8_and_uhc.c`, `utf8_and_euc2004.c`, and
`utf8_and_sjis2004.c` — only the encoding ID, map names, and
function names differ.

The actual conversion work happens in the generated radix tree
(`big5_to_unicode_tree`, `big5_from_unicode_tree` from
`../../Unicode/big5_to_utf8.map` and `../../Unicode/utf8_to_big5.map`)
and in the shared `LocalToUtf` / `UtfToLocal` helpers in
`source/src/backend/utils/mb/conv.c`. This file is pure glue.

## Public symbols

| Symbol | Line | Notes |
|---|---:|---|
| `big5_to_utf8` (`Datum`, fmgr V1) | 42 | BIG5 → UTF-8 entry point. |
| `utf8_to_big5` (`Datum`, fmgr V1) | 63 | UTF-8 → BIG5 entry point. |
| `PG_MODULE_MAGIC_EXT(.name = "utf8_and_big5", .version = PG_VERSION)` | 20 | Module identity. |
| `PG_FUNCTION_INFO_V1(big5_to_utf8)` | 25 | fmgr V1 registration. |
| `PG_FUNCTION_INFO_V1(utf8_to_big5)` | 26 | fmgr V1 registration. |

## Internal landmarks

- `#include "../../Unicode/big5_to_utf8.map"` (line 17) defines
  `big5_to_unicode_tree` — a static `pg_mb_radix_tree` covering all
  ~13,500 mappable BIG5 codepoints.
- `#include "../../Unicode/utf8_to_big5.map"` (line 18) defines the
  reverse tree.
- `big5_to_utf8` (lines 42-60): standard 6-arg unpack →
  `CHECK_ENCODING_CONVERSION_ARGS(PG_BIG5, PG_UTF8)` →
  `LocalToUtf(src, len, dest, &big5_to_unicode_tree, NULL, 0, NULL,
  PG_BIG5, noError)` → `PG_RETURN_INT32(converted)`.
- `utf8_to_big5` (lines 63-81): mirror image with `UtfToLocal` and
  `&big5_from_unicode_tree`.

## Invariants

- Both functions consume exactly the 6-arg fmgr V1 signature:
  `(int4 src_encoding, int4 dst_encoding, cstring src, cstring dest,
  int4 len, bool noError) → int4`. The first two args are
  consistency-checked by `CHECK_ENCODING_CONVERSION_ARGS` against the
  expected pair (PG_BIG5/PG_UTF8); a mismatch raises
  `ERRCODE_INTERNAL_ERROR`.
- The 4th-5th args to `LocalToUtf`/`UtfToLocal` (`NULL, 0`) declare
  "no combined-character map" — BIG5 ↔ Unicode is one-to-one (no
  single BIG5 byte sequence requires multiple Unicode codepoints to
  represent). This is *not* true for JOHAB or GB18030, which pass a
  non-NULL combined-char map.
- The destination buffer (`dest`, arg 3) is pre-allocated by the
  caller at ≥ `len * MAX_CONVERSION_GROWTH` bytes — UTF-8 expansion
  from a single BIG5 byte-pair is bounded.
- `noError = true` requires the helper to return the partial byte
  count on first untranslatable input rather than `ereport(ERROR)`.
  This contract lives in `LocalToUtf`/`UtfToLocal` in `conv.c`; this
  file just hands the flag through.

## Potential issues

- The implementation is so uniform that an auto-generation step
  (Perl script that emits all 11 "trivial" UTF8↔CJK .c files from a
  single template) would be straightforward. There is none today —
  each file is checked in by hand. Drift between the 11 files would
  manifest as inconsistent error reporting or stale
  `PG_MODULE_MAGIC` macros; the upgrade to `PG_MODULE_MAGIC_EXT` in
  PG 18 was applied to all 11 in lockstep.
- `PG_BIG5` is hard-coded twice (lines 50, 56) as both the
  `CHECK_ENCODING_CONVERSION_ARGS` source side AND the encoding ID
  passed to `LocalToUtf`. A mismatch here (e.g. a copy-paste error
  from another UTF8↔X module) would survive the macro check but
  produce silent garbage during conversion. There's no unit test
  that exercises this invariant directly; the `conversion.sql`
  regression test relies on end-to-end SQL conversion to expose it.

## Cross-refs

- `knowledge/files/src/backend/utils/mb/conversion_procs/README.md` —
  directory README, lists all 11 "trivial UTF8↔CJK" modules.
- `knowledge/files/src/backend/utils/mb/conv.c.md` — `LocalToUtf` /
  `UtfToLocal`.
- `source/src/backend/utils/mb/Unicode/UCS_to_BIG5.pl` — generator
  for the `.map` headers.
- `source/src/include/mb/pg_wchar.h` — `PG_BIG5` enum value,
  `pg_mb_radix_tree` layout.

## Synthesized by
<!-- backlinks:auto -->
