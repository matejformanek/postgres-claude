# `src/include/executor/instrument_node.h`

**Pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`

## Role

Per-node-type instrumentation structs shipped via DSM to the leader
at parallel-query shutdown for EXPLAIN ANALYZE display
[from-comment: lines 4-9]. Structs intentionally hold **no
pointers** — they're memcpy-able across processes.

## Public API (struct catalogue)

### Constants [verified-by-code: line 28]

`PARALLEL_KEY_SCAN_INSTRUMENT_OFFSET = 0xD000000000000000` — added
to `plan_node_id` to form a second TOC key for per-worker scan
instrumentation DSM chunks.

### Aggregate [lines 34-48]

`AggregateInstrumentation {hash_mem_peak, hash_disk_used,
hash_batches_used}`; `SharedAggInfo` is per-worker array.

### I/O / Read Streams [lines 51-97]

`IOStats {prefetch_count, distance_sum, distance_max,
distance_capacity, wait_count, io_count, io_nblocks,
io_in_progress}`.

`TableScanInstrumentation {IOStats io}`. Inline
`AccumulateIOStats(dst, src)` merges two — used to roll up per-
worker stats.

### Index scan [lines 101-117]

`IndexScanInstrumentation {nsearches}` — increments via
`pgstat_count_index_scan`.

### Bitmap heap scan [lines 121-141]

`BitmapHeapScanInstrumentation {exact_pages, lossy_pages,
TableScanInstrumentation stats}`.

### Memoize [lines 145-170]

`MemoizeInstrumentation {cache_hits, cache_misses,
cache_evictions, cache_overflows, mem_peak}`.

### Sort [lines 174-216]

`TuplesortSpaceType` (DISK / MEMORY), `TuplesortMethod` bitfield
(`STILL_IN_PROGRESS=0`, `TOP_N_HEAPSORT`, `QUICKSORT`,
`EXTERNAL_SORT`, `EXTERNAL_MERGE`), `NUM_TUPLESORTMETHODS = 4`.
`TuplesortInstrumentation {sortMethod, spaceType, spaceUsed}`.

### Hash [lines 220-239]

`HashInstrumentation {nbuckets, nbuckets_original, nbatch,
nbatch_original, space_peak}`.

### IncrementalSort [lines 243-267]

`IncrementalSortGroupInfo {groupCount, maxDiskSpaceUsed,
totalDiskSpaceUsed, maxMemorySpaceUsed, totalMemorySpaceUsed,
sortMethods (bitmask)}`. Wrapped per-prefix vs full sort.

### Seq / TidRange scans [lines 271-304]

Wrappers over `TableScanInstrumentation`.

Each kind exposes a `Shared*Info {num_workers,
*instrument[FLEXIBLE_ARRAY_MEMBER]}` container.

## Invariants

- **INV-NO-POINTERS** [from-comment: lines 4-9] All structs are
  pure data — memcpy across processes is the contract. Adding a
  pointer field would break parallel-query EXPLAIN.
- **INV-FLEX-ARRAY** [verified-by-code: passim] Every container
  ends with a flexible array member sized by `num_workers`.
- **INV-METHOD-BITMASK** [from-comment: lines 184-191] Sort method
  uses OR-able bits because different workers in one parallel sort
  may use different methods; the OR'd value is what EXPLAIN
  reports.
- **INV-SORT-METHOD-COUNT** [verified-by-code: line 200]
  `NUM_TUPLESORTMETHODS` must stay in sync with the bit count.

## Trust boundary (Phase D)

- These structs are written by workers into DSM and read by the
  leader at shutdown. A buggy worker writing out-of-bounds would
  affect only its own DSM slot.
- Numbers surface in EXPLAIN ANALYZE output (and in
  `pg_stat_statements` via the per-query plan-level accumulators).
  No content-sensitive data — just counts and bytes.
- These counters also feed pg_stat_statements (A11) — coarse-grain
  data only.

## Cross-refs

- `executor/instrument.h` — top-level `Instrumentation` struct;
  this header is the per-node extension.
- `executor/execParallel.h` — DSM marshalling.
- `executor/nodeAgg.h`, `nodeHash.h`, `nodeMemoize.h`,
  `nodeIncrementalSort.h`, `nodeSort.h`, `nodeIndexscan.h`,
  `nodeBitmapHeapscan.h`, `nodeSeqscan.h`, `nodeTidrangescan.h` —
  per-kind writers.

## Issues

- [ISSUE-API: adding a new instrumentation kind requires (a) a new
  struct here, (b) a `Shared*Info` container, (c) DSM TOC key, (d)
  EXPLAIN formatter — easy to miss one (low)] — entire file.
