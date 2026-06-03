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
[in-progress:cloud/pg-docs-miner/2026-06-03] Free_Space_Map_Problems https://wiki.postgresql.org/wiki/Free_Space_Map_Problems
[in-progress:cloud/pg-docs-miner/2026-06-03] Group_Commit https://wiki.postgresql.org/wiki/Group_commit
[in-progress:cloud/pg-docs-miner/2026-06-03] Index-only_scans https://wiki.postgresql.org/wiki/Index-only_scans
[skipped:404-no-such-wiki-page] WAL_Internals https://wiki.postgresql.org/wiki/WAL_Internals
[skipped:404-no-such-wiki-page] Generic_WAL https://wiki.postgresql.org/wiki/Generic_WAL
