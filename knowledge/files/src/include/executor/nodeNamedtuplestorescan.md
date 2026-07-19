# `executor/nodeNamedtuplestorescan.h` — Named tuplestore scan declarations

**Verified against source pin `4b0bf0788b0`** (path: `source/src/include/executor/nodeNamedtuplestorescan.h`)

## Role
Declares entry points for `NamedTuplestoreScan` — reads from a named tuplestore registered in the EState. Used to expose `OLD`/`NEW` transition tables to AFTER-statement triggers and similar transition-set features.

## Public API
- `ExecInitNamedTuplestoreScan(NamedTuplestoreScan *, EState *, int eflags)` — nodeNamedtuplestorescan.h:19
- `ExecReScanNamedTuplestoreScan(NamedTuplestoreScanState *)` — nodeNamedtuplestorescan.h:20

## Notes
No `ExecEnd*` decl — cleanup folds into the generic executor shutdown via the tuplestore's owning context.

## Cross-refs
- Plan node: `NamedTuplestoreScan` in `nodes/plannodes.h`
- State node: `NamedTuplestoreScanState` in `nodes/execnodes.h`
- Registration: `commands/trigger.h` (transition tables)
- `.c` impl: `source/src/backend/executor/nodeNamedtuplestorescan.c`
- Tuplestore: `utils/tuplestore.h`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/executor.md](../../../../subsystems/executor.md)
