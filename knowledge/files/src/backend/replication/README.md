# `src/backend/replication/README`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** 76
- **Source:** `source/src/backend/replication/README`

## Purpose

Tour of two IPC stories: (a) walreceiver / libpqwalreceiver split (libpq
loaded as a dynamic module so the main server binary stays libpq-free), and
(b) postmaster's special handling of walsender processes at shutdown.
[from-README]

## Key facts

- **libpqwalreceiver loadable module.** The transport-specific part of the
  walreceiver (libpq calls) is `src/backend/replication/libpqwalreceiver/`.
  Loaded dynamically. API documented in
  `src/include/replication/walreceiver.h`. [from-README]
- **Walreceiver launch protocol.** Startup process sets
  `WalRcvData->conninfo`, `slotname`, `receiveStart`, then signals postmaster
  to fork the walreceiver. Walreceiver updates `WalRcvData->flushedUpto` as
  WAL hits disk and signals startup. [from-README]
- **Walsender shutdown ordering.** Postmaster does NOT wait for walsenders
  before checkpoint; instead it treats them like `pgarch` and signals them
  at `PM_WAIT_XLOG_ARCHIVAL`, after regular backends die and after the
  shutdown checkpoint is written. Reason: we want standbys to receive the
  shutdown checkpoint record. [from-README]
- **am-I-a-walsender signaling.** Postmaster can't know at fork time
  whether a child is a walsender — that's negotiated in the handshake. The
  walsender therefore marks itself in the `PMSignal` array once it knows.
  [from-README]
- **WalSnd shared array.** Each walsender takes one entry in `WalSndCtl` for
  monitoring (statistics views). [from-README]
- **Protocol details deferred.** "See manual" — the
  walsender↔walreceiver protocol is documented in the user manual, not the
  README.

## Pointers

- libpqwalreceiver: `src/backend/replication/libpqwalreceiver/`
- walreceiver impl: `src/backend/replication/walreceiver.c`
- walsender impl: `src/backend/replication/walsender.c`
- shared-mem ctl: `WalRcvData` and `WalSndCtl` (`walsender_private.h`)
