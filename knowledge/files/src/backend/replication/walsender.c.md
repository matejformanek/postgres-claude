# `src/backend/replication/walsender.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** 4616
- **Source:** `source/src/backend/replication/walsender.c`

## Purpose

The WAL-sender process: server side of streaming replication. One walsender
per connected receiver. Handles both physical streaming (raw WAL records
over COPY) and logical streaming (decoded changes via an output plugin).
Also runs `BASE_BACKUP`, `IDENTIFY_SYSTEM`, `CREATE/DROP/ALTER
REPLICATION_SLOT`, `TIMELINE_HISTORY`, `UPLOAD_MANIFEST`. Looks like a
backend (1:1 with connection) but parses a different command language.
[from-comment] (`walsender.c:1-48`)

## Top-of-file commentary

- Started by postmaster when a walreceiver connects in replication mode
  (`walsender.c:5-9`).
- `START_REPLICATION` enters COPY-both and streams WAL until either side
  ends COPY mode (`walsender.c:14-18`).
- Shutdown choreography is intricate: `PROCSIG_WALSND_INIT_STOPPING` from
  checkpointer drives walsender into `WALSNDSTATE_STOPPING` (rejects further
  commands); `SIGUSR2` from postmaster after the shutdown checkpoint tells
  it to stream the last bytes and exit. `wal_sender_shutdown_timeout` caps
  this wait. (`walsender.c:27-39`)

## Spine entry points

- `InitWalSender` (`:330`) — process initialization; marks `am_walsender`.
- `exec_replication_command` (`:2065`) — main dispatch from PostgresMain
  when a replication-mode connection runs a command. Parses with
  `replication_yyparse` (from `repl_gram.y` via the private cmd_context to
  survive xact boundaries — see `:2104-2126`), then dispatches by node tag
  to `IdentifySystem`, `StartReplication`, `StartLogicalReplication`,
  `CreateReplicationSlot`, `DropReplicationSlot`, `AlterReplicationSlot`,
  `SendBaseBackup`, `SendTimeLineHistory`, `UploadManifest`,
  `ReadReplicationSlot`, or `GetPGVariable` for `SHOW`. (`:2197-2297`)
- `StartReplication` (`:844`) — physical START. Allocates an `XLogReaderState`
  (`:851`), acquires a physical slot if requested, picks a timeline, sends
  `CopyBothResponse`, enters `WALSNDSTATE_CATCHUP`, calls `WalSndLoop(XLogSendPhysical)`.
  Notable: rejects starting from a logical slot here (`:874-878`).
- `StartLogicalReplication` (`:1492`) — logical START. Builds a
  `LogicalDecodingContext` via `CreateDecodingContext` and calls
  `WalSndLoop(XLogSendLogical)`.
- `WalSndLoop` (`:3008`) — the main service loop. Pattern: ResetLatch →
  CHECK_FOR_INTERRUPTS → reload config → ProcessRepliesIfAny → send_data() →
  pq_flush_if_writable → handle caught-up state transition → keepalive →
  WalSndWait. (`:3008-3148`)
- `XLogSendPhysical` (`:3322`) — physical send callback: reads WAL via
  pg_pread, builds a `WalDataMessageHeader`, ships over COPY. Honors
  `MAX_SEND_SIZE = XLOG_BLCKSZ * 16` = 128kB default (`:118`).
- `XLogSendLogical` (`:3632`) — logical send callback: drives
  `LogicalDecodingProcessRecord` on each decoded record; output is emitted
  via `WalSndPrepareWrite` (`:1585`) and `WalSndWriteData` (`:1612`).
- `WalSndWaitForWal` (`:1886`) — logical-side blocking wait until more WAL
  is flushed/available; coordinates with synchronized failover slots.
- `WalSndDone` (`:3770`) — final-byte drain at shutdown.

## Reply / feedback processing

- `ProcessRepliesIfAny` (`:2321`) — read CopyDone or 'r' / 'h' messages
  from receiver; dispatches to `ProcessStandbyReplyMessage`,
  `ProcessStandbyHSFeedbackMessage`, `ProcessStandbyPSRequestMessage`.
- `ProcessStandbyReplyMessage` (`:2505`) — updates
  `MyWalSnd->{write,flush,apply}`, lag measurements, and feeds
  `PhysicalConfirmReceivedLocation` (`:2472`) which advances a physical
  slot's `restart_lsn` and wakes synchronous waiters.
- `ProcessStandbyHSFeedbackMessage` (`:2693`) — Hot Standby feedback;
  updates the slot's xmin via `PhysicalReplicationSlotNewXmin`.

## Sync-rep coupling

Walsender uses `SyncRepInitConfig` and `SyncRepReleaseWaiters` from
`syncrep.c`. State transition from `WALSNDSTATE_CATCHUP` to
`WALSNDSTATE_STREAMING` is the moment sync-rep starts to account this
standby's flushes. (`:3070-3077`) [verified-by-code]

## Failover / logical-on-standby plumbing

- `PhysicalWakeupLogicalWalSnd` (`:1801`) — physical walsenders holding
  slots in `synchronized_standby_slots` ping logical walsenders when a
  standby confirms an LSN, so logical decoding doesn't get ahead of the
  failover guarantee. [verified-by-code]
- `NeedToWaitForStandbys` (`:1826`), `NeedToWaitForWal` (`:1858`) — gating
  predicates for logical decoding when failover slots are configured.

## GUCs / constants

- `max_wal_senders` (default 10), `wal_sender_timeout` (60s),
  `wal_sender_shutdown_timeout` (-1 = inherit), `log_replication_commands`,
  `MAX_SEND_SIZE = 128kB`, `WALSENDER_STATS_FLUSH_INTERVAL = 1000ms`.
  (`:107-156`)

## Shared-memory hooks

`WalSndShmemRequest`/`Init` (`:3965`, `:3979`) allocate `WalSndCtl`
(`WalSndCtlData`, see `walsender_private.h`). Each backend gets a per-slot
`InitWalSenderSlot` (`:3152`).

## Open questions

- The `cmd_context` reuse trick (`:2073-2126`) — why a single long-lived
  context rather than per-command. Comment explains, but verifying the
  cross-xact lifetime is non-obvious. [from-comment]

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
