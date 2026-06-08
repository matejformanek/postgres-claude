---
source_url: https://wiki.postgresql.org/wiki/CommitFest
fetched_at: 2026-06-08T20:56:00Z
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
distilled_by: pg-docs-miner (cloud routine)
audience: a contributor who has a patch in (or about to enter) a CommitFest and needs the process model
---

# Wiki distilled — CommitFest

The CommitFest (CF) is the cadence that turns a stream of -hackers patches
into a release. Distilled for the process model: the rhythm, the "review one
to get one reviewed" social contract, and where the CF app fits.

## What it is / the rhythm

- **A periodic pause that focuses on review-and-commit rather than new
  development** — exists so every patch gets prompt feedback and work doesn't
  pile up at the end of the release cycle. [from-wiki]
- **Roughly one month per CF with a one-month gap between them**, when not
  disrupted by preparing a major release. There are typically several CFs per
  development cycle. [from-wiki]
- A long release hiatus can be preceded by a **ReviewFest (RF)** — a
  review-only phase with no commits. [from-wiki]

## The social contract

- **If you submit, you're expected to review.** During a CF contributors review
  and test *others'* patches, spreading load off the final reviewers/committers.
  This reciprocity is the norm a first-time submitter most often misses. [from-wiki]

## Outcomes (patch state machine)

- Most patches end **Committed**; others are **Returned with Feedback** (needs
  more work, re-submit next CF) or **Rejected** (community decided it's not a
  useful change). [from-wiki]
- The per-patch states the CF app tracks: **Needs Review**, **Waiting on
  Author**, **Ready for Committer**, **Committed**, **Returned with Feedback**,
  **Rejected**, **Withdrawn**, and **Moved to next CF**. [from-wiki]
  [cross: knowledge/wiki-distilled/CommitFest_Checklist.md — the CFM-side state-machine detail]
- After a successful CF an **Alpha** snapshot is released for testing; after the
  *final* CF of a release, a **Beta** is packaged. [from-wiki]
  [cross: knowledge/wiki-distilled/HowToBetaTest.md]

## The app

- **Patches are managed at `commitfest.postgresql.org`** — submit into the
  **Open** CF, review in the **In-Progress** CF. [from-wiki]
- A **CommitFest Manager (CFM)** drives a given CF: arranging reviews, chasing
  stale entries, moving the state machine. [from-wiki]
- The CF app itself is open source (PRs on its GitHub repo). [from-wiki]

## Links into corpus
- [[knowledge/wiki-distilled/CommitFest_Checklist.md]] — the CFM timeline + email templates + full state machine.
- [[knowledge/wiki-distilled/Submitting_a_Patch.md]] — what to attach to register a CF entry.
- [[knowledge/wiki-distilled/RRReviewers.md]] — how reviewers get assigned during a CF.
- [[knowledge/community/patch-workflow.md]] — the broader submit→review→commit synthesis.
- Skill: `patch-submission` — registering a CF entry as part of mailing a patch.

## Caveats
- Exact CF dates/numbers and whether a ReviewFest is scheduled change every
  cycle — read the live commitfest.postgresql.org for current state; this page
  is the stable *process* description only. [inferred]
