# `src/include/executor/hashjoin.h`

**Pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`

## Role

Internal layout of `HashJoinTable` and its parallel variant. Defines
the per-batch tuplestore wrapping, skew-bucket optimization, and the
barrier-coordinated phases of parallel hash join (PHJ).

## Public API (key structs + constants)

### `HashJoinTupleData` [verified-by-code: lines 89-103]

```c
struct HashJoinTupleData {
    union { struct HashJoinTupleData *unshared; dsa_pointer shared; } next;
    uint32 hashvalue;
    /* MinimalTuple follows, MAXALIGN'd */
};
```

`HJTUPLE_OVERHEAD = MAXALIGN(sizeof(HashJoinTupleData))`,
`HJTUPLE_MINTUPLE(hjtup)` accessor.

### Skew optimization [verified-by-code: lines 105-133]

For nonuniform outer distributions: outer MCVs get a dedicated skew
hashtable (`HashSkewBucket`) that never spills.
`SKEW_HASH_MEM_PERCENT = 2`, `SKEW_MIN_OUTER_FRACTION = 0.01`.

### Chunked storage [verified-by-code: lines 135-165]

Tuples packed into 32 kB chunks (`HASH_CHUNK_SIZE`) to amortize
palloc overhead. Per-chunk header tracks `ntuples`, `maxlen`,
`used`. Tuples > `HASH_CHUNK_THRESHOLD` (8 kB) get a dedicated chunk.

### Parallel Hash Join shared state

`ParallelHashJoinBatch` [lines 173-190]: per-batch shared barrier +
chunks/buckets pointers + counters; variable-sized
SharedTuplestore objects follow in memory.

Accessor macros (lines 193-212): `ParallelHashJoinBatchInner(batch)`,
`ParallelHashJoinBatchOuter(batch, nparticipants)`,
`EstimateParallelHashJoinBatch(hashtable)`,
`NthParallelHashJoinBatch(base, n)`.

`ParallelHashJoinBatchAccessor` [lines 218-233]: per-backend
partial counters + `SharedTuplestoreAccessor *` for inner/outer.

`ParallelHashGrowth` enum [lines 241-251]: `PHJ_GROWTH_OK`,
`PHJ_GROWTH_NEED_MORE_BUCKETS`, `PHJ_GROWTH_NEED_MORE_BATCHES`,
`PHJ_GROWTH_DISABLED`.

`ParallelHashJoinState` [lines 257-277]: top-level DSM struct;
`Barrier build_barrier`, `Barrier grow_batches_barrier`,
`Barrier grow_buckets_barrier`, `pg_atomic_uint32 distributor`,
`SharedFileSet fileset`.

### Barrier phases (state machines)

Build phases (lines 280-285): `PHJ_BUILD_ELECT`, `_ALLOCATE`,
`_HASH_INNER`, `_HASH_OUTER`, `_RUN`, `_FREE`.

Batch phases (lines 287-293): `PHJ_BATCH_ELECT`, `_ALLOCATE`,
`_LOAD`, `_PROBE`, `_SCAN`, `_FREE`.

Grow-batches (5 circular phases, line 301) and grow-buckets (3
circular phases, line 307).

### `HashJoinTableData` [verified-by-code: lines 309-381]

The main struct: bucket array (unshared pointer / shared
dsa_pointer union), skew state, batch counters, spill files
(`innerBatchFile[]` / `outerBatchFile[]`), space accounting, three
memory contexts (`hashCxt` / `batchCxt` / `spillCxt`), chunk list,
and parallel state.

Three contexts [from-comment: lines 25-55]:
- `hashCxt` (parent) — whole-join metadata.
- `spillCxt` — temp file buffers, persists across batches.
- `batchCxt` — single-batch storage, reset between batches.

## Invariants

- **INV-POW2-BUCKETS** [verified-by-code: line 312]
  `nbuckets` is a power of 2 (`log2_nbuckets` cached).
- **INV-INCREASING-NBATCH** [from-comment: lines 65-72] Batch
  growth only ever moves tuples to *later* batches — the
  hash-value→batch mapping is arranged so that increasing `nbatch`
  never moves a tuple backward.
- **INV-NULL-KEY-OUTER** [from-comment: lines 74-81] Null-keyed
  tuples on the outer side of an outer join must be emitted with
  null-extension; tuplestore-and-emit-later.
- **INV-CTX-CHAIN** [from-comment: lines 35-50] `spillCxt` and
  `batchCxt` are children of `hashCxt`; reset/discard discipline
  ensures temp files survive batch boundaries but in-memory state
  doesn't.
- **INV-PHASE-MONOTONIC** [verified-by-code: barriers] Each
  participant advances through build / batch phases in order via
  `BarrierAttach`/`BarrierArriveAndWait`. Grow phases are circular
  modulo 5 / 3.

## Trust boundary (Phase D)

- **Spill files** [`innerBatchFile`, `outerBatchFile`, plus
  PHJ `SharedFileSet`]: same posture as
  `sharedtuplestore.h` — raw `MinimalTuple` bytes on disk, postgres-
  uid permission, cleaned up by ResourceOwner.
- **DSM corruption**: parallel hash join's shared state lives in
  DSA. A buggy worker writing past a bucket-array end would corrupt
  the bucket chain for *all* participants — same trust posture as
  any DSM consumer.
- **`distributor` atomic**: lock-free chunk-work-queue stepping;
  starvation if a participant exits mid-build is handled by the
  barrier's `BarrierDetach` path.

## Cross-refs

- `executor/nodeHash.h`, `executor/nodeHashjoin.h` — top-level
  nodes.
- `utils/sharedtuplestore.h` — backing per-batch storage in PHJ.
- `storage/barrier.h` — Barrier primitive.
- `utils/dsa.h` — shared allocation.
- `storage/sharedfileset.h` — spill files.

## Issues

- [ISSUE-DESIGN: many barrier phase constants (PHJ_BUILD_*,
  PHJ_BATCH_*, PHJ_GROW_BATCHES_*, PHJ_GROW_BUCKETS_*); adding a
  state requires touching all participant codepaths plus
  rmgrdesc/explain (medium — documented sufficiently in
  `nodeHash.c` README)] — lines 279-307.
- [ISSUE-PHASE-D: spill files inherit `sharedtuplestore.h` posture
  — column data on disk in clear (medium echo)] — line 358-360.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/executor.md](../../../../subsystems/executor.md)
