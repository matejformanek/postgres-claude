# parse_agg.h

- **Source:** `source/src/include/parser/parse_agg.h` (~60 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## Purpose

Aggregate / window-function entry points.

## Exported entries

- `transformAggregateCall` — finalize an `Aggref` (FILTER, ORDER BY,
  DISTINCT, ordered-set bookkeeping).
- `transformWindowFuncCall` — finalize a `WindowFunc`; resolve the named
  window definition.
- `parseCheckAggregates` — the post-pass that enforces "every
  non-grouped col must be in GROUP BY".
- `expand_grouping_sets` — normalize GROUPING SETS / ROLLUP / CUBE.
- `make_agg_arg` — helper for grammar wiring of agg argument lists.
- `build_aggregate_*_expr` family — used by both planner and parser to
  construct the various aggregate node shapes (count, sum, array_agg).

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/parser-and-rewrite.md](../../../../subsystems/parser-and-rewrite.md)
