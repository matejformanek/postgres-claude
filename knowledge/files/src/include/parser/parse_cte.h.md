# parse_cte.h

- **Source:** `source/src/include/parser/parse_cte.h` (~20 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## Purpose

CTE entry points. Two functions:

```c
extern List *transformWithClause(ParseState *, WithClause *);
extern void  analyzeCTETargetList(ParseState *, CommonTableExpr *, List *tlist);
```

The first transforms WITH and pushes CTEs into `pstate->p_ctenamespace`.
The second is the recursive-CTE result-type unifier between the
non-recursive and recursive arms; called from
`analyze.c:transformSetOperationStmt` when the SET op is the recursive
union.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/parser-and-rewrite.md](../../../../subsystems/parser-and-rewrite.md)
