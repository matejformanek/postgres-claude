# nodeHashjoin.h

- **Source:** `source/src/include/executor/nodeHashjoin.h` (~35 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## API

`ExecInitHashJoin`, `ExecEndHashJoin`, `ExecReScanHashJoin`,
`ExecShutdownHashJoin` (pre-end cleanup for parallel — detaches the
ParallelHashJoinState barrier before workers exit).

Parallel DSM hooks: `ExecHashJoinEstimate / InitializeDSM /
ReInitializeDSM / InitializeWorker`.

Exported tuple spill helper:
`ExecHashJoinSaveTuple(MinimalTuple, hashvalue, BufFile**, HashJoinTable)` —
called from both serial and parallel paths to spill an over-budget tuple to
its target batch's BufFile.

## Tags

- [verified-by-code] full surface.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/executor.md](../../../../subsystems/executor.md)
