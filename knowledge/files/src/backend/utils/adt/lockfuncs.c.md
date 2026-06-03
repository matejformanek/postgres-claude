# src/backend/utils/adt/lockfuncs.c

## Purpose

Two distinct families:
1. **Lock introspection** — `pg_lock_status()` (backs the `pg_locks` view),
   `pg_blocking_pids(pid)`, `pg_safe_snapshot_blocking_pids(pid)`.
2. **Advisory locks** — the full `pg_advisory_*` API (int8 key or two int4
   keys; session-scoped or xact-scoped; exclusive or shared; lock or
   try-lock; lock or unlock).

## Role in PG

- Introspection functions wrap `GetLockStatusData()`,
  `GetPredicateLockStatusData()`, `GetBlockerStatusData()`,
  `GetSafeSnapshotBlockingPids()` from `lmgr`/`predicate.c` into SRF
  rows / int arrays.
- Advisory locks are an explicit application-level locking surface —
  the C side just maps the SQL int8/int4-pair into a LOCKTAG and calls
  `LockAcquire`/`LockRelease`. They live in the regular heavyweight
  lock manager, distinguished by `field4 ∈ {1, 2}` and scoped to
  `MyDatabaseId`.

## Key functions

Introspection:
- `pg_lock_status(PG_FUNCTION_ARGS)` (`lockfuncs.c:92-?`) — 16-column SRF
  emitting one row per heavyweight lock entry plus per-predicate-lock
  entry. Columns: locktype, database, relation, page, tuple,
  virtualxid, transactionid, classid, objid, objsubid,
  virtualtransaction, pid, mode, granted, fastpath, waitstart.
- `VXIDGetDatum(procNumber, lxid)` (`:73-86`) — formats vxid as
  `"<procNumber>/<lxid>"`. `elog.c` also knows this format.
- `pg_blocking_pids(blocked_pid)` (`:466-?`) — calls
  `GetBlockerStatusData(blocked_pid)`; walks both "hard block"
  (`conflictMask & instance->holdMask`) and "soft block" (ahead in
  wait queue with conflicting requested mode) cases. Excludes
  same-lock-group members (`instance->leaderPid ==
  blocked_instance->leaderPid`, `:521-523`).
- `pg_safe_snapshot_blocking_pids(blocked_pid)` (`:573-601`) —
  SSI-specific blockers.

Advisory locks (LOCKTAG layout at `:607-621`):
- `SET_LOCKTAG_INT64(tag, key64)` = ADVISORY tag with field1 =
  `MyDatabaseId`, field2/3 = hi/lo halves of int8, field4 = 1.
- `SET_LOCKTAG_INT32(tag, k1, k2)` = same but field2/3 = k1/k2,
  field4 = 2.
- One function per (int8 vs 2×int4) × (session vs xact) × (exclusive
  vs shared) × (lock vs try-lock vs unlock) — that's a lot of
  functions; each is a 3-5 line wrapper around `LockAcquire(&tag,
  ExclusiveLock, sessionLock, dontWait)` or `LockRelease(&tag,
  ExclusiveLock, sessionLock)`.
- `dontWait=false` for the regular `pg_advisory_lock`,
  `dontWait=true` for `pg_try_advisory_lock`.

## State / globals

None local.

## Phase D notes

- **Database scoping**: advisory locks include `MyDatabaseId` in
  field1 (`:609, :616, :621`). A `pg_advisory_lock(42)` in DB A and
  in DB B are independent — important: cross-database collisions
  cannot happen. Comment is explicit (`:609`).
- **No role-based partitioning**: any role with EXECUTE on
  `pg_advisory_lock` (which is PUBLIC by default) shares the same
  advisory keyspace. So `pg_advisory_lock(42)` taken by
  application A blocks application B (different roles, same DB)
  with no recourse other than naming-convention discipline. This is
  by design but mildly DoS-adjacent.
- **Int4 key overflow / collision**: the int8/int4 forms occupy
  different field4 namespaces, so `pg_advisory_lock(1, 0)` ≠
  `pg_advisory_lock(int8 value 0x0000000100000000)`. The
  field4 discriminator prevents the obvious collision.
- **Session vs xact lock leak**: `pg_advisory_lock` (session-scoped)
  is **not released by transaction abort** — a buggy app can leave
  session locks around forever until explicit unlock or session end.
  Compare to `pg_advisory_xact_lock` (auto-released at txn end).
  The wrapper passes `sessionLock=true` (`:634`).
- **pg_lock_status** is callable PUBLIC (per pg_proc.dat) but
  exposes every other session's lock list including object OIDs,
  database OIDs, and PIDs. Info disclosure for query patterns of
  other roles. The view `pg_locks` is the documented surface.

## Potential issues

- [ISSUE-info-disclosure: `pg_lock_status` exposes every backend's
  locked objects to PUBLIC. Combined with `pg_stat_activity`
  filtered query, an unprivileged role can fingerprint other
  roles' work. (low — matches `pg_locks` documented behaviour)]
- [ISSUE-dos: advisory locks share a database-wide keyspace with
  no role-based partitioning. App developers must coordinate keys;
  a malicious tenant can grab the keys of another tenant's app
  living in the same DB and starve them. (medium for multi-tenant
  shared-database deployments)]
- [ISSUE-correctness: session-scoped `pg_advisory_lock` survives
  transaction abort. A WHILE-loop in plpgsql that errors out leaves
  the lock until the connection drops. Well-documented but a
  frequent footgun (low)]
- [ISSUE-undocumented-invariant: the int8 / int4-pair LOCKTAG
  spaces are partitioned by `field4 ∈ {1, 2}`. Future addition of a
  new advisory shape (e.g. int4 single-key) must pick field4=3.
  Comment notes 1/2 only (low)]
