# pg_ts_config.h

- **Source path:** `source/src/include/catalog/pg_ts_config.h`
- **Last verified commit:** `4b0bf0788b0`

## Purpose

"Definition of the 'text search configuration' system catalog (pg_ts_config)." Each row defines a named TS configuration that binds a parser to a set of token-type→dictionary mappings (held in `pg_ts_config_map`). [from-comment]

## Catalog definition

- `CATALOG(pg_ts_config, 3602, TSConfigRelationId)` — no BKI markings beyond defaults; per-DB, not bootstrap. [verified-by-code]
- `FormData_pg_ts_config` typedef; pointer alias `Form_pg_ts_config`. [verified-by-code]

## Columns

| Column | Type | BKI marking | LOOKUP target |
|---|---|---|---|
| `oid` | `Oid` | — | — |
| `cfgname` | `NameData` | — | — |
| `cfgnamespace` | `Oid` | `BKI_DEFAULT(pg_catalog)` | `pg_namespace` |
| `cfgowner` | `Oid` | `BKI_DEFAULT(POSTGRES)` | `pg_authid` |
| `cfgparser` | `Oid` | — | `pg_ts_parser` |

No `CATALOG_VARLEN` block; all fields fixed-width. [verified-by-code]

## Key declarations beyond FormData

- `DECLARE_UNIQUE_INDEX(pg_ts_config_cfgname_index, 3608, TSConfigNameNspIndexId, ...)` on `(cfgname, cfgnamespace)`. [verified-by-code]
- `DECLARE_UNIQUE_INDEX_PKEY(pg_ts_config_oid_index, 3712, TSConfigOidIndexId, ...)` on `(oid)`. [verified-by-code]
- `MAKE_SYSCACHE(TSCONFIGNAMENSP, ...)` and `MAKE_SYSCACHE(TSCONFIGOID, ...)`. [verified-by-code]

## Cross-refs

- Parent overview: `knowledge/files/src/include/catalog/_catalog_headers_overview.md`
- Companion: `knowledge/files/src/include/catalog/pg_ts_config_map.h.md` (the per-token-type mapping rows owned by each cfg)
- Companion: `knowledge/files/src/include/catalog/pg_ts_parser.h.md` (target of `cfgparser`)
- Runtime cache: `source/src/backend/utils/cache/ts_cache.c` consumes these rows.

## Tally

`[verified-by-code]=5 [from-comment]=1`
