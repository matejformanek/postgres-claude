# `src/include/replication/*.h` — header reference

- **Last verified commit:** `ef6a95c7c64`

Group doc for the replication subsystem's public/internal headers. Each
is short; what matters is the type and lock-protocol surface they
expose.

## `walsender.h`

74 lines. Externs `am_walsender`, `am_cascading_walsender`,
`am_db_walsender`, `wake_wal_senders`, GUCs. Funcs: `InitWalSender`,
`exec_replication_command`, `WalSndErrorCleanup`,
`PhysicalWakeupLogicalWalSnd`, `GetStandbyFlushRecPtr`, `WalSndSignals`,
`WalSndWakeup`, `WalSndInitStopping`, `WalSndWaitStopping`,
`HandleWalSndInitStopping`, `WalSndRqstFileReload`. Inline
`WalSndWakeupProcessRequests` — fast path keyed on `wake_wal_senders`.
`CRSSnapshotAction` enum (CRS_EXPORT_SNAPSHOT / NOEXPORT / USE) for
CREATE_REPLICATION_SLOT.

## `walsender_private.h`

152 lines. Cross-file because parser/scanner code lives outside
walsender.c. `WalSndState` enum (STARTUP, BACKUP, CATCHUP, STREAMING,
STOPPING). `WalSnd` struct (per-walsender shmem): pid, state, sentPtr,
write/flush/apply LSNs and Lag tracking, sync_standby_priority, mutex,
replyTime, `ReplicationKind kind`. `WalSndCtlData`: `SyncRepQueue[3]`,
`lsn[3]`, `sync_standbys_status` flag byte (bits
SYNC_STANDBY_INIT/DEFINED), three CVs (`wal_flush_cv`, `wal_replay_cv`,
`wal_confirm_rcv_cv`) for synchronized failover slots, then
`walsnds[FLEXIBLE_ARRAY_MEMBER]`. Externs `MyWalSnd`, `WalSndCtl`.
Replication-grammar entrypoints (`replication_yyparse` etc.) also
declared here so `walsender.c` and the generated parser share them.

## `walreceiver.h`

Large (16K) — includes the libpqwalreceiver vtable. `WalRcvState` enum.
`WalRcvData` shmem struct (procno, pid, state, startTime, receiveStart,
receiveStartTLI, flushedUpto, receivedTLI, sender_host/port, conninfo,
slotname, mutex, walRcvStoppedCV, atomic writtenUpto). `WalReceiverConn`
opaque + `WalReceiverFunctionsType` vtable (the libpq adapter API). Also
the `MAXCONNINFO=1024` cap and `AllowCascadeReplication()` macro.

## `slot.h`

Big. `ReplicationSlotPersistency` (PERSISTENT/EPHEMERAL/TEMPORARY),
`ReplicationSlotInvalidationCause` bitmask enum (NONE/WAL_REMOVED/HORIZON/
WAL_LEVEL/IDLE_TIMEOUT, max 4), `SlotSyncSkipReason`,
`ReplicationSlotPersistentData` (name, db, persistency, xmin,
catalog_xmin, restart_lsn, confirmed_flush, two_phase fields, failover,
synced, plugin, invalidated, last_inactive). `ReplicationSlot` shmem
struct adds: `in_use`, `active_proc`, `mutex`, `active_cv`,
`effective_xmin`, `effective_catalog_xmin`, candidate fields for
two-phase persistence, `inactive_since`, `slotsync_skip_reason`.
`PG_REPLSLOT_DIR = "pg_replslot"`. Reserved-name constant
`CONFLICT_DETECTION_SLOT = "pg_conflict_detection"`.

## `slotsync.h`

44 lines. Exports `sync_replication_slots` GUC,
`SlotSyncShutdownPending` flag, `PrimaryConnInfo`/`PrimarySlotName`
GUCs. Functions: `ReplSlotSyncWorkerMain`, `ShutDownSlotSync`,
`SlotSyncWorkerCanRestart`, `IsSyncingReplicationSlots`,
`SyncReplicationSlots`, `HandleSlotSyncMessageInterrupt`,
`ProcessSlotSyncMessage`, `CheckAndGetDbnameFromConninfo`,
`ValidateSlotSyncParams`.

## `syncrep.h`

108 lines. Wait modes (-1/0/1/2), syncRepState (0/1/2), method
(PRIORITY=0, QUORUM=1), `SyncRepStandbyData` (snapshot of WalSnd state
returned by `SyncRepGetCandidateStandbys`), `SyncRepConfigData` (flat
GUC blob). Funcs: `SyncRepWaitForLSN`, `SyncRepCleanupAtProcExit`,
`SyncRepInitConfig`, `SyncRepReleaseWaiters`,
`SyncRepGetCandidateStandbys`, `SyncRepUpdateSyncStandbysDefined`. Plus
the grammar entrypoints (`syncrep_yyparse`...).

## `output_plugin.h`

251 lines. Defines `OutputPluginOutputType` (BINARY/TEXTUAL),
`OutputPluginOptions`, the `LogicalDecodeStartupCB`/`BeginCB`/`ChangeCB`/
`TruncateCB`/`CommitCB`/`MessageCB`/`FilterByOriginCB`/`ShutdownCB`/
`FilterPrepareCB`/`BeginPrepareCB`/`PrepareCB`/`CommitPreparedCB`/
`RollbackPreparedCB`/streaming-variants typedefs. `OutputPluginCallbacks`
struct — fill all that apply in `_PG_output_plugin_init`. Functions a
plugin calls: `OutputPluginPrepareWrite`, `OutputPluginWrite`,
`OutputPluginUpdateProgress`.

## `logical.h`

