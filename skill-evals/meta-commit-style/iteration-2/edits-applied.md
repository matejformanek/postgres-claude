# edits-applied — meta-commit-style iter-1 → iter-2

Per-edit disposition. Verification anchor: real-log frequencies and
SHAs from `git log --oneline -200` / `git log --format='%B' -50`.

## Edit 1 — Fix `Co-Authored-By:` → `Co-authored-by:` casing

**Disposition: APPLIED.** Highest-leverage edit. Replaced 6
in-place instances across:

- Frontmatter `description:` line.
- §"How it contrasts with upstream PG" table row.
- §"Format" trailer block — and added a 5-line callout block right
  after the format box explaining git's canonicalization + the
  real-log ratio (45 lowercase vs 11 uppercase).
- §"Trailers" item #4 (`Co-authored-by:` literal + reference back to
  the casing note).
- All three canonical example blocks in §"Examples (canonical)".
- §"Forbidden" — added an explicit bullet calling out GitHub-style
  uppercase as a forbidden variant.
- §"Cross-references" bullet for `commit-message-style`.

Closes assertions A8 / B8 / C7 (all three iter-1 failures) on
iter-2.

## Edit 2 — `ft(skill):` → `ft(skills):` plural

**Disposition: APPLIED.** Verified against `git log --format='%s' -200
| grep -oE '^[a-z]+\([a-z]+\):' | sort | uniq -c` — 23 plural, 0
singular. Changed:

- §"Prefix vocabulary" table row.
- "If unsure" guidance bullet.
- Second canonical example title (`ft(skills): add two-phase
  planner …`).

## Edit 3 — Expand prefix vocabulary

**Disposition: APPLIED, modified.** Added `ft(meta):` as a new
row in the canonical table (anchor `82ebf2e`). Extended the
`docs(<scope>):` row to enumerate observed sub-scopes (`docs(state):`,
`docs(cloud):`, `docs(community):`, `docs(queue):`, `docs(progress):`)
with an anchor (`b707ab2`). Added a "Real-log frequency reference"
paragraph after the "If unsure" line, listing the top scopes from the
last 200 commits with counts — this gives the agent a Bayesian prior
for prefix selection.

`ft(patches):` and `ft(ideologies):` (1x each in real log) were NOT
promoted to the table — too rare to be canonical; the "match the
established vocabulary, don't invent" line in the new paragraph
covers them implicitly.

## Edit 4 — `Plan:` trailer loose vs strict form

**Disposition: APPLIED.** Reworded §"Trailers" item #1 to admit two
shapes: canonical (required when a `planning/<slug>/plan.md` exists)
and loose pointer (for recipe / trio / thread / one-off commits).
Anchors the canonical form to R5 of `pg-implement-discipline.md` and
the loose form to real-log instances like `Plan: cloud routine
.claude/cloud/X.md` and `Plan: catalog trio "..."`. This stops the
skill from contradicting visible practice.

## Edit 5 — Real SHA anchors on canonical examples

**Disposition: APPLIED, partially.** Added `(real-log anchor: <SHA>)`
lines under two of the three canonical examples:

- `ft(corpus):` example → anchor `4925200`.
- `ft(skills):` example → anchor `62da1c2`.

The third example (`ft(dev):` per-phase commit during /pg-implement)
got a caveat added instead — clarifying that this hypothetical commit
would actually live in `dev/` (and thus use `commit-message-style`,
not this skill), so the example is illustrative of the trailer block
shape only. No `[cloud:<routine>]` example was added — the example
set is dense enough already and the §"Prefix vocabulary" table row
covers the format.

## Edit 6 — Side-by-side block: meta vs upstream

**Disposition: APPLIED.** Added §"Side-by-side: same change, two
styles" between the contrast table and §"When to use". Shows two
realistic commits for the same conceptual change (documenting a
PG invariant), one going into `dev/` using `commit-message-style`
trailers (Author/Reviewed-by/Discussion), the other going into the
meta repo using `meta-commit-style` (ft(corpus): prefix +
Co-authored-by trailer). Closes with a back-pointer to R10
("two-repo separation").

## Edit 7 — Frontmatter description casing

**Disposition: APPLIED (folded into Edit 1).** Description now says
`Co-authored-by: Claude Opus 4.7 (1M context)` and explicitly notes
the lowercase + the real-log ratio inline, so the agent sees the
correct form even before opening the body.

## Verification of applied edits

```
$ git diff --stat -- .claude/skills/meta-commit-style/SKILL.md
 .claude/skills/meta-commit-style/SKILL.md | 109 +++++++++++++++++++++++++-----
 1 file changed, 92 insertions(+), 17 deletions(-)
```

Non-zero diff confirmed. No remaining problematic
`Co-Authored-By:` casing except in the explicit "do not write
this" callouts.

## Edits NOT proposed and NOT applied

- No edit to §"When to use" / §"When NOT to use" lists — both still
  accurate.
- No edit to §"Cross-skill notes" beyond the casing fix already done
  in Edit 1.
- No new examples added beyond what's already in §"Examples
  (canonical)" — three illustrative + the side-by-side block covers
  the common shapes.
