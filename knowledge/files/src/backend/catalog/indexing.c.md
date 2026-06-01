# indexing.c

- **Source path:** `source/src/backend/catalog/indexing.c`
- **Lines:** ~354
- **Last verified commit:** `ef6a95c7c64`

## Purpose

"This file contains routines to support indexes defined on system catalogs." The thin `CatalogTuple*` wrappers that every catalog DDL uses — they hide the "open indexes, insert tuple via table AM, then insert into all indexes" dance behind a one-call API. [from-comment, indexing.c:3-6]

## Public surface

- `CatalogOpenIndexes` (43) — wraps `ExecOpenIndices` on a `ResultRelInfo` for the given catalog. Returns an opaque `CatalogIndexState` (actually a ResultRelInfo). Limitation in the comment: "we do not support partial or expressional indexes on system catalogs, nor … generalized exclusion constraints" because no EState is built. [from-comment, indexing.c:34-41]
- `CatalogCloseIndexes` (61) — pair with `CatalogOpenIndexes`.
- `CatalogIndexInsert` (75, static) — internal: insert one tuple into all open indexes of a catalog. Uses `MakeSingleTupleTableSlot` with `TTSOpsHeapTuple`. Skips HOT updates (no index insert needed).
- `CatalogTupleCheckConstraints` (195, static) — sanity assertions on the tuple's NULLs etc.
- `CatalogTupleInsert` (233) — `CatalogOpenIndexes` + `simple_heap_insert` + `CatalogIndexInsert` + `CatalogCloseIndexes`. **This is the universal "write one new row into a system catalog" call.**
- `CatalogTupleInsertWithInfo` (256) — same but caller already has a `CatalogIndexState` open (saves re-opening for bulk inserts).
- `CatalogTuplesMultiInsertWithInfo` (273) — bulk insert path; used by `InsertPgAttributeTuples` in heap.c.
- `CatalogTupleUpdate` (313) — `simple_heap_update` + `CatalogIndexInsert` (note: update inserts new index entry; old one is dead).
- `CatalogTupleUpdateWithInfo` (337) — same with pre-opened indexes.
- `CatalogTupleDelete` (365) — `simple_heap_delete`. No index work needed: index entries for the dead tuple become unreachable via the dead heap line pointer.

## Why no EState

`ExecInsertIndexTuples` would do the same work but require an EState (with all its memory contexts and triggers). For catalog DDL, we skip that overhead — at the cost of not supporting partial/expression/exclusion indexes on system catalogs. None of the existing system catalogs need them.

## Confidence tag tally

`[verified-by-code]=4 [from-comment]=2`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
