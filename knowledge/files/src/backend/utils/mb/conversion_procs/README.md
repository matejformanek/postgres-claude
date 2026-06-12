---
path: src/backend/utils/mb/conversion_procs/
anchor_sha: e18b0cb7344
depth: directory
---

# conversion_procs/ — per-encoding-pair conversion modules

## Purpose

This directory holds 21 build subdirectories (the `Makefile`'s
`SUBDIRS`; the on-disk listing also shows `utf8_and_uhc` for 21
total), each producing one small shared object that is loaded on
demand by the per-backend `dfmgr.c` dynamic-loader the first time a
session needs that conversion. Each `pg_conversion` catalog row names
the C function inside one of these `.so`s. The set covers every
encoding pair PG declares supported in `pg_wchar.h` — the bulk are
`UTF8 ↔ <legacy>`, plus a handful of direct legacy↔legacy pairs that
sidestep the round-trip through Unicode (e.g. `euc_jp_and_sjis`,
`latin2_and_win1250`, `cyrillic/` which packs koi8r/iso8859-5/win1251/alt
into one module).

Every module follows the same fmgr V1 contract:

```
conv_proc(
    INTEGER,    -- source encoding id  (PG_GETARG_INT32(0))
    INTEGER,    -- destination encoding id (PG_GETARG_INT32(1))
    CSTRING,    -- source string (PG_GETARG_CSTRING(2))
    CSTRING,    -- pre-allocated dest buffer (PG_GETARG_CSTRING(3))
    INTEGER,    -- source length in bytes (PG_GETARG_INT32(4))
    BOOL        -- noError: if true, return short count instead of ereport
                --   (PG_GETARG_BOOL(5))
) RETURNS INTEGER  -- number of bytes successfully consumed
```

The bodies are almost always 1-2 paragraphs of glue: call
`CHECK_ENCODING_CONVERSION_ARGS(src, dst)` (a macro in
`src/include/mb/pg_wchar.h` that sanity-checks args 0/1 against
expected encoding IDs and throws on `PG_GETARG_CSTRING` arg 3 being
NULL), then dispatch to one of the shared helpers in
`source/src/backend/utils/mb/conv.c`:

- `LocalToUtf(src, len, dest, &<enc>_to_unicode_tree, ..., encoding,
  noError)` — single-byte/multi-byte legacy → UTF-8 via a sorted radix
  tree.
- `UtfToLocal(src, len, dest, &<enc>_from_unicode_tree, ..., encoding,
  noError)` — UTF-8 → legacy via the reverse tree.
- `local2local(src, dest, len, srcenc, dstenc, table, noError)` — flat
  256-byte direct-mapping for legacy↔legacy pairs (single-byte only).

The radix-tree map data (`<enc>_to_unicode_tree`,
`<enc>_from_unicode_tree`) is `#include`d as a generated C header from
`src/backend/utils/mb/Unicode/`; those headers are *generated* by the
Perl scripts in `Unicode/` from upstream `unicode.org` tables and are
NOT to be hand-edited.

## Coverage table

LOC counts at `e18b0cb7344`. "Doc" column points to a per-file doc
when one exists; otherwise this README is the canonical reference.

