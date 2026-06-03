# pg_propgraph_label.h

- **Source path:** `source/src/include/catalog/pg_propgraph_label.h`
- **Last verified commit:** `4b0bf0788b0`

## Purpose

Per-(property-graph, label-name) row. The set of labels belonging to a property graph; each label can be attached to one or more elements via `pg_propgraph_element_label`. Header has no narrative comment beyond the file banner. [inferred]

## Catalog definition

- `CATALOG(pg_propgraph_label, 6470, PropgraphLabelRelationId)` — no BKI markings beyond defaults; PG 18+. [verified-by-code]
- `FormData_pg_propgraph_label` typedef; pointer alias `Form_pg_propgraph_label`. [verified-by-code]

## Columns

| Column | Type | BKI marking | LOOKUP target |
|---|---|---|---|
| `oid` | `Oid` | — | — |
| `pglpgid` | `Oid` | — | `pg_class` (the property-graph relation) |
| `pgllabel` | `NameData` | — | — |

No `CATALOG_VARLEN` block. [verified-by-code]

## Key declarations beyond FormData

- `DECLARE_UNIQUE_INDEX_PKEY(pg_propgraph_label_oid_index, 6471, ...)`. [verified-by-code]
- `DECLARE_UNIQUE_INDEX(pg_propgraph_label_graph_name_index, 6478, ...)` on `(pglpgid, pgllabel)` — labels are unique per graph. [verified-by-code]
- `MAKE_SYSCACHE(PROPGRAPHLABELOID, ...)` and `MAKE_SYSCACHE(PROPGRAPHLABELNAME, ..., 128)`. [verified-by-code]

## Cross-refs

- Parent overview: `knowledge/files/src/include/catalog/_catalog_headers_overview.md`
- Companions: `pg_propgraph_element.h.md`, `pg_propgraph_element_label.h.md`, `pg_propgraph_label_property.h.md`, `pg_propgraph_property.h.md`
- Backend: `source/src/backend/commands/propgraphcmds.c`.

## Potential issues

- **[ISSUE-DOCS: empty header comment block]** `pg_propgraph_label.h:1-14` — no purpose line. [from-comment]

## Tally

`[verified-by-code]=5 [from-comment]=1 [inferred]=1`
