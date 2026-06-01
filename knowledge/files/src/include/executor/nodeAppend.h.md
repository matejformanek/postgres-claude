# nodeAppend.h

- **Source:** `source/src/include/executor/nodeAppend.h` (~30 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## API

`ExecInitAppend`, `ExecEndAppend`, `ExecReScanAppend`, plus the parallel
DSM hooks (Estimate / InitializeDSM / ReInitializeDSM / InitializeWorker),
plus `ExecAsyncAppendResponse(AsyncRequest *)` — callback registered with
execAsync for FDW async-capable children.

## Tags

- [verified-by-code] complete surface.
