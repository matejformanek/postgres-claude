# `src/backend/replication/walreceiver.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** 1573
- **Source:** `source/src/backend/replication/walreceiver.c`

## Purpose

The WAL-receiver auxiliary process on the standby. Connects to the primary
via the libpqwalreceiver dynamic module, receives WAL records over COPY,
writes/fsyncs them into `pg_wal`, and publishes the high-water mark in
`WalRcv->flushedUpto` for the startup process to replay against.
[from-comment] (`walreceiver.c:1-49`)

## Top-of-file notes

- Started by postmaster on request from startup process (which has stuffed
  conninfo/slot/start position into `WalRcvData`). [from-comment]
- Cannot directly read GUCs related to its primary connection — startup
  process passes them down via shared memory. [from-comment]
- If primary ends the stream without disconnecting, walreceiver enters
  WAITING; startup may re-nudge it rather than respawning. [from-comment]
- libpq-specific code lives in `libpqwalreceiver/`. This file is
  transport-agnostic. (`walreceiver.c:38-40`) [from-comment]

## Wakeup-reason enum

`WalRcvWakeupReason` (lines ~120-128) drives the periodic send-status /
write / flush events; loop selects on a latch with multiple deadlines.

## Static state

- `recvFile`, `recvFileTLI`, `recvSegNo` — current open segment.
- `LogstreamResult.{Write,Flush}` — locally-written/flushed byte positions
  used in feedback messages.
- `wrconn` — libpqwalreceiver connection handle.
- `WalReceiverFunctions` — vtable filled in by the loaded module.

## Key responsibilities

1. Connect (calls into `wrconn->walrcv_connect` etc.).
2. Identify primary's system id / timeline; verify it matches local
   cluster.
3. Issue `START_REPLICATION` with the start LSN/slot.
4. Loop: `walrcv_receive` → `XLogWalRcvWrite` → periodic `XLogWalRcvFlush`
   → `XLogWalRcvSendReply` / `XLogWalRcvSendHSFeedback`.
5. Update `WalRcv->flushedUpto` so startup can replay; wake startup latch.

## Interactions

- Reads/writes `WalRcv` shared struct (see `walreceiverfuncs.c`).
- Calls into `xlog.c` / `xlogarchive.c` to land segments in `pg_wal`.
- Loads `libpqwalreceiver.so` once via `load_external_function` (in
  `libpqwalreceiver/`). [unverified — exact call path]

## Open questions

- Exact reconnection / restart heuristics when the primary stream ends but
  the connection stays up (the README mentions WAITING state but the
  state-machine details want a closer read of `WalReceiverMain`).
  [unverified]
