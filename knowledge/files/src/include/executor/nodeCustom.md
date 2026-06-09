# `executor/nodeCustom.h` — CustomScan extension entry-point declarations

**Verified against source pin `4b0bf0788b0`** (path: `source/src/include/executor/nodeCustom.h`)

## Role
Declares the executor dispatch entry points for `CustomScan` — the third-party extension hook for plugging arbitrary scan-shaped nodes into the executor. Comment "prototypes for CustomScan nodes" (nodeCustom.h:5). Pairs with the `CustomScanMethods` / `CustomExecMethods` function-pointer tables in `nodes/extensible.h`; this header is the symmetric core-side dispatcher that calls into those vtables.

## Public API
- General executor:
  - `ExecInitCustomScan(CustomScan *, EState *, int eflags)` — nodeCustom.h:21
  - `ExecEndCustomScan(CustomScanState *)` — nodeCustom.h:23
  - `ExecReScanCustomScan` — nodeCustom.h:25
  - `ExecCustomMarkPos` / `ExecCustomRestrPos` — nodeCustom.h:26-27 (mark/restore for sortable customs)
- Parallel execution support — nodeCustom.h:32-40:
  - `ExecCustomScanEstimate` / `…InitializeDSM` / `…ReInitializeDSM` / `…InitializeWorker`
  - `ExecShutdownCustomScan` (worker-cleanup hook; rare among scan nodes)

## Phase D
HIGH — this is the explicit extension surface. Every entry point dispatches via function pointers in a `CustomExecMethods` vtable supplied by a third-party module loaded via `shared_preload_libraries` or `CREATE EXTENSION`. Citus, TimescaleDB, Hydra Columnar, pg_strom and others all hang execution off this contract. Trust model: any installed extension that registers a `CustomScan` has full backend privilege; no sandbox.

## Cross-refs
- Plan node + method table: `nodes/extensible.h` (`CustomScan`, `CustomScanMethods`, `CustomExecMethods`)
- State node: `CustomScanState` in `nodes/execnodes.h`
- `.c` impl: `source/src/backend/executor/nodeCustom.c`
- Planner registration: `optimizer/planmain.h` / `RegisterCustomScanMethods`
