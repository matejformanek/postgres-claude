# memory-keeping — eval FINAL report

Skill under test: `.claude/skills/memory-keeping/SKILL.md`
Working dir: `/Users/matej/Work/postgres/postgres-claude/`
Date: 2026-06-02
Methodology: single-context, 2 iterations, 3 evals, with-skill vs baseline,
honest self-grading against 6–7 assertions per eval.

## Numeric results

| Iteration | with-skill | baseline | delta |
|---|---|---|---|
| 1 (pre-edit baseline) | 20/20 = 1.00 | 4.0/20 = 0.20 | +0.80 |
| 2 (after applying iter-1 edits) | 20/20 = 1.00 | 4.0/20 = 0.20 | +0.80 |

Baseline of 0.20 confirmed the hypothesis: this is project-specific bookkeeping
that a generic Claude cannot reconstruct. The only baseline-friendly assertion
across all three evals was "fix the wrong claim in the doc itself" (obvious) and
weak partials on "skip optional log" / "don't rewrite history" — everything
else (files-examined.md, coverage.md row shape, STATE.md fixed shape, four
session-log headings, append-only sessions/) requires the skill.

## Numeric ceiling caveat

Iter-1 with-skill already scored 1.00 because the assertions matched what the
skill explicitly contains, plus what CLAUDE.md provides ambiently. The
iter-1 → iter-2 numeric delta is 0 — but the qualitative improvement is real:

- iter-1 with-skill answer to ev1 mentioned `progress/files-examined.md`, but
  that knowledge came from CLAUDE.md, not the skill. A future invocation
  loaded *only with the skill* would have missed it.
- iter-2 with-skill answer derives `files-examined.md` from invariant 4 inside
  the skill — robust to context loss.

A v3 of these evals should add assertions like "answer does not depend on
files outside the skill itself" to capture this kind of improvement
numerically. Logged as a TODO for the eval rubric, not a SKILL.md issue.

## Edits applied to SKILL.md (iter-2)

1. Added `progress/files-examined.md` and `file-by-file deep read` to the
   frontmatter `description`.
2. Added invariant 4 codifying `files-examined.md` as the append-only
   per-file ledger with full column schema, cross-linked to CLAUDE.md rule 6.
3. Expanded the "When to update what" table from 3 to 4 columns (added
   files-examined.md) and added a new row for "File-by-file deep read with
   no new synthesis" — the most common case in the current phase.
4. Added a paragraph under the table spelling out the four-touch correction
   workflow when a wrong claim is discovered in an existing doc.
5. Added inline note to invariant 3 that session-log filenames use **today's**
   date (defensive against LLM stale-date drift).

No regressions: the four session-log headings, STATE.md fixed shape, and
"Things you must not do" list were left unchanged because they already scored
fully.

## Recommendation

Ship the edited SKILL.md. The skill now stands on its own without leaning on
CLAUDE.md ambient context for the files-examined.md ledger, and covers the
file-by-file-deep-read case that was missing from the trigger table.

## Files produced

- `skill-evals/memory-keeping/iteration-1/evals.json`
- `skill-evals/memory-keeping/iteration-1/answers.json`
- `skill-evals/memory-keeping/iteration-1/grading.json`
- `skill-evals/memory-keeping/iteration-1/proposed-edits.md`
- `skill-evals/memory-keeping/iteration-2/edits-applied.md`
- `skill-evals/memory-keeping/iteration-2/evals.json`
- `skill-evals/memory-keeping/iteration-2/answers.json`
- `skill-evals/memory-keeping/iteration-2/grading.json`
- `.claude/skills/memory-keeping/SKILL.md` (edited)
