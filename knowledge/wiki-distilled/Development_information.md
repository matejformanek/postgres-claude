---
source_url: https://wiki.postgresql.org/wiki/Development_information
fetched_at: 2026-06-08T20:58:00Z
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
distilled_by: pg-docs-miner (cloud routine)
audience: a new backend hacker who needs the real developer hub (Main_Page is thin) — this is the jump-table
---

# Wiki distilled — Development_information (the developer hub)

The **real** developer landing page (Main_Page barely links to dev resources).
Distilled as a jump-table: what categories it organizes and the highest-value
links under each, so a session can route to the right wiki/doc without
re-crawling.

## Development Process
- **Submitting a Patch** + **Reviewing a Patch** — the contribution workflow
  bookends. [from-wiki]
  [cross: knowledge/wiki-distilled/Submitting_a_Patch.md, Reviewing_a_Patch.md]
- **So, you want to be a developer?** — newcomer entry point. [from-wiki]
  [cross: knowledge/community/so-you-want-to-be-a-developer.md]
- **CommitFest** process pages — how patches move to commit. [from-wiki]
  [cross: knowledge/wiki-distilled/CommitFest.md]

## Developer Resources
- **Developer FAQ** — source-tree layout, gdb/perf/rr/valgrind, palloc/ereport,
  catalog access, OID assignment. [from-wiki]
  [cross: knowledge/community/developer-faq-distilled.md]
- **Regression test authoring**, **Working with Git**, **pgindent** /
  coding-style tooling. [from-wiki]
  [cross: knowledge/wiki-distilled/Regression_test_authoring.md, Working_with_Git.md]
- **Development docs at `postgresql.org/docs/devel/`** — the unreleased-branch
  manual (use over `/docs/current/` when working against master). [from-wiki]

## CommitFests
- **`commitfest.postgresql.org`** — all past/current/upcoming cycles; **Open**
  (submit) and **In-Progress** (review) entries. [from-wiki]
  [cross: knowledge/wiki-distilled/CommitFest_Checklist.md]

## Roadmaps & Projects
- Version-specific roadmaps (10, 11, …) and **Development_projects** — **mostly
  archival/stale**; useful for "when was X added" archaeology, not current
  planning. [from-wiki, dated]

## Past Developer Meetings
- **PgCon / FOSDEM-PGDay developer-meeting + unconference notes, 2008–2024** —
  genuinely useful for understanding *why* a design decision was made (often the
  only written rationale for a given choice). [from-wiki]

## Community channels
- **IRC `#postgresql` on Libera Chat**; real-name ↔ handle mappings for
  identifying who's who on -hackers. [from-wiki]

## How to use this doc
- Treat this as the **router**: Main_Page is thin and won't surface dev pages;
  start here (or jump straight to the corpus cross-links above, which already
  distill most of the high-value targets). [from-wiki]

## Links into corpus
- [[knowledge/community/wiki-index.md]] — the annotated, dead-link-flagged map of the whole dev wiki (supersedes browsing this page live).
- [[knowledge/community/developer-faq-distilled.md]] — the Developer FAQ distilled.
- [[knowledge/community/patch-workflow.md]] — submit→review→commit synthesis.

## Caveats
- A hub page: links churn and several it points to are stale (Development_projects,
  old roadmaps). The corpus `wiki-index.md` is the more reliable map; use this
  page only to discover something `wiki-index.md` hasn't catalogued yet. [inferred]
