---
source_url: https://www.postgresql.org/docs/current/system-catalog-declarations.html
fetched_at: 2026-06-14T19:48:00Z
anchor_sha: e18b0cb7344
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Docs distilled — System Catalog Declaration Rules (§68.1)

How a `src/include/catalog/pg_*.h` header declares a catalog so `genbki.pl` can
turn it into `postgres.bki`. Docs companion to the `catalog-conventions` skill;
quote the skill for the OID-assignment + catversion-bump procedure, this for the
macro surface.

## CATALOG(...) is a struct typedef in disguise

- **`CATALOG(catalogname, oid, oidmacro)`** expands to `typedef struct
  FormData_<catalogname>` — the C struct whose fields are the catalog's columns,
  mapping the **fixed-length head of each catalog tuple**. The struct's `oid`
  argument is the catalog relation's own OID. [from-docs]
- Catalog-level property macros (in `genbki.h`) annotate the whole relation:
  **`BKI_BOOTSTRAP`** (a bootstrap catalog), **`BKI_SHARED_RELATION`** (a
  cluster-wide / shared catalog like pg_database). [from-docs]
  [cross: skill `catalog-conventions`]

## Variable-length / nullable columns must hide behind CATALOG_VARLEN

- **Fixed-length columns first; all variable-length or nullable columns go at the
  end**, wrapped in **`#ifdef CATALOG_VARLEN`** so C code can't read them as plain
  struct fields (their offset isn't fixed). Reaching past the last fixed column in
  C is a bug — use `heap_getattr` / the SysCache instead. [from-docs]
- Column-level property macros: **`BKI_DEFAULT(value)`** (the default that
  `reformat_dat_file.pl` elides from `.dat`), **`BKI_FORCE_NOT_NULL`** /
  **`BKI_FORCE_NULL`** (override the inferred nullability), **`BKI_LOOKUP(rule)`**
  (mark an OID column as a symbolic foreign-key reference). [from-docs]
  [cross: knowledge/docs-distilled/system-catalog-initial-data.md]

## Bootstrap catalogs are special — avoid creating new ones

- A handful of catalogs (pg_class, pg_type, pg_attribute, pg_proc) are too
  fundamental to be made by the BKI `create` command; their `pg_class`/`pg_type`
  rows are hand-pre-loaded and `pg_attribute` rows are filled by `genbki.pl`.
  The docs explicitly **recommend not making any new catalog a bootstrap
  catalog** — the extra maintenance burden isn't worth it. [from-docs]

## Frontend isolation: include pg_xxx_d.h, not pg_xxx.h

- Client/frontend code must **not** include `pg_xxx.h` (it can carry backend-only
  C). Instead include the **generated `pg_xxx_d.h`**, which holds the OID
  `#define`s and any data marked **`#ifdef EXPOSE_TO_CLIENT_CODE`**. This split is
  what lets `pg_dump` / psql know catalog OIDs without dragging in backend headers. [from-docs]

## genbki.pl is the generator

- **`genbki.pl`** reads these headers (+ the `.dat` files) and emits
  `postgres.bki` plus the per-catalog `pg_xxx_d.h`. A struct/column change in the
  header is only "real" once it's run through this generator into the BKI. [from-docs]
  [cross: knowledge/docs-distilled/bki.md]

## Links into corpus
- Skill: **`catalog-conventions`** — the procedure for adding a catalog column / OID / catversion bump.
- [[knowledge/docs-distilled/system-catalog-initial-data.md]] — the `.dat` side these declarations are filled from.
- [[knowledge/docs-distilled/bki.md]] / [[knowledge/docs-distilled/bki-structure.md]] — what the emitted postgres.bki looks like.
- [[knowledge/docs-distilled/catalogs-overview.md]] — (if present) the catalog set these declare.

## Gaps / follow-ups
- The page references but does not explain `DECLARE_INDEX` /
  `DECLARE_UNIQUE_INDEX` / `DECLARE_TOAST` / `MAKE_SYS_CACHE` /
  `DECLARE_OID_DEFINING_MACRO` / `BKI_ROWTYPE_OID` / `BKI_SCHEMA_MACRO` — those
  live in `genbki.h` comments; see the `catalog-conventions` skill or the header
  directly for the index/toast/syscache declaration macros.
