---
source_url: https://wiki.postgresql.org/wiki/Creating_Clean_Patches
fetched_at: 2026-06-05T20:50:00Z
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
distilled_by: pg-docs-miner (cloud routine)
primary: false
staleness: process page, low-churn; the git-mechanics advice is stable. Pairs
  with the `patch-submission` and `coding-style` skills for what Claude runs.
---

# Wiki distilled — Creating Clean Patches

The "the diff is itself a deliverable" page: how to scrub a patch of whitespace
and formatting noise *before* it reaches a reviewer's eyes. Companion to
`Submitting_a_Patch` (what must be in the email) — this one is purely about the
mechanical cleanliness of the diff bytes.

## What the wiki page says

- **The patch is a product, not a coding by-product.** "The patch is not just
  the output from a coding process: it's a product in its own right" and needs
  quality monitoring of its own before submission. Sloppiness here colors the
  reviewer's read of the actual code. [from-wiki]
- **First impressions transfer.** Formatting sloppiness biases the reviewer
  negatively toward the *code* quality too — the diff is the first thing seen.
  [from-wiki]
- **Tabs, 4-wide — spaces bloat the diff.** PG indents with 4-character tabs;
  editors that expand tabs to spaces produce large spurious diffs that violate
  the standard. (This is the same rule the `coding-style` skill enforces.)
  [from-wiki]
- **Catch trailing whitespace with `git diff --color`.** Color highlighting
  surfaces invisible trailing spaces that inflate the patch without changing
  behavior. (Mirrors `git diff --check` from the submission page.) [from-wiki]
- **Misaligned diffs → `--patience`.** When the default diff algorithm picks
  poor anchor lines and shows a block as deleted+re-added,
  `git diff --color HEAD^ HEAD --patience` often yields a tighter, more
  readable hunk. [from-wiki]
- **Squash whitespace/format fixes back into their origin commit** via
  `git rebase -i origin/master` — change `pick` to `s` (squash) on the
  follow-up commits so the history doesn't carry "fix whitespace" noise.
  [from-wiki]
- **Iterate commit→diff→fix→rebase until size stabilizes.** Treat shrinking the
  patch as a loop; use `wc` to track that each pass actually removes bytes, and
  practice the rebase dance on throwaway code first. [from-wiki]
- **Back up the pre-rebase patch.** Interactive rebase can corrupt or lose work;
  save the `format-patch` output before starting so you can recover. [from-wiki]
- **After squashing, delete the now-irrelevant commit messages** (the
  "whitespace fix" notes) so the final log reads cleanly. [from-wiki]
- **Review the diff independently of the working tree.** Read the patch as a
  patch — formatting errors invisible while staring at source files jump out in
  the unified diff. [from-wiki]
- **Smaller, focused patches get accepted faster** — fewer unrelated changes
  means less review surface, the same lever `Submitting_a_Patch` pulls. [from-wiki]

## How this maps to what Claude does

- The tabs-4-wide / no-trailing-whitespace rules are exactly what the
  `coding-style` skill and pgindent enforce; this page is the *pre-mail* manual
  check, pgindent is the automated one. [inferred]
- The "squash fixups, one clean commit" discipline is the upstream analogue of
  the meta-repo's R5 (one plan-linked commit per phase, no "WIP" commits) in
  `.claude/rules/pg-implement-discipline.md`. [inferred]
- NOTE: this environment's Bash cannot run `git rebase -i` (interactive flags
  are unsupported). For dev/ patches, prefer composing clean commits up front
  over relying on interactive squash. [verified-by-code, from harness constraints]

## Links into corpus

- [[knowledge/wiki-distilled/Submitting_a_Patch.md]] — the email-contents gate
  this page feeds into.
- [[knowledge/wiki-distilled/Working_with_Git.md]] — the broader git workflow.
- [[knowledge/wiki-distilled/Commit_Message_Guidance.md]] — what the surviving
  commit message should say after the squash.
- [[knowledge/community/patch-workflow.md]] — end-to-end mailing/CF flow.
- [[knowledge/conventions/coding-style.md]] — the tab/whitespace rules in code form.
- Skill: `patch-submission` — format-patch + cover letter + CF registration.
- Skill: `coding-style` — pgindent + whitespace expectations.
- `.claude/rules/pg-implement-discipline.md` R5 — one clean commit per phase.

## Confidence note

All substantive claims `[from-wiki]` (page fetched 2026-06-05). Mappings to the
meta-repo's skills/rules are `[inferred]`. No source-code cites — this is a
git-mechanics process page.
