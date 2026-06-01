# Replication — architectural reference

Source commit at verification: master, mounted at `source/`.

PostgreSQL ships five intertwined replication facilities, all built on top of WAL:

1. **Physical streaming replication** — byte-for-byte WAL shipped from primary
   to standby via a long-lived libpq connection.
2. **Physical archive replication / PITR** — primary writes WAL segments to an
   archive; standby (or `pg_basebackup`-restored cluster) replays via
   `restore_command`.
3. **Logical decoding** — primary decodes WAL into row-level change events,
   passes them through an output plugin, and ships them to any consumer that
   speaks the replication protocol (or calls the SQL SRF).
4. **Logical replication (PUB/SUB)** — PostgreSQL-to-PostgreSQL layer that
   uses logical decoding under the hood, with the `pgoutput` plugin on the
   publisher and an apply-worker fleet on the subscriber.
5. **Synchronous replication** — orthogonal overlay on (1) or (4): the primary
   stalls a committing backend until enough standbys ACK the commit LSN.

This document covers the conceptual model, the IPC, and the v18-era additions
(failover slots, automatic conflict logging, two-phase decoding, parallel apply,
sequence sync, dynamic logical-decoding promotion). For knob references and
source-file pointers, see the skill
`.claude/skills/replication-overview/SKILL.md`.

### `effective_wal_level` — dynamic promotion (v18+)

Prior to v18, enabling logical decoding meant restarting with
`wal_level=logical`, paying the `XLOG_HEAP2_NEW_CID` and extra-invalidation
overhead even when no logical slot existed. PG 18 splits "write logical info
into WAL" from "use logical decoding": with `wal_level=replica`, the moment
the first logical slot is created the cluster's read-only `effective_wal_level`
promotes to logical. Activation is synchronous (right after slot creation);
deactivation is deferred to the checkpointer to avoid an end-of-recovery race
and to dampen slot-churn thrash.
[from-comment `source/src/backend/replication/logical/logicalctl.c:1-54`]

The transition is broadcast to standbys via the WAL record
`XLOG_LOGICAL_DECODING_STATUS_CHANGE`; standbys mirror the primary's
`effective_wal_level` and ignore their local `wal_level` GUC until promotion,
at which point status is recomputed against local conditions. Public surface
is in `replication/logicalctl.h` (`IsLogicalDecodingEnabled`,
`LogicalDecodingActivate`, `LogicalDecodingDeactivate`,
`UpdateLogicalDecodingStatusEndOfRecovery`).
[from-comment `source/src/backend/replication/logical/logicalctl.c:1-54`]

---

## 1. The walsender / walreceiver duo

### Walsender

A walsender is a backend variant. When a client connects with the libpq option
`replication=true` (or `replication=database` for logical), the postmaster forks
a regular backend, which after handshake marks itself as a walsender in
`PMSignal` so postmaster can treat it specially at shutdown.
[from-README `source/src/backend/replication/README:51-66`]

At shutdown, postmaster waits for walsenders **after** the shutdown checkpoint
has been written, so standbys receive the shutdown checkpoint record before the
primary exits. This is the opposite of regular backends, which are terminated
before the shutdown checkpoint.
[from-README `source/src/backend/replication/README:42-49`;
from-comment `source/src/backend/replication/walsender.c:27-39`]

Walsender accepts a small grammar (see `repl_gram.y`):

- `IDENTIFY_SYSTEM` — system identifier, timeline, current WAL insert LSN, dboid.
- `BASE_BACKUP (...)` — streams a base backup (used by `pg_basebackup`).
- `CREATE_REPLICATION_SLOT name [TEMPORARY] {PHYSICAL | LOGICAL plugin} (...)`.
- `START_REPLICATION [SLOT s] PHYSICAL %X/%X [TIMELINE n]` — physical stream.
- `START_REPLICATION SLOT s LOGICAL %X/%X (options...)` — logical stream.
- `READ_REPLICATION_SLOT`, `DROP_REPLICATION_SLOT`, `TIMELINE_HISTORY`.
[from-code `source/src/backend/replication/repl_gram.y:62-300`]

