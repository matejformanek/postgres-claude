---
path: src/include/executor/nodeForeignscan.h
anchor_sha: 4b0bf0788b0
loc: 38
depth: read
---

# nodeForeignscan.h

- **Source path:** `source/src/include/executor/nodeForeignscan.h`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 38

## Purpose

Prototype header for the `ForeignScan` executor node
(`nodeForeignscan.c`). The generic executor shell that delegates to an
FDW's `FdwRoutine` callbacks (`BeginForeignScan`, `IterateForeignScan`,
`EndForeignScan`, …). Carries parallel support, a `Shutdown` hook, and
the **async-execution** request interface used by Append to overlap
multiple foreign scans. [verified-by-code]

## Public symbols

| Symbol | Kind | Notes |
|---|---|---|
| `ExecInitForeignScan(ForeignScan *, EState *, int eflags)` | init | returns `ForeignScanState *` |
| `ExecEndForeignScan` / `ExecReScanForeignScan` | teardown / rescan | |
| `ExecForeignScanEstimate / InitializeDSM / ReInitializeDSM / InitializeWorker` | parallel-aware | FDW-driven parallel scan |
| `ExecShutdownForeignScan(ForeignScanState *)` | shutdown | early resource release before EndNode |
| `ExecAsyncForeignScanRequest / ConfigureWait / Notify` | async | the `AsyncRequest` state machine for parallel-async Append |

## Invariants & gotchas

- The async trio (`Request` / `ConfigureWait` / `Notify`) is the executor
  side of asynchronous Append — see [[execAsync.md]] for the driver. An
  FDW must implement `IsForeignPathAsyncCapable` + the async callbacks for
  these to fire. [verified-by-code / inferred]
- `ExecShutdownForeignScan` lets the FDW release remote connections/cursors
  before the full `ExecEndNode` teardown (e.g. when a Limit stops the scan
  early). [inferred]

## Cross-refs

- [[execAsync.md]] — async request/response loop.
- [[nodeCustom.h]] — the sibling extension-driven scan shell.

## Tags

- [verified-by-code] prototype surface; [inferred] async/shutdown roles.
