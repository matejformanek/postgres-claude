# pg_namespace.h

- **Source path:** `source/src/include/catalog/pg_namespace.h`
- **Last verified commit:** `4b0bf0788b0`

## Purpose

"Definition of the 'namespace' system catalog (pg_namespace)." Schemas. `[from-comment]`

## Catalog definition

- `CATALOG(pg_namespace,2615,NamespaceRelationId)` — no BKI bootstrap, not shared, no rowtype-OID, no schema-macro. `[verified-by-code]`
- `FormData_pg_namespace` / `Form_pg_namespace`.

## Columns

| Column | Type | BKI marking | LOOKUP target |
|---|---|---|---|
| oid | Oid | — | — |
| nspname | NameData | — | — |
| nspowner | Oid | `BKI_DEFAULT(POSTGRES)` | `pg_authid` |
| nspacl | aclitem[1] | — (varlena) | — |

## Key declarations beyond FormData

- TOAST + indexes: `DECLARE_TOAST(pg_namespace, 4163, 4164)`; unique `pg_namespace_nspname_index`, PK `pg_namespace_oid_index`. Syscaches: `NAMESPACENAME`, `NAMESPACEOID`. `[verified-by-code]`
- Function prototype: `NamespaceCreate(const char *nspName, Oid ownerId, bool isTemp)`. `[verified-by-code]`

## Cross-refs

- Parent overview: `knowledge/files/src/include/catalog/_catalog_headers_overview.md`
- `knowledge/files/src/include/catalog/namespace.h.md` (lookup/search-path API consumes this catalog)
- `knowledge/files/src/include/catalog/pg_authid.h.md` (nspowner)

## Tally

`[verified-by-code]=4 [from-comment]=1`
