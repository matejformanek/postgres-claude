# Queue: pg-docs-miner — wiki side

Format: one entry per line.
`[status] <wiki-slug> <full-url>`
Status: `[pending]` / `[in-progress:<branch>]` / `[done:<sha>]` / `[skipped:<reason>]`.

Seed from `knowledge/community/wiki-index.md` rows not yet distilled.
Refill rule: re-walk `knowledge/community/wiki-index.md` for entries
without a corresponding `knowledge/wiki-distilled/<slug>.md`.

## Entries

[done:a49dd51] Hint_Bits https://wiki.postgresql.org/wiki/Hint_Bits
[done:c34e6da] Hot_Standby https://wiki.postgresql.org/wiki/Hot_Standby
[skipped:404-no-such-wiki-page] Logical_Decoding https://wiki.postgresql.org/wiki/Logical_Decoding
[skipped:404-no-such-wiki-page] MultiXacts https://wiki.postgresql.org/wiki/MultiXacts
[skipped:stale-2017-design-stub] Parallel_Query_Execution https://wiki.postgresql.org/wiki/Parallel_Query_Execution
[done:19c6e24] Free_Space_Map_Problems https://wiki.postgresql.org/wiki/Free_Space_Map_Problems
[done:19c6e24] Group_Commit https://wiki.postgresql.org/wiki/Group_commit
[done:19c6e24] Index-only_scans https://wiki.postgresql.org/wiki/Index-only_scans
[skipped:404-no-such-wiki-page] WAL_Internals https://wiki.postgresql.org/wiki/WAL_Internals
[skipped:404-no-such-wiki-page] Generic_WAL https://wiki.postgresql.org/wiki/Generic_WAL

## Refill 2026-06-04 (re-walk of wiki-index.md — developer-relevant pages without a wiki-distilled/<slug>.md)

[done:1aa5183] Submitting_a_Patch https://wiki.postgresql.org/wiki/Submitting_a_Patch
[done:1aa5183] Reviewing_a_Patch https://wiki.postgresql.org/wiki/Reviewing_a_Patch
[done:1aa5183] Valgrind https://wiki.postgresql.org/wiki/Valgrind
[done:1aa5183] Continuous_Integration https://wiki.postgresql.org/wiki/Continuous_Integration
[done:f53b7bf] Creating_Clean_Patches https://wiki.postgresql.org/wiki/Creating_Clean_Patches
[done:f53b7bf] Commit_Message_Guidance https://wiki.postgresql.org/wiki/Commit_Message_Guidance
[done:f53b7bf] Regression_test_authoring https://wiki.postgresql.org/wiki/Regression_test_authoring
[done:f53b7bf] Working_with_Git https://wiki.postgresql.org/wiki/Working_with_Git

## Refill 2026-06-06 (re-walk of wiki-index.md — remaining developer pages without a wiki-distilled/<slug>.md; stale stubs and 404s from prior runs excluded)

[done:a9c263b] Committing_with_Git https://wiki.postgresql.org/wiki/Committing_with_Git
[done:a9c263b] CommitFest_Checklist https://wiki.postgresql.org/wiki/CommitFest_Checklist
[done:b91492b] Committing_checklist https://wiki.postgresql.org/wiki/Committing_checklist
[done:b91492b] Todo https://wiki.postgresql.org/wiki/Todo
[done:b91492b] RRReviewers https://wiki.postgresql.org/wiki/RRReviewers

## Refill 2026-06-08 (re-walk of wiki-index.md — remaining developer pages without a wiki-distilled/<slug>.md; Developer_FAQ + So-you-want already have community/ docs, stale stubs and 404s excluded)

[done:8c2dd79] Mailing_Lists https://wiki.postgresql.org/wiki/Mailing_Lists
[done:8c2dd79] CommitFest https://wiki.postgresql.org/wiki/CommitFest
[done:8c2dd79] HowToBetaTest https://wiki.postgresql.org/wiki/HowToBetaTest
[done:8c2dd79] Development_information https://wiki.postgresql.org/wiki/Development_information

## EXHAUSTED — 2026-06-09 re-walk of wiki-index.md

Wiki side is drained: every developer-relevant page in `knowledge/community/wiki-index.md`
either has a `knowledge/wiki-distilled/<slug>.md` (all rows above) or is explicitly
unusable — `MVCC` (stale 2012 stub), `Parallel_Query_Execution` (stale 2017 design stub,
superseded by docs-distilled/parallel-query.md), `Development_projects`/roadmap pages
(archival), and the confirmed 404s (`Logical_Decoding`, `MultiXacts`, `WAL_Internals`,
`Generic_WAL`, `Backend_flowchart`, `Hacking_on_PostgreSQL`, `Glossary`,
`Working_with_GDB`, `Developer_Mentoring`). `Coding_Conventions` / `Running_a_Commitfest`
are redirects/stubs deferring to docs `source.html` / `CommitFest_Checklist` (both already
distilled). No new wiki candidates exist this run; this routine ran docs-only. Refill only
if wiki-index.md gains new rows.