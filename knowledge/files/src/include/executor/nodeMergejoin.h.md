# nodeMergejoin.h

- **Source:** `source/src/include/executor/nodeMergejoin.h` (~25 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## API

Just three prototypes: `ExecInitMergeJoin`, `ExecEndMergeJoin`,
`ExecReScanMergeJoin`. No parallel hooks (Merge Join is not parallel-aware
— parallelism is achieved by running it inside parallel workers via
partial outer/inner plans).

## Tags

- [verified-by-code] full surface.
