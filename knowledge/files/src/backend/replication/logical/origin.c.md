# `src/backend/replication/logical/origin.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** 1713
- **Source:** `source/src/backend/replication/logical/origin.c`

## Purpose

Replication-origin infrastructure: names a remote node so applied
transactions can be tagged with their source, and tracks per-origin
progress (`remote_lsn` → `local_lsn`) durably. Two-byte internal id
because origins are emitted into WAL on every replicated commit; max ~65k
nodes. [from-comment] (`origin.c:11-43`)

## Key insight

Storing `remote_lsn` in the local commit record lets us recover apply
progress precisely after crash recovery *without* requiring
synchronous_commit — apply can run async (good for throughput),
because the next startup will know exactly where to resume from each
origin. (`:28-37`) [from-comment]

## Shared memory: `ReplicationState[]`

Per-origin slot (`:111`): `roident`, `remote_lsn`, `local_lsn`,
`acquired_by` (proc number), `lsn_lock` (LWLock).

## Locking hierarchy

- Create/drop origin → exclusive lock on `pg_replication_origin`
  (catalog).
- Acquire/release in-memory slot → `ReplicationOrigin` LWLock (exclusive).
- Iterate slots → `ReplicationOrigin` LWLock (shared).
- Read/write a slot's remote_lsn/local_lsn → per-slot `lsn_lock`.
  LWLock not spinlock because we may hold it over an XLogInsert. (`:45-63`)
  [from-comment]

## Persistence

`CheckPointReplicationOrigin` writes
`pg_logical/replorigin_checkpoint` at every checkpoint;
`StartupReplicationOrigin` reads it. WAL-logged via `XLOG_REPLORIGIN_SET`
/ `XLOG_REPLORIGIN_DROP` (`origin.h:18-31`).

## Public API

`replorigin_create`, `replorigin_drop_by_name`, `replorigin_advance`,
`replorigin_get_progress`, plus a per-session variant
`replorigin_session_*` for backends doing apply work (the apply worker
uses this so progress is implicit in commits).

## Filter integration

Output plugins can install a `filter_by_origin_cb` (see
`output_plugin.h:96-97`) using the origin id of each change — used by
pgoutput to honor `publish_no_origin` and the special
`DoNotReplicateId = PG_UINT16_MAX` (`origin.h:34`) sentinel that
suppresses re-replication of changes originating from elsewhere.

## GUC

`max_active_replication_origins = 10` (`:106`).

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
- [subsystems/replication.md](../../../../../subsystems/replication.md)
- [idioms/replication-origin-tracking.md](../../../../../idioms/replication-origin-tracking.md)

