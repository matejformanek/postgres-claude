# pg_ts_template.h

- **Source path:** `source/src/include/catalog/pg_ts_template.h`
- **Last verified commit:** `4b0bf0788b0`

## Purpose

"Definition of the 'text search template' system catalog (pg_ts_template)." A template names the C-function pair (`tmplinit`, `tmpllexize`) used to instantiate dictionaries. [from-comment]

## Catalog definition

- `CATALOG(pg_ts_template, 3764, TSTemplateRelationId)` — no BKI markings beyond defaults. [verified-by-code]
- `FormData_pg_ts_template` typedef; pointer alias `Form_pg_ts_template`. [verified-by-code]

## Columns

| Column | Type | BKI marking | LOOKUP target |
|---|---|---|---|
| `oid` | `Oid` | — | — |
| `tmplname` | `NameData` | — | — |
| `tmplnamespace` | `Oid` | `BKI_DEFAULT(pg_catalog)` | `pg_namespace` |
| `tmplinit` | `regproc` | `BKI_LOOKUP_OPT` (may be 0) | `pg_proc` |
| `tmpllexize` | `regproc` | — | `pg_proc` |

No `CATALOG_VARLEN` block. [verified-by-code]

## Key declarations beyond FormData

- `DECLARE_UNIQUE_INDEX(pg_ts_template_tmplname_index, 3766, ...)` on `(tmplname, tmplnamespace)`. [verified-by-code]
- `DECLARE_UNIQUE_INDEX_PKEY(pg_ts_template_oid_index, 3767, ...)` on `(oid)`. [verified-by-code]
- `MAKE_SYSCACHE(TSTEMPLATENAMENSP, ...)` and `MAKE_SYSCACHE(TSTEMPLATEOID, ...)`. [verified-by-code]

## Cross-refs

- Parent overview: `knowledge/files/src/include/catalog/_catalog_headers_overview.md`
- Consumer: `knowledge/files/src/include/catalog/pg_ts_dict.h.md` (via `dicttemplate`)
- Runtime cache: `source/src/backend/utils/cache/ts_cache.c`.

## Tally

`[verified-by-code]=6 [from-comment]=1`