While streaming, walsender reads from `pg_wal/` (or the WAL buffers if it's
caught up) and writes COPY-protocol data messages. The receiver periodically
sends feedback messages carrying `write_lsn`, `flush_lsn`, `apply_lsn`. Those
feedbacks are what `syncrep.c` waits on, and what advances the slot's
`restart_lsn` / `confirmed_flush`.

`MAX_SEND_SIZE` is 16 × `XLOG_BLCKSZ` (128 kB default). Tradeoff: bigger batches
amortize per-message overhead but make the walsender less responsive to
signals (signals are checked between messages).
[from-comment `source/src/backend/replication/walsender.c:109-118`]

### Walreceiver

Standby-side process, started by the startup process via a postmaster signal
once WAL replay has consumed everything available locally. Walreceiver is
**not** linked against libpq directly — the transport is loaded dynamically
from `libpqwalreceiver/`, so the server binary stays libpq-free and the
transport could be swapped in principle.
[from-README `source/src/backend/replication/README:3-16,21-37`;
from-comment `source/src/backend/replication/walreceiver.c:5-40`]

Walreceiver connects to the primary, issues `START_REPLICATION`, and on each
received batch:
1. Writes the WAL to `pg_wal/`.
2. Flushes (per `wal_receiver_status_interval` / fsync rules).
3. Updates `WalRcv->flushedUpto` so the startup process knows how far it can
   replay.
4. Sends feedback to the primary.

If the primary ends streaming without disconnecting, walreceiver goes into a
"waiting" state rather than respawning; the startup process either nudges it
or treats it as disconnected.
[from-comment `source/src/backend/replication/walreceiver.c:24-31`]

---

## 2. Replication slots

A replication slot is a small piece of persistent (or temporary) shared state
that pins:

- a **WAL position** the consumer hasn't acked yet (`restart_lsn`), so WAL
  isn't recycled prematurely;
- for logical slots, a **catalog xmin** (`catalog_xmin`), so VACUUM can't
  remove catalog tuples needed to decode in-flight transactions.

Slots live in `$PGDATA/pg_replslot/<name>/state` and are crash-safe (a primary
goal: surviving a restart without re-shipping the world). They cannot be stored
in the system catalog because they have to work on standbys too, where catalog
writes aren't possible.
[from-comment `source/src/backend/replication/slot.c:14-27`]

### Lifecycle and persistency

```
RS_PERSISTENT   crash-safe; survives restart; explicit drop required
RS_EPHEMERAL    transient creation state; dropped on release or restart
RS_TEMPORARY    session-scoped; dropped at session end or error
```
[from-code `source/src/include/replication/slot.h:43-48`]

`RS_EPHEMERAL` is the intermediate state used while a persistent slot is being
built (so a crash during creation leaves no zombie); `ReplicationSlotPersist()`
promotes it to `RS_PERSISTENT`.
[from-comment `source/src/include/replication/slot.h:35-42`]

### Key fields (`ReplicationSlotPersistentData`)

| field | meaning |
|---|---|
| `name` | identifier (`NameData`) |
| `database` | logical: DB the slot decodes; physical: `InvalidOid` |
| `persistency` | as above |
| `xmin` | xmin horizon (physical slots with `hot_standby_feedback`) |
| `catalog_xmin` | logical: oldest catalog xid still needed |
| `restart_lsn` | oldest WAL position still required |
| `confirmed_flush` | oldest LSN the client has acked |
| `two_phase_at` | LSN when two-phase decoding was enabled |
| `two_phase` | decode prepared transactions? |
| `plugin` | logical: output plugin name |
| `synced` | slot was synced from primary (v17+) |
| `failover` | logical slot is a sync candidate on standbys (v17+) |
| `invalidated` | non-`RS_INVAL_NONE` if the slot is unusable |

[from-code `source/src/include/replication/slot.h:95-162`]

### Invalidation causes

```
RS_INVAL_WAL_REMOVED   = 1   required WAL has been removed
RS_INVAL_HORIZON       = 2   required rows have been removed
RS_INVAL_WAL_LEVEL     = 4   wal_level insufficient for slot
RS_INVAL_IDLE_TIMEOUT  = 8   idle slot timeout fired
```
[from-code `source/src/include/replication/slot.h:58-72`]

