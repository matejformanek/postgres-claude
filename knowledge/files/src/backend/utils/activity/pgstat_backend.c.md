# `src/backend/utils/activity/pgstat_backend.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** ~380
- **Source:** `source/src/backend/utils/activity/pgstat_backend.c`

Per-backend stats added in PG18 (backs `pg_stat_get_backend_io` etc.).
Variable-numbered using **ProcNumber** as object id, so each running
backend has its own entry. Entries are created at backend start and
**dropped on exit** — and **not written to the stats file** on
shutdown. (`write_to_file = false` in `KindInfo`).

Pending data is special: it does **not** live in
`PgStat_EntryRef->pending` like other variable-numbered stats. Instead
each backend keeps `PendingBackendStats` (a single struct), and
`flush_static_cb` (`pgstat_backend_flush_cb`) flushes it into the per-
backend shared entry. This avoids the overhead of running through the
generic pending-list code path. [from-comment] (`pgstat_backend.c:11-15`)

Counters: per-backend I/O matrix (mirrors `pg_stat_io` per process),
plus xact_commit/rollback, last activity timestamp.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