178 lines. `LogicalDecodingContext` — the central handle: memory ctx,
slot, reader/reorder/snapbuild, fast_forward flag, callbacks vtable,
options, output_plugin_options list, writer callbacks, output buffer,
plugin private data, `streaming`/`twophase`/`twophase_opt_given`,
accept_writes/prepared_write/write_location/write_xid, processing_required.
APIs: `CreateInitDecodingContext`, `CreateDecodingContext`,
`DecodingContextFindStartpoint`, `DecodingContextReady`,
`FreeDecodingContext`, `LogicalIncreaseXminForSlot`/`RestartDecodingForSlot`,
`LogicalConfirmReceivedLocation`. `LogicalDecodingLogLevel()` macro
(DEBUG1 for regular backends, LOG for background).

## `logicalproto.h`

Protocol versions 1..4 (`LOGICALREP_PROTO_*_VERSION_NUM`).
`LogicalRepMsgType` (B/C/O/I/U/D/T/R/Y/M and lowercase 2PC/streaming
variants). `LogicalRepTupleData` (col arrays + status bytes
n/u/t/b). `LogicalRepRelation` (remote relation description from 'R').

## `logicalrelation.h`

`LogicalRepRelMapEntry` (remoterel, localrelvalid, localreloid,
localrel, attrmap, updatable, localindexoid, state, statelsn). APIs:
`logicalrep_relmap_update`, `logicalrep_partmap_reset_relmap`,
`logicalrep_rel_open`/`_partition_open`/`_rel_close`,
`IsIndexUsableForReplicaIdentityFull`, `GetRelationIdentityOrPK`.

## `logicalworker.h`

`ApplyWorkerMain`, `ParallelApplyWorkerMain`, `TableSyncWorkerMain`,
`SequenceSyncWorkerMain`. `IsLogicalWorker`, `IsLogicalParallelApplyWorker`.
`HandleParallelApplyMessageInterrupt`, `ProcessParallelApplyMessages`.
`LogicalRepWorkersWakeupAtCommit`, `AtEOXact_LogicalRepWorkers`.
Externs the `ParallelApplyMessagePending` sigatomic flag.

## `logicallauncher.h`

Externs three GUCs (max_logical_replication_workers,
max_sync_workers_per_subscription,
max_parallel_apply_workers_per_subscription). APIs:
`ApplyLauncherRegister`, `ApplyLauncherMain`,
`ApplyLauncherForgetWorkerStartTime`, `ApplyLauncherWakeupAtCommit`,
`ApplyLauncherWakeup`, `AtEOXact_ApplyLauncher`,
`CreateConflictDetectionSlot`, `IsLogicalLauncher`,
`GetLeaderApplyWorkerPid`.

## `decode.h`

Tiny. `XLogRecordBuffer` wrapper. Per-rmgr decode entry points
(xlog_decode, xlog2_decode, heap_decode, heap2_decode, xact_decode,
standby_decode, logicalmsg_decode). `LogicalDecodingProcessRecord`. Also
declares `change_useless_for_repack` (from commands/repack_worker.c).

## `reorderbuffer.h`

Largest header (23K). Path constants (`pg_logical/`,
`pg_logical/mappings/`, `pg_logical/snapshots/`). GUCs
`logical_decoding_work_mem`, `debug_logical_replication_streaming`.
`ReorderBufferChangeType` enum (INSERT/UPDATE/DELETE/MESSAGE/INVALIDATION/
INTERNAL_SNAPSHOT/COMMAND_ID/TUPLECID/SPEC_INSERT/SPEC_CONFIRM/
SPEC_ABORT/TRUNCATE). Defines `ReorderBufferChange`, `ReorderBufferTXN`,
`ReorderBuffer` plus the rich set of public API functions and callback
typedefs the file installs into `ReorderBuffer`.

## `snapbuild.h`

101 lines. `SnapBuildState` (START=-1, BUILDING=0, FULL=1, CONSISTENT=2).
`AllocateSnapshotBuilder`, `FreeSnapshotBuilder`, `SnapBuildSnapDecRefcount`,
`InitialSnapshot`, `ExportSnapshot`/`ClearExported`/`ResetExportedState`,
`CurrentState`, `GetOrBuildSnapshot`, `XactNeedsSkip`, `GetTwoPhaseAt`/
`SetTwoPhaseAt`, `CommitTxn`, `ProcessChange`, `ProcessNewCid`,
`ProcessRunningXacts`, `SerializationPoint`, `SnapshotExists`,
`CheckPointSnapBuild`.

## `origin.h`

88 lines. `xl_replorigin_set`, `xl_replorigin_drop`. `XLOG_REPLORIGIN_SET=0x00`,
`XLOG_REPLORIGIN_DROP=0x10`. Sentinels `InvalidReplOriginId=0`,
`DoNotReplicateId=PG_UINT16_MAX`. `MAX_RONAME_LEN=512`.
`ReplOriginXactState` per-xact state. APIs split into name/lookup,
progress, session, per-xact, checkpoint/startup, WAL-logging groups.

## `conflict.h`

93 lines. `ConflictType` enum (8 values). `ConflictTupleInfo` (slot,
indexoid, xmin, origin, ts). APIs: `GetTupleTransactionInfo`,
`ReportApplyConflict`, `InitConflictIndexes`. Comment warns about
keeping stats enum in sync.

## `message.h`

43 lines. `xl_logical_message` wire record, `LogLogicalMessage()`,
`logicalmsg_redo/desc/identify`. `XLOG_LOGICAL_MESSAGE=0x00`.

## `pgoutput.h`

40 lines. `PGOutputData` state struct — three memory contexts, protocol
fields, options (binary/streaming/messages/two_phase/publish_no_origin).
