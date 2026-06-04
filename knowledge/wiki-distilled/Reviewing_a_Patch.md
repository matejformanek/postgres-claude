---
source_url: https://wiki.postgresql.org/wiki/Reviewing_a_Patch
fetched_at: 2026-06-04T18:50:00Z
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
distilled_by: pg-docs-miner (cloud routine)
primary: false
staleness: process page; the six-phase structure is stable and is the backbone
  of both the `review-checklist` skill and `pg-patch-review`. CFM name on the
  live page drifts (Daniel Gustafsson at fetch time) — don't quote the name.
---

# Wiki distilled — Reviewing a Patch

The six-phase review checklist that underlies the `review-checklist` skill and
the `pg-patch-review` multi-agent flow. The phases are an *ordering*: cheap,
mechanical checks first; project-wide architecture judgment last.

## The six phases

1. **Submission review** — is the patch in a format with context? Does it apply
   cleanly to current `master`? Are comments understandable English? Are tests
   and doc changes included? [from-wiki]
2. **Usability review** — does it implement what it claims? Do we *want* it / do
   we already have it? Does it follow the SQL spec where one applies, and does it
   support `pg_dump`? [from-wiki]
3. **Feature test** — apply, build (with `--enable-cassert` and
   `--enable-debug`), and actually exercise it. Hunt corner cases, crashes, and
   assertion failures. [from-wiki]
4. **Performance review** — does it slow down simple cases? Do the *claimed*
   improvements actually materialize? Any unintended regressions? [from-wiki]
5. **Coding review** — does it follow the project coding guidelines? Is it
   portable (Windows, BSD)? Compiler warnings? Crash conditions? [from-wiki]
6. **Architecture review** — does it fit together coherently with the rest of the
   system? Interdependencies and module interactions handled cleanly? [from-wiki]

There is also an implicit **"review review"**: did the reviewer actually fulfill
the role's obligations. [from-wiki]

## Non-obvious reviewer guidance

- **Sign up the moment you commit to review** — not when you finish — so CF
  resource planning works. No prior permission is needed to self-assign.
  [from-wiki]
- **Aim for an initial review within ~5 days**; partial reviews and time
  extensions are fine if you communicate. [from-wiki]
- **Reply in-thread to the patch email** so the author sees the feedback and
  threading is preserved. [from-wiki]
- **Performance testing must use a build WITHOUT `--enable-cassert` and
  `--enable-debug`** to measure real speed — the opposite of the feature-test
  build. (`--enable-debug` costs performance on most compilers except gcc; for
  non-perf work you can selectively disable assertions with
  `debug_assertions = false` in `postgresql.conf`.) [from-wiki]
- **The reviewer's job is to report findable problems, not to guarantee
  quality.** Even partial C/SQL knowledge qualifies you if you can apply a patch
  and test the feature. The eventual *committer* does the deep final review.
  [from-wiki]
- CommitFest status transitions a reviewer drives: **Needs review → Waiting on
  author** (found issues) / **→ Ready for committer** (looks good). [from-wiki]

## How this maps to what Claude does

- The six phases are the spine of the `review-checklist` skill (seven-phase
  scaffold = these plus a final committer-readiness pass) and of the four
  `pg-patch-review` critic agents (architecture/invariants, breaking-change,
  test-coverage, style/commit-message map onto phases 6, 2, 1/3, and 5). [inferred]
- **The build-flag inversion is a real gotcha to encode**: feature-test build is
  cassert+debug ON; performance-test build is cassert+debug OFF. Mixing them
  produces wrong perf numbers. [inferred — cross-check `build-and-run`]

## Links into corpus

- [[knowledge/community/review-patterns.md]] — committer review idioms layered on
  top of these phases.
- [[knowledge/community/patch-workflow.md]] — where review sits in the CF cycle.
- [[knowledge/wiki-distilled/Submitting_a_Patch.md]] — the author side; the
  reciprocal-review obligation.
- Skill: `review-checklist` — the seven-phase self/peer review scaffold.
- Skill: `pg-patch-review` — multi-agent deep review (4 critics + synthesizer).
- Skill: `build-and-run` — cassert/debug flags the feature-test vs perf-test
  phases toggle.

## Confidence note

All substantive claims `[from-wiki]` (page fetched 2026-06-04). Mappings to the
review skills are `[inferred]`. CFM identity on the live page is volatile and
deliberately not quoted here.
</content>
