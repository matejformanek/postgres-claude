# preptlist.c — targetlist preprocessing

- **Source:** `source/src/backend/optimizer/prep/preptlist.c` (540 lines)
- **Last verified commit:** `ef6a95c7c64`
- **Depth:** read

## Purpose

Build the post-rewrite Query's planner-side targetlist:
- INSERT: one entry per target column in correct order
- UPDATE: expressions for new column values, plus junk row-identity
  entries (ctid for heap, …) added by the *planner*, not the parser
- All queries: junk tlist entries for sort keys, RETURNING Vars,
  FOR UPDATE locking, EvalPlanQual. [from-comment:5-19]

## Public entries

- `void preprocess_targetlist(PlannerInfo *root)` (line 65) — stores
  result in `root->processed_tlist`; for UPDATE also fills
  `root->update_colnos`. **`processed_tlist` resnos are consecutive**,
  so column targets must be discovered via `update_colnos` instead.
  [from-comment:60-64]
- `List *extract_update_targetlist_colnos(List *tlist)` (349) — also
  applied to ON CONFLICT DO UPDATE tlist (much later in planning).
  [from-comment:341-346]
- `PlanRowMark *get_plan_rowmark(List *rowmarks, Index rtindex)` (527) —
  lookup; "probably ought to be elsewhere, but no better place".
  [from-comment:520-525]

## Tags
`[verified-by-code]` ×1, `[from-comment]` ×5

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
