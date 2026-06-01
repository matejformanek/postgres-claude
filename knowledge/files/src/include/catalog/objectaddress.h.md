# objectaddress.h

- **Source path:** `source/src/include/catalog/objectaddress.h`
- **Last verified commit:** `ef6a95c7c64`

## Purpose

"Functions for working with object addresses."

## Key declarations

- `ObjectAddress` struct: `{ Oid classId; Oid objectId; int32 objectSubId; }`. The universal object identifier. `classId` is the relation OID of the catalog (e.g., RelationRelationId for tables); `objectSubId` is non-zero only for column-on-a-relation (attnum).
- `ObjectAddressSet(addr, class, obj)` macro shortcut.
- API prototypes: `get_object_address`, `get_object_address_rv`, `check_object_ownership`, `get_object_namespace`, `get_object_class_descr`, `pg_get_object_address` (SQL-callable).
- `ObjectAddresses` opaque type (declared in dependency.h actually).

## Tally

`[verified-by-code]=1`
