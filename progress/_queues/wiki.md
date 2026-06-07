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

[in-progress:cloud/pg-docs-miner/2026-06-06] Committing_with_Git https://wiki.postgresql.org/wiki/Committing_with_Git
[in-progress:cloud/pg-docs-miner/2026-06-06] CommitFest_Checklist https://wiki.postgresql.org/wiki/CommitFest_Checklist
[pending] Committing_checklist https://wiki.postgresql.org/wiki/Committing_checklist
[pending] Todo https://wiki.postgresql.org/wiki/Todo
[pending] RRReviewers https://wiki.postgresql.org/wiki/RRReviewers
