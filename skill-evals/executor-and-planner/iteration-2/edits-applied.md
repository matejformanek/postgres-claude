# Iteration 2 — edits applied

All four proposed edits from `iteration-1/proposed-edits.md` were applied
to `.claude/skills/executor-and-planner/SKILL.md`.

## Edit 1 — Tag-asymmetry callout (Part A.2)

Inserted an explicit callout box just after the numbered list of dispatch
switches, naming the Plan-tag vs PlanState-tag distinction as the #1
cause of "unrecognized node type". Also notes that `MultiExecProcNode`
uses the PlanState tag.

## Edit 2 — MultiExecProcNode as 4th switch (Part A.2)

Promoted `MultiExecProcNode` from a trailing remark into a 4th entry of
the numbered list, with explicit "only if the node returns something
other than tuples" gating and an explicit "tuple-returning scans and
joins do NOT need a case here" counterexample.

## Edit 3 — setrefs.c cite path (Common mistakes)

Extended the `set_plan_references` bullet with verified line numbers:

- `set_plan_refs` at `setrefs.c:642` (verified via grep — note the
  proposed edit said ~1100, which was wrong; corrected to 642).
- `fix_scan_expr` at `setrefs.c:160`.
- `fix_join_expr` at `setrefs.c:186`.
- `fix_upper_expr` at `setrefs.c:196`.
- `set_plan_references` itself at `setrefs.c:291`.

Also explicitly named the three responsibilities of `set_plan_references`
(finalrtable / relationOids / invalItems) inline — this targets the
assertion 2.6 partial in iter-1.

## Edit 4 — Forward reference to parser-and-nodes skill (Part A.1)

Added a short parenthetical pointer to the `parser-and-nodes` skill at
the top of A.1, so readers landing on A.1 cold see the dependency before
A.6.

## Verification notes

- Grep confirmed `set_plan_refs` is at line 642, `fix_scan_expr` at 160,
  `fix_join_expr` at 186, `fix_upper_expr` at 196, `set_plan_references`
  at 291 in `source/src/backend/optimizer/plan/setrefs.c`.
- All edits preserve existing structure; no content was removed.
