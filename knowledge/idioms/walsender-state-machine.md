# Walsender state machine — STARTUP → CATCHUP → STREAMING

The walsender process is the **primary-side** counterpart to
the walreceiver — it serves WAL to standbys + logical-decoding
subscribers. Each connected receiver gets its own walsender
process. Each one runs a 5-state machine: STARTUP → CATCHUP →
STREAMING, with BACKUP and STOPPING as side states. Knowing
the current state diagnoses "why is replication lagging"
faster than any other probe.

Anchors:
- `source/src/include/replication/walsender_private.h:24-31`
  — `WalSndState` enum [verified-by-code]
- `source/src/backend/replication/walsender.c` —
  implementation
- `knowledge/idioms/wal-receiver-loop.md` — companion
  receiver side
- `knowledge/idioms/replication-slot-advance.md` — companion
  slot mechanics

## The 5 states

```c
typedef enum WalSndState
{
    WALSNDSTATE_STARTUP = 0,
    WALSNDSTATE_BACKUP,
    WALSNDSTATE_CATCHUP,
    WALSNDSTATE_STREAMING,
    WALSNDSTATE_STOPPING,
} WalSndState;
```

[verified-by-code `walsender_private.h:24-31`]

Visible to operators via `pg_stat_replication.state`:

| State | Meaning |
|---|---|
| `STARTUP` | Walsender process is initializing |
| `BACKUP` | Serving a base backup (pg_basebackup) |
| `CATCHUP` | Streaming WAL but behind the leader's current LSN |
| `STREAMING` | Streaming WAL at the leading edge |
| `STOPPING` | Shutting down |

## STARTUP

The initial state. The walsender:

1. Accepts the connection from a receiver.
2. Performs the replication handshake (timeline, identify
   system, slot attach).
3. Negotiates start position.

Brief (< 1 second normally). If a walsender hangs in
STARTUP, the connection is broken or the receiver isn't
responding to the handshake.

Transitions to BACKUP if the receiver requested
`pg_basebackup`, or to CATCHUP for ordinary streaming.

## BACKUP

A walsender serving a base backup. Different from CATCHUP /
STREAMING because it's reading the FILESYSTEM (not the WAL
stream) — pg_basebackup needs a copy of the data directory.

Streams the data files + a starting WAL segment. Exits when
the backup is complete.

`pg_stat_replication.state = 'backup'` indicates a
pg_basebackup or pg_receivewal session is in progress.

## CATCHUP

The "behind but streaming" state. The receiver has connected
but is far enough behind that the walsender is reading WAL
from `pg_wal/` segments (possibly from a slot's retained
WAL) rather than the latest writes.

Operationally interesting: a connection in CATCHUP for hours
means the receiver fell substantially behind. Either:
- The receiver / network is slow.
- The primary is producing WAL faster than the network
  can ship.
- The receiver was offline and is now catching up since
  reconnecting.

Transitions to STREAMING once the receiver has caught up to
the current insert LSN.

## STREAMING

The "caught up" state. The walsender pushes new WAL records
as they're generated. The receiver-flush feedback drives
slot advance.

This is the normal steady-state for a healthy replica.
`pg_stat_replication.state = 'streaming'` is what you want
to see for every replica.

## STOPPING

Shutdown in progress. The walsender:

1. Sends a final feedback message to the receiver.
2. Closes the connection.
3. Exits.

Brief; transitions to process exit immediately.

## State transitions

```
                  STARTUP
                   /    \
              BACKUP   CATCHUP
                 |        |
              (exit)   STREAMING
                          |
                      STOPPING
                          |
                      (exit)
```

`BACKUP` is a terminal-style branch (doesn't go back to
streaming once done; pg_basebackup connections are short-lived).

## The connection types

Walsenders serve multiple consumer types:

- **Physical replication** — standby's walreceiver.
- **Logical replication** — subscriber's tablesync /
  apply worker.
- **pg_basebackup** — backup utility.
- **pg_receivewal** — WAL-shipping utility.

The state machine is the same; the message protocol differs
(physical = raw WAL; logical = decoded changes).

