---
source_url: https://wiki.postgresql.org/wiki/Continuous_Integration
fetched_at: 2026-06-04T18:55:00Z
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
distilled_by: pg-docs-miner (cloud routine)
primary: false
staleness: the wiki page is THIN (mostly points at src/tools/ci/README); this
  distillation is correspondingly short and flags the gap. The authoritative
  detail lives in the in-tree README, not the wiki.
---

# Wiki distilled — Continuous Integration

How patches get CI coverage before a committer ever looks at them. Two moving
parts: **cfbot** (auto-applies -hackers patches and runs CI) and **Cirrus CI**
(the multi-OS provider). The wiki page is mostly a pointer; the real reference is
`src/tools/ci/README` in the tree.

## What the wiki page says

- **cfbot is the unofficial patch tester.** It picks up patches posted to
  pgsql-hackers (tracked via the CommitFest app), applies them, and runs CI;
  "the branches it creates contain some example control files that might be
  useful." [from-wiki]
- **Cirrus CI is the recommended provider** because it "supports at least Windows,
  Linux, FreeBSD and macOS, so it currently has the widest range of operating
  systems targeted by PostgreSQL." Free for open-source, integrates with GitHub.
  [from-wiki]
- **CI control files live in `src/tools/ci/`** in the source tree (the cfbot
  branches carry example control files derived from these). [from-wiki]
- **A patch author can run the same CI on their own GitHub fork** by following
  `src/tools/ci/README`
  (https://git.postgresql.org/cgit/postgresql.git/tree/src/tools/ci/README) —
  "very easy … configured in a few minutes." Doing this *before* posting lets you
  land a patch already green across all four OSes. [from-wiki]

## Gaps the wiki page does NOT cover (go to the in-tree README)

The page omits — and `src/tools/ci/README` / `.cirrus.yml` carry — the actual
task matrix (compiler-warning task, regression, isolation, TAP, Windows/MSVC
build), how to read a cfbot failure, and any sanitizer/special builds. Flagged
here so a future session knows the wiki is not the source of truth for those.
[from-wiki, gap noted]

## How this maps to what Claude does

- For the meta repo, the practical takeaway: a patch produced by `/pg-implement`
  is "CI-ready" only once it would pass this four-OS Cirrus matrix; the
  `patch-submission` skill's pre-mail checklist is the local stand-in for cfbot.
  [inferred]
- The `Submitting_a_Patch` tests-AND-docs gate is what cfbot's regression/TAP
  tasks mechanically enforce. [inferred — cross-link
  knowledge/wiki-distilled/Submitting_a_Patch.md]

## Links into corpus

- [[knowledge/community/patch-workflow.md]] — where CI sits in the CF cycle.
- [[knowledge/wiki-distilled/Submitting_a_Patch.md]] — the gate cfbot enforces.
- [[knowledge/wiki-distilled/Reviewing_a_Patch.md]] — "applies cleanly to master"
  is phase 1, which cfbot automates.
- Skill: `patch-submission` — the local pre-mail equivalent of getting CI green.
- Skill: `testing` — regress/isolation/TAP, the suites the CI matrix runs.

## Confidence note

All claims `[from-wiki]` (page fetched 2026-06-04). The page is genuinely thin;
the "go to src/tools/ci/README" gap note is the most useful durable takeaway.
Mappings to meta-repo skills are `[inferred]`.
</content>
