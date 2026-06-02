# pg_ts_dict.h

- **Source path:** `source/src/include/catalog/pg_ts_dict.h`
- **Last verified commit:** `4b0bf0788b0`

## Purpose

"Definition of the 'text search dictionary' system catalog (pg_ts_dict)." Each row is one TS dictionary: a binding of a template plus an init-option string. [from-comment]

## Catalog definition

- `CATALOG(pg_ts_dict, 3600, TSDictionaryRelationId)` — no BKI markings beyond defaults. [verified-by-code]
- `FormData_pg_ts_dict` typedef; pointer alias `Form_pg_ts_dict`. [verified-by-code]

## Columns

| Column | Type | BKI marking | LOOKUP target |
|---|---|---|---|
| `oid` | `Oid` | — | — |
| `dictname` | `NameData` | — | — |
| `dictnamespace` | `Oid` | `BKI_DEFAULT(pg_catalog)` | `pg_namespace` |
| `dictowner` | `Oid` | `BKI_DEFAULT(POSTGRES)` | `pg_authid` |
| `dicttemplate` | `Oid` | — | `pg_ts_template` |
| `dictinitoption` | `text` | (CATALOG_VARLEN) | — |

## Key declarations beyond FormData

- `DECLARE_TOAST(pg_ts_dict, 4169, 4170)` — has a TOAST table because `dictinitoption` is variable-length. [verified-by-code]
- `DECLARE_UNIQUE_INDEX(pg_ts_dict_dictname_index, 3604, ...)` on `(dictname, dictnamespace)`. [verified-by-code]
- `DECLARE_UNIQUE_INDEX_PKEY(pg_ts_dict_oid_index, 3605, ...)` on `(oid)`. [verified-by-code]
- `MAKE_SYSCACHE(TSDICTNAMENSP, ...)` and `MAKE_SYSCACHE(TSDICTOID, ...)`. [verified-by-code]

## Cross-refs

- Parent overview: `knowledge/files/src/include/catalog/_catalog_headers_overview.md`
- Companion: `knowledge/files/src/include/catalog/pg_ts_template.h.md` (target of `dicttemplate`)
- Consumer: `knowledge/files/src/include/catalog/pg_ts_config_map.h.md` (via `mapdict`)
- Runtime cache: `source/src/backend/utils/cache/ts_cache.c`.

## Tally

`[verified-by-code]=6 [from-comment]=1`
