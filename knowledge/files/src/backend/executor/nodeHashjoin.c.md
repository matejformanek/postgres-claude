# nodeHashjoin.c

- **Source:** `source/src/backend/executor/nodeHashjoin.c` (≈2000 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** deep-read (full state machine + parallel barrier protocol)

## Purpose

Implements the **hybrid hashjoin** of Zeller & Gray 1990: if inner relation
fits in memory, do a one-pass classical hashjoin; otherwise partition both
sides on hashbits into `n_batches` (power of 2) and process batches one at
a time. Parallel-aware variant uses a Barrier-coordinated shared hashtable.
[from-comment] `:13-26, 58-160`

## Serial state machine `:182-189`

`HJ_BUILD_HASHTABLE → HJ_NEED_NEW_OUTER → HJ_SCAN_BUCKET →
(HJ_FILL_OUTER_TUPLE | HJ_FILL_INNER_TUPLES | …) → HJ_NEED_NEW_BATCH → …`

Implemented as one `pg_attribute_always_inline` function `ExecHashJoinImpl`
`:225` taking `bool parallel`, so the compiler emits two specialized
versions: `ExecHashJoin` `:802` (parallel=false) and
`ExecParallelHashJoin` `:818` (parallel=true), each with the dead branches
DCE'd. This is the cleanest "specialize at compile time" trick in the
executor.

## Batching

- `n_batches` is always a power of 2; lower bits of the hash select bucket,
  higher bits select batch.
- During build (serial): if `hash_mem` exhausted while inserting into
  batch 0, double `n_batches` and move existing tuples to either current
  or a higher batch based on the new bit. `:31-42`
- Outer-side tuples whose batch ≠ 0 are saved into a per-batch BufFile via
  `ExecHashJoinSaveTuple` `:1571` and `ExecHashJoinGetSavedTuple` `:1612`.
- `ExecHashJoinNewBatch` `:1279` loads the next batch's inner side back
  into the hashtable and rewinds the outer-side BufFile.

## Parallel state machine

`PHJ_BUILD_ELECT → PHJ_BUILD_ALLOCATE → PHJ_BUILD_HASH_INNER → PHJ_BUILD_HASH_OUTER
→ PHJ_BUILD_RUN → PHJ_BUILD_FREE` coordinated by a **Barrier** (Barriers are
declared in `storage/ipc/barrier.c`). [from-comment] `:91-96`

Per-batch barriers:
`PHJ_BATCH_ELECT → PHJ_BATCH_ALLOCATE → PHJ_BATCH_LOAD → PHJ_BATCH_PROBE →
PHJ_BATCH_SCAN → PHJ_BATCH_FREE`. Batch 0 starts at PHJ_BATCH_PROBE because
its hashtable was filled during BUILD_HASH_INNER. [from-comment] `:130-139`

**Deadlock avoidance**: backends never wait on a barrier while holding output
they could be drained on. Specifically the build/batch barriers are advanced
from PHJ_BUILD_RUN → PHJ_BUILD_FREE and PHJ_BATCH_PROBE → PHJ_BATCH_SCAN using
`BarrierArriveAndDetach` / `BarrierArriveAndDetachExceptLast` so attached
backends emit tuples without ever waiting. [from-comment] `:146-158`

## Parallel partitioning of outer

`ExecParallelHashJoinPartitionOuter` `:1782` — multi-batch parallel hashjoin
must partition the outer side up front (unlike serial, which streams). Done
during PHJ_BUILD_HASH_OUTER.

## Outer-tuple fetch

- Serial: `ExecHashJoinOuterGetTuple` `:1110` — first call drains the outer
  PlanState into `hj_OuterTupleSlot`, computes hash, picks batch.
- Parallel: `ExecParallelHashJoinOuterGetTuple` `:1197` — same idea but
  reads from a shared SharedTuplestore for non-batch-0 outers.

## Right / Full join unmatched-inner scan

When the join needs to emit unmatched inner rows (RIGHT, FULL, RIGHT ANTI),
`HJ_FILL_INNER_TUPLES` walks every inner-hash entry whose `match` bit is
unset. In parallel, this is done by one elected backend per batch (the
`PHJ_BATCH_SCAN*` phase).

## Tags

- [verified-by-code] state-machine constants, the impl-inline trick, entry points.
- [from-comment] the complete parallel barrier-phase narrative.
- [from-comment] the deadlock-avoidance reasoning.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/executor.md](../../../../subsystems/executor.md)
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
