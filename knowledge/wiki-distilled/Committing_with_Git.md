---
source_url: https://wiki.postgresql.org/wiki/Committing_with_Git
fetched_at: 2026-06-06T00:00:00Z
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
distilled_by: pg-docs-miner (cloud routine)
audience: committers (and contributors who want to know what committers do)
---

# Wiki distilled — Committing with Git

Committer-facing companion to the contributor pages already distilled
(`Submitting_a_Patch`, `Working_with_Git`, `Commit_Message_Guidance`). Captures
the git config + push discipline that produces PG's linear, merge-free history —
useful even to non-committers because it explains *why* the project's history
looks the way it does and what `format-patch` output is expected to apply onto.

## Non-obvious claims

- **Rebase, never merge — enforced by config, not discipline.** Recommended setup:
  ```
  git config branch.master.rebase true
  git config branch.autosetuprebase always
  ```
  Rationale (quoted): "it is a good idea to set up your repository to rebase rather
  than merging" — merge commits "must be manually removed before pushing." PG's
  master is a strictly linear history; a merge commit is a mistake to be undone.
  [from-wiki]
- **Committer identity must match the server's records:**
  `git config user.name "..."` + `git config user.email ...@postgresql.org` — "your
  name and email address must match those configured on the server," or the push is
  rejected. [from-wiki]
- **`git push --dry-run` is mandatory before every real push:** "Always use
  'git push --dry-run' option before the real thing!" Verify with `git log` /
  `git diff` first. There is no force-push safety net on the shared repo. [from-wiki]
- **`push.default tracking`** is recommended to constrain a push to the current
  branch only, reducing the chance of pushing the wrong ref. [from-wiki]
- **Author and committer tags must match exactly** for the recorded commit; squash a
  branch with `git merge --squash <branch>` rather than creating a merge commit.
  [from-wiki]
- **Back-patching is just committing on the stable branch.** Stable branches are
  named `REL<N>_STABLE` (wiki example `REL9_0_STABLE`; modern form `REL_16_STABLE`).
  Workflow: check out the target branch, apply the change, commit — same as master.
  The convention (from the broader process, not just this page) is commit to master
  first, then back-patch as needed with `Backpatch-through:` in the message.
  [from-wiki] [cross: knowledge/wiki-distilled/Commit_Message_Guidance.md for the trailer]
- **Don't `git clone --reference` for a long-lived clone:** the page warns it risks
  data loss when the referenced repo is garbage-collected. Fine only for throwaway
  copies. [from-wiki]

## Links into corpus

- [[knowledge/wiki-distilled/Working_with_Git.md]] — the contributor-side git page
  (clone URL, `REL_N_STABLE`, `make maintainer-clean` on major switch).
- [[knowledge/wiki-distilled/Commit_Message_Guidance.md]] — the trailer block
  (`Author`, `Reviewed-by`, `Backpatch-through`, `Discussion`) a committer fills in.
- [[knowledge/wiki-distilled/Submitting_a_Patch.md]] / [[knowledge/community/patch-workflow.md]]
  — the upstream of what lands on a committer's desk.
- commit-message-style skill — the upstream-PG house format these commits use.
- patch-submission skill — the contributor end (format-patch, CF registration).

## Caveats

- Committer-only operations; a non-committer can't push to the canonical repo. The
  value here is understanding the target history shape so submitted patches rebase
  cleanly. The wiki page predates current branch names (uses `REL9_0_STABLE`); the
  mechanics are unchanged. [from-wiki]