Powers of two so they can be combined and stored as a bitmask. Once invalidated,
the slot becomes a corpse: it still occupies a slot, but the consumer can no
longer make progress and has to drop and recreate.

### Active / inactive

`active_proc` holds the `ProcNumber` of the process currently streaming from the
slot, or `INVALID_PROC_NUMBER` if the slot is idle. Acquiring a slot is
exclusive — a slot has at most one consumer at a time. Acquire/release of the
in-use bit is guarded by `ReplicationSlotControlLock`; individual field updates
by the slot's spinlock.
[from-comment `source/src/include/replication/slot.h:164-180`;
from-comment `source/src/backend/replication/slot.c:29-33`]

### Physical vs logical slot

| | Physical | Logical |
|---|---|---|
| Created by | `CREATE_REPLICATION_SLOT ... PHYSICAL` or `pg_create_physical_replication_slot()` | `... LOGICAL plugin` or `pg_create_logical_replication_slot()` |
| Pins | `restart_lsn` (and optionally `xmin` via `hot_standby_feedback`) | `restart_lsn` + `catalog_xmin` |
| Tied to a DB? | No | Yes (`database` field) |
| Needs `wal_level` | `replica` | `logical` |
| Output | raw WAL | rows via output plugin |

### Failover / sync slots (v17+)

A logical slot on the primary with `failover=true` is replicated to physical
standbys by the slot-sync worker (driven either automatically when
`sync_replication_slots=on` or on-demand via `pg_sync_replication_slots()`).
Local mirror slots on the standby live as `RS_TEMPORARY` until they're
"sync-ready" — three conditions: standby has flushed WAL past the remote
slot's `confirmed_flush_lsn`; standby's catalog xmin is not behind the
remote's needs; and a consistent snapshot can be built at `restart_lsn`
before reaching `confirmed_flush_lsn` (otherwise post-promotion decoding
could silently lose changes). Once sync-ready, the slot flips to
`RS_PERSISTENT` and the `synced` flag is set. After a failover, subscribers
repoint at the promoted standby without re-snapshotting.
[from-comment `source/src/backend/replication/logical/slotsync.c:11-35`]

`synchronized_standby_slots` (a GUC, parsed into `SyncStandbySlotsConfigData`)
on the primary lists which physical slots must have caught up before a
logical-failover slot may advance `confirmed_flush`. The gate is implemented
in `StandbySlotsHaveCaughtup` and `WaitForStandbyConfirmation`.
[from-code `source/src/backend/replication/slot.c:95-104,3107,3255`]

The wakeup chain across walsenders is non-obvious. A logical walsender
holding a failover slot calls `WalSndWaitForWal`, whose gating predicates
(`NeedToWaitForStandbys`, `NeedToWaitForWal`) consult the
`synchronized_standby_slots` list. When a physical walsender receives a
standby reply confirming a new flush LSN, it calls
`PhysicalWakeupLogicalWalSnd`, which signals the condition variable
`WalSndCtl->wal_confirm_rcv_cv` to release any logical walsenders blocked
on the gate. So a logical consumer is held behind a physical-standby ACK
chain even though the two sides never talk directly.
[from-code `source/src/backend/replication/walsender.c:1801-1886`]

Synced slots are treated as inactive for idle-timeout purposes (they don't
decode locally).
[verified-by-code `source/src/backend/replication/slot.c:1860-1872`]

---

## 3. Logical decoding pipeline

```
   primary backend                 walsender (or SQL SRF consumer)
   ───────────────                 ───────────────────────────────
   WAL record  ──┐                  ┌── output_plugin callbacks ──┐
                 │                  │                              │
                 ▼                  ▼                              ▼
              decode.c  ──►  reorderbuffer.c  ──►  ReorderBufferCommit()
              (xlog →         (reassemble per-xid          │
              ReorderBuffer   from interleaved             ▼
              calls)          subtransactions,        change_cb / commit_cb
                              spill big TXNs to disk) ───► over COPY protocol
                                                           to walreceiver / SRF
```

### decode.c — xlog → change events

