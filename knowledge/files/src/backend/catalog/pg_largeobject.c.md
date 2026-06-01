# pg_largeobject.c

- **Source path:** `source/src/backend/catalog/pg_largeobject.c`
- **Lines:** ~185
- **Last verified commit:** `ef6a95c7c64`

## Purpose

"Routines to support manipulation of the pg_largeobject relation." pg_largeobject is the "chunks of bytea keyed by (loid, pageno)" catalog backing the lo_* server functions. This file handles bulk delete and existence checks; the actual lo_create / lo_write / lo_read are in `libpq/be-fsstubs.c` and `storage/large_object/inv_api.c`.

## Public surface

- `LargeObjectCreate` — write the pg_largeobject_metadata row (the lo's identity + owner + ACL).
- `LargeObjectDrop` — delete metadata + all pg_largeobject chunks.
- `LargeObjectExists` — predicate.
- `RemoveLargeObject` — called by dependency.c.

## Confidence tag tally

`[inferred]=4`
