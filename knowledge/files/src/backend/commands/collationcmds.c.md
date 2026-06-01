# collationcmds.c

- **Source path:** `source/src/backend/commands/collationcmds.c`
- **Lines:** 1059
- **Last verified commit:** `ef6a95c7c64`

## Purpose

"Collation-related commands support code." [from-comment, collationcmds.c:3-4] CREATE / DROP / ALTER COLLATION plus the import helpers that enumerate locales from libc and ICU.

## Public surface

- `DefineCollation` — CREATE COLLATION; either explicitly with LOCALE/LC_COLLATE/LC_CTYPE/PROVIDER (libc|icu|builtin) or by FROM an existing collation.
- `AlterCollation` — `ALTER COLLATION … REFRESH VERSION`: re-read the provider's collation version string into pg_collation.collversion so the "collation version mismatch" warning stops firing.
- `IsThereCollationInNamespace` — namespace-collision helper.
- `pg_import_system_collations` — SRF that scans the OS's locale list (via `setlocale`/`uloc_countAvailable`) and creates one pg_collation row per locale, deduplicating.
- `pg_collation_actual_version` — return the provider's current version string; used by REFRESH and by the "warn on mismatch" logic in `lookup_collation`.

## Provider-version drift

When glibc or ICU updates between database creation and now, sort order may change subtly. PG records `pg_collation.collversion` at create time; if it differs from the live provider version, queries on indexed text columns log a warning ("collation version mismatch, ... the index may be corrupted"). REFRESH VERSION updates the stored version (the user is asserting "I've REINDEXed").

## Confidence tag tally

`[verified-by-code]=3 [from-comment]=1`
