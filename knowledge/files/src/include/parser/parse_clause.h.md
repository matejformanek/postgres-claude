# parse_clause.h

- **Source:** `source/src/include/parser/parse_clause.h` (~57 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## Purpose

Prototypes for `parse_clause.c` — the WHERE / FROM / GROUP / ORDER / LIMIT /
WINDOW / FOR UPDATE / ON CONFLICT entry points.

## Exported symbols

`transformFromClause`, `transformWhereClause`, `transformLimitClause`,
`transformGroupClause`, `transformSortClause`, `transformDistinctClause`,
`transformDistinctOnClause`, `transformWindowDefinitions`,
`transformOnConflictArbiter`, plus the locking-clause helpers.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/parser-and-rewrite.md](../../../../subsystems/parser-and-rewrite.md)
