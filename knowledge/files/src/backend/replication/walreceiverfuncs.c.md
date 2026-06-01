# `src/backend/replication/walreceiverfuncs.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** 436
- **Source:** `source/src/backend/replication/walreceiverfuncs.c`

## Purpose

Functions used by the **startup process** (and a few other backends) to
communicate with the walreceiver: launch it, check its state, hand it a
start LSN/timeline/slot, read its progress. The walreceiver itself lives
in `walreceiver.c`; this file is the side that calls *into* it.
[from-comment] (`walreceiverfuncs.c:4-8`)

## Shared memory

`WalRcv` (`WalRcvData *`) — single struct registered via `ShmemCallbacks`
(`:41-44`). `WalRcvShmemRequest` sizes it; `WalRcvShmemInit` zeroes it,
sets `walRcvState = WALRCV_STOPPED`, inits the condition variable
`walRcvStoppedCV` and the spinlock. Atomic `writtenUpto` is also init'd.
(`:54-72`)

## Public surface (callable by startup / backends)

- `WalRcvRunning` (`:76`) — true if state is anything but STOPPED.
- `WalRcvStreaming` — true when STREAMING or CATCHUP.
- `RequestXLogStreaming` — startup sets `receiveStart/TLI/conninfo/slot`,
  flips state to STARTING, posts `PMSIGNAL_START_WALRECEIVER`.
- `ShutdownWalRcv` — request stop, wait on `walRcvStoppedCV`.
- `GetWalRcvFlushRecPtr` — read the high-water mark of replicated WAL.
- `GetWalRcvWriteRecPtr` — atomic read of `writtenUpto`.

## Coupling

- `walRcvState` flows: STOPPED → STARTING → CONNECTING → STREAMING (or
  WAITING) → RESTARTING → STOPPING → STOPPED. Defined in
  `replication/walreceiver.h:42-55`.
- `procno` reset to `INVALID_PROC_NUMBER` until walreceiver attaches.

## Constants

`WALRCV_STARTUP_TIMEOUT = 10` seconds (`:50`).

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
