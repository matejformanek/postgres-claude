---
source_url: https://wiki.postgresql.org/wiki/Commit_Message_Guidance
fetched_at: 2026-06-05T20:50:00Z
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
distilled_by: pg-docs-miner (cloud routine)
primary: false
staleness: process page; the trailer vocabulary is stable and is exactly what
  the `commit-message-style` skill encodes. Cross-check that skill for the
  format Claude actually emits in dev/ commits.
---

# Wiki distilled — Commit Message Guidance

The committer's-eye spec for a PostgreSQL commit log: the three-part shape, the
tag/attribution vocabulary, and the back-patch notation. This is the upstream
source of truth behind the `commit-message-style` skill.

## What the wiki page says

- **Subject ≤ ~64 chars.** "The Postgres email subject has only 64 characters,
  so try to stay under this limit" — because commit subjects become email
  subjects in the commit-notification list. [from-wiki]
- **Three-part structure:** a single summary line, a blank line, one or more
  narrative paragraphs (blank-line separated), then a block of tagged lines at
  the very end. [from-wiki]
- **Tag line format is rigid:** `<tag>: <attribution>`, each starting at the
  beginning of a new line. [from-wiki]
- **One line per attribution.** When several people share a tag (e.g. multiple
  reviewers), give each their own `Reviewed-by:` line rather than a
  comma-joined list. [from-wiki]
- **Attribution = cut-and-paste of the person's email `From:` field, unaltered**
  when possible — preserves exact name spelling/encoding. [from-wiki]
- **The `Author:` tag is omitted when the committer is the sole author** — the
  committer is assumed to be the author by default. [from-wiki]
- **Committers spell out their own attribution too** — no informal "by me";
  use the exact From-field form even for yourself. [from-wiki]
- **Discussion links use `https://postgr.es/m/MESSAGE_ID`** — the short
  redirector to the mailing-list archive thread that produced the patch.
  [from-wiki]
- **Back-patch notation, two cases:** when a fix lands from some old branch
  through master, `Backpatch-through:` names only the *oldest* branch (e.g.
  `15`). For a fix confined to specific branches *excluding* master, use a range
  like `13-15`; a single back-branch is `15 only`. [from-wiki]
- **Attribution ordering is most→least significant participant** within a tag
  type. [from-wiki]
- **Where context goes:** lengthy explanation of who-did-what belongs in the
  narrative paragraphs; only a brief parenthetical may ride on a tag line.
  [from-wiki]

## How this maps to what Claude does

- This page IS the spec the `commit-message-style` skill implements for `dev/`
  commits destined upstream: bare-imperative subject, wrapped body, the
  Author/Reviewed-by/Reported-by/Discussion/Backpatch-through trailer block,
  and crucially **no `Co-authored-by`, no `Signed-off-by`, no emoji**. [inferred]
- Contrast with `meta-commit-style` (this repo): meta commits use
  `ft()/hf()/docs()` prefixes and DO add `Co-Authored-By` — the two styles must
  not be mixed (R10 two-repo separation). [inferred]
- The `Discussion: https://postgr.es/m/...` trailer is what R6 (cite-or-don't-
  claim in commit messages) leans on for dev/ commits headed for the list.
  [inferred]

## Links into corpus

- [[knowledge/wiki-distilled/Submitting_a_Patch.md]] — the email this message
  ends up as the subject/body of.
- [[knowledge/wiki-distilled/Creating_Clean_Patches.md]] — scrubbing the diff
  before the message is finalized.
- [[knowledge/community/patch-workflow.md]] — full mailing/CF flow.
- Skill: `commit-message-style` — the upstream format this page specifies.
- Skill: `meta-commit-style` — the *contrasting* meta-repo format (with
  Co-Authored-By), for commits inside postgres-claude/.
- `.claude/rules/pg-implement-discipline.md` R5/R6 — per-phase commit shape and
  the cite-in-message rule.

## Confidence note

All substantive claims `[from-wiki]` (page fetched 2026-06-05). Mappings to the
two commit-style skills and the implement rules are `[inferred]`. No code cites —
process page.