| Module | Encodings | LOC | Doc | Notes |
|---|---|---:|---|---|
| `cyrillic/cyrillic.c` | KOI8R ↔ ISO-8859-5 ↔ WIN1251 ↔ ALT (direct pairs, no UTF8) | 491 | this README | Largest module; hand-written tables, no radix tree. 4 encodings, 12 conversion procs. |
| `euc2004_sjis2004/euc2004_sjis2004.c` | EUC_JIS_2004 ↔ SHIFT_JIS_2004 | 404 | this README | Direct JP↔JP; uses combined-character maps for multi-codepoint runs. |
| `euc_jp_and_sjis/euc_jp_and_sjis.c` | EUC_JP ↔ SJIS | 329 | this README | Direct JP↔JP, no UTF-8 hop. |
| `euc_tw_and_big5/euc_tw_and_big5.c` + `big5.c` | EUC_TW ↔ BIG5 | 229+377 | this README | Two C files: `big5.c` is a helper table; `euc_tw_and_big5.c` is the entry points. |
| `utf8_and_gb18030/utf8_and_gb18030.c` | UTF8 ↔ GB18030 | 241 | this README | GB18030 is a 4-byte superset of GBK; needs a custom range mapper alongside the radix tree. |
| `utf8_and_iso8859/utf8_and_iso8859.c` | UTF8 ↔ ISO-8859-{2,3,4,5,6,7,8,9,10,13,14,15,16} (13 variants in one module) | 172 | `utf8_and_iso8859.c.md` (deep) | Multi-encoding dispatch via `pg_conv_map[]` table. |
| `utf8_and_win/utf8_and_win.c` | UTF8 ↔ WIN866/874/1250/1251/1252/1253/1254/1255/1256/1257/1258 | 153 | this README | Windows code pages; same multi-encoding dispatch pattern as `utf8_and_iso8859`. |
| `utf8_and_iso8859_1/utf8_and_iso8859_1.c` | UTF8 ↔ ISO-8859-1 | 142 | this README | Special-cased separately because ISO-8859-1 is a direct subset of U+0000-U+00FF: open-coded loop, no radix tree. |
| `utf8_and_cyrillic/utf8_and_cyrillic.c` | UTF8 ↔ KOI8R/KOI8U/WIN1251 | 129 | this README | 3-encoding dispatch. |
| `latin2_and_win1250/latin2_and_win1250.c` | LATIN2 ↔ WIN1250 | 113 | `latin2_and_win1250.c.md` (deep) | Direct non-UTF8 pair; uses `local2local` and two 128-byte tables. |
| `utf8_and_big5/utf8_and_big5.c` | UTF8 ↔ BIG5 | 81 | `utf8_and_big5.c.md` (deep) | Canonical "trivial UTF8↔CJK" shape. |
| `utf8_and_euc_cn/utf8_and_euc_cn.c` | UTF8 ↔ EUC_CN | 81 | this README | Identical shape to `utf8_and_big5`. |
| `utf8_and_euc_jp/utf8_and_euc_jp.c` | UTF8 ↔ EUC_JP | 81 | this README | Identical shape. |
| `utf8_and_euc_kr/utf8_and_euc_kr.c` | UTF8 ↔ EUC_KR | 81 | this README | Identical shape. |
| `utf8_and_euc_tw/utf8_and_euc_tw.c` | UTF8 ↔ EUC_TW | 81 | this README | Identical shape. |
| `utf8_and_gbk/utf8_and_gbk.c` | UTF8 ↔ GBK | 81 | this README | Identical shape. |
| `utf8_and_johab/utf8_and_johab.c` | UTF8 ↔ JOHAB | 81 | this README | Identical shape; combined-character map used internally for some codepoints. |
| `utf8_and_sjis/utf8_and_sjis.c` | UTF8 ↔ SJIS | 81 | this README | Identical shape. |
| `utf8_and_uhc/utf8_and_uhc.c` | UTF8 ↔ UHC | 81 | this README | Identical shape. |
| `utf8_and_euc2004/utf8_and_euc2004.c` | UTF8 ↔ EUC_JIS_2004 | 81 | this README | Identical shape. |
| `utf8_and_sjis2004/utf8_and_sjis2004.c` | UTF8 ↔ SHIFT_JIS_2004 | 81 | this README | Identical shape. |

Total: 22 conversion modules on disk; 21 are wired into the Makefile
`SUBDIRS` list (`utf8_and_uhc` is present in both source and Makefile).

## Common pattern

For the 9 "trivial UTF8↔legacy" modules at 81 LOC each:

1. `PG_MODULE_MAGIC_EXT(.name = "<modname>", .version = PG_VERSION);`
   declares the shared object as a PG loadable module. (Older trees
   used the legacy `PG_MODULE_MAGIC` macro; the `_EXT` variant
   landed in PG 18 and is now required by `dfmgr.c`.)
2. `PG_FUNCTION_INFO_V1(<encA>_to_<encB>);` and
   `PG_FUNCTION_INFO_V1(<encB>_to_<encA>);` register the two
   conversion procs.
3. Each `Datum`-returning function:
   - reads its six args via `PG_GETARG_*`,
   - calls `CHECK_ENCODING_CONVERSION_ARGS(<expected_src>,
     <expected_dst>)` — note: this macro reads `PG_GETARG_INT32(0)`
     and `PG_GETARG_INT32(1)` directly, so the caller must pass
     a *constant* pair of encoding IDs that match what `pg_conversion`
     said this proc handles; mismatched call → `ereport(ERROR,
     ERRCODE_INTERNAL_ERROR)`,
   - calls `LocalToUtf` or `UtfToLocal` with the `&<enc>_to_unicode_tree`
     or `&<enc>_from_unicode_tree` pointer from the `#include`d map,
   - returns the byte count via `PG_RETURN_INT32(converted)`.

