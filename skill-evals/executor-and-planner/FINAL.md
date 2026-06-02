# executor-and-planner skill — FINAL eval report

## Headline

| Iteration | with_skill score | % | Baseline |
|-----------|-----------------:|--:|---------:|
| iter-1    | 19.5 / 22        | 88.6 | (not measured) |
| iter-2    | **22 / 22**      | **100.0** | 15 / 22 (68.2%) |
| **Delta** | **+2.5 / 22**    | **+11.4 pp** | — |

The four edits applied between iter-1 and iter-2 closed every remaining gap
in iter-1's grading rubric.

## What changed

Four edits to `.claude/skills/executor-and-planner/SKILL.md`:

1. **Tag-asymmetry callout** in Part A.2 — names the Plan-tag vs
   PlanState-tag distinction as the #1 cause of "unrecognized node type",
   pre-derived so the answerer doesn't have to reason from function
   signatures.
2. **`MultiExecProcNode` promoted to 4th switch** in Part A.2, with
   explicit gating ("only if the node returns something other than
   tuples") and an explicit counterexample ("tuple-returning scans and
   joins do NOT need a case here").
3. **`setrefs.c` cite path** added to Common Mistakes, with verified
   line numbers: `set_plan_refs` at `setrefs.c:642`, `fix_scan_expr` at
   `setrefs.c:160`, `fix_join_expr` at `setrefs.c:186`, `fix_upper_expr`
   at `setrefs.c:196`, `set_plan_references` itself at `setrefs.c:291`.
   Note: the original proposed edit guessed ~1100 for `set_plan_refs`;
   grep showed 642 — corrected before applying. Also explicitly names
   the three responsibilities (finalrtable / relationOids / invalItems).
4. **Forward reference to `parser-and-nodes` skill** in Part A.1 so
   readers landing on A.1 cold see the NodeTag dependency before A.6.

## How the deltas map to assertion-level changes

| Assertion | iter-1 | iter-2 | Caused by |
|-----------|--------|--------|-----------|
| 1.8 (close-relations in ExecEnd) | partial-B | pass | Existing skill content was sufficient once reread; both attempts now cite the rule. |
| 2.6 (finalrtable/relationOids/invalItems) | partial-A | pass | Edit 3 explicitly names invalItems. |
| 3.2 (Plan-tag vs PlanState-tag asymmetry) | partial-B | pass | Edit 1 callout box. |
| 3.6 (which switch fires) | partial-A | pass | Existing skill content + the new tag callout made the localization step natural. |
| 3.7 (MultiExecProcNode skip-for-tuples) | fail-A | pass | Edit 2 promotion to 4th switch. |

## Baseline comparison (iter-2)

With no skill loaded, baseline scored 15/22 (68%). The biggest skill-vs-baseline
gaps were:

- **File:line citation accuracy** — baseline frequently guessed locations
  (e.g., "execProcnode.c or maybe execAmi.c") where the skill gave exact
  line numbers.
- **The Plan-tag vs PlanState-tag asymmetry** — baseline could derive it
  from function signatures but spent words doing so; with-skill answer
  led with it as a named pitfall.
- **`set_plan_references` internals** — baseline got the high-level
  purpose but missed `invalItems` and could not name the walker family
  with confidence.

## Files

- `iteration-1/` — original answers, proposed edits, iter-1 grading.
- `iteration-2/` — edits-applied log, copied evals, iter-2 answers and grading.
- `.claude/skills/executor-and-planner/SKILL.md` — the in-place updated skill.