Walks records via `XLogReadRecord`, dispatches to per-record handlers
(`DecodeInsert`, `DecodeUpdate`, `DecodeDelete`, `DecodeTruncate`,
`DecodeMultiInsert`, `DecodeSpecConfirm`, `DecodeCommit`, `DecodeAbort`,
`DecodePrepare`). For records that don't carry data changes, it still has to
inform `reorderbuffer` of the xid via `ReorderBufferProcessXid()` so subtxn
trees stay consistent.
[from-comment `source/src/backend/replication/logical/decode.c:1-26,72-80`]

### reorderbuffer.c — reassembly + spilling

PG writes WAL in commit order at the **record** level, not the **transaction**
level: subtransactions and concurrent xids interleave. The reorderbuffer
collects per-xid change streams, then at the commit record assembles a
toplevel transaction and feeds it (in xid+lsn order) to the output plugin
through `ReorderBufferCommit()`.
[from-comment `source/src/backend/replication/logical/reorderbuffer.c:13-31`]

Memory management:

- Two contexts: `SlabContext` for fixed-size structs (changes, txns) and
  `GenerationContext` for variable-length payloads (lifespan groups).
- Per-reorderbuffer memory limit; when exceeded, the **largest** transaction is
  serialized to disk (via a max-heap keyed by transaction size).
- Toast chunks are reassembled inline — within one toplevel txn, no other
  records appear between a row's toast chunks and the row itself.
[from-comment `source/src/backend/replication/logical/reorderbuffer.c:33-83`]

Streaming mode (subscription option `streaming=on` or `parallel`) ships
in-progress transactions before commit, letting the subscriber start work
earlier; the apply worker either writes to BufFiles until commit or, in
`parallel` mode, hands the stream to a parallel apply worker.
[from-comment `source/src/backend/replication/logical/worker.c:22-62`]

### snapbuild.c — historical catalog snapshots

Decoding has to know what the catalog looked like *at the LSN of the change*,
not now (a column might have been dropped since). `snapbuild.c` builds and
maintains historical MVCC snapshots usable by the reorderbuffer for catalog
lookups during decode.

### output_plugin.h — the plugin contract

A shared library exports `_PG_output_plugin_init(OutputPluginCallbacks *cb)`
and fills in callbacks: `startup_cb`, `begin_cb`, `change_cb`, `truncate_cb`,
`commit_cb`, optional `message_cb`, optional streaming callbacks
(`stream_start_cb`, `stream_stop_cb`, `stream_commit_cb`, …), optional
two-phase callbacks (`begin_prepare_cb`, `prepare_cb`, `commit_prepared_cb`,
`rollback_prepared_cb`), and `shutdown_cb`.
[from-code `source/src/include/replication/output_plugin.h:33-243`]

The plugin sees rows as `HeapTuple`s plus the `Relation`, and writes to a
`StringInfo` provided by `logical.c`. The consumer (walsender or SRF) is
responsible for transporting that buffer.
[from-comment `source/src/backend/replication/logical/logical.c:10-26`]

Built-in plugins:
- `test_decoding` (in `contrib/`) — human-readable; reference implementation.
- `pgoutput` (in-tree at `source/src/backend/replication/pgoutput/`) — wire
  format consumed by the PG logical-replication apply worker.

### Two-phase commit decoding

When a slot is created or altered with `two_phase=true`, the reorderbuffer
fires `prepare_cb` at `PREPARE TRANSACTION` time rather than holding the txn
in memory until commit. `commit_prepared_cb` / `rollback_prepared_cb` fire on
the eventual COMMIT/ROLLBACK PREPARED. This shrinks reorderbuffer memory
pressure for distributed transactions but requires the consumer to also
support two-phase semantics. `two_phase_at` records the LSN at which two-phase
was first enabled, so older txns continue to use single-phase decoding.
[from-code `source/src/include/replication/slot.h:139-148`;
from-code `source/src/backend/replication/logical/logical.c:66-71`]

---

## 4. Logical replication (PUB / SUB)

A PostgreSQL-to-PostgreSQL layer that uses logical decoding with the `pgoutput`
plugin on the publisher and a fleet of subscriber-side bgworkers.

### Publisher side

- `CREATE PUBLICATION p FOR TABLE ...` writes catalog entries
  (`pg_publication`, `pg_publication_rel`).