For the multi-encoding modules (`utf8_and_iso8859`, `utf8_and_win`,
`utf8_and_cyrillic`): instead of hard-coding one source/dest pair,
they build a static `pg_conv_map` array keyed by `pg_enc` and
dispatch on the runtime arg-0 encoding ID. The `CHECK_ENCODING_*`
call uses `-1` as a wildcard for whichever side is variable.

For the direct legacy↔legacy modules (`cyrillic`,
`latin2_and_win1250`, `euc_jp_and_sjis`, `euc_tw_and_big5`,
`euc2004_sjis2004`): no radix tree; instead a 128-byte table covering
the high-half of the byte range, fed to `local2local` (from
`conv.c:33`).

## Invariants

- The fmgr arg shape `(int4, int4, cstring, cstring, int4, bool) →
  int4` is fixed by `pg_conversion`'s declaration and the
  `CHECK_ENCODING_CONVERSION_ARGS` macro in
  `source/src/include/mb/pg_wchar.h`. Adding a 7th arg would break
  every loader. [verified-by-code; all 22 files use exactly args
  0-5]
- Returned byte count is the number of *input* bytes successfully
  consumed, not the number of output bytes written. The destination
  buffer is pre-allocated by the caller (`pg_do_encoding_conversion`
  in `mbutils.c`) at 4× the source length to absorb the worst
  per-codepoint expansion.
- Map headers under `Unicode/` are generated artefacts — see
  `Unicode/UCS_to_*.pl`. The radix-tree binary format
  (`pg_mb_radix_tree`) is shared with `LocalToUtf`/`UtfToLocal` and
  cannot drift between the generator and the consumer.
- Every conversion proc must be safe to call from any backend in any
  database: no shared state, no GUC dependence, no MemoryContext
  assumptions beyond the per-tuple context the caller installs.
- `noError = true` callers (used by `pg_any_to_server` for client
  message preflight in `pqcomm.c` paths) must NEVER `ereport(ERROR)`
  on unmappable input — they must instead truncate and return the
  short byte count. `LocalToUtf`/`UtfToLocal`/`local2local` enforce
  this in `conv.c`; the per-module glue inherits the contract.

## Potential issues / gotchas

- `utf8_and_iso8859` only services *9* of the 13 ISO-8859-* encodings
  via its `maps[]` table (LATIN2-LATIN10 + ISO_8859_5/6/7/8); the
  others (LATIN1 in `_iso8859_1/`) live in separate modules. The
  module's "unexpected encoding ID" `ereport` at line 130 covers the
  defensive case where a `pg_conversion` row points an iso8859_*_*
  proc at a non-iso encoding ID. Adding a new ISO-8859-* variant
  requires *both* a new map under `Unicode/` *and* a new row in
  `maps[]`.
- The legacy `cyrillic.c` (491 LOC) is the only module that does NOT
  go through `Unicode/`-generated tables. Its 128-byte translation
  tables are hand-maintained against KOI8R/ISO-8859-5/WIN1251/ALT
  charts. Any "fix" here is high-blast-radius because the same byte
  in the source table affects all 12 conversion procs the file
  exports.

## Cross-refs

- `knowledge/files/src/backend/utils/mb/conv.c.md` — the shared
  `LocalToUtf` / `UtfToLocal` / `local2local` helpers.
- `knowledge/files/src/backend/utils/mb/_conversion_procs.md` — flat
  summary doc (predates this README; eventually subsumed).
- `knowledge/files/src/backend/utils/mb/mbutils.c.md` — the
  `pg_do_encoding_conversion` driver that allocates dest buffers and
  invokes each proc through fmgr.
- `source/src/include/mb/pg_wchar.h` — `pg_enc` enum,
  `CHECK_ENCODING_CONVERSION_ARGS` macro, `pg_mb_radix_tree` layout.
- `source/src/backend/utils/mb/Unicode/` — the radix-tree generator
  Perl scripts and downloaded `unicode.org` reference tables.

## Synthesized by
<!-- backlinks:auto -->
