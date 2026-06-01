# nodeSort.h

- **Source:** `source/src/include/executor/nodeSort.h` (~32 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## API

`ExecInitSort`, `ExecEndSort`, `ExecSortMarkPos`, `ExecSortRestrPos`,
`ExecReScanSort`. Parallel hooks: `ExecSortEstimate / InitializeDSM /
InitializeWorker / RetrieveInstrumentation`.

Sort supports Mark/Restore (used by MergeJoin's inner), so the planner's
`ExecSupportsMarkRestore` returns true for Sort.

## Tags

- [verified-by-code] surface.
