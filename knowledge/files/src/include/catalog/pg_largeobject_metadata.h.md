# pg_largeobject_metadata.h

- **Source path:** `source/src/include/catalog/pg_largeobject_metadata.h`
- **Last verified commit:** `4b0bf0788b0`

## Purpose

Per-large-object metadata: owner and ACL. Splits LO ownership/permissions out of `pg_largeobject` (which holds the bulk chunks) so a single row identifies each LO regardless of how many `LOBLKSIZE`-sized chunks back it.

## Catalog definition

- `CATALOG(pg_largeobject_metadata, 2995, LargeObjectMetadataRelationId)` — per-DB; no shared/bootstrap. [verified-by-code] `pg_largeobject_metadata.h:32`
- `FormData_pg_largeobject_metadata` typedef; pointer alias `Form_pg_largeobject_metadata`. [verified-by-code] `pg_largeobject_metadata.h:42,51`

## Columns

| Column | Type | BKI marking | LOOKUP target |
|---|---|---|---|
| oid | Oid | — | — (this is the LO's `loid`) |
| lomowner | Oid | BKI_LOOKUP | `pg_authid` |
| lomacl | aclitem[1] (varlena) | — | — (under `#ifdef CATALOG_VARLEN`; nullable, no BKI_FORCE_NOT_NULL) |

## Key declarations beyond FormData

- `DECLARE_UNIQUE_INDEX_PKEY(pg_largeobject_metadata_oid_index, 2996, ...)`. [verified-by-code] `pg_largeobject_metadata.h:53`
- No TOAST table declared in this header (acl arrays are usually short enough).

## Cross-refs

- Parent overview: `knowledge/files/src/include/catalog/_catalog_headers_overview.md`
- Related: `pg_largeobject.h` (chunks; `loid` LOOKUP→ here)
- Related backend: `src/backend/catalog/objectaddress.c`, `src/backend/storage/large_object/inv_api.c`

## Potential issues

- **[ISSUE-leak: no TOAST table on lomacl]** `pg_largeobject_metadata.h` — `lomacl aclitem[1]` is VARLEN but no `DECLARE_TOAST` is present. If an LO accumulates many grantees, the row could exceed page size. Compare `pg_default_acl` and `pg_init_privs` which both have TOAST. Severity `maybe`, type `correctness` (or could be deliberate sizing assumption — needs a closer read). Worth verifying whether `GRANT ... ON LARGE OBJECT` to thousands of roles actually fails.

## Tally

`[verified-by-code]=5 [inferred]=1`
