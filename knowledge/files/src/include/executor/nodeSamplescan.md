# `executor/nodeSamplescan.h` — TABLESAMPLE scan declarations

**Verified against source pin `4b0bf0788b0`** (path: `source/src/include/executor/nodeSamplescan.h`)

## Role
Declares entry points for `SampleScan` — the executor node for SQL `TABLESAMPLE` clauses. Dispatches into a `TsmRoutine` method table (`access/tsmapi.h`) provided by a sampling method (`SYSTEM`, `BERNOULLI`, or contrib `tsm_system_rows`, `tsm_system_time`).

## Public API
- `ExecInitSampleScan(SampleScan *, EState *, int eflags)` — nodeSamplescan.h:19
- `ExecEndSampleScan(SampleScanState *)` — nodeSamplescan.h:20
- `ExecReScanSampleScan(SampleScanState *)` — nodeSamplescan.h:21

## Phase D
Sampling-method extension surface (A14 echo). `tsm_system_rows` and `tsm_system_time` are contrib extensions; arbitrary third-party TSM methods can be loaded and invoked by any user with `SELECT` on the table. The TSM `NextSampleBlock` / `NextSampleTuple` callbacks run in backend context with full privilege — same trust model as Custom and Foreign scans.

## Cross-refs
- Plan node: `SampleScan` in `nodes/plannodes.h`
- State node: `SampleScanState` in `nodes/execnodes.h`
- TSM vtable: `access/tsmapi.h` (`TsmRoutine`)
- `.c` impl: `source/src/backend/executor/nodeSamplescan.c`
- Builtin methods: `access/tablesample/system.c`, `bernoulli.c`
- Contrib: `contrib/tsm_system_rows/`, `contrib/tsm_system_time/`
