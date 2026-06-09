# Issues — `contrib/pg_buffercache`

Shared-buffers introspection extension. 1 source file / ~873 LOC.

**Parent docs:** `knowledge/files/contrib/pg_buffercache/pg_buffercache_pages.c.md`.

**Source:** 5 entries surfaced 2026-06-09 by A14-1.

## Headlines

1. **No C-side privilege checks on read entrypoints** — SQL REVOKE is sole gate. Same A12/A14 pattern.
2. **`evict_all` / `mark_dirty_all` do full NBuffers sweep with no rate limit** — DoS amplification.
3. **NUMA/OS-pages GRANT to `pg_monitor` exposes per-block working-set info** — defense-in-depth surface.

## Entries — `pg_buffercache_pages.c`

- [ISSUE-audit-gap: read entrypoints have no C-side privilege check; SQL REVOKE is sole gate (likely)] — `:85,521,588,502`
- [ISSUE-defense-in-depth: NUMA/OS-pages GRANT to `pg_monitor` exposes per-block working-set info (nit)] — `pg_buffercache--1.6--1.7.sql:10-12`
- [ISSUE-resource: `evict_all` / `mark_dirty_all` do full NBuffers sweep with no rate limit (nit)] — `:729-757,845-873`
- [ISSUE-documentation: `mark_dirty_relation` WAL amplification not flagged in comments (nit)] — `:794-839`
- [ISSUE-nit: `LockBufHdr`/`UnlockBufHdr` around lone bufferid read in `os_pages_internal` is defensive but unnecessary (nit)] — `:405-408`

## Cross-sweep references

- A14 pg_visibility — twin "REVOKE-only gate" pattern.
- A11 pg_stat_statements, A7 genfile.c — monitoring-as-extraction cluster.
