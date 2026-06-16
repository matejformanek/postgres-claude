# meta-commit-style — FINAL evaluation summary

Two-iteration skill eval of `.claude/skills/meta-commit-style/SKILL.md`.

## Score progression

| Run | with_skill | baseline | delta (skill - baseline) |
|---|---|---|---|
| Iteration 1 | 28 / 31 = 0.903 | 8 / 31 = 0.258 | +0.645 |
| Iteration 2 | 31 / 31 = 1.000 | 8 / 31 = 0.258 | +0.742 |

The skill clears 100% of assertions after iter-2's edits. Iter-1
missed exactly one assertion per eval — all three failures were the
same root cause: SKILL.md taught `Co-Authored-By:` (GitHub uppercase),
but the real meta-repo log dominantly uses `Co-authored-by:`
(lowercase) by a ratio of 45-vs-11 in the last 50 commits with a
co-author trailer.

## What changed between iter-1 and iter-2

Seven edits from `iteration-1/proposed-edits.md` were considered;
all seven were applied (with Edit 7 folded into Edit 1):

1. **Edit 1** — Global `Co-Authored-By:` → `Co-authored-by:` casing
   fix across 6+ in-place sites (description, contrast table,
   format box, trailer spec, all three canonical examples,
   forbidden list, cross-references). New callout block explaining
   git canonicalization + the real-log ratio. Closes A8 / B8 / C7.
2. **Edit 2** — `ft(skill):` → `ft(skills):` plural in the §"Prefix
   vocabulary" table, the "if unsure" rule, and the planner-suite
   example. Real log: 23 plural, 0 singular.
3. **Edit 3** — Added `ft(meta):` row to the canonical prefix table;
   extended the `docs(<scope>):` row to enumerate observed
   sub-scopes (`docs(state|cloud|community|queue|progress):`); added
   a "Real-log frequency reference" paragraph after the "if unsure"
   line, with top-10 prefix counts from last 200 commits.
4. **Edit 4** — `Plan:` trailer reworded to admit both the canonical
   `planning/<slug>/plan.md (phase <N>: <title>)` form (required when
   a plan exists per R5 of `pg-implement-discipline.md`) and the
   loose pointer form (`Plan: cloud routine X.md`, etc.) observed
   in real-log instances. Stops the skill from contradicting visible
   practice.
5. **Edit 5** — Added `(real-log anchor: <SHA>)` lines under the
   `ft(corpus):` and `ft(skills):` canonical examples (4925200 and
   62da1c2). Added a caveat under the `ft(dev):` example noting that
   a `src/...` commit would actually use `commit-message-style`, not
   this skill.
6. **Edit 6** — Added a §"Side-by-side: same change, two styles"
   block between the contrast table and §"When to use". Shows the
   same conceptual change ("document a PG invariant") with both the
   `dev/` commit-message-style trailer block and the meta-repo
   meta-commit-style trailer block side by side. Back-pointer to R10.
7. **Edit 7** — Folded into Edit 1 (frontmatter description casing).

## Source / real-log verifications performed

Before applying, the following anchors in `proposed-edits.md` were
verified against the worktree's `git log`:

- Co-author casing ratio (45 lowercase / 8 short-form lowercase /
  11 uppercase) — `git log --format='%B' -50 | grep -i 'co-author'
  | sort | uniq -c`.
- Prefix vocabulary frequencies — `git log --format='%s' -200 |
  grep -oE '^[a-z]+\([a-z]+\):' | sort | uniq -c | sort -rn`.
  Results: `ft(corpus):` 122, `ft(skills):` 23, `docs(cloud):` 8,
  `hf(corpus):` 6, `ft(cloud):` 5, `ft(meta):` 2, `docs(community):`
  2, `docs(state):` 1, etc.
- `[cloud:<routine>]` form — confirmed present in real log
  (`aecd8e3`, etc.) with descriptive payload after the bracket
  rather than colon-then-imperative.
- `Plan:` trailer loose-form examples (`Plan: cloud routine
  pg-quality-auditor.md`, `Plan: catalog trio "..."`,
  `Plan: cross-ref-audit fixup on PR 4/4.`).
- Real SHAs cited in examples (62da1c2, 4925200, aecd8e3, 82ebf2e,
  b707ab2, 5a39b7d) all present and titled as described.

## Diff verification

```
$ git diff --stat -- .claude/skills/meta-commit-style/SKILL.md
 .claude/skills/meta-commit-style/SKILL.md | 109 +++++++++++++++++++++++++-----
 1 file changed, 92 insertions(+), 17 deletions(-)
```

Non-zero diff confirmed.

## Highest-leverage finding

The SKILL.md was teaching an incorrect spelling of the
`Co-authored-by:` trailer (`Co-Authored-By:` GitHub-style uppercase
in every example). An agent that followed the skill faithfully
produced commits visually inconsistent with the established
meta-repo log. The 45-vs-11 ratio in the real log made this an
unambiguous fix, not a per-committer preference issue.

This is structurally analogous to the
`commit-message-style/iteration-1/proposed-edits.md` "two-space
after sentence-ending period" hypothesis that was DROPPED after
the 32-vs-41 log count showed it was per-committer preference — the
sibling-skill methodology of counting real-log instances saved us
from going the other direction here. The casing call is
unambiguous (~4:1 lowercase) and matches git's own canonicalization.

## Verdict

`meta-commit-style` is **ready**. The skill now clears 100% of
assertions, the highest-leverage casing bug is fixed, the prefix
vocabulary matches established real-log usage with frequency
anchors, and the `Plan:` trailer spec no longer contradicts visible
practice. Lift over baseline at +0.742 lands at the high end of the
campaign range (+10pp to +100pp; mean ~+49pp across 21 skills in the
2026-06-02 campaign).

Files:
- `/Users/matej/Work/postgres/postgres-claude/.claude/worktrees/ft_meta_skill_creator_round_2/.claude/skills/meta-commit-style/SKILL.md`
- `/Users/matej/Work/postgres/postgres-claude/.claude/worktrees/ft_meta_skill_creator_round_2/skill-evals/meta-commit-style/iteration-1/`
- `/Users/matej/Work/postgres/postgres-claude/.claude/worktrees/ft_meta_skill_creator_round_2/skill-evals/meta-commit-style/iteration-2/`
