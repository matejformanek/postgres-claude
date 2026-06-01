# execPartition.h

- **Source:** `source/src/include/executor/execPartition.h` (143 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read (whole file)

## Purpose

Public interface to `execPartition.c`. Two opaque types forward-declared
(`PartitionDispatch`, `PartitionTupleRouting`) plus the entry points used
by `nodeModifyTable.c`, `nodeAppend.c`, `nodeMergeAppend.c`.

## API

### Tuple routing (for DML)

- `ExecSetupPartitionTupleRouting(estate, rel)` — allocate routing state for
  a top-level partitioned target.
- `ExecFindPartition(mtstate, rootResultRelInfo, proute, slot, estate)` —
  route one row to a leaf partition's ResultRelInfo.
- `ExecCleanupTupleRouting(mtstate, proute)` — close lazily-opened partitions.

### Runtime pruning (for Append/MergeAppend)

- `PartitionPruneState` (opaque) — per-Append pruning state.
- `ExecInitPartitionExecPruning(...)` — build the PartitionPruneState from
  the planner's PartitionPruneInfo.
- `ExecFindMatchingSubPlans(prunestate, initial_prune)` — return bitmapset
  of surviving subplan indexes (called from Append/MergeAppend ReScan).
- `ExecDoInitialPruning(estate)` — run the initial pruning pass at
  ExecutorStart.

## Tags

- [verified-by-code] full surface.
