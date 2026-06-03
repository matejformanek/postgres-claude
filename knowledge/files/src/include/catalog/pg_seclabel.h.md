# pg_seclabel.h

- **Source path:** `source/src/include/catalog/pg_seclabel.h`
- **Last verified commit:** `4b0bf0788b0`

## Purpose

`SECURITY LABEL` storage for per-database objects. One row per (object, provider) — multiple label providers (sepgsql, custom) can coexist for the same object via the `provider` column.

## Catalog definition

- `CATALOG(pg_seclabel, 3596, SecLabelRelationId)` — per-DB; no shared/bootstrap. [verified-by-code] `pg_seclabel.h:30`
- `FormData_pg_seclabel` typedef (no `Form_pg_seclabel` alias declared in this header). [verified-by-code] `pg_seclabel.h:41`

## Columns

| Column | Type | BKI marking | LOOKUP target |
|---|---|---|---|
| objoid | Oid | — | — (OID of the labeled object) |
| classoid | Oid | BKI_LOOKUP | `pg_class` (catalog containing the object) |
| objsubid | int32 | — | — (column number, or 0) |
| provider | text (varlena) | BKI_FORCE_NOT_NULL | — (under `#ifdef CATALOG_VARLEN`) |
| label | text (varlena) | BKI_FORCE_NOT_NULL | — (under `#ifdef CATALOG_VARLEN`) |

## Key declarations beyond FormData

- `DECLARE_TOAST(pg_seclabel, 3598, 3599)`. [verified-by-code] `pg_seclabel.h:45`
- `DECLARE_UNIQUE_INDEX_PKEY(pg_seclabel_object_index, 3597, ...)` on (objoid, classoid, objsubid, provider). [verified-by-code] `pg_seclabel.h:47`

## Cross-refs

- Parent overview: `knowledge/files/src/include/catalog/_catalog_headers_overview.md`
- Related: `pg_shseclabel.h` (shared-object sibling)
- Related backend: `src/backend/catalog/objectaddress.c`, `src/backend/commands/seclabel.c`

## Potential issues

- **[ISSUE-undocumented-invariant: label text is opaque to PG, parsed only by provider]** `pg_seclabel.h:38-39` — the `label` text is interpreted entirely by the registered label provider (e.g. sepgsql). Header has no comment noting this is a provider-defined opaque payload — a future reviewer could think it's a regular string and add a citext-style normalization. Severity `nit`, type `undocumented-invariant`.
- **[ISSUE-question: no Form_pg_seclabel typedef]** `pg_seclabel.h:41` — most catalog headers declare both `FormData_X` and `Form_X` (pointer alias). This one only declares the struct. Likely intentional because callers always go through `GetSecurityLabel`/`SetSharedSecurityLabel`, but inconsistent with the rest of the directory. Severity `nit`, type `style`.

## Tally

`[verified-by-code]=7 [inferred]=2`
