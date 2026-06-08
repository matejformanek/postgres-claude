---
source_url: https://wiki.postgresql.org/wiki/Mailing_Lists
fetched_at: 2026-06-08T20:55:00Z
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
distilled_by: pg-docs-miner (cloud routine)
audience: a contributor deciding which list to post to and how to format the mail so it isn't ignored
---

# Wiki distilled — Mailing Lists

The mailing list is still where PostgreSQL development happens (patches,
review, design) — GitHub is a mirror, not the forum. Distilled for "which
list, and how to not get filtered/ignored on the first post".

## Which list for what

- **`pgsql-hackers`** — patches, internals/design discussion, and **bug
  reports against *unreleased* versions** (beta/master). The list backend
  hackers live on. [from-wiki]
- **`pgsql-bugs`** — bug reports against *released* versions (preferred for
  beta-test bug reports too). [from-wiki]
  [cross: knowledge/wiki-distilled/HowToBetaTest.md]
- **`pgsql-docs`** — documentation edits/contributions. [from-wiki]
- **`pgsql-general`** — usage questions from developers/DBAs/admins. [from-wiki]
- **`pgsql-performance`** — tuning, benchmarking, performance case studies. [from-wiki]
- **`pgsql-novice`** — beginner questions in a lower-traffic, friendlier space. [from-wiki]
- **`pgsql-www`** — website + project infrastructure. [from-wiki]
- **`pgsql-advocacy`** — conferences, user groups, outreach. [from-wiki]
- (`pgsql-committers` carries commit announcements; `pgsql-rrreviewers` the
  round-robin review program — see cross-links.) [from-wiki]
  [cross: knowledge/wiki-distilled/RRReviewers.md]

## Etiquette — the rules that get a first post ignored if broken

- **Reply-all**, so the list *and* the original sender both receive the reply.
  [from-wiki]
- **No top-posting** — quote the relevant text and reply *beneath* it, trimming
  the rest ("appropriate quoting"). [from-wiki]
- **Plain text only — no HTML-enriched mail.** HTML mail is the classic
  silently-dropped/filtered first post. [from-wiki]
- **Strip corporate confidentiality notices** before sending — **every message
  is archived publicly**, so a "this email is confidential" footer is both
  false and noise. [from-wiki]

## Mechanics

- **Subscribe** via the web form at
  `postgresql.org/community/lists/subscribe/`. [from-wiki]
- **You can post without subscribing** — but moderation may delay an
  unsubscribed poster's first message. [from-wiki, inferred]
- **Archives** are at `postgresql.org/list/`. To reply into an existing thread
  set the **`In-Reply-To`** header to the archived message-id so your mail
  threads correctly (the same message-id format the commit `Discussion:`
  trailer uses: `postgr.es/m/<id>`). [from-wiki]
  [cross: knowledge/wiki-distilled/Commit_Message_Guidance.md]

## Links into corpus
- [[knowledge/community/patch-workflow.md]] — the end-to-end submit→review→commit flow these lists carry.
- [[knowledge/wiki-distilled/Submitting_a_Patch.md]] — what a -hackers patch mail must contain.
- [[knowledge/wiki-distilled/RRReviewers.md]] — the pgsql-rrreviewers on-ramp.
- Skill: `patch-submission` — operational "mail this upstream" steps.

## Caveats
- List membership/names are stable but moderation behavior and exact subscribe
  URLs drift; re-verify the URL on the live site before quoting it in a
  user-facing instruction. [inferred]
