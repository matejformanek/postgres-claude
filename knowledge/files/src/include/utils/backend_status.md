# `src/include/utils/backend_status.h`

**Pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`

## Role

Declares `PgBackendStatus`, the per-backend shared-memory descriptor
read by `pg_stat_activity` / `pg_stat_ssl` / `pg_stat_gssapi` /
`pg_stat_progress_*`. Each live backend (and each auxiliary process)
owns one slot, indexed by `ProcNumber` [from-comment: lines 89-95].

> "Note that this is unrelated to the cumulative stats system (i.e.
> pgstat.c et al)." [from-comment: line 92]

## Public API

Globals:
- `pgstat_track_activities` (bool GUC) — gates activity reporting
  [verified-by-code: line 290].
- `pgstat_track_activity_query_size` (int GUC) — controls
  `st_activity_raw` buffer width [line 291].
- `MyBEEntry` — this backend's slot [line 298].

Functions (lines 307-337):
- Init: `pgstat_beinit`, `pgstat_bestart_initial`,
  `pgstat_bestart_security`, `pgstat_bestart_final` — three-phase
  startup (pre-auth → post-auth → post-init).
- Reporting: `pgstat_report_activity(state, cmd_str)`,
  `pgstat_report_query_id`, `pgstat_report_plan_id`,
  `pgstat_report_tempfile`, `pgstat_report_appname`,
  `pgstat_report_xact_timestamp`.
- Read: `pgstat_get_backend_current_activity(pid, checkUser)`,
  `pgstat_get_crashed_backend_activity(pid, buffer, buflen)`,
  `pgstat_clip_activity(raw_activity)`.
- Per-`ProcNumber` lookup: `pgstat_get_beentry_by_proc_number`,
  `pgstat_get_local_beentry_by_proc_number`,
  `pgstat_get_local_beentry_by_index`.

## Key structs

### `BackendState` enum [verified-by-code: lines 24-34]

UNDEFINED, STARTING, IDLE, RUNNING, IDLEINTRANSACTION, FASTPATH,
IDLEINTRANSACTION_ABORTED, DISABLED.

### `PgBackendStatus` [verified-by-code: lines 98-177]

- `st_changecount` — even ⇒ valid snapshot; odd ⇒ writer mid-update.
  Documented as a critical section [lines 100-115].
- `st_procpid > 0` ⇒ slot in use [line 118].
- Identity: `st_databaseid`, `st_userid`, `st_clientaddr`,
  `st_clienthostname`, `st_backendType`.
- SSL/GSS: pointers to `PgBackendSSLStatus` / `PgBackendGSSStatus`
  (separate structs, only filled when enabled) [lines 50-83].
- Activity: `st_state`, `st_appname`, `st_activity_raw` (query text,
  may be **truncated mid-multibyte-character** — caller of display
  must use `pgstat_clip_activity()` [lines 150-158]).
- Progress: `st_progress_command`, `st_progress_command_target` (OID),
  `st_progress_param[PGSTAT_NUM_PROGRESS_PARAM]`.
- Query/plan id: `st_query_id`, `st_plan_id` (filled via
  `post_parse_analyze_hook` / `planner_hook`) [lines 172-176].

### Lockless write protocol [verified-by-code: lines 209-238]

`PGSTAT_BEGIN_WRITE_ACTIVITY` / `PGSTAT_END_WRITE_ACTIVITY` bracket
every writer. They wrap `START_CRIT_SECTION()` — **any error between
them PANICs the cluster** [from-comment: lines 184-187].

Reader does:
```
pgstat_begin_read_activity(beentry, before);
... copy ...
pgstat_end_read_activity(beentry, after);
if (pgstat_read_activity_complete(before, after)) break;
```

### `LocalPgBackendStatus` [verified-by-code: lines 249-283]

Snapshot wrapper used when building the array view. Carries
`backendStatus`, `proc_number`, `backend_xid`, `backend_xmin`,
`backend_subxact_count`, `backend_subxact_overflowed`.

## Invariants

- **INV-CRITSEC** [verified-by-code: lines 184-222] Code between
  `PGSTAT_BEGIN_WRITE_ACTIVITY` and `PGSTAT_END_WRITE_ACTIVITY` must
  not call `ereport(ERROR, ...)` — promotion to PANIC restarts the
  cluster.
- **INV-CHANGECOUNT** [verified-by-code: line 220] `st_changecount`
  must be even after a successful write (asserted).
- **INV-NULTERM** [from-comment: lines 48, 54, 73] All char[] in
  SSL/GSS substructs are null-terminated and bounded by `NAMEDATALEN`.
- **INV-TRUNCATION** [from-comment: lines 152-155] `st_activity_raw`
  is stored truncated — display side must clip on character boundary.

## Trust boundary (Phase D)

This is the BIG Phase D surface for the utils slice.

- **`st_activity_raw` contains the query text.** Visible via
  `pg_stat_activity.query` to (a) the same role, (b) superuser, (c)
  `pg_read_all_stats`. The `checkUser` arg to
  `pgstat_get_backend_current_activity` gates the (a)/(b)/(c) check
  [verified-by-code: line 321].
- **Password leak risk** [from common knowledge, header silent]: a
  query like `ALTER USER foo PASSWORD 'plain'` lands in
  `st_activity_raw` as plaintext. Mitigated only by GUC
  `track_activities` (allows opt-out) and by the
  `password_command_tag` redaction in `postmaster.c` — not by this
  header. **Same family of leak as A11 pg_stat_statements `query`
  column.**
- **`st_userid` / `st_databaseid`** revealed cross-role through
  `pg_stat_activity` even when query text is redacted — enumeration
  vector for role/db names.
- **`st_query_id` / `st_plan_id`** are filled from hooks
  (`post_parse_analyze_hook`, `planner_hook`); an extension can
  spoof or leak these. (Same trust as A11.)
- **SSL / GSS fields** show client cert DN / GSS principal — visible
  cross-role via `pg_stat_ssl`/`pg_stat_gssapi`; possible PII leak
  in multi-tenant deployments.

## Cross-refs

- `pgstat_kind.h` — cumulative stats system (different mechanism).
- `pgstat_internal.h` — shared stats hash; orthogonal to per-backend
  array.
- `storage/procnumber.h` — `ProcNumber` index basis.
- A7 `pg_stat_statements`, A11 monitoring cluster, A14 monitoring
  contrib — same "monitoring = extraction" Phase D theme.

## Issues

- [ISSUE-DOC: header does not state the query-text redaction policy
  for password commands — relies on `postmaster.c` cooperation
  (medium)] — line 157 — could be silently broken by a future utility
  command that bypasses the redaction site.
- [ISSUE-API: `pgstat_track_activity_query_size` width chosen at
  postmaster start (PGC_POSTMASTER); changing it requires restart;
  not documented at header (low)] — line 291.
- [ISSUE-INV: `PGSTAT_BEGIN/END_WRITE_ACTIVITY` PANIC-on-error
  property is documented only in a comment block; no static-analyser
  tag (low)] — lines 184-187.
