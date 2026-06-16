# pg-patch-review — FINAL evaluation summary

Two-iteration skill eval of `.claude/skills/pg-patch-review/SKILL.md`.

## Score progression

| Run | with_skill | baseline | delta (skill - baseline) |
|---|---|---|---|
| Iteration 1 | 32 / 32 = 1.000 | 9 / 32 = 0.281 | +0.719 |
| Iteration 2 | 32 / 32 = 1.000 | 9 / 32 = 0.281 | +0.719 |

Iter-2 numeric score is unchanged (matches the campaign pattern —
17 of 21 sibling skills saturated at iter-1). The qualitative value
of iter-2 is in fixing two broken cross-references and making the
Critic-E severity contract scannable.

## What changed between iter-1 and iter-2

Five of seven proposed edits applied to SKILL.md:

1. **Edit #1** — replaced the dead
   `sessions/2026-06-02-cf6402-review-validation.md` path in
   §Validation reference with an `[unverified: session log not
   preserved]` marker. Preserves the calibration intent; future
   sessions can replace the marker.
2. **Edit #2** — replaced the dead `pg-corpus-maintainer` skill
   reference in §"What to escalate to the user mid-review" with the
   real `hf(corpus):` commit workflow documented in Rule R9 of
   `.claude/rules/pg-implement-discipline.md`. The escalation now
   points at a real handler.
3. **Edit #3** — added an 8-row Critic-E **severity matrix at a
   glance** table immediately before the §Critic E §Output line.
   Restates the prose's per-probe defaults and escalation
   conditions in a scannable form. Echoes the REJECT-track
   threshold (3+ blocking rows + context-awareness signal).
4. **Edit #4** — added an inline 9-step Stage-0 recipe to §Stage 0
   for when the skill is invoked directly (without `/pg-review`).
   The skill is now self-contained.
5. **Edit #5** — prefixed §Stage 3 with the "Critic-E recommends;
   Stage 3 decides" rule, promoted from being buried in §Critic E
   §REJECT-track escalation (M4).

Two edits (#6 REJECT-A/B/C ASCII decision tree, #7 explicit
parallel-tool-call shape example) were marked optional in iter-1
and skipped — both would bloat the skill without clarifying.

## Source-value verifications performed

Before applying, verified against repo state:

- `sessions/2026-06-02-cf6402-review-validation.md` — **DOES NOT
  EXIST** (`find sessions/ -name '*6402*' -o -name '*validation*'`
  returns nothing). Triggered Edit #1.
- `.claude/skills/pg-corpus-maintainer/` — **DOES NOT EXIST** (`ls
  .claude/skills/`). Triggered Edit #2.
- `knowledge/calibration/gap-catalog.md` — exists; item numbering
  #1-#11 matches SKILL.md descriptions (verified via `grep -n
  "catalog #"` on the gap-catalog).
- `knowledge/shadow-implementations/money-fx-exchange/skill-gaps.md`
  — exists; REJECT-A/B/C definitions at lines 84-88 match SKILL.md
  Stage-3 §Verdict text (verified via `grep -n REJECT`).
- `.claude/skills/review-checklist/SKILL.md` — exists; Phase 0 with
  REJECT-track + 3 reflex gates at lines 43-159.
- `.claude/rules/pg-implement-discipline.md` Rule R9 — exists;
  explicitly names "the corpus needs a `hf(corpus)` fix in a
  SEPARATE meta-repo commit".
- macOS pre-existing flake `recovery/040_standby_failover_slots_sync`
  — referenced in multiple sessions; safe to cite as the canonical
  example in Edit #4's Stage-0 recipe.

All applied edits' content matches source.

## Verdict

`pg-patch-review` is **ready**. The skill provides a strong
absolute lift over baseline (+0.72) and clears 100% of assertions
across both iterations. The five-stage pipeline + five-critic
fan-out + REJECT-A/B/C verdict structure is the right shape and
was preserved. The iter-2 edits closed two dead-reference holes
and tightened the Critic-E contract.

## Gotchas surfaced

1. **Skills can reference siblings or sessions that never landed.**
   The skill cited a calibration session file that doesn't exist
   and a `pg-corpus-maintainer` skill that doesn't exist. Both
   citations had been there since the skill's creation. The
   methodology — "spot-check cites against repo state before
   applying edits" — caught them; otherwise they'd have stayed
   dead. Worth a one-time `grep -r` audit across all skills for
   `.claude/skills/<name>` references and `sessions/<file>`
   references to find others like this.
2. **Score saturation is real but not the signal.** Per the
   campaign SUMMARY (17 of 21 skills saturated at iter-1), the
   right measurement on a high-quality skill's iter-2 is
   qualitative: did the proposed edits land correctly, did the
   verifying pass catch any factual errors in the proposals
   themselves? For this skill, yes on both counts — the dead
   references would have introduced bugs if pasted in
   uncritically.

Files:
- `/Users/matej/Work/postgres/postgres-claude/.claude/skills/pg-patch-review/SKILL.md` — updated (5 edits)
- `/Users/matej/Work/postgres/postgres-claude/.claude/worktrees/ft_meta_skill_creator_round/skill-evals/pg-patch-review/iteration-1/`
- `/Users/matej/Work/postgres/postgres-claude/.claude/worktrees/ft_meta_skill_creator_round/skill-evals/pg-patch-review/iteration-2/`
