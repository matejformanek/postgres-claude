# pg_propgraph_label_property.h

- **Source path:** `source/src/include/catalog/pg_propgraph_label_property.h`
- **Last verified commit:** `4b0bf0788b0`

## Purpose

Per-(element-label, property) row holding the property expression that maps from the underlying element-table row to the property value when the label is matched. Header has no narrative comment beyond the file banner. [inferred]

## Catalog definition

- `CATALOG(pg_propgraph_label_property, 6482, PropgraphLabelPropertyRelationId)` — no BKI markings beyond defaults; PG 18+. [verified-by-code]
- `FormData_pg_propgraph_label_property` typedef; pointer alias `Form_pg_propgraph_label_property`. [verified-by-code]

## Columns

| Column | Type | BKI marking | LOOKUP target |
|---|---|---|---|
| `oid` | `Oid` | — | — |
| `plppropid` | `Oid` | — | `pg_propgraph_property` |
| `plpellabelid` | `Oid` | — | `pg_propgraph_element_label` |
| `plpexpr` | `pg_node_tree` | `BKI_FORCE_NOT_NULL` (CATALOG_VARLEN) | — |

## Key declarations beyond FormData

- `DECLARE_TOAST(pg_propgraph_label_property, 6483, 6484)` — TOAST for `plpexpr`. [verified-by-code]
- `DECLARE_UNIQUE_INDEX_PKEY(pg_propgraph_label_property_oid_index, 6492, ...)`. [verified-by-code]
- `DECLARE_UNIQUE_INDEX(pg_propgraph_label_property_label_prop_index, 6493, ...)` on `(plpellabelid, plppropid)`. [verified-by-code]
- `MAKE_SYSCACHE(PROPGRAPHLABELPROP, ..., 128)` — only one syscache (no by-OID syscache). [verified-by-code]

## Cross-refs

- Parent overview: `knowledge/files/src/include/catalog/_catalog_headers_overview.md`
- Companions: `pg_propgraph_element.h.md`, `pg_propgraph_label.h.md`, `pg_propgraph_element_label.h.md`, `pg_propgraph_property.h.md`
- Backend: `source/src/backend/commands/propgraphcmds.c`. The `pg_node_tree` in `plpexpr` is a serialized expression tree consumed via `stringToNode()` (see `idioms/parser-and-nodes`).

## Potential issues

- **[ISSUE-DOCS: empty header comment block]** `pg_propgraph_label_property.h:1-14` — no purpose line. [from-comment]
- **[ISSUE-PARSETREE: serialized expr in catalog]** `pg_propgraph_label_property.h:42` — `plpexpr` is a serialized `pg_node_tree`. Any change to primnodes.h / parsenodes.h that affects its out/read func format requires a `CATALOG_VERSION_NO` bump (see `catversion.h`). [inferred]

## Tally

`[verified-by-code]=6 [from-comment]=1 [inferred]=2`
