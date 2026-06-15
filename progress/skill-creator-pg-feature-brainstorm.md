# skill-creator iteration — pg-feature-brainstorm

## What I ran

Sixth `run_eval.py` iteration. First **null-result** datapoint
in the genuine-eval series — same intent-verb + bolded-Use-
proactively + enumerated-phrasings pattern applied to
`pg-feature-brainstorm`, but no measurable improvement.

Worth recording honestly: the pattern doesn't ALWAYS produce a
positive delta. It depends on baseline description quality.

## Setup

20 trigger-eval cases:
- 10 should-trigger: realistic "rough idea + half-formed PG
  feature" queries — FK deferrable-at-xact-start, per-role
  parallel-worker GUC, `/pg-brainstorm` async commit, page-
  level encryption at rest, read-only logical replication,
  per-tablespace compression, user-defined B-tree comparators,
  soft delete in core, NULLS NOT DISTINCT on partial indexes,
  per-database autovacuum_naptime.
- 10 should-NOT-trigger: brainstorms that should route
  elsewhere — already-picked-approach queries (route to
  pg-feature-plan), product/UX/marketing/sprint/roadmap
  brainstorms, MongoDB/Redis feature brainstorms, design-
  review of an already-written plan (route to review-checklist
  or pg-patch-review).

## Results

| Metric | Baseline | Iter-1 | Δ |
|---|---|---|---|
| should-trigger pass | **2/10 (20%)** | **2/10 (20%)** | **0** |
| should-NOT-trigger pass | 10/10 (100%) | 10/10 (100%) | 0 |
| overall | 12/20 (60%) | 12/20 (60%) | 0 |

**Same overall count but the passing queries shifted:**
- Baseline passed: parallel-workers GUC cap + user-defined
  B-tree comparators.
- Iter-1 passed: parallel-workers GUC cap + NULLS NOT DISTINCT
  partial index.

So **3 unique queries passed across both runs**, similar to the
locking PR #281 pattern (1-run noise floor ~±1 query).

Zero regressions on should-NOT-trigger.

## Why no improvement

The pre-existing baseline description was already well-crafted
relative to the eval set: it already listed 5+ trigger phrasings
("let's brainstorm a PG idea", "I have an idea for PG", "what
would it take to add X to PG", "could we do Y in PG", "explore
the design space for Z") plus the `/pg-brainstorm` slash
command. So the additional pattern application (bolding,
adding 4 more phrasings: "rough idea: [PG thing]", "what if we
let PG [do X]", "what are the 2-3 candidate approaches for [PG
feature]", and the "even when they don't use the literal word
'brainstorm'" hedge) had less marginal value.

Compare with pg-feature-plan (PR #280) where the baseline
description started with "Write a citation-rich implementation
plan ..." — narrow verb framing, less list — and the rewrite
gave a big jump.

**Lesson: pattern delta size is inversely correlated with
baseline description quality.** When the baseline was already
on-pattern, more on-pattern doesn't help.

## Why I committed anyway

The new iter-1 description is **better-written and more pushy**
even if it doesn't move the needle on this small noisy eval.
Specific improvements:

- Bolded `**Use this skill proactively whenever ...**` (matches
  the proven format from PR #280 / #281 — even if it didn't help
  here, it's consistent across the suite).
- More phrasing patterns (9+ vs the original 5).
- Explicit "the signal is: design space still open, no approach
  is locked yet" hint — helps Claude reason about when to
  trigger.
- Expanded skip list: covers Cassandra, Kafka, "design-review of
  an already-written plan" (route to review-checklist), and
  "already-committed PG features" (corpus / explanation
  questions).

Quality of description matters beyond just trigger rate; it
helps the future skill-creator iterations build on a solid
baseline and onboards new contributors who read these skills.

## Pattern now validated across 4 datapoints

| PR | Skill | Type | Δ should-trigger |
|---|---|---|---|
| #241 | parallel-query | topical | 0/3 → 1/5 (first non-zero) |
| #280 | pg-feature-plan | workflow | 0/10 → 3/10 (+30pp) |
| #281 | locking | topical | 1/10 → 2/10 (+10pp) |
| this | pg-feature-brainstorm | workflow | 2/10 → 2/10 (**0pp**) |

The pattern works when baseline is description-poor. It is
roughly neutral when baseline is already description-rich. Net
expected value across all skills: still positive (most skill
descriptions in this repo HAD weaker baselines before the
sweep).

## Methodology notes for future iterations

For future genuine evals, a better workflow might be:
1. Inspect baseline description first — count trigger phrasings
   already present.
2. If ≥ 5 phrasings + skip list already enumerated → expect
   small delta; consider running 3-runs-per-query for cleaner
   signal, or skip the iteration.
3. If < 5 phrasings or weak skip list → expect positive delta
   even at 1-run-per-query noise.

## Files touched

- `.claude/skills/pg-feature-brainstorm/SKILL.md` — description-
  only rewrite; body / when_to_load / companion_skills
  unchanged.
- `.claude/skill-creator-workspaces/pg-feature-brainstorm/` —
  workspace dir (gitignored).
- `progress/skill-creator-pg-feature-brainstorm.md` — this
  honest-null-result recap.

## Cross-references

- `progress/skill-creator-intent-verb-sweep.md` — the 8-PR
  arc that established the pattern.
- `progress/skill-creator-pg-feature-plan.md` — PR #280 (+30pp).
- `progress/skill-creator-locking.md` — PR #281 (+10pp).
- `sessions/2026-06-14-handoff-pre-compact-round3.md` — the
  catalog item these PRs close.
