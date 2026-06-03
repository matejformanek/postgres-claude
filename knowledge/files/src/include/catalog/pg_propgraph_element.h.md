# pg_propgraph_element.h

- **Source path:** `source/src/include/catalog/pg_propgraph_element.h`
- **Last verified commit:** `4b0bf0788b0`

## Purpose

"Definition of the 'property graph elements' system catalog (pg_propgraph_element)." One row per graph element (vertex or edge) declared by `CREATE PROPERTY GRAPH`. Edges additionally carry source/destination references and per-key equality operators. [from-comment]

## Catalog definition

- `CATALOG(pg_propgraph_element, 6466, PropgraphElementRelationId)` — no BKI markings beyond defaults; PG 18+. [verified-by-code]
- `FormData_pg_propgraph_element` typedef; pointer alias `Form_pg_propgraph_element`. [verified-by-code]

## Columns

| Column | Type | BKI marking | LOOKUP target |
|---|---|---|---|
| `oid` | `Oid` | — | — |
| `pgepgid` | `Oid` | — | `pg_class` (the property-graph relation) |
| `pgerelid` | `Oid` | — | `pg_class` (the backing element table) |
| `pgealias` | `NameData` | — | — |
| `pgekind` | `char` | — | — (`PGEKIND_VERTEX 'v'` / `PGEKIND_EDGE 'e'`) |
| `pgesrcvertexid` | `Oid` | `BKI_LOOKUP_OPT` | `pg_propgraph_element` (self-ref) |
| `pgedestvertexid` | `Oid` | `BKI_LOOKUP_OPT` | `pg_propgraph_element` (self-ref) |
| `pgekey` | `int16[1]` | `BKI_FORCE_NOT_NULL` (CATALOG_VARLEN) | — |
| `pgesrckey` | `int16[1]` | (CATALOG_VARLEN) | — |
| `pgesrcref` | `int16[1]` | (CATALOG_VARLEN) | — |
| `pgesrceqop` | `Oid[1]` | (CATALOG_VARLEN) | — (`pg_operator` semantically, no LOOKUP) |
| `pgedestkey` | `int16[1]` | (CATALOG_VARLEN) | — |
| `pgedestref` | `int16[1]` | (CATALOG_VARLEN) | — |
| `pgedesteqop` | `Oid[1]` | (CATALOG_VARLEN) | — (`pg_operator` semantically, no LOOKUP) |

## Key declarations beyond FormData

- `DECLARE_TOAST(pg_propgraph_element, 6479, 6480)` — TOAST because of the varlen arrays. [verified-by-code]
- `DECLARE_UNIQUE_INDEX_PKEY(pg_propgraph_element_oid_index, 6467, ...)`. [verified-by-code]
- `DECLARE_UNIQUE_INDEX(pg_propgraph_element_alias_index, 6468, ...)` on `(pgepgid, pgealias)`. [verified-by-code]
- `MAKE_SYSCACHE(PROPGRAPHELOID, ...)` and `MAKE_SYSCACHE(PROPGRAPHELALIAS, ...)`, both 128 buckets. [verified-by-code]
- `#ifdef EXPOSE_TO_CLIENT_CODE` block defines on-disk character constants: `PGEKIND_VERTEX 'v'`, `PGEKIND_EDGE 'e'`. **The characters are on-disk values** — changing them is an on-disk break. [verified-by-code]

## Cross-refs

- Parent overview: `knowledge/files/src/include/catalog/_catalog_headers_overview.md`
- Companions: `pg_propgraph_label.h.md`, `pg_propgraph_element_label.h.md`, `pg_propgraph_property.h.md`, `pg_propgraph_label_property.h.md`
- Backend: SQL/PGQ implementation under `source/src/backend/commands/propgraphcmds.c` (PG 18+).

## Potential issues

- **[ISSUE-DOCS: header comment is minimal for a brand-new PG18 catalog]** `pg_propgraph_element.h:1-15` — Beyond a one-line purpose and "NOTES: Catalog.pm reads this file," the header has no narrative explaining the vertex-vs-edge invariant (e.g. that `pgesrcvertexid`/`pgedestvertexid` MUST be non-null exactly when `pgekind = 'e'`, and that the parallel `pgesrc*[]` / `pgedest*[]` arrays must all be same-length per row). These invariants are enforced only in the backend; a reviewer reading the catalog header alone will not see them. [inferred]
- **[ISSUE-LOOKUP: equality-operator OIDs lack BKI_LOOKUP]** `pg_propgraph_element.h:70,87` — `pgesrceqop[]` and `pgedesteqop[]` are arrays of `pg_operator.oid` semantically but have no `BKI_LOOKUP(pg_operator)` (because BKI_LOOKUP isn't supported on array columns). Means pg_dump / pg_depend bookkeeping for these refs must be done by hand in the backend. [inferred]

## Tally

`[verified-by-code]=9 [from-comment]=1 [inferred]=2`
