# `src/backend/utils/adt/pg_locale.c`

- **File:** `source/src/backend/utils/adt/pg_locale.c` (1851 lines)
- **Header:** `source/src/include/utils/pg_locale.h`,
  `source/src/include/utils/pg_locale_c.h`
- **Source pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`

## Purpose

Provider-agnostic dispatch for locale-sensitive operations
(collation/`strcoll`, ctype/`tolower`, monetary/numeric/time
localization). Routes calls to one of three provider backends —
**builtin** (`pg_locale_builtin.c`), **ICU** (`pg_locale_icu.c`), or
**libc** (`pg_locale_libc.c`) — based on `pg_collation.collprovider`.
(`pg_locale.c:11-29` [from-comment])

## Architecture: per-collation `pg_locale_t`

- LC_COLLATE / LC_CTYPE are **per-database** (fixed at CREATE
  DATABASE), so `strcoll`-style operations always run in one of a
  finite set of locales. Each is materialized lazily as a
  `pg_locale_t`.
- LC_MESSAGES is **session-settable**, applied via global libc state.
- LC_MONETARY / LC_NUMERIC / LC_TIME are **always "C"** in PG; the GUCs
  of the same names produce per-call `locale_t` objects, cached.
- `default_locale` (`:1168`) holds the database default, populated by
  `init_database_collation` at startup (`:1130`).

## Key entry points

- `create_pg_locale(collid, context)` (`:1048`) — fetches
  `pg_collation` row, dispatches on `collprovider` (COLLPROVIDER_BUILTIN
  / ICU / LIBC) (`:1062-1070`). Returns palloc'd `pg_locale_t`.
- `pg_newlocale_from_collation(collid)` (`:1188`) — **cached**
  wrapper. Results live in `CollationCacheContext` for the backend
  lifetime; no free required (`:1181-1187` [from-comment]).
- `pg_database_locale()` (`:1174`) → `pg_newlocale_from_collation(
  DEFAULT_COLLATION_OID)`.
- `lookup_collation_cache(collid)` (`:~1200`) — hashtable lookup,
  insertion. Cache keyed by collation OID.
- **Collation operations** (all dispatch on `locale->collate->*`):
  `pg_strcoll`, `pg_strncoll` (`:1381, 1400`).
  `pg_strxfrm` (`:1430`), `pg_strnxfrm` — transformed-key generation.
  `pg_strxfrm_enabled(locale)` (`:1414`) — boolean for sortsupport.
  `pg_strxfrm_prefix_enabled` / `pg_strxfrm_prefix` (`:1465, 1476`)
  — prefix transform for abbreviated keys.

## Version checking (`:1080-1120`)

On `create_pg_locale`, the stored `collversion` (TEXT in pg_collation)
is compared against the live provider's actual version. Mismatch →
`WARNING` with errhint to `ALTER COLLATION ... REFRESH VERSION`. This
is the **silent-data-corruption-after-OS-upgrade** mitigation: indexes
built under glibc 2.27 may sort differently under glibc 2.28.
[verified-by-code]

## Phase D notes

- **Locale identifier validation**: handled per-provider. `pg_locale.c`
  itself does no string parsing of locale names; it just hands them
  to `make_libc_collator` / `make_icu_collator` / `make_builtin_*`.
  See `pg_locale_icu.c` and `pg_locale_libc.c`.
- **GUC `icu_validation_level`** (`:92`) — `WARNING` by default;
  controls whether unrecognized ICU options elevate to error. User-
  facing via SQL `CREATE COLLATION (provider=icu, locale=...)`.
- **Process-wide setlocale calls** — pg_locale.c does set
  LC_MESSAGES globally on GUC change (via the libc helpers); this is
  safe because Postgres backends are single-threaded.
- The `pg_strxfrm_enabled` decision tree is the load-bearing part
  for abbreviated-key sort support; see varlena.c for consumer.

## Potential issues

- [ISSUE-correctness: version-mismatch is WARNING-only, not ERROR.
  Continuing to use an index built with an obsolete collation version
  silently risks wrong query results. Per the errhint, the burden is
  on the operator to REFRESH. (informational, by design)]
- [ISSUE-undocumented-invariant: `default_locale` is a process-global
  pointing into `TopMemoryContext`; never freed for the life of the
  backend. Each backend's first-touch path resolves it; no contention
  but each backend independently parses locale-name → ICU/libc state.
  (informational)]
- [ISSUE-info-disclosure: `errdetail` in version-mismatch warning
  echoes the stored collversion verbatim (`:1112-1114`). Acceptable;
  collversion comes from DBA-controlled CREATE COLLATION. (low)]

## Cross-references

- `source/src/backend/utils/adt/pg_locale_builtin.c`
- `source/src/backend/utils/adt/pg_locale_icu.c`
- `source/src/backend/utils/adt/pg_locale_libc.c`
- `source/src/include/catalog/pg_collation.h` — `Form_pg_collation`.
- `source/src/backend/utils/adt/varlena.c` — primary consumer of
  pg_strcoll/pg_strxfrm.

## Confidence tag tally

- `[verified-by-code]` × 7
- `[from-comment]` × 3
