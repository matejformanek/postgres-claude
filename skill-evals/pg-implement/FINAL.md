# pg-implement — FINAL evaluation summary

Two-iteration skill eval of `.claude/skills/pg-implement/SKILL.md`.

## Score progression

| Run         | with_skill         | baseline           | delta (skill − baseline) |
|---|---|---|---|
| Iteration 1 | 29 / 31 = 0.935    | 12 / 31 = 0.387    | +0.548 (+54.8pp)         |
| Iteration 2 | **31 / 31 = 1.000**| 12 / 31 = 0.387    | +0.613 (+61.3pp)         |

The skill clears the assertion bar at 100% after iter-2's edits. Both iter-1 with_skill misses (Eval 3 assertions 7 + 8, both on Eval 3's "trap" question) closed cleanly via Edit 1.

`pg-implement` is one of the rare skills where iter-2 lifted the with_skill score — comparable to `executor-and-planner` (+11pp), `extension-development` (+4 hits), `replication-overview` (+1) from the original campaign. The +2 hits here come from a single rationale block (Edit 1, "Why per-phase = per-commit + per-test").

## What changed between iter-1 and iter-2

All six edits from `iteration-1/proposed-edits.md` were applied to SKILL.md:

1. **Edit 1 — added §"Why per-phase = per-commit + per-test"** rationale block (bisectability + per-commit-reviewability). Inserted between §Strict rules item 6 and §Method. **This closes both iter-1 with_skill misses** by promoting the operational *why* of R3 + R4 + the anti-pattern list into the skill itself.
2. **Edit 2 — Status field semantics** appended under §Phase-end log step 14 (done / partial / deferred meanings).
3. **Edit 3 — R2 drift definition promoted** into §Strict rules item 2 ("~20 lines, since-removed symbol").
4. **Edit 4 — §Style commit-message bullet tightened** with R6's exact "addresses / fixes / implements" verb list.
5. **Edit 5 — §"Forbidden patterns" sub-block added** mirroring the five anti-patterns from `pg-implement-discipline.md`.
6. **Edit 6 — slug-naming convention examples** added to §Inputs (`sp2-pgstr-maxalloc`, etc.).

No proposed edits were dropped; all six verified cleanly before applying.

## Source-value verifications performed

`pg-implement` is a *procedure + policy* skill — its claims are about the meta repo's own R1–R12 rules, not PG source internals. So the verifications are policy-level, not source-line-level:

- Read `.claude/rules/pg-implement-discipline.md` end-to-end. Confirmed R2 wording, R6 verb list, R7 three-path enumeration, R8 notes.md template fields, R10 two-repo separation language, R12 gate steps. All applied edits match rules wording.
- Read `.claude/rules/pg-implement-discipline.md` §Anti-patterns. Five forbidden items mirrored verbatim into new SKILL.md §"Forbidden patterns" sub-block.
- Confirmed real-world planning slugs by `ls planning/` in the worktree: `cb1-pgcrypto-bomb`, `cb7-ltree-amplification`, `cb8-hstore-forge`, `sp2-pgstr-maxalloc`, `sp6-autoprewarm-revoke`, `sp7-tablefunc-quoting`. Used three of these as in-repo examples in §Inputs.
- Read `planning/sp2-pgstr-maxalloc/plan.md` + `notes.md` to confirm the example slug + branch-name pattern (`feature_sp2_pgstr_maxalloc`) is real and the workflow described in SKILL.md actually matches how phase 1 was executed.
- The bisectability + per-commit-reviewability rationale (Edit 1) is a project-policy claim, not a PG-internals claim — verified consistent with R4 + R12 + the anti-pattern list, not with `source/<path>:<line>`.

No proposed edits cited `source/<path>:<line>`, so no source-tree drift was possible.

## Honest gotchas

1. **Rubric saturated after iter-2.** 31/31 with_skill means the rubric can no longer measure further improvement. The campaign-wide pattern (17 of 21 skills saturated on iter-1) repeats here. To stress-test further you'd need harder evals — e.g. "the plan's §3 file table missed visibilitymap.c because the upstream README was wrong; reconcile" — that probe the limits of R7's three-path enumeration, or "the dev/ branch was rebased onto a master that moved one of the cited files; what's the recovery?".

2. **Baseline is high here (38.7%) compared to the typical campaign floor (~24% for `wal-and-xlog` / `build-and-run`).** Reason: a lot of the procedure is general OSS hygiene (run tests before commit; don't silently expand scope; don't ship broken phases) that any decent contributor will paraphrase from instinct. The skill's distinctive value is the *naming* — R-numbers, exact trailer formats, the rules file by name. That's where the +54–61pp lift comes from.

3. **The skill is now closely coupled to the rules file.** All six edits import R-number references or rule wording into SKILL.md. This is a deliberate tradeoff (discoverability beats single-source-of-truth here, per the typical project-doc pattern) but means if `pg-implement-discipline.md` is rev'd to v2, SKILL.md needs a synchronized review. The cross-reference block at the bottom of SKILL.md still names the rules file as authoritative.

4. **The skill does NOT cover what happens when the underlying plan itself is wrong** (cite drift after work has started, mid-stream re-plan triggered by R2 fail). It points at `/pg-plan` re-run but doesn't describe the handoff. That's a real gap, but it's a `pg-feature-plan` boundary issue, not a `pg-implement` issue — leaving it for that skill's eval round.

## Verdict

`pg-implement` is **ready**. The skill provides a strong absolute lift over baseline (+0.613) and clears 100% of assertions in this test set after iter-2. The structural split (SKILL.md = procedure, `.claude/rules/pg-implement-discipline.md` = invariants) is preserved and now mutually discoverable: the rules file still wins where they disagree, but SKILL.md is no longer dependent on a doc hop for the most critical contract points.

Files:
- `/Users/matej/Work/postgres/postgres-claude/.claude/worktrees/ft_meta_skill_creator_round/.claude/skills/pg-implement/SKILL.md`
- `/Users/matej/Work/postgres/postgres-claude/.claude/worktrees/ft_meta_skill_creator_round/.claude/rules/pg-implement-discipline.md` (unchanged; cross-referenced)
- `/Users/matej/Work/postgres/postgres-claude/.claude/worktrees/ft_meta_skill_creator_round/skill-evals/pg-implement/iteration-1/`
- `/Users/matej/Work/postgres/postgres-claude/.claude/worktrees/ft_meta_skill_creator_round/skill-evals/pg-implement/iteration-2/`
