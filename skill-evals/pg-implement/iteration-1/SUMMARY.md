# Iteration 1 — Summary

**Skill**: `pg-implement`
**Date**: 2026-06-16
**Method**: single-context, no subagents

## Prompts evaluated

1. **Task trace**: Walk through implementing phase 2 of `planning/sp2-pgstr-maxalloc/plan.md` — pre-phase, edit cadence, phase-end check, commit, notes.
2. **Concrete edit**: Mid-phase realization that a file outside §3 must be touched — what's the procedure?
3. **Trap question**: Junior wants to commit phase 3 with a regress failure as TODO and continue to phase 4 — why is that wrong?

## Scores

| Cohort     | Passed / Total | Pass rate |
|---|---|---|
| with_skill | 29 / 31        | 0.935     |
| baseline   | 12 / 31        | 0.387     |

Skill delta: **+0.548 (17 additional assertions)**.

## What the skill clearly helped with

- Cited the binding rules file (`pg-implement-discipline.md`) by name and pulled R-numbers (R2, R3, R4, R5, R6, R7, R8, R9, R10, R12) directly.
- Named the exact `Plan:` and `Sites:` trailer convention with format.
- Named the drift threshold (>10% / ~20 lines / since-removed symbol) for R2.
- Reproduced the R8 notes.md template (Status/Commit/Tests-run/What-changed/Surprises/What-this-phase-did-NOT-do).
- Named R7's three resolution paths for scope creep in the right order of preference.
- Named the anti-pattern list (WIP commits, --amend across phases, no Plan: trailer, cherry-picking phases, mixing meta-repo + dev/ writes).
- Named the explicit upstream-style choice (no Co-Authored-By in dev/ commits because they may be format-patched).

## Where baseline kept up

- General "don't start phase 4 before phase 3 is done" (R3 by instinct).
- "Run tests before commit" (R4 by instinct).
- "Incremental build" (general C-hacking habit).
- "STOP and ask if scope expands" (general OSS hygiene).
- "Bisectability is good" (general git-hygiene knowledge).
- "Reviewers can't be expected to skip known-broken commits" (general OSS hygiene).

## With_skill misses (2)

Both on Eval 3:

1. **Bisectability not cited.** The skill talks about per-phase commits being upstream-bound but never names `git bisect` as a downstream consequence of broken phase commits.
2. **Per-commit-must-pass convention not cited.** The skill says "may be format-patched upstream" but doesn't spell out the upstream convention that **every commit in a posted series must compile + pass on its own**.

Both are operational rationale; both can be added to SKILL.md as a "Why these rules exist" sub-block without bloating it.

## Recommended edits (see `proposed-edits.md`)

1. **HIGH** — Add "Why per-phase = per-commit + per-test" rationale block (bisectability + per-commit-must-pass). Closes both with_skill misses.
2. **MED** — Inline the notes.md Status field semantics (`done` / `partial` / `deferred`).
3. **MED** — Promote R2's drift definition into SKILL.md §Strict rules item 2.
4. **MED** — Tighten the §Style commit-message bullet to import R6's exact "fixes / addresses / implements" language.
5. **MED** — Mirror the anti-pattern list from rules into SKILL.md (keeps rules authoritative, but discoverable from the skill alone).
6. **LOW** — Name slug-naming convention with an example in §Inputs.

## Decision

Skill is strong; the procedure + rules pairing already does its job. Edit 1 is the only one that closes a measured gap; edits 2-5 harden against regression. Apply all six in iter-2 (six are small and additive).
