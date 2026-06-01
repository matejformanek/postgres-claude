# prepunion.c — set-op planning (UNION/INTERSECT/EXCEPT)

- **Source:** `source/src/backend/optimizer/prep/prepunion.c` (1788 lines)
- **Last verified commit:** `ef6a95c7c64`
- **Depth:** read

## Purpose

Plan SetOperationStmt trees. Two paths exist:

1. **Pure UNION ALL** of simple subqueries → converted into an "append
   relation" (handled by `pull_up_simple_union_all` in prepjointree.c +
   path generation in `allpaths.c`).
2. **Everything else** (INTERSECT, EXCEPT, mixed UNION ALL/DISTINCT) →
   `plan_set_operations` here. [from-comment:7-13]

Filename retained for historical reasons (originally only UNION supported). [from-comment:4-5]

## Public entry

`RelOptInfo *plan_set_operations(PlannerInfo *root)` at line 97. Returns
an upperrel containing at least one Path; also sets `root->processed_tlist`
to the top setop output. ORDER BY / LIMIT are added back by
`grouping_planner` on return. [from-comment:85-95]

## Mental model

Recursively plans each leaf SELECT via `subquery_planner`, then walks
the SetOperationStmt tree bottom-up building Append / SetOp / HashSetOp
paths. UNION-ALL with non-trivial children still pays for sort+unique
unless flattenable; INTERSECT/EXCEPT require sorted or hashed unique
inputs.

## Tags
`[verified-by-code]` ×1, `[from-comment]` ×4

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
