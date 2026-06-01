# heapam_handler.c

- **Source path:** `source/src/backend/access/heap/heapam_handler.c`
- **Lines:** 2734
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `access/tableam.h` (the abstract AM contract), `heapam.c` (callees), `executor/*` (slot mechanics), `commands/cluster.c` (CLUSTER consumer)

## Purpose

"Wires up the lower level heapam.c et al routines with the tableam abstraction." [from-comment, heapam_handler.c:96-98] Provides the function pointers in the `TableAmRoutine` struct returned by `GetHeapamTableAmRoutine()` — the entry point installed in `pg_am` for the heap AM. Almost every callback here is a thin shim from a tableam.h prototype to the corresponding `heap_*` function.

## Top-of-file comment
> "heap table access method code … This files wires up the lower level heapam.c et al routines with the tableam abstraction." [from-comment, heapam_handler.c:83-100]

## Public surface (non-static functions)

- `GetHeapamTableAmRoutine(void)` (line 2725) — returns the static `heapam_methods` struct.
- `heap_tableam_handler(PG_FUNCTION_ARGS)` (line 2731) — the SQL-callable handler (registered in `pg_am`).

Everything else in this file is `static` and slotted into `heapam_methods` by function pointer.

## Callback shims (static functions, grouped by tableam.h section)

**Slot/snapshot:**
- `heapam_slot_callbacks` (77) — returns `&TTSOpsBufferHeapTuple`.
- `heapam_fetch_row_version` (89), `heapam_tuple_tid_valid` (113), `heapam_tuple_satisfies_snapshot` (122).

**DML:**
- `heapam_tuple_insert` (150), `_insert_speculative` (169), `_complete_speculative` (192), `_delete` (209), `_update` (224), `_lock` (271).

**Relation lifecycle:**
- `heapam_relation_set_new_filelocator` (492), `_nontransactional_truncate` (535), `_copy_data` (541), `_copy_for_cluster` (594 — the CLUSTER/VACUUM FULL rewrite driver).

**Analyze:**
- `heapam_scan_analyze_next_block` (974), `_next_tuple` (998).

**Index builds:**
- `heapam_index_build_range_scan` (1143), `_index_validate_scan` (1718).

**Estimation / TOAST:**
- `heapam_relation_needs_toast_table` (2010), `_relation_toast_am` (2060), `_estimate_rel_size` (2077).

**Bitmap heap scans:**
- `heapam_scan_bitmap_next_tuple` (2094), and the static `BitmapHeapScanNextBlock` (2508) it calls via the read stream.

**Sample scans (TABLESAMPLE):**
- `heapam_scan_sample_next_block` (2145), `_next_tuple` (2235), `SampleHeapTupleVisible` (2459).

**CLUSTER helpers (static):**
- `reform_and_rewrite_tuple` (2352), `heap_insert_for_repack` (2383), `reform_tuple` (2407).

## Key types / structs

- The file's most important *data* is the static `TableAmRoutine heapam_methods = { ... }` (just before line 2725) — the table of function pointers that defines the heap AM.

## Key invariants and locking

- `heapam_relation_copy_for_cluster` (line 594) is the entry point for VACUUM FULL / CLUSTER / pg_repack-style table rewrites. Holds `AccessExclusiveLock` on both old and new heap. Uses `rewriteheap.c` for the actual mapping work. [from-comment, heapam_handler.c around line 594]
- `heapam_tuple_lock` (line 271) is a long shim that translates the tableam lock-mode enum into the heap-specific `LockTupleMode`. Handles follow-update chains. [verified-by-code]
- Analyze/sample callbacks use `SampleHeapTupleVisible` which calls `HeapTupleSatisfiesVisibility` against the analyzing-xact's snapshot. [verified-by-code]

## Functions of note

- `heapam_relation_copy_for_cluster` — the CLUSTER mechanism: scan source, optionally sort, write to new heap via `raw_heap_insert`, fix ctid chains via `rewriteheap.c`'s `unresolved_tups` / `old_new_tid_map` machinery. **Many subtle visibility rules** about which RECENTLY_DEAD tuples to copy. [verified-by-code]
- `heapam_index_build_range_scan` — used by index AMs to build a fresh index. Iterates the heap via an internal HeapScan, applies the IndexBuildCallback to each visible tuple. Concurrent-build paths (with `READ_COMMITTED` snapshot management) live here. [verified-by-code]
- `BitmapHeapScanNextBlock` — the read-stream callback for bitmap heap scans; handles lossy vs exact pages and per-block VM-skipping. [verified-by-code]
- `heap_tableam_handler` — the function registered in `pg_am.amhandler`; one-liner that PG_RETURN_POINTER(GetHeapamTableAmRoutine()). [verified-by-code]

## Cross-references

- Called *by* (via function pointers): the executor (`nodeSeqscan.c`, `nodeBitmapHeapscan.c`, `nodeIndexscan.c`, `nodeSamplescan.c`, `nodeModifyTable.c`), `commands/analyze.c`, `commands/cluster.c`, `commands/vacuum.c`, `catalog/index.c`, `catalog/storage.c`.
- Calls out: nearly every public function in `heapam.c`, `heapam_visibility.c`, `pruneheap.c`, `rewriteheap.c`, plus `bufmgr`, `tableam` slot helpers, `predicate.c` (SSI), `tuplesort.c` (for CLUSTER).

## Open questions

- The exact concurrent-index-build snapshot management in `heapam_index_build_range_scan` — has changed multiple times across versions. [unverified]
- Whether `heapam_relation_copy_data` is still used for any path other than `CREATE TABLE … AS` and the no-rewrite ALTER TABLE. [unverified]

## Confidence tag tally
`[verified-by-code]=15 [from-comment]=2 [from-readme]=0 [inferred]=0 [unverified]=2`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/access-heap.md](../../../../../subsystems/access-heap.md)
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
