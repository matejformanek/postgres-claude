# `executor/nodeMergeAppend.h` — ordered Append declarations

**Verified against source pin `4b0bf0788b0`** (path: `source/src/include/executor/nodeMergeAppend.h`)

## Role
Declares entry points for `MergeAppend` — combines multiple sorted child subplans into one merged sorted output via a binary-heap k-way merge. The ordered analogue of `Append`; commonly used for partitioned tables where each child returns rows in the same sort order.

## Public API
- `ExecInitMergeAppend(MergeAppend *, EState *, int eflags)` — nodeMergeAppend.h:19
- `ExecEndMergeAppend(MergeAppendState *)` — nodeMergeAppend.h:20
- `ExecReScanMergeAppend(MergeAppendState *)` — nodeMergeAppend.h:21

## Cross-refs
- Plan node: `MergeAppend` in `nodes/plannodes.h`
- State node: `MergeAppendState` in `nodes/execnodes.h`
- Sibling (unordered): `executor/nodeAppend.h`
- `.c` impl: `source/src/backend/executor/nodeMergeAppend.c`
- Heap: `lib/binaryheap.h`
