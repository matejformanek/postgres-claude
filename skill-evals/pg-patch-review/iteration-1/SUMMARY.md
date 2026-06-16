# pg-patch-review — iteration 1 SUMMARY

**Skill:** `.claude/skills/pg-patch-review/SKILL.md`
**Methodology:** single-context. One agent reads SKILL.md, writes 3
realistic evals, answers each with_skill and baseline, grades
against self-drafted assertions.

## Score

| Condition | Passed | Total | Rate |
|---|---|---|---|
| with_skill | 32 | 32 | 1.000 |
| baseline | 9 | 32 | 0.281 |
| Lift | +23 | | +0.719 |

## Eval shape

- E1 — drive a mailing-grade review end-to-end (hypothetical CF #5912).
- E2 — adversarial: BufFile leak on ereport in ReorderBufferIterTXNInit.
- E3 — trap: regress + iso + warning-clean, "pure refactor" — what else?

## Headline findings

1. Skill content covers the claimed contract fully — all 32
   assertions pass with skill. Lift over baseline (+0.72)
   concentrates on the named pipeline (stages, critic letters,
   verdict grades) and named catalog items.
2. Two dead cross-references. SKILL.md cites
   `sessions/2026-06-02-cf6402-review-validation.md` (does not
   exist) and `pg-corpus-maintainer` skill (does not exist).
3. Critic-E severity contract is correct but scattered across 8
   prose paragraphs — a scannable table would help.

## Proposed edits

7 items in proposed-edits.md:
- Blocking (1,2): fix two dead references.
- Structural (3,4,5): severity-matrix table; inline Stage-0 recipe;
  promote "Critic E recommends; Stage 3 decides" into Stage 3.
- Optional (6,7): REJECT-A/B/C decision tree; tool-call shape example.

## Anchors verified

- knowledge/calibration/gap-catalog.md items 1-11 — exists, matches.
- knowledge/shadow-implementations/money-fx-exchange/skill-gaps.md
  Gap M4 — confirmed REJECT-A/B/C grades match.
- .claude/skills/review-checklist/SKILL.md Phase 0 — confirmed at
  lines 43-159.

## Anchors failed verification

- sessions/2026-06-02-cf6402-review-validation.md — NOT FOUND.
- .claude/skills/pg-corpus-maintainer/ — NOT FOUND.

## Next step

Apply verified edits (1-5) to SKILL.md; rerun 3 evals in iter-2.
