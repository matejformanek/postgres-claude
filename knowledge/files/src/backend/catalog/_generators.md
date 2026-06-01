# Catalog generators (genbki.pl, Catalog.pm, system_*.sql, information_schema.sql)

- **Source path:** `source/src/backend/catalog/`
- **Last verified commit:** `ef6a95c7c64`

This doc covers the four non-C generator inputs in the catalog directory.

## genbki.pl (~32 KB)

Perl script run at build time. Reads every `pg_*.h` header under `src/include/catalog/`, recognises the `CATALOG()`, `BKI_BOOTSTRAP`, `BKI_SHARED_RELATION`, `BKI_ROWTYPE_OID`, `BKI_LOOKUP`, `BKI_DEFAULT` macros (defined as empty in `genbki.h` for the C compiler), pairs each header with its sibling `.dat` data file, and emits:

- `src/backend/catalog/postgres.bki` — the **bootstrap script** consumed by `bootstrap/bootstrap.c` during `initdb`. Declares every catalog, inserts the bootstrap-required rows (pg_proc, pg_type, pg_class entries for the catalogs themselves, etc.).
- `src/backend/catalog/postgres.description` — initial pg_description rows.
- `src/backend/catalog/postgres.shdescription` — initial pg_shdescription rows.
- `src/include/catalog/system_fk_info.h` — recorded FK relationships for the documentation generator.
- `src/include/catalog/pg_*_d.h` — one per catalog, with `#define <NAME>_oid` constants and the `Anum_<catalog>_<column>` attribute-number macros consumed by C source code. **Critical**: every `*_d.h` is generated; never edit it.

## Catalog.pm (~15 KB)

Perl module loaded by `genbki.pl`, `reformat_dat_file.pl`, `renumber_oids.pl`, and the documentation builders. Exports parsers for:

- Catalog header files (CATALOG() blocks, FormData declarations).
- `.dat` files (a restricted Perl-Data-Dumper-like syntax: list of hashrefs).
- The `BKI_LOOKUP(catalog)` and `BKI_LOOKUP_OPT(catalog)` macros that say "this column refers to oid in pg_X; resolve symbolic names at BKI-emit time".

`Catalog.pm`'s `RenameTempFile` / `ParseHeader` / `ParseData` are the canonical readers — any new tool that processes catalog input should use them rather than rolling its own parser.

## system_functions.sql (~10 KB)

CREATE OR REPLACE FUNCTION statements that **complete** functions whose pg_proc row was created by the bootstrap (with placeholder prosrc) — usually because the function body references SQL syntax (CASE, COALESCE, ARRAY) that can't be expressed in a `.dat` file string literal. Examples: `make_interval`, `jsonb_path_query_first`, default-value wrapper functions. Run after bootstrap during initdb.

## system_views.sql (~58 KB)

CREATE VIEW + CREATE MATERIALIZED VIEW for every standard system view (`pg_stat_*`, `pg_locks`, `pg_replication_slots`, `pg_publication_tables`, `pg_settings`, `pg_user`, `pg_roles`, `pg_indexes`, …). Run during initdb. Edited frequently as new monitoring views are added.

## information_schema.sql (~125 KB)

The SQL-standard `information_schema` schema: thousands of lines of CREATE VIEW that wrap PG's pg_catalog into the standard-mandated shape. Run during initdb. Driven by the spec; edits are rare and align to SQL standard updates.

## Build flow

```
.dat + pg_*.h
   │
   ▼
genbki.pl (uses Catalog.pm)
   │
   ├──► postgres.bki + postgres.{des,shdes}cription   ──► consumed by bootstrap.c
   └──► pg_*_d.h                                       ──► #included from .c
```

During initdb:

```
bootstrap.c reads postgres.bki   → catalogs + pinned rows exist
              │
              ▼
system_functions.sql              → patch placeholder pg_proc rows
              │
              ▼
system_views.sql                   → create pg_stat_*, pg_user, etc.
              │
              ▼
information_schema.sql             → create information_schema views
```

## Confidence tag tally

`[verified-by-code]=2 [from-comment]=3 [inferred]=2`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