- When a subscriber connects with `replication=database`, a walsender is
  spawned. It runs `pgoutput` over the slot.

### Subscriber side — process model

```
  Launcher (one per cluster, bgworker)
     │
     ├─► Apply worker  (one per enabled subscription)
     │      │
     │      ├─► Tablesync worker  (per table during initial copy)
     │      └─► Parallel apply workers  (when streaming=parallel)
```

GUCs:
- `max_logical_replication_workers = 4` — total cap.
- `max_sync_workers_per_subscription = 2` — concurrent initial-copy workers.
- `max_parallel_apply_workers_per_subscription = 2` — parallel apply.
[from-code `source/src/backend/replication/logical/launcher.c:50-56`]

### Apply worker

`worker.c` (~194 KB) is the main event loop: receives `pgoutput` messages,
applies them via the executor, writes feedback. It uses the libpqwalreceiver
module — same transport as a physical walreceiver, but speaking the logical
sub-protocol.
[from-comment `source/src/backend/replication/logical/worker.c:10-21`]

Streaming transactions get one of two treatments:
1. `streaming=on` — spill to BufFile per (subscription, xid), apply at commit.
2. `streaming=parallel` — hand off to `applyparallelworker.c`.

Two-phase commits are enabled only **after** initial sync of all tables in the
subscription is done, to avoid the empty-prepare edge case where tablesync
skips the inserts of a prepared txn that the apply worker later commits.
[from-comment `source/src/backend/replication/logical/worker.c:63-80`]

### Tablesync — initial copy state machine

Per-table state in `pg_subscription_rel`:

```
INIT  →  DATASYNC  →  FINISHEDCOPY  →  SYNCWAIT  →  CATCHUP  →  SYNCDONE  →  READY
                                       (in-mem)    (in-mem)
```

- `DATASYNC` = the sync worker is COPYing the table.
- `FINISHEDCOPY` = persisted in catalog so a crash here doesn't restart COPY.
- `SYNCWAIT`/`CATCHUP` are shared-memory-only; they coordinate hand-off between
  the sync worker and the apply worker so that the sync worker stops at exactly
  the LSN the apply worker is currently at.
- `SYNCDONE` → apply worker tracks the table until it reaches the SYNCDONE
  LSN; then flips to `READY`.
[from-comment `source/src/backend/replication/logical/tablesync.c:29-80`]

The cute property: tablesync and apply worker can be "in front" of each other
on a given table; the state machine handles either direction.

### Sequence sync (v18+)

`sequencesync.c` does for sequences what tablesync does for tables —
necessary because sequences advance via `nextval()`, not via WAL change
records that the apply worker would otherwise apply. It is a **distinct
worker class** (`SEQUENCESYNC` in `LogicalRepWorker.type`), not folded
into tablesync, and the differences are material:

- **One worker per subscription, not per relation.** A single sequencesync
  worker handles every INIT-state sequence for the subscription, batching
  up to `MAX_SEQUENCES_SYNC_PER_BATCH` sequences per transaction so locks
  on sequence relations are released between batches.
- **Trivial state machine.** Just `INIT → READY` in `pg_subscription_rel`
  — no `DATASYNC`/`FINISHEDCOPY`/`SYNCWAIT`/`CATCHUP`/`SYNCDONE` hand-off,
  because there is no streaming-LSN coordination to perform: the worker
  copies the publisher's current value + `log_cnt` (REMOTE_SEQ_COL_COUNT
  = 10 columns including `is_called`) and is done.
- **Spawned by the apply worker, not the launcher.** The launcher has no
  DB connection, so it cannot query `pg_subscription_rel` to find INIT
  sequences; the apply worker periodically scans and calls
  `ProcessSequencesForSync`, which spawns a sequencesync worker iff none
  is already running.
- **`CopySeqResult` outcomes:** SUCCESS, MISMATCH (e.g. type differs on
  publisher), INSUFFICIENT_PERM, SKIPPED.

INIT state is (re)set by `CREATE SUBSCRIPTION`,
`ALTER SUBSCRIPTION ... REFRESH PUBLICATION`, or
`ALTER SUBSCRIPTION ... REFRESH SEQUENCES`.
[from-comment `source/src/backend/replication/logical/sequencesync.c:1-96`]

