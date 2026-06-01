# parse_cte.c

- **Source:** `source/src/backend/parser/parse_cte.c` (1270 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## Purpose

Handle `WITH` clauses: parse-analyze each CTE body, detect recursion,
order CTEs by dependency, type-check the output columns of recursive
CTEs (the UNION-arm unification), enforce the legal kinds of statements
allowed inside WITH.

## Entries

- `transformWithClause(pstate, withClause)` — top entry, called from
  `transformSelectStmt` / `transformInsertStmt` / etc. Populates
  `pstate->p_ctenamespace` and `Query.cteList`.
- `analyzeCTE` — wrap a single CTE body with `parse_sub_analyze`.
- `analyzeCTETargetList` — produce `cte->ctecolnames` /
  `ctecoltypes` / `ctecoltypmods` / `ctecolcollations` from the resolved
  query.
- `analyzeCTETerm` (for recursive CTEs) — handles the non-recursive vs
  recursive arms separately and unifies column types between them.

## Recursive CTE detection

A CTE is recursive if its body references its own name. The walker
`makeDependencyGraph` produces a Tarjan-SCC DAG; CTEs in a non-singleton
SCC must all be marked `RECURSIVE` and conform to the standard's shape
(non-recursive arm UNION [ALL] recursive arm, where the recursive arm
references the CTE exactly the right way).

## SEARCH / CYCLE

These optional clauses are **not** expanded here — they're stored on the
CTE node and later expanded by `rewriteSearchCycle.c` during
`fireRIRrules`. See `rewriteHandler.c:2049-2063` for the hookup.

## MATERIALIZED hint

`MATERIALIZED` / `NOT MATERIALIZED` is recorded on the `CommonTableExpr`
and consulted by the planner — it controls whether the CTE gets inlined
into the outer query or always materialized as a separate plan node.
