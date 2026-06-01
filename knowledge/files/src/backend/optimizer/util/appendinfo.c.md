# appendinfo.c — parent ↔ child Var translation

- **Source:** 1111 lines · **Last verified commit:** `ef6a95c7c64`
- **Depth:** read

## Purpose

`AppendRelInfo` records the per-child translations needed to map
expressions from an inheritance/UNION-ALL parent to a child. Anything
that needs to push quals down through an Append or pull tlist entries up
goes through this module.

## Key entries

- `make_append_rel_info(parentrel, childrel, parentRTindex, childRTindex)` (51)
  — build mapping (attribute number translation, type/collation checks).
- `adjust_appendrel_attrs(root, node, nappinfos, appinfos)` (200) —
  expression-tree mutator that rewrites Vars from parent attnum to child.
  Run *after* sublink→subplan conversion (no recursion into subqueries).
  [from-comment:192-197]
- `adjust_appendrel_attrs_multilevel` (596) — child can be multiple
  inheritance levels below parent.
- `adjust_child_relids` (629) / `adjust_child_relids_multilevel` (663) —
  substitute child relids in a Relids set.
- `adjust_inherited_attnums` (703) — translate attno integer list.
- `get_translated_update_targetlist` (765) — UPDATE per-child tlist.
- `add_row_identity_var` (863), `add_row_identity_columns` (958),
  `distribute_row_identity_vars` (1039) — ROWID_VAR machinery for
  UPDATE/DELETE/MERGE on inheritance trees; expand_targetlist can't see
  them because it runs pre-expansion. [from-comment:1030-1035]

## Tags
`[verified-by-code]` ×2, `[from-comment]` ×4
