# nodeMergeAppend.c

- **Source:** `source/src/backend/executor/nodeMergeAppend.c` (≈400 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## Purpose

Like Append, but children each deliver tuples in a common sort order, and
this node **k-way-merges** them via a binary heap so total output is sorted.
Used when the planner needs ordering from partitioned/inherited scans for
ORDER BY (e.g., index scans on each child sharing the index order).
[from-comment] `:22-27`

## Mechanics

- `binaryheap` (lib/binaryheap.c) keyed by the sort key columns of the
  current top tuple of each subplan.
- Init: pull first tuple from each subplan, push onto heap.
- Per call: pop top, return it, pull next from that subplan; if a row was
  pulled, push back, else mark that subplan dead. Continue until heap empty.

## Runtime pruning

Shares `PartitionPruneState` with Append — same `ExecFindMatchingSubPlans`
mechanism. Pruned-at-init subplans are absent from the heap entirely.

## No parallel coordination

MergeAppend is not parallel-aware; the planner uses GatherMerge above
partial subplans instead.

## Tags

- [verified-by-code] heap interface usage.
- [from-comment] purpose statement.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/executor.md](../../../../subsystems/executor.md)
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
