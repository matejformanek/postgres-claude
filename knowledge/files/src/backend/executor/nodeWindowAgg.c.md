# nodeWindowAgg.c

- **Source:** `source/src/backend/executor/nodeWindowAgg.c` (≈4100 lines, 129 KB)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** deep-read (architecture only)

## Purpose

Evaluates **window functions** (`OVER (PARTITION BY … ORDER BY … frame_spec)`).
Input must already arrive sorted by `partition keys, order keys`; the planner
inserts the necessary Sort. One WindowAgg evaluates all window functions
sharing identical OVER specs; multiple distinct OVER specs become stacked
WindowAggs separated by Sorts. [from-comment] `:5-23`

## Two kinds of "window functions"

1. **True window functions** (e.g. row_number, rank, lead/lag, ntile).
   Called via the WindowObject API that lets them peek at any row in the
   current partition.
2. **Plain aggregate functions used as windows** (e.g.
   `SUM(x) OVER (ORDER BY t)`). These reuse Agg-style transition machinery
   but reset/restart per partition and recompute as the frame slides.
   [from-comment] `:18-23`

## Partition processing

- Tuples are buffered into a per-partition Tuplestorestate. Window functions
  randomly seek to specific rows within the current partition through
  Tuplestore positions (mark/restore semantics).
- We never buffer more than one partition at a time; on partition boundary,
  finalize, emit, then reset and start the next.

## Frame specification

Frames are described by `frameOptions` (`ROWS | RANGE | GROUPS` × `BETWEEN
start AND end`). Edge tracking is incremental: as the current row advances,
we move the frame head/tail pointers and adjust transition state via:

- **agg_transfn + retract_inverse_transfn** — when the frame's lower bound
  advances past a row, retract it from the aggregate via the inverse
  transition function (the planner picks aggregates that have an inverse
  transition for sliding-window aggregation; without an inverse, the agg
  re-aggregates the whole frame each row, which is expensive).
- **special peer-row handling for RANGE/GROUPS** — peer = rows with equal
  ORDER BY key; framing decisions look at peer-group boundaries.

## EXCLUDE clause

`EXCLUDE CURRENT ROW | GROUP | TIES | NO OTHERS`. Implemented by remembering
which rows fall in the "excluded" sub-set and removing their contribution
from transitions, again via inverse-transition when available.

## Tags

- [verified-by-code] partition tuplestore + frame variables.
- [from-comment] purpose statement + plain-agg-as-window note.
- [inferred] inverse-transition is what makes sliding-window aggregates fast
  (consistent with code; the alternative is re-aggregating per output row).

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/executor.md](../../../../subsystems/executor.md)
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
