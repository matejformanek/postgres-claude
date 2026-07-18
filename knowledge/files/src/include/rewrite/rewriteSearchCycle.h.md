# rewriteSearchCycle.h

- **Source:** `source/src/include/rewrite/rewriteSearchCycle.h` (~20 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## Purpose

One function:

```c
extern CommonTableExpr *rewriteSearchAndCycle(CommonTableExpr *cte);
```

Called only by `rewriteHandler.c:fireRIRrules` at `:2060`. The CTE comes
in with `search_clause` / `cycle_clause` set; returns a CTE with those
cleared and the equivalent extra columns/quals merged into the body
Query.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/parser-and-rewrite.md](../../../../subsystems/parser-and-rewrite.md)
