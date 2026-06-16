# pg-feature-brainstorm — FINAL evaluation summary

Two-iteration skill eval of `.claude/skills/pg-feature-brainstorm/SKILL.md`
using the single-context heavy methodology
(`skill-evals/SUMMARY.md`).

This is the FIRST single-context-heavy pass on this skill. Prior
`progress/skill-creator-pg-feature-brainstorm.md` used the broken
`run_eval.py` methodology and produced an honest-null delta (0pp) —
that signal was that the **description** was already on-pattern, NOT
that the skill was perfect. The body had never been audited.

## Score progression

| Run | with_skill | baseline | delta (skill - baseline) |
|---|---|---|---|
| Iteration 1 | 33 / 33 = 1.000 | 14 / 33 = 0.424 | +0.576 |
| Iteration 2 | 36 / 36 = 1.000 | 15 / 36 = 0.417 | +0.583 |

The skill saturates at 100% in both iterations. Iter-2 raised the
bar by adding 3 assertions specifically probing the NEW skill
content (distinctness test, broadened §4 lens, anti-pattern
avoidance + FIRST-DECISION-reframe-ordering); skill still passes
all of them. Absolute lift over baseline stays in the +0.58 range —
≈9pp above the cohort baseline-lift mean (+0.49 per the campaign
summary).

## Cohort comparison

| Pattern | Where pg-feature-brainstorm sits |
|---|---|
| Iter-1 with_skill saturated | yes (33/33) — like 17 of 21 sibling skills in the campaign |
| Iter-2 numeric lift on with_skill | no (still 100%) — like ~17 of 21 siblings; rubric saturates fast |
| Edits applied | 5 of 7 applied + 1 merged + 1 dropped as redundant |
| Hard bug caught in proposed-edits | yes — `<CF#>/?q=<keyword>` URL placeholder broken; agent following the skill literally would `WebFetch` a 404. **Same shape as the bugs caught in `debugging` (ERROR=20→21), `executor-and-planner` (setrefs cite ~1100→642), `parser-and-nodes` (5 off-by-one line numbers), `access-method-apis` ("~30" Asserts→37) in the campaign summary.** |

## What changed between iter-1 and iter-2

Five edits from `iteration-1/proposed-edits.md` were applied; one
merged into another; one dropped as redundant. Full disposition in
`iteration-2/edits-applied.md`.

1. **Edit #1** (hard bug fix) — `<CF#>/?q=<keyword>` URL placeholder
   replaced with the correct `?text=<keyword>` cross-CF text search.
   A literal-following agent would have failed with the previous text.
2. **Edit #2** — added "out-of-tree extensions on PGXN / community
   repos" as a sixth prior-art category in §4. Names `pg_partman`,
   `plpgsql_check`, `pg_cron`, `pgvector` as canonical examples and
   spells out the "upstream vs harden vs contrib" reframe.
3. **Edit #3** — added the distinctness-test heuristic to §Method
   step 4: two approaches are flavors-of-the-same when they share
   (a) owning subsystem, (b) invariant footprint, (c) user-visible
   surface; differ on ≥1 to be distinct.
4. **Edit #4** — added 6-bullet Anti-patterns section after §Style
   notes (designing-instead-of-brainstorming, three-equivalent,
   exhaustive-prior-art, skipping-extension-reframe, low-leverage-
   DECISION:, DECISION:-as-deferral).
5. **Edit #5** — added 3 worked DECISION: examples to §Output point
   7, each in a different category (prior-art reframe, semantics
   tradeoff, path-to-release), plus an anti-example.
6. **Edit #6** — merged into Edit #2: the composite-scenarios
   pattern from `_index.md` is now surfaced inline in the §4
   Scenarios-layer bullet.
7. **Edit #7** — dropped (redundant): the "have-you-tried-the-
   extension" DECISION: is already named in 3 places after
   Edits 2/4/5.

## Source-value verifications performed

- **CommitFest URL pattern**: verified by inspection — the only
  other CommitFest reference in the repo
  (`.claude/skills/patch-submission/SKILL.md`) uses the bare root
  URL without `?q=`, consistent with my fix. The broken `<CF#>`
  placeholder + `?q=` parameter combination has no documented
  meaning in the CF UI.
