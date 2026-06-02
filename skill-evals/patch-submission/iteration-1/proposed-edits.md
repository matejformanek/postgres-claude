# Proposed edits to SKILL.md after iteration 1

The skill is already strong — `with_skill` passed 22/22 across the three
evals; the baseline got 13/22. Most uplift comes from specifics that
already exist in the skill (PG20-1, review-bartering, version-macro bumps,
anti-checklist). Below are small additions that the iter-1 answers
*relied on* implicitly but the skill doesn't yet spell out.

## Edit 1 — section 2 (history cleanup): require rebase onto current master

Reviewers reject patches that don't apply cleanly. Section 2 talks about
squashing/splitting but not about rebasing onto current `master` before
`format-patch`. Add a line under section 2:

> Before formatting, rebase onto current upstream master so the series
> applies cleanly: `git fetch upstream && git rebase upstream/master`.
> A v(N) that doesn't apply is the most common reason a CF entry gets
> bounced back without review.

## Edit 2 — section 7 (review feedback): explicit "fold into commits"

The current step 3 says "Generate vN+1" but doesn't tell the author *how*
to incorporate fixes. New contributors often append a "fix review
comments" commit on top, which is wrong — the v2 series should look like
a clean rewrite. Add:

> When addressing feedback, **fold the fixes back into the right logical
> commit via `git rebase -i master`** — don't ship a "fix review
> comments" commit on top. v(N+1) should look like a clean rewrite of
> v(N) with the asks applied, not v(N) + fixup.

## Edit 3 — section 4 (cover email): point at error-message style guide

Style nits on `ereport`/`elog` messages are one of the most common review
asks. Add to the completeness section (1) or cover email (4):

> If your patch adds or changes user-facing error messages, conform to
> the **Error Message Style Guide** in `doc/src/sgml/sources.sgml`
> before sending — the in-repo `error-handling` skill summarizes the
> rules.

## Edit 4 — section 6 (CF registration): "Topic" field guidance

The skill lists the fields to fill in but a first-time submitter doesn't
know what `Topic` should be. Add:

> The `Topic` field maps to a backend subsystem (Server / Autovacuum,
> SQL Commands, Replication & Recovery, Performance, …). Pick the one
> closest to the patch's primary impact.

## Edit 5 — quick-reference: add `rebase onto current master`

In the Quick reference block, add:

```bash
# Refresh against upstream before re-formatting
git fetch upstream && git rebase upstream/master
```

## Edit 6 — pre-flight section: explicit "ready for review vs WIP" tag

Section 4 mentions the WIP-vs-ready tag at the end. Promote it to a
visible bullet in section 0 so the author decides upfront:

> Decide upfront: is this **WIP** (you want shape/design feedback before
> the community spends serious review cycles) or **ready for review**
> (you believe it's committable modulo nits)? The tag goes in the cover
> email subject prefix and changes how reviewers triage.

## Not changing

- The version-bump list (catversion / XLOG_PAGE_MAGIC /
  PG_CONTROL_VERSION / PGSTAT_FILE_FORMAT_ID) is already accurate and
  load-bearing — leave as is.
- The 7-step structure is good; no reorganization needed.
- PG20-1 reference will need updating when the CF rolls over, but is
  correct as of 2026-06.
