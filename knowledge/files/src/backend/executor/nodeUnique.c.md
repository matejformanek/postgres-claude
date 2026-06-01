# nodeUnique.c

- **Source:** `source/src/backend/executor/nodeUnique.c` (≈160 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## Purpose

Drops consecutive duplicate tuples — used to implement `SELECT DISTINCT`
when input is already sorted, and for `UNION` (the planner sticks a Unique
above a Sort over UNION ALL).

Input must be pre-sorted by the columns to dedup; the node compares each
arriving row to the previously emitted row using a compiled equality
ExprState. [from-comment NOTES]

## Mechanics

`ExecUnique`: read from outer; compare to `last_tuple_emitted`; emit and
update on mismatch, drop on match.

For hash-based DISTINCT, the planner uses HashAgg with no aggregates rather
than Unique.

## Tags

- [verified-by-code] equality probe + interface.
- [from-comment] NOTES section at top.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/executor.md](../../../../subsystems/executor.md)
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
