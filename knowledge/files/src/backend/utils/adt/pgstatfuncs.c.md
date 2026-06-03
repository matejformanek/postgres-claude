# src/backend/utils/adt/pgstatfuncs.c

## Purpose

The SQL surface over `pgstat` — every column of every `pg_stat_*` system
view ultimately resolves to a function here. ~2360 lines covering
backend activity (`pg_stat_get_activity`), per-DB counters
(`pg_stat_get_db_*`), checkpointer / bgwriter / I/O / WAL / SLRU /
archiver / subscription / replication-slot statistics, function call
stats, and the `pg_stat_progress_*` view family.

## Role in PG

- Reads from `LocalPgBackendStatus` (the local copy of
  `PgBackendStatus` shared-memory state) via
  `pgstat_fetch_stat_numbackends()` /
  `pgstat_get_local_beentry_by_index()`, and from the regular pgstat
  snapshot for the various accumulator views.
- Backend-state functions return immediately via stale snapshot;
  consistency across rows isn't guaranteed ("no extra lock is being
  held" — comment at `:467-470`).

## Key permission macro

```
#define HAS_PGSTAT_PERMISSIONS(role)   \
    (has_privs_of_role(GetUserId(), ROLE_PG_READ_ALL_STATS) || \
     has_privs_of_role(GetUserId(), role))
```
(`pgstatfuncs.c:39`) — caller is allowed to see detailed stats for a
backend owned by `role` if they are a member of `pg_read_all_stats`
OR if they have role membership of the backend's owning role
(including self via `has_privs_of_role`'s `member == role` fast path).
This is the central trust gate for the whole file.

## Key functions

Function-level stats:
- `pg_stat_get_function_calls(funcOid)` (`:176-?`).
- `pg_stat_get_function_stat_reset_time(funcOid)` (`:208`).

Backend activity:
- `pg_stat_get_backend_idset()` (`:226-?`) — SRF of backend
  procNumbers; PUBLIC, no per-backend gate (just the index list).
- `pg_stat_get_progress_info(cmd_name)` (`:277-350`) — generic
  progress reporter for VACUUM/ANALYZE/REPACK/CREATE INDEX/BASEBACKUP/
  COPY/DATACHECKSUMS. **Filters at row level**:
  - Always exposes `pid`, `databaseid` (`:328-330`).
  - Exposes target relid + 20 numeric progress params only when
    `HAS_PGSTAT_PERMISSIONS(beentry->st_userid)` (`:333-344`).
- `pg_stat_get_activity(pid)` (`:355-711`) — the big one, 31 columns,
  backing `pg_stat_activity`. Column-level masking pattern:
  - **Always exposed (columns 0-3, 15-16)**: databaseid, pid, userid,
    application_name, backend_xid, backend_xmin (`:387-412`).
    Comment at `:386`: "Values available to all callers".
  - **HAS_PGSTAT_PERMISSIONS-gated (columns 4-14, 17-30)**: state,
    query, wait_event_type, wait_event, xact_start, query_start,
    backend_start, state_change, client_addr, client_hostname,
    client_port, leader_pid, query_id, backend_type, etc.
    (`:415-672`).
  - Non-permitted callers get column 5 = `'<insufficient privilege>'`
    and the rest NULL (`:673-700`).
  - Snapshot is unlocked — race against backend exit; comment
    `:466-470` accepts inconsistency.
- `pg_backend_pid()` (`:714-718`) — `MyProcPid` constant per call.
  No gate (your own PID).
- Per-procNumber accessors: `pg_stat_get_backend_pid`,
  `..._dbid`, `..._userid`, `..._subxact`, `..._activity`,
  `..._wait_event_type`, `..._wait_event`, `..._activity_start`,
  `..._xact_start`, `..._start`, `..._client_addr`, `..._client_port`
  (`:721-1029`). Pattern: lookup `beentry`, return NULL if missing,
  return `'<insufficient privilege>'` text or NULL if
  `!HAS_PGSTAT_PERMISSIONS(beentry->st_userid)`. **client_addr** /
  **client_port** return NULL on permission failure (not the
  placeholder text), so they leak nothing.

Per-database / cluster counters:
- `pg_stat_get_db_numbackends`, `..._db_stat_reset_time`,
  `..._db_conflict_all`, `..._db_checksum_failures`,
  `..._db_checksum_last_failure` (`:1032-?`). The
  checksum-failure functions check that the caller is a superuser
  via dedicated logic (most other counter functions are PUBLIC by
  default).

Checkpointer / bgwriter / WAL / I/O / SLRU / archiver:
- Long parade of `pg_stat_get_checkpointer_*`,
  `pg_stat_get_bgwriter_*`, `pg_stat_get_wal_*`,
  `pg_stat_get_io`, `pg_stat_get_slru`, `pg_stat_get_archiver`
  functions, mostly thin wrappers around `pgstat_fetch_stat_*()`
  accumulators. These are typically PUBLIC; the data is cluster-level
  and not per-backend.

Subscription / replication:
- `pg_stat_get_subscription`, `pg_stat_get_subscription_stats`,
  `pg_stat_get_replication_slot` — return per-subscription /
  per-slot metrics. Some have superuser / role gates.

## State / globals

None. Reads `pgstat` snapshots.

## Phase D notes — critical surface

- **`HAS_PGSTAT_PERMISSIONS` is the universal gate** for per-backend
  detail. Membership in `pg_read_all_stats` is the broadcast bypass —
  granting it equals "see every backend's query text, client IP,
  wait events". `pg_monitor` includes `pg_read_all_stats` by default
  (verified upstream).
- **`<insufficient privilege>` literal placeholder** in column 5
  (query column) is a *value*, not a NULL — so a `SELECT query FROM
  pg_stat_activity WHERE query LIKE '%password%'` from a non-priv
  role gets zero rows for masked sessions (false negative). Common
  app-layer footgun.
- **Always-exposed columns reveal**: `userid` of every backend, plus
  `application_name`, `backend_xmin`, `backend_xid`. So an unprivileged
  role can enumerate which roles are connected to which DBs, and
  approximately what they're doing via `application_name`. Designed.
- **client_addr** masking returns NULL on failed perm (`:956-957`),
  good — doesn't leak the IP via placeholder.
- **`pg_stat_get_progress_info`** correctness gate is unusual: the
  *command name* arg is validated against a hard-coded list
  (`:288-301`), errors on anything else (`:302-305`). Good — prevents
  custom progress-command leakage.
- **Wait event read** uses `UINT32_ACCESS_ONCE` (`:476`) for
  atomicity but does NOT hold any lock, so tearing across the type
  vs ID halves of the wait-event word is possible. Documented in
  the comment.
- **Snapshot staleness**: `LocalPgBackendStatus` is a copy taken at
  the start of the SRF, so a backend that exits mid-iteration shows
  its last activity. Combined with PID reuse, in pathological cases
  the row could attribute the prior backend's activity to a newly
  forked unrelated backend. The comment `:282-288` of
  `pg_stat_get_backend_activity` acknowledges this. [from-comment]
- **`backend_xmin` is exposed to PUBLIC** (`:409-411`) — reveals
  oldest in-progress xact, which combined with `txid_current()` lets
  a low-priv attacker fingerprint cluster txn rate.

## Potential issues

- [ISSUE-info-disclosure: `application_name` is exposed PUBLIC
  (`:399-402`). Apps that put session-identifying info or even
  secrets in app_name leak across roles. (low — by design, well
  known)]
- [ISSUE-info-disclosure: `userid` and `databaseid` columns are
  PUBLIC. Lets an unprivileged role enumerate which roles connect
  to which DBs — useful for targeted phishing / SET ROLE attempts.
  (low — matches documented pg_stat_activity)]
- [ISSUE-correctness: `<insufficient privilege>` is a string value,
  not NULL. Queries filtering on `query` column miss masked rows
  silently (false negatives). Documented but recurring footgun
  (low)]
- [ISSUE-state-transition: snapshot-then-read race against backend
  exit means a freshly forked backend reusing a recently freed
  PgBackendStatus slot could show as having the prior backend's
  activity. Documented at `:466-470`. (low)]
- [ISSUE-undocumented-invariant: `HAS_PGSTAT_PERMISSIONS` uses
  `has_privs_of_role` rather than `member_can_set_role`. So a
  non-INHERIT grant doesn't help — you must have INHERIT to see a
  member role's stats. Subtle; not documented in the macro
  comment. (low)]
- [ISSUE-dos: `pg_stat_get_activity` iterates over `num_backends`
  unconditionally before filtering by PID (`:367-384`); on a 10K
  connection cluster this is expensive per call. The PID-filtered
  fast path could early-exit by procNumber lookup but doesn't. (low)]
- [ISSUE-info-disclosure: `pg_stat_get_progress_info` exposes
  `pid`, `databaseid` to PUBLIC even for masked rows (`:328-330`).
  Reveals that some role is running a VACUUM / CREATE INDEX, which
  combined with `pg_locks` lets a low-priv role fingerprint
  maintenance windows. (low)]
- [ISSUE-correctness: wait-event read with `UINT32_ACCESS_ONCE`
  but no fence — type/ID tear is possible. Practical impact:
  occasional bogus wait-event string in pg_stat_activity. (low)]
