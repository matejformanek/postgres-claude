# iter-1 SUMMARY — meta-commit-style

Three evals, 31 assertions, graded against the current SKILL.md text.

| Eval | with_skill | baseline |
|---|---|---|
| E1 (knowledge/idioms commit) | 10/11 | 5/11 |
| E2 (phase-3 multi-domain commit with Plan:/Sites:) | 9/10 | 3/10 |
| E3 (prefix correctness probe vs feat:) | 9/10 | 0/10 |
| **Total** | **28/31 (90.3%)** | **8/31 (25.8%)** |

**Uplift: +20 assertions (+64.5pp).** Comparable to commit-message-style
sibling (+17 → +81pp range across campaign).

## What the with_skill answers got right

- Cleanly picked `ft(corpus):` for E1 (vs baseline `feat(knowledge):`).
- Picked `ft(skills):` for E2 multi-domain commit; matched the plural
  scope from real log even though SKILL.md example uses singular.
- E3: clean rejection of `feat:` / `feat(scope):` / bare-imperative
  forms with explicit citation to §"Forbidden" and the contrast table.
- Plan: trailer format matched the strict spec; Sites: trailer used
  comma-separated multi-line form.

## What the with_skill answers got WRONG

**All three evals failed the same assertion** — `Co-authored-by:`
lowercase casing. The SKILL.md itself uses `Co-Authored-By:`
(GitHub-style uppercase) in every example. The real meta-repo log
uses lowercase `Co-authored-by:` 45 times vs uppercase 11 in the last
50 commits with a co-author trailer. The skill teaches an incorrect
spelling — agents that follow it faithfully will produce commits that
look slightly off from the established log.

## Highest-leverage edit

**Edit 1** — global `Co-Authored-By:` → `Co-authored-by:` replace.
Affects the description frontmatter, the contrast table row, the
§Trailers list item, all three canonical examples, and the §Forbidden
list. 7 sites total in SKILL.md.

This single fix closes the 3 failed assertions across E1/E2/E3 and
will saturate the rubric on iter-2.

## Secondary edits

- **Edit 2** — `ft(skill):` → `ft(skills):` (plural matches real-log
  23 occurrences; singular has 0).
- **Edit 3** — Expand prefix vocabulary table with real-log scopes
  (`ft(meta):`, `docs(state|cloud|community):`).
- **Edit 4** — Acknowledge looser `Plan:` trailer usage (`Plan: cloud
  routine X.md`, `Plan: catalog trio "..."`).
- **Edit 5** — Anchor each canonical example to a real commit SHA.
- **Edit 6** — Side-by-side block: same change, two styles
  (meta vs upstream).
- **Edit 7** — Folded into Edit 1 (description frontmatter casing).

## Baseline failure modes (consistent across 3 evals)

- Reaches for Conventional Commits (`feat(scope):`).
- Uses uppercase `Co-Authored-By: Claude <noreply@anthropic.com>`
  (GitHub-default).
- Doesn't know about `Plan:` / `Sites:` trailer format.
- Treats bare-imperative as universally valid (true for kernel/PG
  upstream, wrong for this repo).
- Doesn't know `(#NN)` is auto-appended by squash-merge — would
  inline-cite tickets.

The skill, post-edits, will reliably steer away from all of these.

## Source verifications performed

- Real-log scope vocabulary frequency.
- Co-author casing distribution (lowercase wins 45-vs-11).
- Plan: trailer real usage (strict-form + loose-form both observed).
- `[cloud:<routine>]` form structure verified.
- All example commit SHAs (62da1c2, 4925200, aecd8e3, 82ebf2e,
  b707ab2, 5a39b7d) verified present in current worktree's git log.
