# src/include/replication/walsender.h

## Purpose

Public surface of the **walsender** backend variant: GUCs, mode flags
(physical/logical/cascading/db), entry points called from postmaster
and `PostgresMain`, plus the WalSnd wakeup primitive.

## Role in PG

A walsender is a regular backend (forked per connection) that runs the
replication protocol instead of normal SQL. It is selected at connect
time by the libpq option `replication=true|database`. Physical
walsenders ship raw WAL; logical walsenders decode WAL into protocol
messages via the reorderbuffer + output plugin. Cascading walsenders
serve a downstream standby from this node's received WAL. See
`knowledge/subsystems/replication.md`.

## Key types/struct fields

- `CRSSnapshotAction` enum (lines 20-25) — what to do with the snapshot
  on `CREATE_REPLICATION_SLOT`: EXPORT (to use via `SET TRANSACTION
  SNAPSHOT`), NOEXPORT, or USE (consume in current xact). Mirrors the
  `CREATE_REPLICATION_SLOT ... { EXPORT_SNAPSHOT | NOEXPORT_SNAPSHOT |
  USE_SNAPSHOT }` syntax. [verified-by-code]

- Process-mode globals (lines 28-31):
  - `am_walsender` — am I a walsender backend at all?
  - `am_cascading_walsender` — am I serving WAL I myself received as a
    standby? (Sets stricter WAL-availability rules.)
  - `am_db_walsender` — am I a logical-replication walsender bound to a
    database? (vs physical, which has no DB.)
  - `wake_wal_senders` — request flag set by other backends (commit,
    flush), consumed by `WalSndWakeupProcessRequests()`.
  [verified-by-code]

- GUCs (lines 34-37): `max_wal_senders`, `wal_sender_timeout`,
  `wal_sender_shutdown_timeout`, `log_replication_commands`.
  [verified-by-code]

- Entry points (lines 39-49) — `InitWalSender`, `exec_replication_command`
  (the main command-loop dispatch called from `PostgresMain` when the
  conn is replication), `WalSndErrorCleanup`, `GetStandbyFlushRecPtr`
  (for cascading), `WalSndSignals`, `WalSndWakeup(physical, logical)`,
  `WalSndInitStopping`/`WalSndWaitStopping` (graceful shutdown handshake
  during smart/fast postmaster shutdown), `WalSndRqstFileReload`.
  [verified-by-code]

- `WalSndWakeupRequest()` macro (lines 57-58) — sets `wake_wal_senders=true`.
  Comment (lines 52-55) explains the split: the actual wakeup is
  deferred because the writeout path that knows new WAL exists is
  holding contended locks (typically WAL insertion lock), and the
  wakeup itself takes locks (SyncRepLock, latch sets). So mark-now,
  wake-later. [verified-by-code]

- `WalSndWakeupProcessRequests()` static inline (lines 63-72) — called
  at a safe point (no contended locks held) to drain the request. Cheap
  fast-path when `wake_wal_senders` is false. [verified-by-code]

## Phase D notes

**REPLICATION-role auth boundary.** The walsender backend runs as a
user with the `REPLICATION` attribute (or superuser). Logical walsenders
additionally need `CONNECT` on the specific DB. Once connected, the
walsender executes replication commands (`START_REPLICATION`,
`CREATE_REPLICATION_SLOT`, `READ_REPLICATION_SLOT`, etc.) — not SQL.
The header doesn't gate this; auth happens in `PostgresMain`'s
walsender branch and in `exec_replication_command` per command. The
trust boundary worth tracking: any backend connected with
`replication=true` can read WAL, which includes data from ALL databases
on the cluster regardless of `CONNECT` privileges on individual DBs.
That is the documented design (physical replication is cluster-wide),
but it means a single compromised replication user exfiltrates the
whole cluster's WAL stream. [inferred]

**Logical-decoding privilege check.** A logical walsender opens a slot.
Slot creation requires REPLICATION (and DB-CONNECT for the slot's DB);
slot consumption inherits the slot's role. Mismatch between slot owner
and connected role is checked at slot acquisition, not in this header.
[unverified — see `slot.h` for the actual check]

**Wakeup leak channel.** `wake_wal_senders` is a single global bool,
not per-walsender. Any backend's commit/flush wakes ALL walsenders to
re-scan. A spammy committer thus generates many context switches in
walsenders. Not a security issue; performance only. [inferred]

## Potential issues

- [ISSUE-trust-boundary: replication-role connection reads WAL for ALL
  databases regardless of per-DB CONNECT privilege (documented but
  worth flagging in security review of multi-tenant clusters) (maybe)]
- [ISSUE-undocumented-invariant: `am_db_walsender` vs `am_walsender` vs
  `am_cascading_walsender` are three independent booleans; the
  legal combinations are not enumerated in the header — must read
  `WalSndInit` paths to know (low)]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `include-replication`](../../../../issues/include-replication.md)
<!-- issues:auto:end -->
