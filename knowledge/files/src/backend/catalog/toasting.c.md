# toasting.c

- **Source path:** `source/src/backend/catalog/toasting.c`
- **Lines:** ~420
- **Last verified commit:** `ef6a95c7c64`

## Purpose

"This file contains routines to support creation of toast tables." Side TOAST-relation creation: heap relation with relkind='t' under pg_toast namespace, with a 2-column schema (`chunk_id oid`, `chunk_seq int4`, `chunk_data bytea`) and a UNIQUE index on (chunk_id, chunk_seq).

## Public surface

- `AlterTableCreateToastTable` (59) — wrapper that calls `CheckAndCreateToastTable` with `check=true` (skip if not needed).
- `NewHeapCreateToastTable` (65), `NewRelationCreateToastTable` (72) — wrappers for fresh relations (no skip, just create).
- `CheckAndCreateToastTable` (79) — if `needs_toast_table(rel)` says yes, call `create_toast_table`.
- `BootstrapToastTable` (99) — initdb path: create toast for a hardcoded relname with pre-chosen OIDs.
- `create_toast_table` (128) — **the worker.** Builds the toast TupleDesc, calls `heap_create_with_catalog` to make `pg_toast.pg_toast_<oid>`, then `index_create` for the unique index, then updates `pg_class.reltoastrelid` on the parent. Records an INTERNAL pg_depend so the toast is dropped with its owner. [verified-by-code]
- `needs_toast_table` (408) — predicate: total nominal tuple size > TOAST_TUPLE_THRESHOLD and at least one attr has a variable-length type with non-PLAIN storage.

## Atomicity

Toast creation runs inside the parent's CREATE TABLE (or ALTER TABLE ADD COLUMN). All catalog rows + storage are produced in the same xact; abort cleans up via `storage.c` pending-deletes and pg_class row rollback.

## Confidence tag tally

`[verified-by-code]=3 [inferred]=1`
