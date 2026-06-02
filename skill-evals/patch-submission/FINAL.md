# patch-submission skill — eval report

## Results

| Iteration | with_skill | baseline | gap |
|-----------|-----------:|---------:|----:|
| 1         | 22/22 (100%) | 13/22 (59.1%) | +40.9 pp |
| 2         | 22/22 (100%) | 13/22 (59.1%) | +40.9 pp |

Three evals, 7–8 assertions each, 22 total.

## What the skill adds on top of baseline

Baseline (Claude with no skill) already gets the obvious workflow right:
plain text email to pgsql-hackers, attached patch, `git format-patch
-vN`, reply on the same thread, CF status transitions. That's ~60% of
the value.

The skill's marginal lift is concrete specifics that don't come "for
free":

- Naming the current open CommitFest (`PG20-1` as of mid-2026)
- The exact SGML doc file for a GUC (`doc/src/sgml/config.sgml`)
- The review-bartering norm (review one other patch per CF)
- The four backpatch criteria (frequently-encountered / low-risk /
  security / data-corruption)
- The "fold via `git rebase -i`, no fix-on-top commit" rule
- `git diff --check master..HEAD` for whitespace
- Catalog / WAL / pg_control / pgstat version-macro bumps when needed

## Iteration 2 changes (applied to SKILL.md)

Six small edits, none reorganizing the skill:

1. Section 0: WIP-vs-ready decision promoted to pre-flight bullet.
2. Section 1: error-message style guide pointer for user-facing messages.
3. Section 2: `git fetch origin && git rebase origin/master` block.
4. Section 6: concrete `Topic` examples for CF registration.
5. Section 7: explicit "fold fixes via `git rebase -i master`" step.
6. Quick reference: prepended the rebase-onto-upstream command.

The iter-2 score didn't move (already at ceiling in iter-1), but the
iter-2 with_skill answers are visibly tighter on: rebase hygiene,
error-message style guidance, explicit Topic picks, and the fold-vs-fix
distinction. Those are real-world frequent reviewer gripes, so even
without a score delta the edits are worth keeping.

## Validity caveats

- The grader is the same model that wrote both the answers and the
  assertions; a stricter human grader would likely mark a couple of
  baseline assertions as partial credit.
- The current-CF reference (`PG20-1`) and supported-version range
  (`14–18`) will rot — these will need updating when CF / release
  cycle advances.
- No subagents, no `claude -p`, single-context run as instructed.
