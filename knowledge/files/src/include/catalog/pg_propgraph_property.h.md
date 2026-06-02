# pg_propgraph_property.h

- **Source path:** `source/src/include/catalog/pg_propgraph_property.h`
- **Last verified commit:** `4b0bf0788b0`

## Purpose

Per-(property-graph, property-name) row carrying the property's declared SQL type, typmod, and collation. The actual per-label expression lives in `pg_propgraph_label_property.plpexpr`. Header has no narrative comment beyond the file banner. [inferred]

## Catalog definition

- `CATALOG(pg_propgraph_property, 6473, PropgraphPropertyRelationId)` — no BKI markings beyond defaults; PG 18+. [verified-by-code]
- `FormData_pg_propgraph_property` typedef; pointer alias `Form_pg_propgraph_property`. [verified-by-code]

## Columns

| Column | Type | BKI marking | LOOKUP target |
|---|---|---|---|
| `oid` | `Oid` | — | — |
| `pgppgid` | `Oid` | — | `pg_class` (the property-graph relation) |
| `pgpname` | `NameData` | — | — |
| `pgptypid` | `Oid` | `BKI_LOOKUP_OPT` | `pg_type` |
| `pgptypmod` | `int32` | — | — |
| `pgpcollation` | `Oid` | `BKI_LOOKUP_OPT` | `pg_collation` |

No `CATALOG_VARLEN` block. [verified-by-code]

## Key declarations beyond FormData

- `DECLARE_UNIQUE_INDEX_PKEY(pg_propgraph_property_oid_index, 6474, ...)`. [verified-by-code]
- `DECLARE_UNIQUE_INDEX(pg_propgraph_property_name_index, 6475, ...)` on `(pgppgid, pgpname)` — property names unique per graph. [verified-by-code]
- `MAKE_SYSCACHE(PROPGRAPHPROPOID, ...)` and `MAKE_SYSCACHE(PROPGRAPHPROPNAME, ..., 128)`. [verified-by-code]

## Cross-refs

- Parent overview: `knowledge/files/src/include/catalog/_catalog_headers_overview.md`
- Companions: `pg_propgraph_element.h.md`, `pg_propgraph_label.h.md`, `pg_propgraph_element_label.h.md`, `pg_propgraph_label_property.h.md`
- Backend: `source/src/backend/commands/propgraphcmds.c`.

## Potential issues

- **[ISSUE-DOCS: empty header comment block]** `pg_propgraph_property.h:1-14` — no purpose line. [from-comment]

## Tally

`[verified-by-code]=7 [from-comment]=1 [inferred]=1`
