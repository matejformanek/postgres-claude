# pg_language.h

- **Source path:** `source/src/include/catalog/pg_language.h`
- **Last verified commit:** `4b0bf0788b0`

## Purpose

"Definition of the 'language' system catalog (pg_language)." One row per procedural language (`internal`, `c`, `sql`, `plpgsql`, …). `[from-comment]`

## Catalog definition

- `CATALOG(pg_language,2612,LanguageRelationId)` — no BKI bootstrap, not shared. `[verified-by-code]`
- `FormData_pg_language` / `Form_pg_language`.

## Columns

| Column | Type | BKI marking | LOOKUP target |
|---|---|---|---|
| oid | Oid | — | — |
| lanname | NameData | — | — |
| lanowner | Oid | `BKI_DEFAULT(POSTGRES)` | `pg_authid` |
| lanispl | bool | `BKI_DEFAULT(f)` | — |
| lanpltrusted | bool | `BKI_DEFAULT(f)` | — |
| lanplcallfoid | Oid | `BKI_DEFAULT(0)` | `pg_proc` (OPT) |
| laninline | Oid | `BKI_DEFAULT(0)` | `pg_proc` (OPT) |
| lanvalidator | Oid | `BKI_DEFAULT(0)` | `pg_proc` (OPT) |
| lanacl | aclitem[1] | `BKI_DEFAULT(_null_)` (varlena) | — |

## Key declarations beyond FormData

- TOAST + indexes: `DECLARE_TOAST(pg_language, 4157, 4158)`; unique `pg_language_name_index`, PK `pg_language_oid_index`. Syscaches: `LANGNAME`, `LANGOID`. `[verified-by-code]`
- No further function prototypes or macros declared in this header.

## Cross-refs

- Parent overview: `knowledge/files/src/include/catalog/_catalog_headers_overview.md`
- `knowledge/files/src/include/catalog/pg_proc.h.md` (prolang → this catalog)
- `knowledge/files/src/include/catalog/pg_authid.h.md` (lanowner)

## Tally

`[verified-by-code]=3 [from-comment]=1`
