---
path: src/backend/utils/mb/conversion_procs/utf8_and_cyrillic/utf8_and_cyrillic.c
anchor_sha: e18b0cb7344
loc: 129
depth: read
---

# `utf8_and_cyrillic.c` — KOI8-R/KOI8-U ↔ UTF-8

## Purpose

Conversion proc for the Cyrillic **KOI8-R ↔ UTF-8** and
**KOI8-U ↔ UTF-8** pairs in a single module. Backs four
`pg_conversion` rows: `koi8r_to_utf8`, `utf8_to_koi8r`,
`koi8u_to_utf8`, `utf8_to_koi8u`. Consumes four `.map` headers
(`koi8r_to_utf8.map`, `utf8_to_koi8r.map`, `koi8u_to_utf8.map`,
`utf8_to_koi8u.map`) from `src/backend/utils/mb/Unicode/`.

## Public symbols

| Symbol | Line | Notes |
|---|---:|---|
| `PG_MODULE_MAGIC_EXT(.name = "utf8_and_cyrillic", …)` | 22 | Module identity. |
| `PG_FUNCTION_INFO_V1(utf8_to_koi8r)` | 27 | fmgr V1. |
| `PG_FUNCTION_INFO_V1(koi8r_to_utf8)` | 28 | fmgr V1. |
| `PG_FUNCTION_INFO_V1(utf8_to_koi8u)` | 30 | fmgr V1. |
| `PG_FUNCTION_INFO_V1(koi8u_to_utf8)` | 31 | fmgr V1. |
| `utf8_to_koi8r` (`Datum`) | 47 | UTF-8 → KOI8-R. |
| `koi8r_to_utf8` (`Datum`) | 68 | KOI8-R → UTF-8. |
| `utf8_to_koi8u` (`Datum`) | 89 | UTF-8 → KOI8-U. |
| `koi8u_to_utf8` (`Datum`) | 110 | KOI8-U → UTF-8. |

## Internal landmarks

- Standard 6-arg fmgr unpack in each Datum function.
- Each function calls `CHECK_ENCODING_CONVERSION_ARGS` with the
  expected pair (e.g. `(PG_UTF8, PG_KOI8R)` on line 56).
- Local-to-UTF branches call `LocalToUtf(...)` with the
  `<enc>_to_unicode_tree`; UTF-to-local branches call `UtfToLocal(...)`
  with the `<enc>_from_unicode_tree`. Combined-char map is `NULL, 0`
  throughout — single-byte legacy charsets need no two-codepoint
  canonicalization.
- Returns `PG_RETURN_INT32(converted)`.

## Invariants & gotchas

- Loaded via fmgr from `pg_conversion`.
- Single module covering both KOI8 variants because they share the
  Cyrillic domain and ship together; pg_conversion still has four
  distinct entries with their own oids.
- Note that KOI8 ↔ ISO-8859-5 / Windows-1251 / Windows-866 transcoding
  is NOT in this file — it lives in `cyrillic/cyrillic.c` (no UTF-8
  involvement, table-driven).
- Invalid input → `ereport(ERROR, ...CHARACTER_NOT_IN_REPERTOIRE)`
  unless `noError = true`.

## Cross-refs

- `knowledge/files/src/backend/utils/mb/conv.c.md` — `LocalToUtf` /
  `UtfToLocal`.
- `knowledge/files/src/backend/utils/mb/conversion_procs/cyrillic/cyrillic.c.md`
  — sibling for non-UTF8 Cyrillic transcoders.
- `source/src/include/mb/pg_wchar.h` — `PG_KOI8R`, `PG_KOI8U` enum
  values.

## Synthesized by
<!-- backlinks:auto -->
