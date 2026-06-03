# `src/backend/utils/adt/pg_locale_libc.c`

- **File:** `source/src/backend/utils/adt/pg_locale_libc.c` (1327 lines)
- **Source pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`

## Purpose

The **libc locale provider** — binds Postgres collations to POSIX
`newlocale`/`strcoll_l`/`towupper_l`. Maintains separate code paths
for single-byte encodings, UTF-8, and "other multibyte" (e.g. EUC_JP),
plus a Windows special case using `_create_locale`. (`pg_locale_libc.c`)

## Entry points

- `create_pg_locale_libc(collid, context)` (`:733`):
  1. Read `collcollate` and `collctype` from pg_collation (or
     `datcollate`/`datctype` from pg_database for default OID).
  2. Call `make_libc_collator(collate, ctype)` (`:817`) which
     `newlocale`s the LC_COLLATE/LC_CTYPE locale.
  3. Set `collate_is_c` / `ctype_is_c` based on string comparison to
     `"C"` and `"POSIX"`.
  4. Pick method table based on DB encoding (`:798-803`):
     - UTF-8 → `ctype_methods_libc_utf8`
     - Other multibyte → `ctype_methods_libc_other_mb`
     - Single-byte → `ctype_methods_libc_sb`
- `make_libc_collator(collate, ctype)` (`:817`) — calls `newlocale`
  with `LC_COLLATE_MASK | LC_CTYPE_MASK` when the two strings match,
  else two separate `newlocale` calls and a careful cleanup path. On
  Windows, falls back to `_create_locale(LC_ALL, ...)` and errors out
  if collate ≠ ctype (`:866-874` [verified-by-code]).
- `report_newlocale_failure(localename)` (`:1126`) — central error
  helper. **Echoes the user-supplied locale name** in the errmsg and
  errdetail (`:1147, :1150`). Handles platform-specific `errno`
  quirks (BSD/Win32 don't set errno).

## Per-encoding method tables

- `ctype_methods_libc_sb` (single-byte) — direct `tolower_l`/`toupper_l`
  on the byte value. Functions like `tolower_libc_sb` (`:300`).
- `ctype_methods_libc_other_mb` — multi-byte non-UTF-8: convert each
  char to `wchar_t` via `mbstowcs_l`, apply, convert back. Functions
  `tolower_libc_mb` (`:314`) etc.
- `ctype_methods_libc_utf8` — UTF-8 specialized path; some
  optimizations (ASCII fast-path).
- `strupper_libc_mb` (`:692-731`) — example of the conversion dance:
  - Allocate `wchar_t[srclen + 1]`. Cap with `srclen + 1 > INT_MAX /
    sizeof(wchar_t)` overflow check (`:700-703`).
  - `char2wchar` → loop `towupper_l` → `max_size = curr_char *
    pg_database_encoding_max_length()` for output palloc → `wchar2char`.

## Phase D notes — `setlocale` and thread safety

- **PG is per-process / per-connection-forked**, so the libc global
  `setlocale` state is per-backend. Other backends' locale switches
  do not affect this one. The `newlocale`/`uselocale` API is used
  almost everywhere; bare `setlocale` is reserved for LC_MESSAGES
  (the GUC).
- Helper functions `mbstowcs_l` / `wcstombs_l` (`:1158, 1175`) are
  PG replacements for systems lacking `_l` variants. The non-`_l`
  fallback uses `uselocale(loc)` and restores it (`:1166-1169`) — this
  is the thread-safe way to scope a locale change.
- **Locale name validation**: `newlocale` itself is the validator.
  Unknown names → `errno = ENOENT` → `report_newlocale_failure`.
  PG does NOT validate the string before passing to libc.

## Phase D notes — name injection

- The locale string is read directly from `pg_collation.collcollate`
  / `pg_database.datcollate`, populated by `CREATE
  COLLATION/DATABASE`. So an attacker must already have COLLATION /
  DATABASE creation privilege.
- Passing arbitrary strings to `newlocale` itself is **NOT** a
  shell-out — POSIX `newlocale` doesn't fork/exec. But on glibc,
  custom locale paths via env vars (LOCPATH) could expand the
  filesystem search; PG does not override LOCPATH.
- The fallback path on locale-not-found (`save_errno == ENOENT`)
  emits an errdetail echoing the locale name. Acceptable.

## Potential issues

- [ISSUE-dos: `strupper_libc_mb`'s `palloc_array(wchar_t, srclen+1)`
  is bounded by INT_MAX/sizeof(wchar_t) (`:700`). On platforms with
  4-byte wchar_t and a multi-GB input, the bound is ~500M chars.
  No CFI inside the towupper_l loop (`:710-711`). (low)]
- [ISSUE-correctness: Windows `_create_locale` doesn't support split
  collate/ctype, so PG errors out (`:866-874`). This means a
  Windows-hosted PG can't honor a collation where collate ≠ ctype. A
  known platform limitation. (informational)]
- [ISSUE-info-disclosure: `errdetail("The operating system could not
  find any locale data for the locale name \"%s\".", localename)`
  (`:1150`) echoes the locale name. Acceptable. (low)]
- [ISSUE-undocumented-invariant: PG sets LC_MONETARY/NUMERIC/TIME to
  "C" globally (per pg_locale.c contract); if libc functions invoked
  here rely on the global state, they get C-locale results unless we
  override via `uselocale`. The method tables consistently use `_l`
  variants. (informational)]

## Cross-references

- `source/src/backend/utils/adt/pg_locale.c` — dispatcher.
- `source/src/include/utils/pg_locale_c.h` — method-table typedefs.
- `source/src/backend/commands/collationcmds.c` — CREATE COLLATION.
- `<locale.h>` POSIX — `newlocale`, `strcoll_l`, `uselocale`.

## Confidence tag tally

- `[verified-by-code]` × 8
- `[from-comment]` × 3
- `[inferred]` × 1
