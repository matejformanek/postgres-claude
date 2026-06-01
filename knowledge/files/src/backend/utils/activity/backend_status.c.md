# `src/backend/utils/activity/backend_status.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** ~1260
- **Source:** `source/src/backend/utils/activity/backend_status.c`

`pg_stat_activity` backing — the per-backend status array
`BackendStatusArray` (`PgBackendStatus`), allocated once at postmaster
start (size = `MaxBackends + auxiliary procs`). Each backend writes its
own slot, readers walk the whole array.

## Status fields

`PgBackendStatus` holds: `st_procpid`, `st_backendType`,
`st_userid`, `st_databaseid`, `st_clientaddr`, `st_clienthostname`,
`st_appname`, `st_activity_raw` (current SQL),
`st_state` (idle/active/idle in transaction/...), `st_xact_start_timestamp`,
`st_query_start_timestamp`, `st_state_start_timestamp`,
`st_proc_start_timestamp`, `st_query_id`, `st_progress_command*`.

## Concurrency trick

Readers must avoid torn reads of long strings (query text). Each
backend has a `st_changecount` (incremented at start and end of every
update, even-final means stable). Readers `PG_USED_FOR_ASSERTS_ONLY`-style
loop: read changecount, copy fields, read changecount again, retry if
different or odd. No locks involved. [from-comment]
(`pgstat_*_changecount_*` macros)

## Notable API

- `pgstat_bestart_initial` / `pgstat_bestart_security` /
  `pgstat_bestart_final` — staged backend startup, so partial state is
  observable before client cert/SSL handshake completes.
- `pgstat_report_activity(STATE, query)` — called by tcop for every
  command boundary.
- `pgstat_report_xact_timestamp`, `pgstat_report_query_id`.
- `pgstat_fetch_stat_beentry(idx)` / `pgstat_fetch_stat_local_beentry` —
  reader path; returns a memcpy'd snapshot.
- Activity-string truncation by `pgstat_track_activity_query_size`
  (GUC, default 1024).

## Notable invariants

- `st_activity_raw` is raw bytes; the SQL view applies
  `pgstat_clip_activity` to UTF-validate (or replace with `?`).
- After backend exit, slot is cleared by atexit hook
  `pgstat_beshutdown_hook`. [from-comment]