## State diagnostics

Per the operator's playbook:

| Symptom | State |
|---|---|
| `state = 'startup'` for > 5 seconds | Handshake failure — check network + auth |
| `state = 'catchup'` for hours | Receiver fell behind; check `replay_lag` |
| `state = 'streaming'` | Healthy — `replay_lag` should be small |
| `state = 'backup'` | pg_basebackup in progress |
| (No row in pg_stat_replication) | Receiver disconnected; check primary's `pg_replication_slots` for the slot's state |

## The replication-lag metrics

`pg_stat_replication` exposes:

- **`sent_lsn`** — how far the walsender has sent.
- **`write_lsn`** — receiver has acknowledged the byte write.
- **`flush_lsn`** — receiver has fsync'd.
- **`replay_lsn`** — standby has applied (for hot-standby
  queries).

Lag = current_lsn - replay_lsn. A growing lag while
`state = 'streaming'` indicates the standby is slow at
**applying** (not receiving) — typically because read
queries hold conflicting locks.

`max_standby_streaming_delay` / `max_standby_archive_delay`
control when the standby cancels conflicting queries to
catch up.

## The wal_sender_timeout

A walsender that doesn't send anything for
`wal_sender_timeout` (default 60s) considers the receiver
gone and exits. Useful for kicking out hung receivers.
Receivers must send keepalives at least this often.

## Common review-time concerns

- **Don't add work to the walsender main loop.** It's the
  cluster's WAL-ship bottleneck. New features should defer
  to other processes.
- **State transitions are observable.** A new state
  added/renamed must update `pg_stat_replication` view.
- **Per-walsender state is in shared memory** — `MyWalSnd`
  pointer. Changes need locking via `WalSndCtl->ss_mutex`.
- **STOPPING → exit is one-way.** A walsender can't go back
  to STREAMING after STOPPING.

## Invariants

- **[INV-1]** The state machine has 5 well-defined states;
  no other values.
- **[INV-2]** Per-walsender state in shared memory; LWLock
  protected.
- **[INV-3]** State visible to operators via
  `pg_stat_replication.state`.
- **[INV-4]** `wal_sender_timeout` enforces keepalive
  protocol.
- **[INV-5]** STOPPING is terminal — no return to streaming.

## Useful greps

- All state transitions:
  `grep -RIn 'WalSndSetState\|WALSNDSTATE_' source/src/backend/replication | head -15`
- The state-observation view:
  `grep -n 'pg_stat_get_wal_senders' source/src/backend/replication/walsender.c`
- The keepalive logic:
  `grep -n 'wal_sender_timeout\|XLogSendKeepalive' source/src/backend/replication/walsender.c`

## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/replication/walsender.c`](../files/src/backend/replication/walsender.c.md) | — | implementation |
| [`src/include/replication/walsender_private.h`](../files/src/include/replication/walsender_private.h.md) | 24 | WalSndState enum |
| [`src/include/replication/walsender_private.h`](../files/src/include/replication/walsender_private.h.md) | — | state enum + per-walsender struct |

<!-- /callsites:auto -->

## Scenarios that use me
<!-- scenarios:auto -->

*Auto-derived from direct references + transitive file-overlap.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

- [`add-new-guc`](../scenarios/add-new-guc.md)
- [`add-new-protocol-message`](../scenarios/add-new-protocol-message.md)
- [`add-new-replication-message`](../scenarios/add-new-replication-message.md)

<!-- /scenarios:auto -->
## Cross-references

- `knowledge/idioms/wal-receiver-loop.md` — companion;
  receiver side.
- `knowledge/idioms/replication-slot-advance.md` —
  companion; slots track walsender's served position.
- `knowledge/idioms/wal-record-construction.md` — what the
  walsender ships.
- `knowledge/subsystems/replication.md` — replication
  subsystem at large.
- `.claude/skills/wal-and-xlog/SKILL.md` — WAL + replication
  skill.
- `source/src/include/replication/walsender_private.h` —
  state enum + per-walsender struct.
- `source/src/backend/replication/walsender.c` —
  implementation.
