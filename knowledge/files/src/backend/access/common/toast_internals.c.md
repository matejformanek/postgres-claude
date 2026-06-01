# toast_internals.c

- **Source path:** `source/src/backend/access/common/toast_internals.c`
- **Lines:** 647
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `toast_internals.h`, `heaptoast.c` (heap-AM toaster), `detoast.c` (read side), `table/toast_helper.c` (AM-facing helpers), `toast_compression.c`.

## Purpose

The TOAST storage layer: compress, save and delete out-of-line values in a TOAST relation. Insertion produces a chain of fixed-size chunks indexed by `(chunk_id, chunk_seq)`; deletion is a TID-driven systable_delete. Used by every table AM that out-of-lines varlenas (heap and any future AM that follows the heap TOAST convention). [from-comment, toast_internals.c:1-12]

## Top-of-file comment

> "Functions for internal use by the TOAST system." [from-comment, toast_internals.c:3-4]

## Public surface

- `toast_compress_datum` (46) — Compress with the requested method (`'p'` or `'l'`). Returns NULL if the compressed form wouldn't be smaller (must store uncompressed instead). Dispatches to `pglz_compress_datum` / `lz4_compress_datum`.
- `toast_save_datum` (119) — Allocate a fresh `chunk_id` (Oid; via `GetNewOidWithIndex`), write all chunks into the toast relation and its valid index(es), produce a `varatt_external` pointer to return. Heavy lifter.
- `toast_delete_datum` (376) — Given an EXTERNAL pointer, delete all matching chunks. Honours `is_speculative` (super-delete for failed speculative inserts).
- `toast_get_valid_index` (519) — Identify the currently-valid index of the TOAST relation (REINDEX CONCURRENTLY can leave multiple).
- `toast_open_indexes` (553), `toast_close_indexes` (612) — Open / close all TOAST indexes for a relation. Multiple may exist transiently during REINDEX CONCURRENTLY; the "valid" one is determined by `toast_get_valid_index`.
- `get_toast_snapshot` (629) — Build a `SnapshotToast` based on the oldest registered snapshot (so concurrent readers see our writes).

## Key invariants and locking

- Chunks are written in `chunk_seq` order starting at 0; max chunk data size is `TOAST_MAX_CHUNK_SIZE` (computed from `BLCKSZ` to leave room for the chunk header). [verified-by-code, toast_internals.c:119-375]
- `chunk_id` is a fresh Oid for each TOASTed value; uniqueness is enforced by the toast index (a unique index on `(chunk_id, chunk_seq)`). [verified-by-code, toast_internals.c:119-200]
- During REINDEX CONCURRENTLY, multiple indexes can exist on the same toast relation. `toast_open_indexes` opens ALL of them; inserts go into every open index; reads use only the `validIndex` slot. [verified-by-code, toast_internals.c:519-628]
- `toast_save_datum` calls `heap_insert` on each chunk row — this means TOAST writes ARE WAL-logged like any other heap insert. [verified-by-code, toast_internals.c:119-375]
- `toast_delete_datum` uses `systable_beginscan` against the valid index to find chunks, then `simple_heap_delete` (or `heap_abort_speculative` for super-delete) per chunk. [verified-by-code, toast_internals.c:376-449]
- `get_toast_snapshot` requires an active snapshot to exist (`ActiveSnapshotSet()`); else `elog(ERROR, "no known snapshots")`. The TOAST snapshot is set up so as not to be ahead of any concurrent reader. [verified-by-code, toast_internals.c:629-647]

## Functions of note

1. **`toast_save_datum`** (119) — Decides whether the to-be-toasted value is compressed or raw (via `VARATT_IS_COMPRESSED`), assigns a chunk_id, loops emitting `chunk_id, chunk_seq, chunk_data` rows; builds the `varatt_external` (raw size, extended size, oid, toast relid) and returns it as a Datum pointer the caller embeds in the main-table tuple. [verified-by-code]
2. **`toast_delete_datum`** (376) — Range-scans the toast index on `chunk_id`, deletes each row, supports speculative-abort (super-delete) path used by upserts. [verified-by-code]
3. **`toast_get_valid_index`** (519) — Walks `RelationGetIndexList`, returns the one whose `indisvalid` is true. Acquires the requested lock on it. [verified-by-code]

## Cross-references

- Called by: `heaptoast.c::heap_toast_insert_or_update`, `heaptoast.c::toast_delete`, `table/toast_helper.c` (the AM-facing helpers).
- Calls into: `heapam.c` (`heap_insert`, `simple_heap_delete`, `heap_abort_speculative`), `indexam.c` (catalog-style scans), `catalog/index.c` (`GetNewOidWithIndex`), `toast_compression.c`.

## Open questions

- Behavior of `toast_save_datum` when the toast relation itself is unlogged — TOAST writes follow the same WAL discipline as the parent's heap_insert, so unlogged parent ⇒ unlogged TOAST inserts. Inferred not explicitly verified here. [unverified]

## Confidence tag tally
`[verified-by-code]=10 [from-comment]=2 [from-readme]=0 [inferred]=0 [unverified]=1`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
