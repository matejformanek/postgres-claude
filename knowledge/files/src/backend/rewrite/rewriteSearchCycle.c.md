# rewriteSearchCycle.c

- **Source:** `source/src/backend/rewrite/rewriteSearchCycle.c` (681 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## Purpose

Expand `SEARCH BREADTH FIRST BY ...` / `SEARCH DEPTH FIRST BY ...` and
`CYCLE ... SET ... TO ... DEFAULT ...` clauses on recursive CTEs into the
equivalent extra columns and qualifications the planner can handle
directly. SQL spec §7.16 mechanics.

## Entry

- `rewriteSearchAndCycle(CommonTableExpr *cte)` — called from
  `rewriteHandler.c:2060` inside `fireRIRrules`. Mutates a copy of the
  CTE: adds an extra ordering column (BFS uses a depth counter; DFS uses
  an array of the row's path), adds a cycle-detection helper column
  (array of visited keys), wraps the outer query to project / filter
  appropriately.

## Why it lives in rewrite/

Conceptually this is parser-level lowering, but it's done after parse
analysis because:

- The CTE column types must already be resolved (we synthesize columns
  of compatible types).
- The expansion produces nontrivial expression trees that re-use
  rewriter helpers (`OffsetVarNodes`, `ReplaceVarsFromTargetList` from
  `rewriteManip.c`).

## Related

- SQL spec ISO/IEC 9075-2 §7.16 — SEARCH and CYCLE clause semantics.
- `parse_cte.c` — leaves the SEARCH/CYCLE clauses untransformed on the
  `CommonTableExpr` for this file to consume.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
- [subsystems/parser-and-rewrite.md](../../../../subsystems/parser-and-rewrite.md)
