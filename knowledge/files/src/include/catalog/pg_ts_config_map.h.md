# pg_ts_config_map.h

- **Source path:** `source/src/include/catalog/pg_ts_config_map.h`
- **Last verified commit:** `4b0bf0788b0`

## Purpose

"Definition of the system catalog for text search token mappings (pg_ts_config_map)." Per-(configuration, token-type) rows naming, in `mapseqno` order, which dictionaries to consult for that token type. [from-comment]

## Catalog definition

- `CATALOG(pg_ts_config_map, 3603, TSConfigMapRelationId)` — no BKI markings beyond defaults. **No `oid` column** — this is a many-to-many edge table keyed by `(mapcfg, maptokentype, mapseqno)`. [verified-by-code]
- `FormData_pg_ts_config_map` typedef; pointer alias `Form_pg_ts_config_map`. [verified-by-code]

## Columns

| Column | Type | BKI marking | LOOKUP target |
|---|---|---|---|
| `mapcfg` | `Oid` | — | `pg_ts_config` |
| `maptokentype` | `int32` | — | — |
| `mapseqno` | `int32` | — | — |
| `mapdict` | `Oid` | — | `pg_ts_dict` |

No `CATALOG_VARLEN` block. [verified-by-code]

## Key declarations beyond FormData

- `DECLARE_UNIQUE_INDEX_PKEY(pg_ts_config_map_index, 3609, TSConfigMapIndexId, ...)` on `(mapcfg, maptokentype, mapseqno)`. [verified-by-code]
- `MAKE_SYSCACHE(TSCONFIGMAP, pg_ts_config_map_index, 2)`. [verified-by-code]

## Cross-refs

- Parent overview: `knowledge/files/src/include/catalog/_catalog_headers_overview.md`
- Companion: `knowledge/files/src/include/catalog/pg_ts_config.h.md` (owner, via `mapcfg`)
- Companion: `knowledge/files/src/include/catalog/pg_ts_dict.h.md` (target of `mapdict`)
- `maptokentype` values come from the parser's `prslextype` function — see `pg_ts_parser.h.md`.

## Tally

`[verified-by-code]=4 [from-comment]=1`
