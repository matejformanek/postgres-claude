# `src/backend/utils/adt/pg_locale_builtin.c`

- **File:** `source/src/backend/utils/adt/pg_locale_builtin.c` (298
  lines)
- **Source pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`

## Purpose

The **builtin locale provider** — PG-internal collation/ctype tables
that don't require libc or ICU. Supports three locale names: `"C"`,
`"C.UTF-8"`, and `"PG_UNICODE_FAST"` (the latter is the new fast
Unicode-aware ctype provider). All three are `memcmp`-based for
collation; only ctype/casemap varies. (`pg_locale_builtin.c:275-298`
[from-comment])

## Key functions

- `create_pg_locale_builtin(collid, context)` (`:227`):
  1. Reads `colllocale` from pg_collation (or `datlocale` from
     pg_database for the default OID).
  2. Calls `builtin_validate_locale(GetDatabaseEncoding(), locstr)`
     (`:260`) — rejects invalid combinations (e.g. `C.UTF-8` with a
     non-UTF8 DB encoding).
  3. Sets `collate_is_c = true` always (no strcoll variation).
  4. Sets `ctype_is_c = (locstr == "C")` — only the literal C locale
     bypasses ctype methods.
- `get_collation_actual_version_builtin(collcollate)` (`:275`) —
  returns `"1"` for the three supported names, errors otherwise.
- `wc_isdigit_builtin` etc. (`:128-200`) — Unicode-table-driven ctype
  predicates and `wc_toupper`/`wc_tolower` (`:194, 200`).
- `strlower_builtin` / `strtitle_builtin` / `strupper_builtin` /
  `strfold_builtin` (`:86-126`) — case operations with full or simple
  casemap based on `casemap_full` flag.
- `initcap_wbnext` (`:59`) — wordbreak iterator for `initcap`.

## Phase D notes

- **Locale name validation**: `builtin_validate_locale` (called at
  `:260`) is the single entry-point check. If a user creates a
  collation with `provider=builtin, locale=BOGUS`, this errors at
  CREATE COLLATION time, not at usage time.
- The three valid names are hard-coded; **no shell-out, no libc
  setlocale**, no fopen, no untrusted file reads. The builtin
  provider is therefore the most-isolated of the three.
- Ctype methods use Unicode tables baked into the binary
  (`source/src/common/unicode_*.c`); behavior changes between PG
  major versions if Unicode tables are updated.

## Potential issues

- [ISSUE-info-disclosure: `errmsg("invalid locale name \"%s\" for
  builtin provider", collcollate)` (`:293-295`) echoes the user-
  supplied locale name in the error. Acceptable; comes from DBA-
  controlled SQL. (low)]
- [ISSUE-correctness: collation version is hardcoded "1" for all
  three locales (`:285-290`). If Unicode tables in the build change
  ctype semantics, the collversion does NOT bump — but the comment
  at `:282-283` explicitly says collversion only tracks sort order,
  which is memcmp-stable. So ctype behavior changes silently after
  upgrade. (informational, by design)]

## Cross-references

- `source/src/include/utils/pg_locale_c.h` — `pg_locale_struct`,
  `collate_methods` / `ctype_methods` interfaces.
- `source/src/common/unicode_norm.c`,
  `source/src/common/unicode_category.c` — backing tables.
- `source/src/backend/utils/adt/pg_locale.c` — dispatcher.

## Confidence tag tally

- `[verified-by-code]` × 4
- `[from-comment]` × 2
