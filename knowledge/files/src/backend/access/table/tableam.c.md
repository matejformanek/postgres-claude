# tableam.c

- **Source path:** `source/src/backend/access/table/tableam.c`
- **Lines:** 825
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `tableam.h` (most of the API surface is inline functions there), `tableamapi.c`, `heap/heapam_handler.c` (the only in-tree AM implementation), `syncscan.c`, `bufmgr.c`, `optimizer/plancat.c`.

## Purpose

The bigger-than-inline parts of the table-AM dispatch layer. Provides slot-callback selection, catalog/parallel scan setup, simple-DML helpers used by catalog code, the heap-style parallel block allocator, and the canonical default `relation_size` / `relation_estimate_size` implementations that any block-based AM can reuse. [from-comment, tableam.c:1-18]

## Top-of-file comment

> "Table access method routines too big to be inline functions… Note that most functions in here are documented in tableam.h, rather than here. That's because there's a lot of inline functions in tableam.h and it'd be harder to understand if one constantly had to switch between files." [from-comment, tableam.c:1-17]

## GUCs and constants

- `default_table_access_method` (49) — String GUC, default `DEFAULT_TABLE_ACCESS_METHOD` ("heap"). Validated in `tableamapi.c::check_default_table_access_method`.
- `synchronize_seqscans` (50) — Boolean GUC; controls whether `syncscan.c` is consulted.
- `PARALLEL_SEQSCAN_NCHUNKS = 2048`, `PARALLEL_SEQSCAN_RAMPDOWN_CHUNKS = 64`, `PARALLEL_SEQSCAN_MAX_CHUNK_SIZE = 8192` — parameters for the parallel-seqscan I/O allocator. [verified-by-code, tableam.c:41-46]

## Public surface (grouped)

- **Slot callbacks:** `table_slot_callbacks` (59) — Returns the right `TupleTableSlotOps` for a relation. For `rd_tableam` non-NULL, dispatches to `am->slot_callbacks`. For foreign tables returns `TTSOpsHeapTuple` (FDW back-compat). For views/matviews returns `TTSOpsVirtual`.
- `table_slot_create` (92) — Build a TupleTableSlot using the right ops + descriptor.
- **Scan setup:** `table_beginscan_catalog` (113) — convenience wrapper that uses an MVCC snapshot, intended for catalog reads.
- **Parallel scan:** `table_parallelscan_estimate` (131), `table_parallelscan_initialize` (146), `table_beginscan_parallel` (166), `table_beginscan_parallel_tidrange` (193).
- **Index fetch:** `table_index_fetch_tuple_check` (242) — Convenience for callers that just want "does the heap tuple at this TID exist and pass the snapshot?" (used by trigger code and the unique-check path).
- **`get_latest_tid`:** `table_tuple_get_latest_tid` (269) — Walk an update chain forward to the latest version. Handles `ItemPointerIsValid` and `relation->rd_tableam->tuple_get_latest_tid` dispatch.
- **Simple DML (for catalogs):** `simple_table_tuple_insert` (302), `simple_table_tuple_delete` (316), `simple_table_tuple_update` (361) — All assume "no concurrent updaters" semantics; throw on conflict. Used pervasively in `catalog/*`.
- **Reusable block-based AM helpers:** `table_block_parallelscan_estimate` (408), `table_block_parallelscan_initialize` (414), `table_block_parallelscan_reinitialize` (433), `table_block_parallelscan_startblock_init` (453), `table_block_parallelscan_nextpage` (548). Heap-style block allocators that any AM with sequential-page semantics can plug into its parallel-scan callbacks.
- **Default size estimators:** `table_block_relation_size` (681), `table_block_relation_estimate_size` (718). Used as the implementation of `relation_size` / `relation_estimate_size` for `heap` and any block-based future AM.

## Key invariants

- Slot-callback dispatch is required because the per-tuple slot ops are AM-specific (heap uses `TTSOpsBufferHeapTuple`; a column-store would use something else). All executor code that opens a slot for a relation goes through `table_slot_callbacks`. [from-comment, tableam.c:67-90]
- The parallel-block allocator divides the relation into `PARALLEL_SEQSCAN_NCHUNKS` chunks; each chunk's size is `nblocks / NCHUNKS` capped at `MAX_CHUNK_SIZE = 8192`. When fewer than `RAMPDOWN_CHUNKS = 64` are left, chunk size is halved to reduce the chance of one worker finishing late. [verified-by-code, tableam.c:548-680]
- The startblock initialiser consults `syncscan.c` (`ss_get_location`) when `synchronize_seqscans` is on AND the relation is at least `synchronize_seqscans_offset` blocks; this lets parallel seqscans cooperate with concurrent ad-hoc seqscans. [verified-by-code, tableam.c:453-547]
- `simple_table_tuple_{insert,delete,update}` are NOT general-purpose; they assume the caller is doing catalog-style single-row work and `elog(ERROR)` on `TM_BeingModified` / `TM_Updated`. User DML goes through the executor, which handles concurrency. [verified-by-code, tableam.c:302-407]
- `table_block_relation_estimate_size` honours the planner's normal "use pg_class.reltuples & relpages, scaled up to current relation size" formula — overridable per AM. [verified-by-code, tableam.c:718-825]

## Functions of note

1. **`table_block_parallelscan_nextpage`** (548) — The atomic "give me the next block to scan" for parallel seqscan. Uses `pg_atomic_compare_exchange_u64` on the chunk allocator state, and ramps chunk size down near the end. The trickiest concurrency in this file. [verified-by-code]
2. **`simple_table_tuple_update`** (361) — Loops until `tuple_update` returns `TM_Ok`; on `TM_BeingModified` it would wait (but the simple path bails out instead). Throws on any conflict. [verified-by-code]
3. **`table_beginscan_parallel`** (166) — Asserts the passed `ParallelTableScanDesc` was set up by the leader with a matching relfilelocator; calls `am->scan_begin` with `SO_TYPE_SEQSCAN | SO_ALLOW_*` flags plus the parallel descriptor. [verified-by-code]

## Cross-references

- All AMs in tree (just `heap`) register `table_block_parallelscan_*` and `table_block_relation_size` as their callbacks.
- Called by: executor scan nodes, catalog DML in `catalog/*`, `commands/copyfrom.c` (multi-insert), `commands/vacuum*`, planner (`plancat.c::estimate_rel_size`).

## Open questions

- The exact synchronization between `table_block_parallelscan_startblock_init` and `syncscan.c`'s LRU under contention — `ss_get_location` is best-effort, so divergence is benign, but I didn't trace the worst case. [unverified]

## Confidence tag tally
`[verified-by-code]=9 [from-comment]=3 [from-readme]=0 [inferred]=0 [unverified]=1`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
