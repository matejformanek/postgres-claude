---
source_url: https://wiki.postgresql.org/wiki/Todo
fetched_at: 2026-06-07T00:00:00Z
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
distilled_by: pg-docs-miner (cloud routine)
audience: contributors hunting for a feature to work on (and routines that mine the page for project direction)
---

# Wiki distilled — Todo

The project's long-running wishlist/bug catalogue, organized by subsystem. Its
value to this corpus is **as a direction signal, not a spec** — and its loudest
message is a disclaimer about exactly that. Distilled here as a corpus-orientation
artifact: what the page is, what it is *not*, and how to read an item.

## What the page IS / IS NOT

- It is a community-maintained list of bugs, feature requests, and proposed
  enhancements, grouped by subsystem, each typically linking to an archived
  pgsql-hackers thread for rationale. [from-wiki]
- **The disclaimer (load-bearing):** "This list does not contain all the
  information necessary for someone to start coding a feature. Some of these items
  might have become unnecessary since they were added — others might be desirable
  but the implementation might be unclear." [from-wiki — exact wording]
- And, blunt: **"Do not assume that you can select one, code it and then expect it
  to be committed."** The sanctioned path is
  **Desirability → Design → Implement → Test → Review → Commit**, with
  mailing-list discussion *before* coding. [from-wiki — exact wording]
  [cross: knowledge/wiki-distilled/Submitting_a_Patch.md,
  knowledge/community/patch-workflow.md]

## How to read an item

- **Markers:** an unchecked box = open/unstarted; a checked box with a `[D]` tag =
  done, slated for the next release. (The crawler observed `[D]` items tagged for
  PG17 at one point — the tag's target version moves each cycle, so treat the
  specific version as volatile.) [from-wiki] [inferred — version target drifts]
- Each item's real content is the **linked -hackers thread**, not the one-line
  summary; the summary is bait, the thread is the substance (often including "why
  this is harder than it looks" or "why we decided not to"). [inferred, from-wiki]

## Top-level category headings (the subsystem map)

Administration · Data Types · Functions · Multi-Language Support · Views and
Rules · SQL Commands · Integrity Constraints · Server-Side Languages · Clients ·
Triggers · Inheritance · Indexes · Sorting · Cache Usage · Vacuum · Locking ·
Startup Time · Write-Ahead Log · Optimizer/Executor · Background Writer · TOAST ·
Monitoring · Performance · Miscellaneous. [from-wiki — ~28 sections]

These headings double as a coarse index of where the project itself thinks the
open problems live — useful when a brainstorm asks "has this been wanted before?"

## Links into corpus

- [[knowledge/community/patch-workflow.md]] — the Desirability→…→Commit pipeline
  the disclaimer invokes.
- [[knowledge/wiki-distilled/Submitting_a_Patch.md]] / [[knowledge/wiki-distilled/Reviewing_a_Patch.md]]
  — the steps after picking an item.
- [[knowledge/community/so-you-want-to-be-a-developer.md]] — onboarding companion.
- pg-feature-brainstorm skill — its "has this been tried?" check should consult
  the relevant Todo section + the linked thread.

## Caveats

- **Never cite a Todo item as evidence PG behaves a certain way** — it describes
  what does *not yet* exist (or what someone wished for). It's a wishlist; treat
  every entry as `[unverified]` until the linked thread + current source confirm
  status. The page is also edited continuously, so the section set above can
  shift. [from-wiki]