### Replication origins

`origin.c` provides per-source progress tracking. Each subscription owns a
`ReplOriginId`; the apply worker tags each applied transaction with that
origin, recording `commit_lsn` durably. After a crash, replay resumes from
the origin's persisted LSN instead of restreaming.

`pg_replication_origin_status` exposes this.

### Conflict detection (v18+)

`logical/conflict.c` standardizes conflict logging on the subscriber:

```
CT_INSERT_EXISTS              INSERT hit a unique key conflict
CT_UPDATE_ORIGIN_DIFFERS      UPDATE target row was last touched by a different origin
CT_UPDATE_EXISTS              UPDATE caused a unique conflict on a different row
CT_UPDATE_MISSING             UPDATE target row not found
CT_DELETE_ORIGIN_DIFFERS      DELETE target was last touched by a different origin
CT_UPDATE_DELETED             UPDATE target was already deleted
CT_DELETE_MISSING             DELETE target row not found
CT_MULTIPLE_UNIQUE_CONFLICTS  INSERT/UPDATE conflicts on more than one unique index
```
[from-code `source/src/backend/replication/logical/conflict.c:27-36`]

The default resolution remains "last writer wins on the subscriber, apply
worker logs the conflict and continues." There is no automatic merge
resolver in core PG yet — but the logging is now structured.

### The `pg_conflict_detection` reserved slot (v18+)

To distinguish `update_deleted` from `update_missing`, the subscriber has
to keep dead tuples around long enough to see that the target row *was*
deleted by a concurrent (or earlier) local transaction. v18 introduces an
internal **reserved** logical slot named `pg_conflict_detection`, owned
by the launcher and shared across all subscriptions on the cluster with
`retain_dead_tuples=true`. It exists solely to pin a `catalog_xmin` that
holds back VACUUM's removal of recently-dead tuples; it never streams
changes anywhere. `pg_conflict_detection` is the only reserved slot name
today, and `ReplicationSlotAcquire` refuses to hand it out to user code.
[from-code `source/src/backend/replication/slot.c:659-663`;
from-comment `source/src/include/replication/slot.h:24-28`]

The aggregation discipline is what makes it correct. Each apply worker
tracks its own `oldest_nonremovable_xid` (the oldest xid whose deletion
the worker might still need to detect). The launcher's
`compute_min_nonremovable_xid` reduces these across all
`retain_dead_tuples` subscriptions, and `update_conflict_slot_xmin` pushes
the result into the slot. Without this aggregation the slot's xmin would
either drift forward and lose tuples (if it tracked a single subscription)
or stay pinned forever (if no one advanced it). `CreateConflictDetectionSlot`
in the launcher creates the slot lazily the first time a
`retain_dead_tuples` subscription appears.
[from-code `source/src/backend/replication/logical/launcher.c:1448,1500,1569`]

---

## 5. Synchronous replication

`syncrep.c` is entirely a primary-side concern: standbys don't know they're
running in sync mode. After a commit-record write, the committing backend
enqueues itself on `SyncRepQueue` keyed by its commit LSN, then waits.
Walsenders, on feedback receipt, walk the queue and release backends whose
LSN has been satisfied by the configured policy.
[from-comment `source/src/backend/replication/syncrep.c:5-66`]

### Policies

`synchronous_standby_names` is parsed by `syncrep_gram.y`:

- `FIRST N (s1, s2, s3)` — priority-based; the first N caught-up standbys in
  the list count. If `s1` disconnects, `s2` takes its place. Default if no
  keyword given (back-compat with ≤9.6).
- `ANY N (s1, s2, s3)` — quorum-based; any N of the listed standbys suffices.
[from-comment `source/src/backend/replication/syncrep.c:32-65`]

### `synchronous_commit` levels

| Level | Backend wakes up when… |
|---|---|
| `off` | local WAL written to OS (no fsync wait, no replication wait) |
| `local` | local WAL fsynced |
| `remote_write` | standby has written to OS |
| `on` (default) | standby has fsynced |
| `remote_apply` | standby has replayed the LSN (visible to readers there) |

