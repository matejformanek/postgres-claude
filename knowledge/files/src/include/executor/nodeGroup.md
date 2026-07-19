# `executor/nodeGroup.h` — Group (presorted grouping) declarations

**Verified against source pin `4b0bf0788b0`** (path: `source/src/include/executor/nodeGroup.h`)

## Role
Declares entry points for `Group` — collapses runs of duplicate grouping keys from a presorted child into one output row each. Distinct from `Agg` (which both groups and aggregates); `Group` purely deduplicates by key.

## Public API
- `ExecInitGroup(Group *, EState *, int eflags)` — nodeGroup.h:19
- `ExecEndGroup(GroupState *)` — nodeGroup.h:20
- `ExecReScanGroup(GroupState *)` — nodeGroup.h:21

## Cross-refs
- Plan node: `Group` in `nodes/plannodes.h`
- State node: `GroupState` in `nodes/execnodes.h`
- Sibling (aggregating): `executor/nodeAgg.h`
- `.c` impl: `source/src/backend/executor/nodeGroup.c`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/executor.md](../../../../subsystems/executor.md)
