# `src/include/storage/lockdefs.h`

- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
- **Lines:** 61

## Role

**The 8 standard SQL-visible LOCKMODE values** plus `NoLock`
sentinel and the `xl_standby_lock` WAL record for replaying
AccessExclusiveLocks on a standby. Split out from `lock.h`
because some FRONTEND code (pg_waldump, recovery utilities)
needs the constants without dragging in the whole backend lock
manager. [from-comment] lines 4-9.

## Public API

[verified-by-code] `source/src/include/storage/lockdefs.h:33-48`

| Value | LOCKMODE | SQL example |
|---|---|---|
| 0 | `NoLock` | "don't get a lock" sentinel |
| 1 | `AccessShareLock` | SELECT |
| 2 | `RowShareLock` | SELECT FOR UPDATE/SHARE |
| 3 | `RowExclusiveLock` | INSERT, UPDATE, DELETE |
| 4 | `ShareUpdateExclusiveLock` | VACUUM (non-exclusive), ANALYZE, CREATE INDEX CONCURRENTLY |
| 5 | `ShareLock` | CREATE INDEX (no CONCURRENTLY) |
| 6 | `ShareRowExclusiveLock` | EXCLUSIVE MODE + ROW SHARE compat |
| 7 | `ExclusiveLock` | blocks ROW SHARE / SELECT FOR UPDATE |
| 8 | `AccessExclusiveLock` | ALTER TABLE, DROP TABLE, VACUUM FULL, LOCK TABLE |

`MaxLockMode = 8`. Conflict matrix lives in
`src/backend/storage/lmgr/lock.c`.

Special: `InplaceUpdateTupleLock = ExclusiveLock` (line 51) —
referenced by `README.tuplock`.

## xl_standby_lock (WAL)

```
{ TransactionId xid, Oid dbOid, Oid relOid }
```

[verified-by-code] lines 54-59. Emitted by primary; standby
replays during recovery to grab AccessExclusiveLock to defer
queries that would conflict.

## Invariants

- INV-1: LOCKMODE integers are **on-disk** via `xl_standby_lock`
  and replication-protocol-visible. Renumbering breaks
  replication compatibility.
- INV-2: `NoLock = 0` is a sentinel, NOT a lock mode. APIs
  accepting LOCKMODE typically short-circuit on this value.

## Trust boundary (Phase D)

None — pure constants. Conflict matrix in lock.c is the trust
surface; this header just enumerates the modes.

## Cross-refs

- `knowledge/files/src/include/storage/lock.h.md` (existing) —
  the conflict matrix lives there
- `knowledge/files/src/include/storage/locktag.h.md`
- `knowledge/files/src/include/storage/lmgr.h.md`

## Issues

None.
