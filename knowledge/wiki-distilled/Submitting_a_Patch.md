---
source_url: https://wiki.postgresql.org/wiki/Submitting_a_Patch
fetched_at: 2026-06-04T18:50:00Z
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
distilled_by: pg-docs-miner (cloud routine)
primary: false
staleness: process page, kept reasonably current by the community; cross-check
  against the `patch-submission` skill and knowledge/community/patch-workflow.md
  for the operational steps Claude actually runs.
---

# Wiki distilled — Submitting a Patch

The canonical "what must be in a patch email before it counts as more than a
sketch" page. Pairs with the `patch-submission` skill (the how) and
`commit-message-style` (the message format).

## What the wiki page says

- **The two-item gate: regression tests AND documentation.** "Any patch without
  these two items is automatically considered a WIP one." A patch missing either
  is treated as work-in-progress regardless of how complete the code is — this is
  the single most-quoted rule on the page. [from-wiki]
- **A submission email is expected to state, explicitly:** project/feature name,
  a uniquely identifiable patch filename (versioned — `v1`, `v24`…), the patch's
  purpose, whether it's for discussion or for application, the **target branch**
  (ordinarily `master`; back-branches must be named), compile + test status with
  platform notes, regression-test coverage, documentation with examples,
  performance impact, and the rationale for the implementation choices made.
  [from-wiki]
- **`git format-patch` is the standard tool** — "The simplest way to format your
  patch is to use `git format-patch`." [from-wiki]
- **The fastest way to get rejected is unrelated changes.** Reformatting,
  re-wording comments, or touching code the feature doesn't need will get a patch
  bounced — keep the diff to exactly the change. [from-wiki]
- **Code must read as native.** The change should look "as if it has always been
  written in that way" — avoid `#ifdef` guards and "this is the new bit"
  delineating comments. [from-wiki]
- **Performance claims require reproducible tests in the patch.** Reviewers will
  not independently construct a benchmark; without an included test case
  demonstrating the improvement, a performance patch is returned. [from-wiki]
- **CommitFest registration is a separate, mandatory step.** Mailing the patch to
  pgsql-hackers is not enough — add it to the next CommitFest page to enter the
  formal review queue. [from-wiki]
- **Revisions link by Message-Id.** When resubmitting, give Message-Id-based
  links to the prior posts so reviewers (and the CF app) can follow the thread.
  [from-wiki]
- **Review is a reciprocal obligation.** Each CF submission carries an
  expectation to review at least one comparable-sized patch; paid contributors
  should budget that review time. [from-wiki]
- **Split large patches into separately-committable pieces** with a clear
  application order, rather than one monolith. [from-wiki]
- **Whitespace hygiene: `git diff --check`** to catch trailing/spurious
  whitespace before mailing. [from-wiki]

## How this maps to what Claude does

- The "regression tests AND docs" gate is exactly Rule R11 (test-first when
  changing behavior) in `.claude/rules/pg-implement-discipline.md` — a behavior
  change without its test is, by this page's definition, still WIP. [inferred]
- `git format-patch` + cover letter + CF entry is the `patch-submission` skill's
  job; this page is the *why* behind that skill's checklist. [inferred]
- "Unrelated changes get you rejected" is the upstream mirror of the meta-repo's
  scope discipline (R7 scope-creep-escalates). [inferred]

## Links into corpus

- [[knowledge/community/patch-workflow.md]] — the end-to-end mailing/CF flow.
- [[knowledge/community/so-you-want-to-be-a-developer.md]] — onboarding context
  this page assumes you already have.
- [[knowledge/wiki-distilled/Reviewing_a_Patch.md]] — the other side of the
  reciprocal-review obligation.
- Skill: `patch-submission` — format-patch + cover letter + CF registration.
- Skill: `commit-message-style` — the upstream message format a submission uses.
- Skill: `review-checklist` — the pre-mail self-review.
- `.claude/rules/pg-implement-discipline.md` R11 — test-first, the meta-repo
  echo of the tests-AND-docs gate.

## Confidence note

All substantive claims `[from-wiki]` (page fetched 2026-06-04). Mappings to the
meta-repo's rules/skills are `[inferred]`. No code cites — this is a process
page.
</content>
