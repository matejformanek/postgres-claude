# Issues — `contrib/pg_freespacemap`

FSM-introspection extension. 1 source file / ~53 LOC.

**Parent docs:** `knowledge/files/contrib/pg_freespacemap/pg_freespacemap.c.md`.

**Source:** 1 entry surfaced 2026-06-09 by A14-1.

## Headlines

The smallest contrib module — barely more than a wrapper around `GetRecordedFreeSpace`. Same audit-gap as its sibling modules.

## Entries — `pg_freespacemap.c`

- [ISSUE-audit-gap: no C-side privilege check, only SQL grant to `pg_stat_scan_tables` (nit)] — `:27-53`

## Cross-sweep references

- A14 pg_visibility, pg_buffercache — same "REVOKE-only / pg_stat_scan_tables-only" gate pattern.
