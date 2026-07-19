# nodeHash.h

- **Source:** `source/src/include/executor/nodeHash.h` (~75 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## API surface

### Node-level
`ExecInitHash`, `MultiExecHash`, `ExecEndHash`, `ExecReScanHash`,
`ExecShutdownHash` (parallel cleanup).

### HashJoinTable lifecycle
- `ExecHashTableCreate / ExecHashTableDestroy`
- `ExecHashTableDetach / ExecHashTableDetachBatch` (parallel-aware drop of
  shared state with reference counting).
- `ExecHashTableReset` (clear in-memory contents at batch transition).
- `ExecHashTableResetMatchFlags` (right/full join requires re-iterating
  unmatched on retry).

### Insertion
`ExecHashTableInsert` (serial), `ExecParallelHashTableInsert` (build phase),
`ExecParallelHashTableInsertCurrentBatch` (probe phase: insert into a batch
that's already in-memory).

### Bucket math
`ExecHashGetBucketAndBatch`, `ExecHashGetSkewBucket`.

### Probe scans
`ExecScanHashBucket` / `ExecParallelScanHashBucket` — walk the chain.
`ExecPrepHashTableForUnmatched` / `ExecScanHashTableForUnmatched` — driver
for RIGHT/FULL/RIGHT ANTI unmatched-inner output.

### Sizing
`ExecChooseHashTableSize(ntuples, tupwidth, useskew, try_combined_hash_mem,
parallel_workers, &space_allowed, &numbuckets, &numbatches, &num_skew_mcvs)`
— the famous planner-and-executor sizing function.

### Parallel + EXPLAIN
`ExecHashEstimate / InitializeDSM / InitializeWorker / RetrieveInstrumentation`,
`ExecHashAccumInstrumentation`.

### Special
`ExecParallelHashTableAlloc(table, batchno)` — DSA-allocate buckets for one
batch; called during PHJ_BATCH_ALLOCATE.
`ExecParallelHashTableSetCurrentBatch` — attach to a chosen batch when
multiple workers split up.
`ExecHashBuildNullTupleStore(table)` — for FULL OUTER JOIN, builds the
all-NULL inner tuple template.

## Tags

- [verified-by-code] full prototype list.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/executor.md](../../../../subsystems/executor.md)