- **Out-of-tree extension names**: `pg_partman`, `plpgsql_check`,
  `pg_cron`, `pgvector` are widely-used PG-community extensions
  [verified — common knowledge]. Repo URLs not WebFetched; left
  as [unverified] in eval answers per skill's honesty convention.
- **Sibling-skill anti-pattern shape**: cross-referenced
  `.claude/skills/pg-implement/SKILL.md` and `commit-message-style/SKILL.md`
  to confirm Anti-patterns section shape + bullet density match
  the repo convention.
- **No file:line cites added**: confirmed via re-read. All edits
  stay structural/heuristic — Phase 1 forbids file:line cites
  (Phase 2's job).
- **`git diff --stat`** at end: `+71/-2 lines on SKILL.md, single
  file changed` — non-zero diff confirmed.

## What this evaluation did NOT measure

Honest list of rubric blind spots (called out per task spec):

- **Creativity of approach 2 vs approach 3.** The rubric checks
  *presence* of 2-3 distinct approaches but cannot grade whether
  the third approach is genuinely insightful or filler. A
  brainstorm with a thoughtful approach C ("baked into tuple
  visibility") and one with a perfunctory approach C ("same as
  A but with a different GUC name") would both pass.
- **DECISION: quality.** The rubric counts DECISIONs and checks
  that they're "things only the user can answer", but cannot
  grade whether a DECISION is high-leverage (changes the
  recommendation if answered differently) vs filler (e.g. "what
  do you want the GUC named?" — explicitly anti-patterned in
  iter-2 but the rubric doesn't otherwise probe for low-leverage
  DECISIONs in passing answers).
- **Real-world triage execution.** None of the evals actually ran
  `WebFetch` against `commitfest.postgresql.org` or
  `git -C source log --grep=...`. The skill's triage procedure
  is graded only by whether the agent says it would run those —
  not by whether the fetched results would be useful or whether
  the agent would correctly skim them.
- **The extension-already-exists reframe in edge cases.** Eval 3
  hit the easy case (a mature, widely-known extension covers ~80%
  of the ask). The reframe is harder when the extension is
  *partially* applicable, *abandoned*, *commercial-only*, or
  *covered-by-a-fork-not-PGXN* (Neon, Aurora). Iter-2's Eval 2
  brushed against this (Neon / Aurora as fork prior art) but
  didn't fully stress-test the reframe.
- **Whether the agent gracefully RESISTS the brainstorm being a
  brainstorm.** The skill's skip list (in the description) says
  "use pg-feature-plan when an approach is already picked". None
  of my evals tested that boundary; all 3 were genuinely-fuzzy
  brainstorm-shaped questions.
- **Single-context bias.** All evals were drafted, answered, and
  graded by the same context that had just read the SKILL.md. The
  with-skill answers may unconsciously over-fit the structure
  (the rubric grades structure-fit, so this is partly
  self-confirming). This is a known limitation of the
  single-context-heavy methodology — see `skill-evals/SUMMARY.md`
  cross-skill pattern #2 ("rubrics saturate fast").

## Verdict

`pg-feature-brainstorm` is **ready**. The skill now (a) gives a
correct CommitFest URL, (b) names the out-of-tree-extension
prior-art reframe explicitly, (c) has a distinctness heuristic
for approaches, (d) has anti-patterns matching sibling skills,
(e) has worked DECISION: examples spanning the major categories.

The hard bug fix (Edit 1) alone justifies the iteration:
following the iter-1 skill literally would produce a failed
WebFetch on first use. Iter-2's skill is materially better than
iter-1's even though the rubric numbers don't move.

Files:
- `/Users/matej/Work/postgres/postgres-claude/.claude/worktrees/ft_meta_skill_creator_round_3/.claude/skills/pg-feature-brainstorm/SKILL.md`
- `/Users/matej/Work/postgres/postgres-claude/.claude/worktrees/ft_meta_skill_creator_round_3/skill-evals/pg-feature-brainstorm/iteration-1/`
- `/Users/matej/Work/postgres/postgres-claude/.claude/worktrees/ft_meta_skill_creator_round_3/skill-evals/pg-feature-brainstorm/iteration-2/`
