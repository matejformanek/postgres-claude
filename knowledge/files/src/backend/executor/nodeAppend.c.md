# nodeAppend.c

- **Source:** `source/src/backend/executor/nodeAppend.c` (≈1000 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** deep-read

## Purpose

Iteratively drain a list of subplans, concatenating their outputs. Used for
UNION ALL, inheritance, and partitioned-table scans. Also the home of
**runtime partition pruning** and **parallel Append** coordination.
[from-comment] `:15-43`

## Three variants in one node

1. **Plain serial Append** — round-robin `whichplan`; trivially yields rows
   from each subplan in turn.
2. **Parallel Append** — coordinated via shared `ParallelAppendState`
   (sized in `ExecAppendEstimate`, populated in `ExecAppendInitializeDSM`).
   Backends grab subplans from a shared work queue. "Costly" subplans go
   first and are claimed by one worker each; "cheap" subplans can be shared
   (multiple workers join a parallel-aware child). This is what the planner
   labels with `first_partial_plan` — subplans below it are exclusive,
   above are shared.
3. **Async Append** — when subplans include async-capable children
   (ForeignScans on different remote servers). Uses
   `ExecAppendAsyncEventWait` to drive a WaitEventSet across all async
   children's fds and pull whichever returns first. The protocol is
   described in execAsync.c.

## Runtime pruning

`ExecCreatePartitionPruneState` (execPartition.c) is called from init when
the Append's plan has a `PartitionPruneInfo`. Each ReScan with relevant
`chgParam` calls `ExecFindMatchingSubPlans` to recompute the surviving
subplans (an integer bitmapset). Subplans pruned at init time are never
even initialized — `appendplans[]` may have gaps. Subplans pruned at rescan
are skipped without de-init.

## ExecAppend per-row

A flag tracks current `whichplan`. We ExecProcNode the current subplan; on
NULL, advance to the next that survived pruning. The async variant overrides
this with the wait-loop.

## ReScan

`ExecReScanAppend` rescans every active subplan (those whose chgParam needs
it); some pruning can shed children entirely.

## Tags

- [verified-by-code] coordination structures + variants.
- [from-comment] interface routines at top.
- [from-README] async-exec protocol.
