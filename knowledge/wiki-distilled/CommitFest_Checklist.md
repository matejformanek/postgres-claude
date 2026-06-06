---
source_url: https://wiki.postgresql.org/wiki/CommitFest_Checklist
fetched_at: 2026-06-06T00:00:00Z
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
distilled_by: pg-docs-miner (cloud routine)
audience: CommitFest Manager (CFM); also useful to submitters tracking patch state
---

# Wiki distilled — CommitFest Checklist

The CFM-facing operational page. Distilled mainly for the **patch-state machine**
and the **timing rules** — those are what a submitter (or a routine tracking CF
status, e.g. `pg-community-pulse`) needs to interpret a patch's standing, even
though the bulk of the page is CFM chores.

## The CommitFest cycle & timing rules

- **~one-month cycle**; a CFM is recruited "several weeks prior." [from-wiki]
- **Submission deadline = CF start.** "Patches must be submitted before the CF
  officially begins; new submissions after start go to next CF." [from-wiki]
- CFM cadence: a **patch sweep** of the prior ~two months' -hackers archive 5–7 days
  before start; status review every **5–7 days** during the CF; reviewer-status
  emails 5–7 days before end; disposition reminder 3 days before end. [from-wiki]
- **First day:** CFM flips the CF from "Open" to "In Progress" and announces it. [from-wiki]

## Patch states (the machine submitters care about)

The CF app tracks: **Needs Review · Waiting on Author · Ready for Committer ·
Committed · Returned with Feedback · Rejected · Withdrawn · Moved to next CF.**
[from-wiki]

Transitions worth knowing:

- **Waiting on Author → Needs Review** when the author responds (CFM does this on
  the 5–7 day sweep). [from-wiki]
- **Needs Review → Ready for Committer** when review is complete and positive; CFM
  then checks **cfbot** and nudges the author if a rebase is needed. [from-wiki]
- **Final-day disposition:** a patch still "Waiting on Author" *with ≥1 review* →
  **Returned with Feedback**; a patch still "Needs Review" → **Moved to next CF**
  if it got a good review, else it stays pending into "sudden death overtime."
  [from-wiki]
- **"Sudden Death Overtime"** (after the close deadline): anything needing changes is
  **Returned with Feedback** immediately; "needs review" patches whose submitter did
  no reviews **Move to next CF**. [from-wiki]

## The review-quota rule (affects every submitter)

- "each patch submitter is required to do at least one patch review for each
  submitted patch." The CFM's nag templates enforce it, and "public lists shame
  non-reviewers if necessary." [from-wiki — exact intent]

## cfbot interaction

- **cfbot** continuously applies + CI-tests CF patches; the CFM uses it to spot
  patches that "no longer apply and need rebasing" before/during the CF. A red
  cfbot is the standard trigger for a "please rebase" nudge. [from-wiki]
  [cross: knowledge/wiki-distilled/Continuous_Integration.md]

## CFM email templates (named, not quoted in full)

Patch sweep (onboarding new contributors) · patch reminder (review-quota nag) ·
reviewer clear (drop inactive reviewers after ~5 idle days) · returned-with-feedback
notice. [from-wiki]

## Links into corpus

- [[knowledge/wiki-distilled/Reviewing_a_Patch.md]] — what a review the quota
  demands actually consists of (the six-phase checklist).
- [[knowledge/wiki-distilled/Submitting_a_Patch.md]] — the submitter side feeding
  the CF.
- [[knowledge/wiki-distilled/Continuous_Integration.md]] — cfbot / Cirrus, the CI
  the CFM reads.
- [[knowledge/community/patch-workflow.md]] / [[knowledge/community/review-patterns.md]]
  — corpus synthesis of the end-to-end flow.
- review-checklist + patch-submission skills — the operational versions.

## Caveats

- Audience is the CFM, not the average contributor; the live source of truth is the
  CF app at https://commitfest.postgresql.org. Status-machine wording can drift as
  the app evolves — re-verify state names against the app before quoting in tooling.
  [from-wiki]
