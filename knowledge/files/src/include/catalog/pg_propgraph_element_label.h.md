# pg_propgraph_element_label.h

- **Source path:** `source/src/include/catalog/pg_propgraph_element_label.h`
- **Last verified commit:** `4b0bf0788b0`

## Purpose

Many-to-many edge table associating property-graph elements (`pg_propgraph_element`) with labels (`pg_propgraph_label`). Header has no narrative comment beyond the file banner. [inferred]

## Catalog definition

- `CATALOG(pg_propgraph_element_label, 6472, PropgraphElementLabelRelationId)` — no BKI markings beyond defaults; PG 18+. [verified-by-code]
- `FormData_pg_propgraph_element_label` typedef; pointer alias `Form_pg_propgraph_element_label`. [verified-by-code]

## Columns

| Column | Type | BKI marking | LOOKUP target |
|---|---|---|---|
| `oid` | `Oid` | — | — |
| `pgellabelid` | `Oid` | — | `pg_propgraph_label` |
| `pgelelid` | `Oid` | — | `pg_propgraph_element` |

No `CATALOG_VARLEN` block. [verified-by-code]

## Key declarations beyond FormData

- `DECLARE_UNIQUE_INDEX_PKEY(pg_propgraph_element_label_oid_index, 6476, ...)`. [verified-by-code]
- `DECLARE_UNIQUE_INDEX(pg_propgraph_element_label_element_label_index, 6477, ...)` on `(pgelelid, pgellabelid)`. [verified-by-code]
- `DECLARE_INDEX(pg_propgraph_element_label_label_index, 6481, ...)` on `(pgellabelid)` — non-unique, for reverse lookups. [verified-by-code]
- `MAKE_SYSCACHE(PROPGRAPHELEMENTLABELELEMENTLABEL, ..., 128)` — only one syscache (no by-OID syscache). [verified-by-code]

## Cross-refs

- Parent overview: `knowledge/files/src/include/catalog/_catalog_headers_overview.md`
- Companions: `pg_propgraph_element.h.md`, `pg_propgraph_label.h.md`, `pg_propgraph_label_property.h.md`
- Backend: `source/src/backend/commands/propgraphcmds.c`.

## Potential issues

- **[ISSUE-DOCS: empty header comment block]** `pg_propgraph_element_label.h:1-14` — file banner has no purpose line beyond the filename. New PG18 catalog deserves a one-line description for consistency with sibling TS / pg_class headers. [from-comment]
- **[ISSUE-CACHE: no by-oid syscache]** `pg_propgraph_element_label.h:52-53` — only `PROPGRAPHELEMENTLABELELEMENTLABEL` exists. Lookups by `oid` (e.g. from `pg_depend.objid`) must fall back to systable scan via `pg_propgraph_element_label_oid_index`. [inferred]

## Tally

`[verified-by-code]=6 [from-comment]=1 [inferred]=2`
