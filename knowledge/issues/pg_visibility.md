# Issues — `contrib/pg_visibility`

VM/FSM-introspection extension. 1 source file / ~933 LOC.

**Parent docs:** `knowledge/files/contrib/pg_visibility/pg_visibility.c.md`.

**Source:** 5 entries surfaced 2026-06-09 by A14-1.

## Headlines

1. **Zero C-side privilege checks** on any of the 8 SQL entrypoints — install-script REVOKE-from-PUBLIC is the SOLE gate. Same A12 pattern as `amcheck`. Echoes A11 `pg_stat_statements`.
2. **`pg_truncate_visibility_map` accepts system-catalog OIDs** (only relkind filter); defense-in-depth absent — a superuser typo or extension confusion deputy can truncate `pg_class`'s VM.
3. **`collect_visibility_data` does `palloc0(MaxBlockNumber)`** without huge-alloc flag — adversary relfilenode → multi-GB allocation.

## Entries — `pg_visibility.c`

- [ISSUE-audit-gap: no C-side privilege checks on any of 8 entrypoints (likely)] — `:58-66`
- [ISSUE-correctness: `pg_truncate_visibility_map` doesn't check ownership or superuser (confirmed)] — `:370-446`
- [ISSUE-defense-in-depth: `pg_truncate_visibility_map` accepts system-catalog OIDs (maybe)] — `:925-933`
- [ISSUE-concurrency: manual `LWLockRelease(ProcArrayLock)+XidGenLock` after `GetRunningTransactionData` is fragile (nit)] — `:622-638`
- [ISSUE-resource: `collect_visibility_data` palloc0s up to ~MaxBlockNumber bytes without huge-alloc flag (maybe)] — `:500-501`

## Cross-sweep references

- A12 `amcheck` — same "no C-side checks" pattern.
- A11 `pg_stat_statements`, A7 `genfile.c` — "monitoring access = sensitive data extraction" cluster.
