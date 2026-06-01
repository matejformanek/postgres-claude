# nodeHash.c

- **Source:** `source/src/backend/executor/nodeHash.c` (≈3500 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** deep-read

## Purpose

The Hash node's job: scan the inner relation **once**, hash every row, build
the `HashJoinTable`. Always appears as the inner child of a HashJoin. The
HashJoinTable produced is consumed (and torn down) by the HashJoin parent.
See nodeHashjoin.c for the algorithm; this file is the table-management half.

## Key entry points

- `MultiExecHash(HashState*)` `:106` — drains the outerPlan (the inner-side
  child) and inserts every row. "Multi" because the API is the MultiExec
  variant: nodeHashjoin calls `MultiExecProcNode(hashNode)` which returns
  a fully-built `HashJoinTable*` rather than one tuple at a time.
- `ExecHashTableCreate(HashState*)` `:471` — allocate the in-memory bucket
  array, BufFile arrays for non-zero batches, optional skew hashtable.
- `ExecChooseHashTableSize(ntuples, tupwidth, useskew, parallel, parallel_workers, &space_allowed, &nbuckets, &nbatch, &num_skew_mcvs)` `:683`
  — the famous sizing function. Picks `nbatch` and `nbuckets` so that the
  in-memory hashtable + BufFile arrays fit in `work_mem` (or `hash_mem`)
  given the planner's row-count and tuple-width estimates. For parallel,
  divides budget by the number of participants and scales accordingly.
- `ExecHashTableInsert(table, slot, hashvalue)` `:1774` — serial insert.
  If the bucket is in batch 0, allocate from the `chunks` (Bump-context-like
  chunk allocator) and link; otherwise spill via ExecHashJoinSaveTuple.
  Triggers `ExecHashIncreaseNumBatches` `:1055` if `spaceUsed > spaceAllowed`.
- `ExecParallelHashTableInsert*` `:1865, 1931` — same but writes into the
  shared per-batch SharedTuplestore and atomically updates the shared
  bucket head pointer (CAS).
- `ExecHashGetBucketAndBatch(table, hashvalue, &bucket, &batch)` `:1986` —
  decode bucket/batch from hashvalue. Lower `log2(nbuckets)` bits → bucket;
  next `log2(nbatch)` bits → batch.

## In-memory layout

The hashtable owns:
- `buckets.unshared[]` (or `.shared[]`) — head pointer per bucket to a chain
  of `HashJoinTuple` (one MinimalTuple + next pointer + match flag).
- `chunks` — list of `HashMemoryChunk` (≥32KB blocks) that all current-batch
  tuples are bump-allocated from. Lets us free all batch-0 tuples by walking
  this list when we move to the next batch.
- `innerBatchFile[]` / `outerBatchFile[]` — BufFile* arrays of size `nbatch`,
  one each for spilled inner / outer tuples per future batch.
- Optional `skewBucket[]` — separate slots for MCV inner-side keys. Outer
  rows with a matching MCV avoid the main hashtable and join directly here,
  improving cache behaviour for skewed joins.

## Growing

- `ExecHashIncreaseNumBatches` `:1055` — double `nbatch`, walk every batch-0
  tuple, recompute its batch, push spilled ones into their new file. If
  this fails to actually reduce in-memory space (everything still hashes to
  batch 0), disable further batch growth (`growEnabled = false`) and accept
  the over-budget batch.
- `ExecHashIncreaseNumBuckets` `:1612` — double `nbuckets`, redistribute
  in-batch tuples; raises load factor's denominator without re-hashing
  (uses bits already in `hashvalue`).

## Parallel

- `ExecParallelHashJoinSetUpBatches(table, nbatch)` `:3182` — once-only
  setup of N shared `ParallelHashJoinBatch` records in the DSA.
- `ExecParallelHashTableAlloc(table, batchno)` `:3347` — DSA-allocate the
  bucket array for a batch during PHJ_BATCH_ALLOCATE.

## Tags

- [verified-by-code] all entry points + the chunked allocator.
- [from-comment] file header notes about parallelism.
- [inferred] skew bucket cache-locality rationale (consistent with original
  patch commit message).

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/executor.md](../../../../subsystems/executor.md)
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
