# parse_target.h

- **Source:** `source/src/include/parser/parse_target.h` (~55 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## Purpose

API for target-list construction.

## Exported symbols

- `transformTargetEntry` — single expression → `TargetEntry`.
- `transformTargetList` — `List<ResTarget>` → `List<TargetEntry>` (handles
  `*` expansion).
- `transformAssignedExpr` — coerce RHS for UPDATE/INSERT assignment.
- `updateTargetListEntry` — used during INSERT-from-SELECT to wire
  assigned columns.
- `transformExpressionList` — used for VALUES / IN / row-comparison RHS.
- `resolveTargetListUnknowns` — at end of SELECT analysis, resolve
  UNKNOWN-typed outputs as TEXT.
- `markTargetListOrigins` — fill `resorigtbl`/`resorigcol` for SELECT.
- `FigureColname` / `FigureIndexColname` — output column name heuristics.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/parser-and-rewrite.md](../../../../subsystems/parser-and-rewrite.md)
