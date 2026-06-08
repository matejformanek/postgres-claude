---
source_url: https://wiki.postgresql.org/wiki/RRReviewers
fetched_at: 2026-06-07T00:00:00Z
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
distilled_by: pg-docs-miner (cloud routine)
audience: contributors who want to start reviewing (the lowest-friction on-ramp into the dev community)
---

# Wiki distilled — Round-Robin Reviewers (RRReviewers)

The community's on-ramp for new reviewers: volunteers get **randomly assigned** a
CommitFest patch so that every patch gets at least an initial review and so that
newcomers learn the codebase by reviewing. Distilled for the sign-up steps and the
minimal-review bar — the concrete "what's expected of me if I sign up".

## What it is / why it exists

- A program where volunteer hackers (solid C + some PG knowledge) are randomly
  assigned patches to review during a CommitFest, distributing review load and
  guaranteeing patches don't sit unreviewed. [from-wiki]
- **Active as of recent crawls** (the page carries no deprecation/historical
  marker). [from-wiki] [cross: knowledge/community/wiki-index.md notes it active
  as of Aug 2025]

## Sign-up (the four steps)

1. Subscribe to **`pgsql-hackers`** and **`pgsql-rrreviewers`**. [from-wiki]
2. Volunteer on the `pgsql-rrreviewers` list. [from-wiki]
3. Create a wiki account. [from-wiki]
4. Study the **Reviewing a Patch** page first. [from-wiki]
   [cross: knowledge/wiki-distilled/Reviewing_a_Patch.md]

## The assignment loop / minimal bar

- The **CommitFest Manager assigns** a patch by email; the reviewer then **claims
  it on commitfest.postgresql.org**. [from-wiki]
- Expected turnaround: **review within ~4 days**, post feedback to pgsql-hackers,
  update the CF app status (Waiting on Author / Ready for Committer / Rejected),
  and **tell the manager if you can't finish** (so it can be reassigned). [from-wiki]
- The minimal review is the first phases of the Reviewing-a-Patch checklist
  (does it apply, build, pass tests; does it do what it claims) — a round-robin
  reviewer is not expected to do a committer-grade architecture review, just to
  move the patch off "needs an initial look". [inferred, from-wiki]

## Links into corpus

- [[knowledge/wiki-distilled/Reviewing_a_Patch.md]] — the six-phase checklist a
  round-robin reviewer applies (step 4 of sign-up mandates reading it).
- [[knowledge/wiki-distilled/CommitFest_Checklist.md]] — the CFM side that does
  the assigning and chases stale reviewers.
- [[knowledge/community/review-patterns.md]] / [[knowledge/community/so-you-want-to-be-a-developer.md]]
  — the broader "how to start contributing" synthesis.
- review-checklist skill — the operational version of the review bar.

## Caveats

- Live process state (whether assignments are currently flowing, list activity)
  changes; the wiki page is the entry doc but `pgsql-rrreviewers` traffic is the
  real signal of whether the program is active in any given CF. [inferred]
