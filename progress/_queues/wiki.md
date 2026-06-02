# Queue: pg-docs-miner — wiki side

Format: one entry per line.
`[status] <wiki-slug> <full-url>`
Status: `[pending]` / `[in-progress:<branch>]` / `[done:<sha>]` / `[skipped:<reason>]`.

Seed from `knowledge/community/wiki-index.md` rows not yet distilled.
Refill rule: re-walk `knowledge/community/wiki-index.md` for entries
without a corresponding `knowledge/wiki-distilled/<slug>.md`.

## Entries

[done:a49dd51] Hint_Bits https://wiki.postgresql.org/wiki/Hint_Bits
[done:pending-merge] Hot_Standby https://wiki.postgresql.org/wiki/Hot_Standby
[pending] Logical_Decoding https://wiki.postgresql.org/wiki/Logical_Decoding
[pending] MultiXacts https://wiki.postgresql.org/wiki/MultiXacts
[pending] Parallel_Query_Execution https://wiki.postgresql.org/wiki/Parallel_Query_Execution
[pending] Free_Space_Map_Problems https://wiki.postgresql.org/wiki/Free_Space_Map_Problems
[pending] Group_Commit https://wiki.postgresql.org/wiki/Group_commit
[pending] Index-only_scans https://wiki.postgresql.org/wiki/Index-only_scans
[pending] WAL_Internals https://wiki.postgresql.org/wiki/WAL_Internals
[pending] Generic_WAL https://wiki.postgresql.org/wiki/Generic_WAL
