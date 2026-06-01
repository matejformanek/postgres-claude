# rewriteheap.c

- **Source path:** `source/src/backend/access/heap/rewriteheap.c`
- **Lines:** 1256
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `access/rewriteheap.h`, `heapam_handler.c::heapam_relation_copy_for_cluster` (caller), `replication/logical/decode.c` (consumes the rewrite-mapping WAL records).

## Purpose

Support routines for completely rewriting a heap relation while **preserving visibility info and update chains**, used by VACUUM FULL, CLUSTER, and a few ALTER-TABLE flavours. Handles the hard part: when a tuple's `t_ctid` points to another (presumably newer) tuple, the new heap will have different TIDs, so the ctid chain must be rewritten. Also produces "logical rewrite mapping" files so logical-decoding replication slots can keep following the rewritten data. [from-comment, rewriteheap.c:1-70]

## Top-of-file comment
> 100+ line block at rewriteheap.c:1-150 covering INTERFACE (the begin/loop/end usage pattern), IMPLEMENTATION (the two hash tables `unresolved_tups` and `old_new_tid_map` that resolve A↔B chain pointers when one end is encountered before the other), MEMORY (in-memory only — could in pathological cases OOM but in practice CLUSTER orders tuples by key so chains are seen together), and LOGICAL DECODING (why logical replication needs help across rewrites). [from-comment, rewriteheap.c:1-150]

## Public surface (non-static functions)

