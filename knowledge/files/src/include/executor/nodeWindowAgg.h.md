# nodeWindowAgg.h

- **Source:** `source/src/include/executor/nodeWindowAgg.h` (~25 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## API

`ExecInitWindowAgg`, `ExecEndWindowAgg`, `ExecReScanWindowAgg`. Nothing
else. WindowAgg is not parallel-aware (the planner stacks WindowAgg above
Gather or other sort-providing nodes, not the reverse).

## Tags

- [verified-by-code] full surface.
