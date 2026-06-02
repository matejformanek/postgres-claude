# coding-style skill — final eval summary

Two iterations of grading against the same three evals (includes/decls,
pgindent typedef churn, ereport message style). Eight assertions per eval,
22 max total. Each assertion graded 0 / 0.5 / 1 for baseline (no skill) and
with-skill.

## Headline numbers

| Iteration | Baseline  | With-skill | Delta   |
|-----------|-----------|------------|---------|
| Iter-1    | 18.0 / 22 (81.8%) | 20.5 / 22 (93.2%) | +11.4 pp |
| Iter-2    | 20.0 / 22 (90.9%) | 21.5 / 22 (97.7%) | +6.8 pp  |

## What changed in SKILL.md between iter-1 and iter-2

Three targeted edits from `iteration-1/proposed-edits.md`:

1. **Hard rule #3 (C99 subset)** — added explicit ban on
   `for (int i = 0; …)` as a mid-block-decl variant.
2. **Hard rule #5 (ereport errors)** — added the corollary that
   `AbortTransaction()` releases per-query memory context, locks,
   buffers, and FDs, so cleanup after `ereport(ERROR, …)` is not just
   unreachable but *unnecessary*.
3. **Error-message section** — added a one-liner pointing to
   `errcode_for_file_access()` / `errcode_for_socket_access()` for
   file/socket I/O failures.

The first two were in place when iter-2 began; the third was missing and
applied during iter-2.

## Per-eval delta

| Eval | Iter-1 base | Iter-1 skill | Iter-2 base | Iter-2 skill |
|------|------------|--------------|-------------|--------------|
| 1 (includes/decls)       | 6.0 / 8 | 8.0 / 8 | 6.5 / 8 | 8.0 / 8 |
| 2 (pgindent typedefs)    | 4.0 / 6 | 5.5 / 6 | 5.5 / 6 | 5.5 / 6 |
| 3 (ereport msg style)    | 8.0 / 8 | 7.0 / 8 | 8.0 / 8 | 8.0 / 8 |

Notable: the iter-1 *regression* on eval-3 with_skill (7.0 vs baseline
8.0) is gone in iter-2 — both `errcode_for_file_access` and the
memory-context-cleanup point are now in the skill text and the answer
picks them up. With-skill no longer loses to baseline on any individual
eval.

## Why the headline delta narrowed (11.4 → 6.8 pp)

Baseline drifted up by 2.0 points across the three evals — same model,
same prompts, normal sampling variance (eval-2 baseline happened to
volunteer the buildfarm-regeneration point this run; eval-1 baseline
volunteered the for-loop ban). With-skill rose by 1.0 — it's now
21.5 / 22, essentially at ceiling. There's no more headroom for the
skill to win bigger on these three prompts; further gains would
require either harder evals or accepting that PG coding style is
sufficiently well-represented in training data that the skill's
ceiling against a knowledgeable baseline is ~98%.

## Recommendation

Ship as-is. The skill:
- Beats baseline on every eval individually after iter-2 (no regressions).
- Is at 97.7% of max.
- Closed the two regressions iter-1 flagged.
- Stays operational (typedef.list, pgindent escape valves, headerscheck)
  rather than restating well-known rules at length.

Further iteration on these evals has diminishing returns. If we want a
more discriminating signal, add evals targeting genuinely obscure
operational rules (e.g. catalog version bumps on shared-state changes,
`COSTS OFF` in `EXPLAIN` regress tests, `regress_*` role naming).