- `begin_heap_rewrite(Relation old_heap, Relation new_heap, TransactionId oldest_xmin, TransactionId freeze_xid, MultiXactId cutoff_multi)` (line 235) — Allocate the `RewriteState`. Opens the new heap with bulk-insert state.
- `end_heap_rewrite(RewriteState state)` (line 298) — Flush remaining tuples in `unresolved_tups`, finalise the new heap (`heap_sync` or its meson-era equivalent), free hash tables.
- `rewrite_heap_tuple(RewriteState, HeapTuple old_tuple, HeapTuple new_tuple)` (line 342) — Write `new_tuple` (already reformed to new tupdesc and frozen as appropriate) to the new heap; handle ctid-chain bookkeeping using `old_tuple`'s self-tid.
- `rewrite_heap_dead_tuple(RewriteState, HeapTuple old_tuple)` (line 547) — Record that `old_tuple` was dead (so its successor's ctid pointer becomes a dangling reference we must repair).
- `heap_xlog_logical_rewrite(XLogReaderState *r)` (line 1076) — Redo for `xl_heap_rewrite_mapping` records (replays the writing of an on-disk mapping file).
- `CheckPointLogicalRewriteHeap(void)` (line 1158) — Checkpoint hook that flushes finished rewrite-mapping files and unlinks obsolete ones.

## Static helpers

- `raw_heap_insert` (597) — Insert one already-prepared tuple into the new heap, doing TOAST work as needed. Bypasses `heap_insert` so that visibility metadata is preserved verbatim.
- `logical_begin_heap_rewrite` (762), `logical_heap_rewrite_flush_mappings` (810), `logical_end_heap_rewrite` (908), `logical_rewrite_log_mapping` (938), `logical_rewrite_heap_tuple` (1002) — The logical-decoding mapping file writers.

## Key types / structs

- `RewriteStateData` (in `rewriteheap.h`; allocated by `begin_heap_rewrite`) — Carries: new_heap relation, BulkInsertState, OldestXmin, freeze_xid, cutoff_multi, the two hash tables (`unresolved_tups`, `old_new_tid_map`), plus per-logical-slot mapping-file state.
- The hash table entries store `HeapTupleHeader` copies (palloc'd) keyed by old-TID, allowing the second-encounter handler to patch the ctid.

## Key invariants and locking

- **Caller holds AccessExclusiveLock on the target table.** Stated explicitly at rewriteheap.c:46-48. The rewrite trusts that no concurrent writer exists. [from-comment]
- **Visibility metadata is preserved as-is for RECENTLY_DEAD tuples** — we copy `xmin`/`xmax`/`cmin`/`cmax`/`infomask` over so post-rewrite visibility decisions match pre-rewrite. The only structural change is `t_ctid` (and `t_self`, implicitly, via the new TID). [from-comment]
- **DEAD tuples are dropped entirely**; their successor's ctid will be rewritten by the time that successor is encountered (or after, via `unresolved_tups`). [from-comment]
- **End-state**: `unresolved_tups` and `old_new_tid_map` should normally be empty. If a tuple is stranded in `unresolved_tups` at end-of-rewrite, it gets written with its original (now-bogus) ctid; this is acceptable because the entire chain past that point is DEAD per `HeapTupleSatisfiesVacuum` and unreachable. The comment justifies this in detail. [from-comment, rewriteheap.c:55-75]
- **Logical decoding consistency.** Whenever a tuple is logically interesting (catalog or user table being decoded) and its TID changes, a mapping is appended to a per-slot file. The file is fsynced at end_heap_rewrite and at checkpoint. Logical decoding consults these files to translate old TIDs into new ones during catalog snapshot reconstruction. [from-comment, rewriteheap.c bottom; verified-by-code]
- **`raw_heap_insert` uses `HEAP_INSERT_NO_LOGICAL`** because the rewriting transaction itself shouldn't appear in logical replication (the rewrite is a physical reorganisation, not a logical change). [verified-by-code]

## Functions of note

1. **`rewrite_heap_tuple`** (line 342) — The chain-fixup centrepiece. Algorithm:
   - If old tuple's ctid points to itself (head of chain, no successor) → just insert.
   - Else if successor's new TID is already in `old_new_tid_map` → patch new_tuple's t_ctid to that, then insert.
   - Else → insert the new tuple, then add `(old_tid → new_tid)` to `unresolved_tups` keyed by the predecessor we'd want; the predecessor walker will patch us later.
   The exact code uses both maps symmetrically; comment at rewriteheap.c:602-665 walks through the cases. [verified-by-code]

2. **`raw_heap_insert`** (line 597) — Performs TOAST (calls `heap_toast_insert_or_update`), then writes via `RelationGetBufferForTuple` + `RelationPutHeapTuple`. Does NOT call `heap_insert` — that path would clobber xmin/xmax with the current xact's xid. [verified-by-code]

3. **`logical_rewrite_log_mapping`** (line 938) — Emits a `xl_heap_rewrite_mapping` WAL record describing where new mappings were appended in the on-disk mapping file. Lets standbys replay the file writes via `heap_xlog_logical_rewrite`. [verified-by-code]

4. **`CheckPointLogicalRewriteHeap`** (line 1158) — Hooked from the checkpointer; fsyncs and possibly unlinks finished mapping files based on slot LSN tracking. Ensures recovery doesn't fail because of stale rewrite map files. [verified-by-code]

## Cross-references

- Called by: `heapam_handler.c::heapam_relation_copy_for_cluster` (line 594) — CLUSTER and VACUUM FULL.
- Calls into: `heaptoast.c` (TOAST), `hio.c` (`RelationGetBufferForTuple`, `RelationPutHeapTuple`), `xloginsert.c`, `bufmgr.c`, `multixact.c` (`MultiXactIdGetUpdateXid`).
- Logical-decoding side consumer: `replication/logical/decode.c::ReorderBufferProcessTXN` and friends (via `LogicalRewriteHeapDecode`).

## Open questions

- Exact failure mode if `unresolved_tups` reaches the OOM-relevant size — comment says "shouldn't happen", but there's no spill-to-disk. [unverified]
- Whether `heap_sync` is still called in `end_heap_rewrite` or has been replaced by the smgr immediate-sync flag set by `begin_heap_rewrite`. [unverified — implementation detail]

## Confidence tag tally
`[verified-by-code]=11 [from-comment]=8 [from-readme]=0 [inferred]=0 [unverified]=2`
