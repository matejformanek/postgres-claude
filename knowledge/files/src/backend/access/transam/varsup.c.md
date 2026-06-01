# varsup.c

- **Source path:** `source/src/backend/access/transam/varsup.c`
- **Lines:** 704
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `source/src/include/access/transam.h`, `clog.c`,
  `commit_ts.c`, `subtrans.c`, `procarray.c` (storage/ipc).

## Purpose

Postgres OID and XID counter management. Allocates new XIDs
(`GetNewTransactionId`), advances the wraparound limits, and allocates
new OIDs (`GetNewObjectId`). [from-comment] `varsup.c:3-5`.

## Top-of-file comment (verbatim)

```
varsup.c
   postgres OID & XID variables support routines
```
[from-comment] `varsup.c:3-4`.

## Public surface

- `GetNewTransactionId(bool isSubXact)` — `varsup.c:68` [verified-by-code]
- `ReadNextFullTransactionId(void)` — `varsup.c:283` [verified-by-code]
- `AdvanceNextFullTransactionIdPastXid(TransactionId xid)` — `varsup.c:299`
  [verified-by-code]
- `AdvanceOldestClogXid(TransactionId oldest_datfrozenxid)` — `varsup.c:350`
  [verified-by-code]
- `SetTransactionIdLimit(TransactionId oldest_datfrozenxid, Oid oldest_datoid)` —
  `varsup.c:367` [verified-by-code]
- `ForceTransactionIdLimitUpdate(void)` — `varsup.c:516` [verified-by-code]
- `GetNewObjectId(void)` — `varsup.c:554` [verified-by-code]
- `SetNextObjectId(Oid nextOid)` — `varsup.c:622` [verified-by-code]
- `StopGeneratingPinnedObjectIds(void)` — `varsup.c:651` [verified-by-code]
- `AssertTransactionIdInAllowableRange(TransactionId xid)` — `varsup.c:672`
  [verified-by-code]
- `VarsupShmemRequest(void *arg)` — `varsup.c:47` [verified-by-code]

## Key types / structs

- `TransamVariables` (declared in `access/transam.h`) — the shared
  `VariableCacheData` structure with `nextXid`, `oldestXid`,
  `xidVacLimit`, `xidWarnLimit`, `xidStopLimit`, `xidWrapLimit`,
  `oldestXidDB`, `nextOid`, `oidCount`. [verified-by-code]
  `varsup.c:98, 114, 199-209, 555-625`.

## Key invariants and locking

1. **`XidGenLock` (exclusive) protects XID allocation.**
   `GetNewTransactionId` takes it exclusive (`varsup.c:96`); the lock is
   held across `ExtendCLOG`, `ExtendCommitTs`, `ExtendSUBTRANS`, the
   `nextXid` advance, and the store into `ProcGlobal->xids[]`.
   [verified-by-code] `varsup.c:96-274`.

2. **Store-into-ProcArray-before-release.** "We must store the new XID
   into the shared ProcArray before releasing XidGenLock. This ensures
   that every active XID older than `latestCompletedXid` is present in
   the ProcArray." `LWLockRelease` provides the release barrier.
   [from-comment] [verified-by-code] `varsup.c:211-254, 274`.

3. **CLOG must be extended before nextXid advances.** "Now advance the
   nextXid counter. This must not happen until after we have
   successfully completed ExtendCLOG()." [from-comment]
   `varsup.c:203-209`.

4. **Subxid overflow flag.** If `PGPROC_MAX_CACHED_SUBXIDS` exceeded,
   set `overflowed = true` on both `MyProc->subxidStatus` and
   `ProcGlobal->subxidStates[]`; readers must consult `pg_subtrans`.
   [from-comment] [verified-by-code] `varsup.c:264-272`.

5. **Three-tier wraparound defense.** Past `xidVacLimit` → trigger
   autovacuum; past `xidWarnLimit` → warn; past `xidStopLimit` → refuse
   new XIDs (unless single-user). [from-comment] [verified-by-code]
   `varsup.c:102-188`.

6. **Single-user escape hatch.** `IsUnderPostmaster` gate on stop-error
   allows DBA to assign XIDs in standalone mode. [verified-by-code]
   `varsup.c:138-158`.

7. **No XID assignment in parallel mode or recovery.** Both error out.
   [verified-by-code] `varsup.c:77-94`.

8. **`pg_write_barrier()` between subxid count increment and array
   write** so concurrent readers don't see `count = N+1` with an
   uninitialized slot. [from-comment] `varsup.c:264-268`. Cross-ref
   `storage/lmgr/README.barrier`.

## Functions of note

### `GetNewTransactionId` — `varsup.c:68-277` [verified-by-code]

The single XID-allocation chokepoint. Path:

1. Reject parallel mode / recovery / bootstrap-mode shortcut.
2. `LWLockAcquire(XidGenLock, LW_EXCLUSIVE)`.
3. Read `nextXid` (FullTransactionId).
4. Wraparound check (autovac signal / warning / stop).
5. `ExtendCLOG(xid); ExtendCommitTs(xid); ExtendSUBTRANS(xid)` —
   pre-zero the new SLRU pages while still holding the lock.
6. `FullTransactionIdAdvance(&TransamVariables->nextXid)`.
7. Store into `MyProc->xid` and `ProcGlobal->xids[MyProc->pgxactoff]`
   (top XID) or append to subxid cache (subxact, with possible overflow
   flag).
8. `LWLockRelease(XidGenLock)`.

### `SetTransactionIdLimit` — `varsup.c:367-515` [verified-by-code]

Called after vacuum finishes a database-wide pass. Updates `oldestXid`,
recomputes `xidVacLimit`, `xidWarnLimit`, `xidStopLimit`, `xidWrapLimit`
based on safe margins (≈ 3M / 11M / 1M / `MaxTransactionId/2` constants;
not deep-read here). Signals autovacuum if `xidVacLimit` passes us.
[unverified] (margins not re-derived)

### `GetNewObjectId` — `varsup.c:554-621` [verified-by-code]

Sequential OID generator with `OidGenLock`; skips through the "system"
range below `FirstNormalObjectId`; refills `oidCount` from the shared
counter in chunks of `VAR_OID_PREFETCH = 8192` (read in code; not
re-derived).

## Cross-references

- `xact.c:AssignTransactionId` is the primary caller (`xact.c:637`).
- `clog.c:ExtendCLOG`, `commit_ts.c:ExtendCommitTs`,
  `subtrans.c:ExtendSUBTRANS` are called from inside the XidGenLock
  critical section.
- `procarray.c` is the consumer of the `ProcGlobal->xids[]` store; see
  the README's "Interlocking Transaction Begin/End and Snapshots".
- Autovacuum (`postmaster/autovacuum.c`) receives the
  `PMSIGNAL_START_AUTOVAC_LAUNCHER` signal here.

## Open questions

- Exact safety margins computed by `SetTransactionIdLimit` (the 3M/11M
  constants) not deep-read. [unverified]
- `GetNewObjectId`'s collision-avoidance against on-disk relfilenodes
  (mentioned in README §"Filesystem Actions": "we check for on-disk
  collisions when allocating new relfilenumber OIDs") — implementation
  not located here. [unverified]

## Confidence tag tally

- `[verified-by-code]`: 16
- `[from-comment]`: 6
- `[unverified]`: 2
