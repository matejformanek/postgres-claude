# `storage/procarray.h`

- **Source:** `source/src/include/storage/procarray.h` (101 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** full-read

Public API for `storage/ipc/procarray.c`. See that file's doc for the
full mental model.

## API groups

- **Lifecycle**: `ProcArrayAdd` / `ProcArrayRemove` / `ProcArrayEndTransaction`
  / `ProcArrayClearTransaction`.
- **Recovery**: `ProcArrayInitRecovery`, `ProcArrayApplyRecoveryInfo`,
  `ProcArrayApplyXidAssignment`, the `KnownAssignedXids*` family
  (record / expire-tree / expire-all / expire-old / idle-maintenance).
- **Snapshot building**: `GetMaxSnapshotXidCount`,
  `GetMaxSnapshotSubxidCount`, `GetSnapshotData`,
  `ProcArrayInstallImportedXmin` / `ProcArrayInstallRestoredXmin`.
- **Running-xact bookkeeping**: `GetRunningTransactionData`,
  `TransactionIdIsInProgress`, `GetOldestNonRemovableTransactionId`,
  `GetOldestTransactionIdConsideredRunning`,
  `GetOldestActiveTransactionId`, `GetOldestSafeDecodingTransactionId`,
  `GetReplicationHorizons`.
- **Checkpoint VXID delays**: `GetVirtualXIDsDelayingChkpt` /
  `HaveVirtualXIDsDelayingChkpt`.
- **Lookup**: `ProcNumberGetProc`, `BackendPidGetProc`,
  `BackendPidGetProcWithLock`, `BackendXidGetPid`, `IsBackendPid`.
- **VXID enumeration**: `GetCurrentVirtualXIDs`,
  `GetConflictingVirtualXIDs`.
- **Recovery conflicts**: `SignalRecoveryConflict`,
  `SignalRecoveryConflictWithVirtualXID`,
  `SignalRecoveryConflictWithDatabase`.
- **Counts**: `MinimumActiveBackends`, `CountDBBackends`,
  `CountDBConnections`, `CountUserBackends`, `CountOtherDBBackends`,
  `TerminateOtherDBBackends`.
- **xid cache**: `XidCacheRemoveRunningXids`.
- **Replication slot xmin**: `ProcArraySetReplicationSlotXmin` /
  `ProcArrayGetReplicationSlotXmin`.

`PGPROC` itself is in `proc.h`. `KnownAssignedXids` operations are
pure functions over the shared array, callable from recovery code in
`xlogrecovery.c`.