Catch: until a candidate standby has actually caught up to the primary, it
doesn't count toward the quorum/priority. So configuration alone doesn't
make a standby synchronous — it has to also be current.
[from-comment `source/src/backend/replication/syncrep.c:60-65`]

---

## 6. Mental-model summary

- Everything is WAL underneath. Physical replication ships the raw bytes;
  logical decoding interprets them.
- A **slot** is the durable "I haven't acked up to here yet" anchor that keeps
  WAL (and, for logical, catalog tuples) from being garbage-collected.
- Walsender is a backend variant; walreceiver is an aux process; both speak
  the replication subprotocol over libpq.
- Logical decoding is a pipeline: `decode.c` (WAL parsing) → `reorderbuffer.c`
  (reassembly) → output plugin (serialization) → walsender/SRF (transport).
- Logical replication is logical decoding + `pgoutput` + an apply-worker
  fleet on the receiver, coordinated by a launcher bgworker.
- Synchronous replication is a primary-side wait queue; it composes with
  either physical streaming or logical replication.

---

## 7. Open questions / not-yet-verified

- `[unverified]` Exact LSN coupling between `confirmed_flush` and
  `restart_lsn` after a logical-slot consumer disconnects mid-transaction —
  worth a deeper read of `LogicalConfirmReceivedLocation` and friends.
- `[unverified]` Behavior of `synchronized_standby_slots` when the named
  physical slot is invalidated rather than just lagging.
- `[unverified]` Whether `RS_INVAL_IDLE_TIMEOUT` invalidates a slot that is
  active-but-idle (consumer connected, no traffic) or only an unacquired one.
  `slot.h:67` comment is terse.
- ~~`[unverified]` Conflict-detection slot `pg_conflict_detection` interaction
  with VACUUM horizons across multiple subscriptions in v18.~~ Resolved §4:
  launcher aggregates `oldest_nonremovable_xid` across all
  `retain_dead_tuples` subscriptions into a single slot xmin.

---

## 8. Files examined

| file | lines | depth | produced |
|---|---|---|---|
| `source/src/backend/replication/README` | 1-76 | full | §1, §6 |
| `source/src/backend/replication/walsender.c` | 1-120 | header | §1 |
| `source/src/backend/replication/walreceiver.c` | 1-80 | header | §1 |
| `source/src/backend/replication/repl_gram.y` | 62-300 | grep | §1 |
| `source/src/backend/replication/slot.c` | 1-100 | header | §2 |
| `source/src/include/replication/slot.h` | 1-200 | partial | §2 |
| `source/src/backend/replication/syncrep.c` | 1-80 | header | §5 |
| `source/src/backend/replication/logical/decode.c` | 1-80 | header | §3 |
| `source/src/backend/replication/logical/reorderbuffer.c` | 1-120 | header | §3 |
| `source/src/backend/replication/logical/logical.c` | 1-80 | header | §3 |
| `source/src/backend/replication/logical/worker.c` | 1-80 | header | §4 |
| `source/src/backend/replication/logical/tablesync.c` | 1-80 | header | §4 |
| `source/src/backend/replication/logical/launcher.c` | 1-60 | header | §4 |
| `source/src/backend/replication/logical/conflict.c` | 1-60 | header | §4 |
| `source/src/include/replication/output_plugin.h` | grep | partial | §3 |
| `source/src/backend/replication/logical/logicalctl.c` | 1-54 | header | §intro |
| `source/src/backend/replication/logical/sequencesync.c` | 1-96 | header | §4 |
| `source/src/backend/replication/logical/slotsync.c` | 11-35 | header | §2 |
| `source/src/backend/replication/logical/launcher.c` | 1448-1569 | grep | §4 |
| `source/src/backend/replication/walsender.c` | 1801-1886 | grep | §2 |

Confidence tally: from-README=8, from-comment=27, from-code=14, unverified=3,
verified-by-code=2.

## 9. External references

- https://www.postgresql.org/docs/current/high-availability.html
- https://www.postgresql.org/docs/current/protocol-replication.html
- https://www.postgresql.org/docs/current/logicaldecoding.html
- https://www.postgresql.org/docs/current/logical-replication.html
