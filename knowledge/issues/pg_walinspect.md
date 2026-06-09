# Issues — `contrib/pg_walinspect`

WAL-record introspection extension. 1 source file / ~865 LOC.

**Parent docs:** `knowledge/files/contrib/pg_walinspect/pg_walinspect.c.md`.

**Source:** 3 entries surfaced 2026-06-09 by A14-1.

## Headlines

1. **🚨 `show_data=true` is a confirmed RLS/column-privilege bypass** — returns raw FPI page bytes from WAL, including DELETE'd and pre-UPDATE tuple contents. Gated only by `pg_read_server_files` grant, no per-relation check. **The most sensitive finding in A14.**
2. **`pg_get_wal_record_info` description text leaks transaction internals** — defense-in-depth nit (XIDs, txn names).
3. Per-block-ref inner loop has no `CHECK_FOR_INTERRUPTS` (bounded ~33 iters per record — nit).

## Entries — `pg_walinspect.c`

- [ISSUE-defense-in-depth: `show_data=true` returns raw FPI page bytes — DELETE'd / pre-UPDATE tuples bypass RLS, column privs, table SELECT (likely)] — `:377-409,425-467`
- [ISSUE-defense-in-depth: `pg_get_wal_record_info` description text leaks transaction internals (nit)] — `:217-247`
- [ISSUE-correctness: per-block-ref inner loop has no `CHECK_FOR_INTERRUPTS`; bounded ~33 iters (nit)] — `:284-416`

## Cross-sweep references

- A11 pg_stat_statements `track_utility=on` captures CREATE USER PASSWORD cleartext — both are "intended monitoring → unintended data extraction".
- A12 pageinspect / amcheck / pgstattuple `raw tuple data` family.
- A7 genfile.c, A11 pg_stat_statements — monitoring-as-extraction cluster.
