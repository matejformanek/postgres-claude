# `executor/nodeForeignscan.h` — ForeignScan FDW-dispatch declarations

**Verified against source pin `4b0bf0788b0`** (path: `source/src/include/executor/nodeForeignscan.h`)

## Role
Declares the core-side executor entry points for `ForeignScan` — the FDW (Foreign Data Wrapper) plan node. Each entry dispatches into the `FdwRoutine` function-pointer table provided by the FDW (postgres_fdw, file_fdw, etc.). Parallel-aware and async-capable.

## Public API
- Standard scan lifecycle — nodeForeignscan.h:20-22:
  - `ExecInitForeignScan` / `ExecEndForeignScan` / `ExecReScanForeignScan`
- Parallel execution — nodeForeignscan.h:24-32:
  - `ExecForeignScanEstimate` / `…InitializeDSM` / `…ReInitializeDSM` / `…InitializeWorker`
  - `ExecShutdownForeignScan`
- Async execution (Append-driven async) — nodeForeignscan.h:34-36:
  - `ExecAsyncForeignScanRequest(AsyncRequest *)`
  - `ExecAsyncForeignScanConfigureWait(AsyncRequest *)`
  - `ExecAsyncForeignScanNotify(AsyncRequest *)`

## Phase D
HIGH — FDW trust boundary. `postgres_fdw` (A11 echo) opens libpq connections to remote servers with credentials from the `USER MAPPING` catalog; connection-cache reuse means a session that switched roles may still hold a remote connection authenticated as the previous role unless explicit invalidation hooks fire. Async path makes timing and retry semantics non-obvious.

## Cross-refs
- Plan node: `ForeignScan` in `nodes/plannodes.h`
- State node: `ForeignScanState` in `nodes/execnodes.h`
- FDW vtable: `foreign/fdwapi.h` (`FdwRoutine`)
- Async framework: `executor/execAsync.h` (`AsyncRequest`)
- `.c` impl: `source/src/backend/executor/nodeForeignscan.c`
- postgres_fdw connection cache: `contrib/postgres_fdw/connection.c`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/executor.md](../../../../subsystems/executor.md)
