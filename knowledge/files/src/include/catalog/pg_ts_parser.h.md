# pg_ts_parser.h

- **Source path:** `source/src/include/catalog/pg_ts_parser.h`
- **Last verified commit:** `4b0bf0788b0`

## Purpose

"Definition of the 'text search parser' system catalog (pg_ts_parser)." Each row binds a parser name to its five C-function callbacks (start/token/end/headline/lextype). [from-comment]

## Catalog definition

- `CATALOG(pg_ts_parser, 3601, TSParserRelationId)` — no BKI markings beyond defaults. [verified-by-code]
- `FormData_pg_ts_parser` typedef; pointer alias `Form_pg_ts_parser`. [verified-by-code]

## Columns

| Column | Type | BKI marking | LOOKUP target |
|---|---|---|---|
| `oid` | `Oid` | — | — |
| `prsname` | `NameData` | — | — |
| `prsnamespace` | `Oid` | `BKI_DEFAULT(pg_catalog)` | `pg_namespace` |
| `prsstart` | `regproc` | — | `pg_proc` |
| `prstoken` | `regproc` | — | `pg_proc` |
| `prsend` | `regproc` | — | `pg_proc` |
| `prsheadline` | `regproc` | `BKI_LOOKUP_OPT` (may be 0) | `pg_proc` |
| `prslextype` | `regproc` | — | `pg_proc` |

No `CATALOG_VARLEN` block. [verified-by-code]

## Key declarations beyond FormData

- `DECLARE_UNIQUE_INDEX(pg_ts_parser_prsname_index, 3606, ...)` on `(prsname, prsnamespace)`. [verified-by-code]
- `DECLARE_UNIQUE_INDEX_PKEY(pg_ts_parser_oid_index, 3607, ...)` on `(oid)`. [verified-by-code]
- `MAKE_SYSCACHE(TSPARSERNAMENSP, ...)` and `MAKE_SYSCACHE(TSPARSEROID, ...)`. [verified-by-code]

## Cross-refs

- Parent overview: `knowledge/files/src/include/catalog/_catalog_headers_overview.md`
- Consumer: `knowledge/files/src/include/catalog/pg_ts_config.h.md` (via `cfgparser`)
- Runtime cache: `source/src/backend/utils/cache/ts_cache.c` resolves these regprocs.

## Tally

`[verified-by-code]=6 [from-comment]=1`
