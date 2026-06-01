# setrefs.c — set_plan_references: the planner's last pass

- **Source:** `source/src/backend/optimizer/plan/setrefs.c` (3831 lines)
- **Last verified commit:** `ef6a95c7c64`
- **Depth:** read

## 1. Purpose

Final planner pass over the finished Plan tree. Adjusts representational
details for the executor's convenience; does not change the join order or
cost. [from-comment:227-229]

## 2. What it does (the 9-item contract from the top comment)

1. Flatten subquery rangetables into a single list; null out RTE fields
   the executor doesn't need.
2. Rewrite Vars in scan nodes to match the flat rangetable (varno fixup).
3. Rewrite Vars in upper plan nodes to reference subplan outputs
   (varno=OUTER_VAR/INNER_VAR/INDEX_VAR with varattno = subplan tlist
   position).
4. Adjust Aggrefs (partial aggregation, minmax replacement).
5. PARAM_MULTIEXPR → PARAM_EXEC.
6. AlternativeSubPlan → pick one alternative based on estimated calls.
7. Compute regproc OIDs for operators.
8. Build plan dependency lists: `relationOids` (relations) +
   `invalItems` (functions/domains) — fed to plancache for invalidation.
9. Assign every plan node a unique `plan_node_id`. [from-comment:231-258]

Plus an extra "final optimization": delete useless SubqueryScan / Append
/ MergeAppend nodes — must be done *here*, not earlier, because earlier
removal would break `set_upper_references` (Var numbering mismatch
across the buffer those nodes provide). [from-comment:260-272]

## 3. Mutation discipline

- Plan nodes are mutated in-place (single-referenced post-planning).
- Expressions go through `expression_tree_mutator` because they may be
  shared. [from-comment:285-289]
- Recursive walk; return value is normally the same Plan but may differ
  when the node is dropped. [from-comment:273-276]

## 4. Other public entry points

| Line | Function | Notes |
|---|---|---|
| 290 | `set_plan_references` | The main entry |
| 1527 | `trivial_subqueryscan(SubqueryScan *)` | Checks if a SubqueryScan can be flattened; const/resjunk must be preserved [from-comment:1517-1525] |
| 3598 | `find_minmax_agg_replacement_param` | Used by SS_finalize_plan *before* setrefs runs |
| 3631 | `record_plan_function_dependency` | Skips built-in funcs (assumed never to change in plan-invalidating ways) [from-comment:3632-3636] |
| 3671 | `record_plan_type_dependency` | Currently unused for domains (CoerceToDomain handled elsewhere) |
| 3712 | `extract_query_dependencies` | Walks pre-planning query tree for cached-plan deps; doesn't see inlined funcs / elided CoerceToDomain [from-comment:3705-3710] |
| 3748 | `extract_query_dependencies_walker` | Exported for `expression_planner_with_deps` |

## 5. Globals written

`root->glob->finalrtable`, `finalrowmarks`, `resultRelations`,
`appendRelations`, `relationOids`, `invalItems` — all appended-to.
[from-comment:278-283]

## 6. Tags
`[verified-by-code]` ×3, `[from-comment]` ×10

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
