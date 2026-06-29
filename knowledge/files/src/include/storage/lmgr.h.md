# `src/include/storage/lmgr.h`

- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
- **Lines:** 127

## Role

**Heavy-weight lock manager public API.** Wraps the generic
`LockAcquire/Release` machinery in `storage/lock.h` with
typed helpers for the standard locktag kinds (relation, page,
tuple, transaction, vxid, speculative-insert, object, advisory,
apply-transaction).

Cross-link: `knowledge/subsystems/storage-lmgr.md`.

## Public API (selected)

- **Relation locks**: `LockRelation`, `LockRelationOid`,
  `LockRelationId`, `ConditionalLockRelation*`, `UnlockRelation*`,
  `CheckRelationLockedByMe`, `LockHasWaitersRelation`,
  `LockRelationIdForSession`
- **Relation extension**: `LockRelationForExtension`,
  `RelationExtensionLockWaiterCount` — used to serialize fork
  growth
- **Page locks** (currently indexes only): `LockPage`,
  `ConditionalLockPage`, `UnlockPage`
- **Tuple locks** (see heap_lock_tuple before using):
  `LockTuple`, `ConditionalLockTuple` (with `logLockFailure`
  flag for failure-event auditing), `UnlockTuple`
- **Xact locks**: `XactLockTableInsert/Delete/Wait`,
  `ConditionalXactLockTableWait`
- **VXID/locker-wait**: `WaitForLockers`,
  `WaitForLockersMultiple`
- **Speculative insertion**: `SpeculativeInsertionLockAcquire`,
  `SpeculativeInsertionLockRelease`, `SpeculativeInsertionWait`
  (PG INSERT ... ON CONFLICT plumbing)
- **Object locks**: `LockDatabaseObject`, `LockSharedObject`,
  `LockSharedObjectForSession`
- **Logical replication apply**: `LockApplyTransactionForSession`
  / `UnlockApplyTransactionForSession`
- **Diagnostics**: `DescribeLockTag(StringInfo, *LOCKTAG)`,
  `GetLockNameFromTagType`
- **XLTW_Oper enum** (lines 23-35) — `XactLockTableWait` reason
  for `pg_locks`/wait-event reporting:
  `XLTW_None/Update/Delete/Lock/LockUpdated/InsertIndex/
  InsertIndexUnique/FetchUpdated/RecheckExclusionConstr`.

## Invariants

- INV-1: tuple-lock APIs (`LockTuple`) must be used in
  coordination with `heap_lock_tuple` — the comment on line 73
  is a warning shot: SQL `SELECT FOR UPDATE` semantics live in
  the tuple-lock + heap interaction.
- INV-2: `*ForSession` variants persist across xact boundaries —
  used for `LOCK TABLE ... NOWAIT` from session-level scripts and
  for replication apply.
- INV-3: `ConditionalLockTuple(... logLockFailure=true)` emits a
  wait-event/log entry on failure — used to support deadlock
  postmortems.
- INV-4: relation-extension lock is a single per-relation
  bottleneck; the `RelationExtensionLockWaiterCount` API exists
  to let callers (heap_multi_insert, etc.) decide whether to
  amortise across multiple blocks.

## Trust boundary (Phase D)

- All Lmgr operations are operating on locktags ultimately
  derived from catalog OIDs or block/offset numbers; user input
  reaches this API only through the SQL layer (`LOCK TABLE`,
  `SELECT FOR UPDATE`, etc.) which validates ACLs first.
- Advisory locks (`USER_LOCKMETHOD`) are user-controlled int64
  keys with no ACL — already a known SQL-visible primitive
  (`pg_advisory_lock`); the API itself trusts callers.
- **Lock-monitoring exposure** (`pg_locks` view, `pg_log_locks`)
  is a Phase-D oracle: an unprivileged role can read other
  sessions' lock holdings, which leaks information about
  schema (relation OIDs being locked) and activity. Already
  addressed by view-level filters but worth noting.
- `DescribeLockTag(StringInfo, …)` uses `appendStringInfo` —
  bridges to the A13/A14 stringinfo injection cluster via
  `pg_locks` text rendering. Inputs are catalog-validated, so
  not directly exploitable.

## Cross-refs

- `knowledge/subsystems/storage-lmgr.md` — primary doc
- `knowledge/files/src/include/storage/lock.h.md` (existing) —
  generic `LockAcquire`
- `knowledge/files/src/include/storage/locktag.h.md`
- `knowledge/files/src/include/storage/lockdefs.h.md`

## Issues

- ISSUE-PHASE-D: `pg_locks` exposes per-tuple LOCKTAG info to
  unprivileged users; covered by A11/A14 monitoring-as-oracle
  cluster. (Informational.)

## Synthesized by
<!-- backlinks:auto -->
- [idioms/relation-extension-lock.md](../../../../idioms/relation-extension-lock.md)
