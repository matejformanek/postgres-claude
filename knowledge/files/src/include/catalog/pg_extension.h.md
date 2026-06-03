# pg_extension.h

- **Source path:** `source/src/include/catalog/pg_extension.h`
- **Last verified commit:** `4b0bf0788b0`

## Purpose

"Definition of the 'extension' system catalog (pg_extension)." `[from-comment]` One row per installed extension — names the owner, schema, version string, and the optional list of "dumpable configuration tables" (extconfig) plus per-table WHERE clauses (extcondition).

## Catalog definition

- `CATALOG(pg_extension,3079,ExtensionRelationId)` — per-DB. No special BKI markings. `[verified-by-code]` `pg_extension.h:31`
- `FormData_pg_extension` typedef. Pointer alias: `Form_pg_extension`. `[verified-by-code]`

## Columns

| Column | Type | BKI marking | LOOKUP target |
|---|---|---|---|
| oid | Oid | — | — |
| extname | NameData | — | — |
| extowner | Oid | `BKI_LOOKUP` | `pg_authid` |
| extnamespace | Oid | `BKI_LOOKUP` | `pg_namespace` |
| extrelocatable | bool | — | — (gates ALTER EXTENSION SET SCHEMA) |
| extversion | text | (varlena) `BKI_FORCE_NOT_NULL` | — |
| extconfig | Oid[1] | (varlena) `BKI_LOOKUP` | `pg_class` (dumpable config tables) |
| extcondition | text[1] | (varlena) | — (WHERE clauses parallel to extconfig) |

Header note: "extversion may never be null, but the others can be." `[from-comment]` `pg_extension.h:41`

## Key declarations beyond FormData

- `DECLARE_TOAST(pg_extension, 4147, 4148)`. `[verified-by-code]`
- Indexes: `pg_extension_oid_index` (PK, 3080); `pg_extension_name_index` (3081, unique on extname). `[verified-by-code]`
- Syscaches: `EXTENSIONOID`, `EXTENSIONNAME`. `[verified-by-code]`
- No function prototypes here — runtime API lives in `commands/extension.h`.

## Cross-refs

- Parent overview: `knowledge/files/src/include/catalog/_catalog_headers_overview.md`
- `knowledge/files/src/include/catalog/pg_depend.h` (DEPENDENCY_EXTENSION / DEPENDENCY_AUTO_EXTENSION pin contained objects)
- `knowledge/files/src/include/catalog/pg_namespace.h` (extnamespace target)
- `knowledge/files/src/include/catalog/pg_init_privs.h` (extension-member ACL snapshot)

## Potential issues

- **[ISSUE-parallel-array-invariant]** `pg_extension.h:43-45` — `extconfig` (Oid[]) and `extcondition` (text[]) must have the same length and corresponding indices; nothing in the schema enforces this. Code that iterates one without checking the other can crash on a malformed extension install (typically only reachable via direct catalog edit or a buggy extension script).

## Tally

`[verified-by-code]=8 [from-comment]=2`
