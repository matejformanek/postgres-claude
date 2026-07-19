# `executor/nodeMaterial.h` — Materialize node declarations

**Verified against source pin `4b0bf0788b0`** (path: `source/src/include/executor/nodeMaterial.h`)

## Role
Declares entry points for `Material` — buffers all child tuples into a tuplestore on first read, then serves rescans from the store. Used to make a non-rescannable child rescannable (e.g. inner side of a Nested Loop where the child is a `Sort` or `FunctionScan`) and as a mark/restore target for Merge Join.

## Public API
- `ExecInitMaterial(Material *, EState *, int eflags)` — nodeMaterial.h:19
- `ExecEndMaterial(MaterialState *)` — nodeMaterial.h:20
- `ExecMaterialMarkPos` / `ExecMaterialRestrPos` — nodeMaterial.h:21-22 (Merge-Join mark/restore)
- `ExecReScanMaterial(MaterialState *)` — nodeMaterial.h:23

## Cross-refs
- Plan node: `Material` in `nodes/plannodes.h`
- State node: `MaterialState` in `nodes/execnodes.h`
- `.c` impl: `source/src/backend/executor/nodeMaterial.c`
- Tuplestore: `utils/tuplestore.h`
- Consumer for mark/restore: `executor/nodeMergejoin.h`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/executor.md](../../../../subsystems/executor.md)
