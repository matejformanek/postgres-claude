# nodeGroup.c

- **Source:** `source/src/backend/executor/nodeGroup.c` (≈200 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## Purpose

Implements bare `GROUP BY` **without** aggregates — i.e., "return one row per
group". Input must be pre-sorted by the group columns; the node walks until
the group key changes, then emits the first row of each group.

Compare with nodeAgg.c (group + aggregate values) and nodeUnique.c (which
removes duplicates). Group is rarely useful on its own; the planner often
prefers HashAgg or sorted-Agg even when no aggregates exist, but Group
remains the fallback for SELECT DISTINCT ON or specific cases.

## Mechanics

`ExecGroup`: pull rows; compare each new row's grouping columns to the
previous group's first row via the precompiled equality ExprState
(`ExecBuildGroupingEqual`). On mismatch, emit the previous group's first
row and start a new group.

## Tags

- [verified-by-code] equality ExprState use.
- [from-comment] interface comment at top.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/executor.md](../../../../subsystems/executor.md)
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
