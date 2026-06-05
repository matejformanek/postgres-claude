---
source_url: https://wiki.postgresql.org/wiki/Working_with_Git
fetched_at: 2026-06-05T20:50:00Z
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
distilled_by: pg-docs-miner (cloud routine)
primary: false
staleness: workflow page; repo URLs and branch-naming are stable. The
  interactive-rebase / push advice mostly applies to a local clone, not this
  cloud harness (no `git rebase -i`, no push to upstream).
---

# Wiki distilled — Working with Git

How the PostgreSQL project actually uses git: the canonical repo + mirror, the
`master` + `REL_NN_STABLE` branch scheme, the per-feature-branch +
`format-patch` contributor loop, and the "don't push branches you didn't clear"
rule. Background for `Creating_Clean_Patches` (which scrubs the diff this page's
workflow produces).

## What the wiki page says

- **Canonical repo:** `https://git.postgresql.org/git/postgresql.git`; an
  official read-only GitHub mirror lives at `https://github.com/postgres` for
  forking. [from-wiki]
- **Branch scheme:** `master` for development, plus one stable back-branch per
  major release named `REL_NN_STABLE` (e.g. `REL_15_STABLE`). [from-wiki]
- **Contributor loop is per-feature-branch:** `git checkout -b my-cool-feature`
  off `master`, develop there, then emit a patch with
  `git diff --patience master my-cool-feature > ../my-cool-feature.patch`. The
  `--patience` algorithm is recommended for cleaner hunks. [from-wiki]
- **Review by applying to a throwaway branch** (`patch -p1 < feature.patch`),
  not by reading the diff alone. [from-wiki]
- **`make maintainer-clean` before switching branches** so stale generated files
  don't leak across checkouts and cause spurious conflicts/build errors.
  [from-wiki]
- **Set `pager = less -x4` in `.git/config`** so 4-wide tabs render correctly in
  `git log`/`git diff` paging (PG uses 4-char tabs). [from-wiki]
- **A pre-commit hook to run `pgindent`** is available to keep indentation
  conformant automatically. [from-wiki]
- **Do NOT casually push your own branches to the core repo.** "If you are
  working with the postgresql core code, do NOT casually make up your own
  branches and push them, without clearing it on the pgsql-hackers list first."
  Public history is curated; contributors mail patches rather than push.
  [from-wiki]
- **`git push --dry-run origin master`** before any real push, to preview what
  would go. [from-wiki]
- **Clean up merged local branches** with `git branch -D my-cool-feature` once
  the change has landed upstream. [from-wiki]
- **Track commits without the list** via the gitweb RSS feed
  `https://git.postgresql.org/gitweb/?p=postgresql.git;a=rss`. [from-wiki]

## How this maps to what Claude does

- The per-feature-branch model is exactly R1 (one plan, one branch) in
  `.claude/rules/pg-implement-discipline.md`: dev/ work happens on a single
  slug-named branch off the upstream base. [inferred]
- "Mail patches, don't push to core" is why the `patch-submission` skill ends in
  `format-patch` + a pgsql-hackers email + a CommitFest entry, never a push to
  the canonical repo. [inferred]
- **Harness caveat:** this cloud environment cannot run `git rebase -i`
  (interactive flags unsupported) and does not push to upstream postgres — it
  fetches source by URL and works in `dev/`. The rebase/push advice here is for
  a developer's local clone. [verified-by-code, from harness constraints]
- The 4-wide-tab pager + pgindent hook are the git-config side of the same
  whitespace discipline the `coding-style` skill enforces. [inferred]

## Links into corpus

- [[knowledge/wiki-distilled/Creating_Clean_Patches.md]] — scrubbing the diff
  this workflow produces.
- [[knowledge/wiki-distilled/Submitting_a_Patch.md]] — what to put in the email.
- [[knowledge/wiki-distilled/Commit_Message_Guidance.md]] — the message format
  the committer applies.
- [[knowledge/community/patch-workflow.md]] — the end-to-end mailing/CF flow.
- Skill: `patch-submission` — format-patch + cover letter + CF registration.
- Skill: `coding-style` — pgindent + tab conventions.
- `.claude/rules/pg-implement-discipline.md` R1 — one plan, one branch.

## Confidence note

All substantive claims `[from-wiki]` (page fetched 2026-06-05). Mappings to the
meta-repo's rules/skills are `[inferred]`; the harness caveat is
`[verified-by-code]` from this environment's known constraints. No source-code
cites — workflow page.
