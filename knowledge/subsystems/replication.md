# Subsystem: replication

## Owners (as of 2026-06-12)

- **Top committers (last 24mo):** Amit Kapila (87), Peter Eisentraut (39), Fujii Masao (34), Michael Paquier (33)
- **Top reviewers (last 24mo):** Amit Kapila (107), Chao Li (44), Masahiko Sawada (32), Hayato Kuroda (30)
- **Recent landmark commits (12mo):**
  - `d87d07b7ad3 (Masahiko Sawada, 2025-06-16): Fix re-distributing previously distributed invalidation messages during logical decoding.`
  - `64bf53dd61e (Noah Misch, 2025-12-15): Revisit cosmetics of "For inplace update, send nontransactional invalidations."`
  - `883a95646a8 (Fujii Masao, 2025-10-22): Fix stalled lag columns in pg_stat_replication when replay LSN stops advancing.`

See `knowledge/personas/domain-ownership.md` for the cross-subsystem index, methodology, and committer/reviewer affinity clusters.

---


- **Paths:** `source/src/backend/replication/` (+ `logical/`, `pgoutput/`,
  `libpqwalreceiver/` subdirs), `source/src/include/replication/`
- **Verified against commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
  (2026-06-01 refresh anchor)
- **Confidence:** verified=28, from-README=4, from-comment=39, inferred=2,
  unverified=4 (Open Questions §9)
- **Primary README:** `source/src/backend/replication/README` (76 lines —
  small; covers walreceiver/libpqwalreceiver split + walsender shutdown
  ordering only. Logical-replication design lives in file headers.)

## 1. Purpose

The replication subsystem implements three layered services:

1. **Physical streaming replication** — primary ships WAL bytes to standbys
   via walsender↔walreceiver over libpq. Backbone of HA + read replicas +
   `pg_basebackup`. [from-comment] `walsender.c:1-48`.
2. **Synchronous replication** — primary backends wait for standby
   acknowledgment of commit LSN before returning. FIRST n / ANY n
   quorum. [from-comment] `syncrep.c:1-26`.
3. **Logical replication** — WAL is decoded into row-level changes via an
   output plugin, streamed to subscribers that apply through the executor.
   Subscriptions = publications + apply workers + per-table tablesync.
   [from-comment] `logical.c:10-25`.

**Replication slots** (`slot.c`) are the crash-safe state object underneath
all three: they pin WAL retention + catalog xmin horizon so a consumer
that goes away briefly doesn't lose its position. Physical slots reserve
WAL; logical slots additionally reserve catalog xmin (for historic
snapshots) and a startpoint LSN.

**The four PG18-era additions** that make this synthesis larger than it
otherwise would be:

- **Failover slots** (PG 17+, `slotsync.c`) — logical slots that primary
  replicates onto its physical standbys so promotion preserves logical
  subscriptions.
- **Conflict detection** (PG 18, `conflict.c` + the internal
  `pg_conflict_detection` slot) — surfaces what last-write-wins
  replication is masking.
- **Retain dead tuples** (PG 18, in `worker.c`) — apply worker maintains
  `oldest_nonremovable_xid` so vacuum can't reclaim versions needed for
  `update_deleted` / `*_origin_differs` conflict detection.
- **Sequence sync** (PG 18, `sequencesync.c`) — initial sync of sequences
  alongside tables, so subscribers start at correct nextval.

The subsystem totals ~120 KB of `.h` + ~470 KB of `.c` across 30+ files.
This synthesis distills the 28 per-file docs under
`knowledge/files/src/backend/replication/{,logical/}` plus the consolidated
header doc under `knowledge/files/src/include/replication/headers.md`.

## 2. Key files

### `replication/` (top level — physical + slot + transport)

| File | Role | Per-file doc |
|---|---|---|
| `README` | 76 lines — walreceiver split + walsender shutdown ordering | [via `README.md`] |
| `walsender.c` (4616 lines) | Server-side replication process. Physical + logical streaming + admin commands (`IDENTIFY_SYSTEM`, `BASE_BACKUP`, slot mgmt) | [via `walsender.c.md`] |
| `walreceiver.c` (1573 lines) | Standby-side WAL receiver auxiliary process | [via `walreceiver.c.md`] |
| `walreceiverfuncs.c` | `WalRcv` shmem accessors used by startup + walreceiver | [via `walreceiverfuncs.c.md`] |
| `slot.c` (3291 lines) | Replication-slot lifecycle, persistence, invalidation, failover-slot integration | [via `slot.c.md`] |
| `slotfuncs.c` | SQL-callable wrappers (`pg_create_*_replication_slot`, `pg_drop_replication_slot`) | [via `slotfuncs.c.md`] |
| `syncrep.c` (1150 lines) | Synchronous-replication wait/release on the primary | [via `syncrep.c.md`] |
| `repl_gram.y`, `repl_scanner.l` | Replication-command grammar | [via per-file docs] |
| `syncrep_gram.y` | `synchronous_standby_names` parser | [via per-file doc] |
| `libpqwalreceiver/` (subdir) | Dynamically loaded libpq adapter — the only libpq dependency the main server binary has | (covered by README) |

### `replication/logical/` (decoding + apply)

| File | Role | Per-file doc |
|---|---|---|
| `logical.c` (2220 lines) | `LogicalDecodingContext` lifecycle + output-plugin callback wrappers + plugin loading | [via `logical.c.md`] |
| `logicalctl.c` | Enable/disable logical decoding at runtime | [via `logicalctl.c.md`] |
| `logicalfuncs.c` | SRF-style logical decoding via SQL (`pg_logical_slot_get_changes`) | [via `logicalfuncs.c.md`] |
| `decode.c` (1346 lines) | Per-WAL-record decoder; dispatches by `rm_decode` | [via `decode.c.md`] |
| `snapbuild.c` (2080 lines) | Historic-catalog snapshot builder — 4-state machine driven by `xl_running_xacts` | [via `snapbuild.c.md`] |
| `reorderbuffer.c` (5643 lines, **largest file**) | Per-xid change buffer; spill to disk; k-way merge on commit LSN; toast reassembly; invalidation overflow | [via `reorderbuffer.c.md`] |
| `worker.c` (6435 lines, **largest in subsystem**) | Apply worker: receive logicalrep messages, apply DML through executor, coordinate tablesync + parallel-apply + retain-dead-tuples | [via `worker.c.md`] |
| `tablesync.c` (1715 lines) | Per-table initial-sync worker; 7-state machine | [via `tablesync.c.md`] |
| `applyparallelworker.c` (1658 lines) | Parallel apply over shm_mq; lmgr-visible deadlock prevention | [via `applyparallelworker.c.md`] |
| `launcher.c` (1721 lines) | Logical-replication launcher bgworker — spawns apply / tablesync / parallel-apply / sequencesync workers | [via `launcher.c.md`] |
| `origin.c` (1713 lines) | Replication-origin infrastructure — 2-byte id, durable progress per origin via `replorigin_checkpoint` | [via `origin.c.md`] |
| `conflict.c` (651 lines, PG 18) | 8 conflict types + `ReportApplyConflict` + arbiter-index setup | [via `conflict.c.md`] |
| `slotsync.c` (2099 lines, PG 17+) | Failover-slot synchronization to physical standbys | [via `slotsync.c.md`] |
| `relation.c` | Subscriber-side `LogicalRepRelMap` (publisher→local rel mapping incl. attrmap) | [via `relation.c.md`] |
| `proto.c` | `logicalrep` wire-protocol read/write helpers | [via `proto.c.md`] |
| `message.c` | `pg_logical_emit_message` + decoder side | [via `message.c.md`] |
| `sequencesync.c` (PG 18) | Initial sequence sync alongside table sync | [via `sequencesync.c.md`] |
| `syncutils.c` | Shared helpers between tablesync + sequencesync | [via `syncutils.c.md`] |

### `replication/pgoutput/`

`pgoutput.c` — built-in output plugin used by logical replication
subscribers. Honors publication filters, column lists, row filters,
`publish_via_partition_root`, `publish_no_origin`.

### Headers — `src/include/replication/`

Covered in the omnibus [via `headers.md`]. The load-bearing ones:
`walsender.h`, `walsender_private.h`, `walreceiver.h`, `slot.h`,
`slotsync.h`, `syncrep.h`, `logical.h`, `output_plugin.h`,
`reorderbuffer.h`, `snapbuild.h`, `decode.h`, `worker_internal.h`,
`logicalproto.h`, `origin.h`, `conflict.h`, `message.h`.

## 3. Key data structures

### `WalSnd` (per-walsender, in `WalSndCtl->walsnds[]`)

`walsender_private.h`. Per-walsender shmem: `pid`, `state` (`WalSndState`:
STARTUP/BACKUP/CATCHUP/STREAMING/STOPPING), `sentPtr`, `write`/`flush`/
`apply` LSNs + lag tracking, `sync_standby_priority`, `mutex`,
`replyTime`, `ReplicationKind kind`. `MyWalSnd` is per-process pointer.

### `WalSndCtl` (singleton in shmem)

`walsender_private.h`. `SyncRepQueue[3]` (one dlist per sync mode),
`lsn[3]` (sync-confirmed LSN per mode), `sync_standbys_status` flag byte
(`SYNC_STANDBY_INIT`/`DEFINED`), three CVs (`wal_flush_cv`,
`wal_replay_cv`, `wal_confirm_rcv_cv`) for synchronized failover slots,
flexible-array tail `walsnds[]`.

### `WalRcvData` (singleton in shmem)

`walreceiver.h`. Procno, pid, `WalRcvState`, `startTime`, `receiveStart`,
`receiveStartTLI`, `flushedUpto`, `receivedTLI`, sender host/port,
conninfo, slotname, mutex, `walRcvStoppedCV`, atomic `writtenUpto`.
Startup process stuffs conninfo/slot/start position in before signaling
postmaster to fork the walreceiver. [from-README]

### `ReplicationSlot` (per-slot in `ReplicationSlotCtl->replication_slots[]`)

`slot.h`. Adds to `ReplicationSlotPersistentData`: `in_use`,
`active_proc`, `mutex` (spinlock), `active_cv`, `effective_xmin`,
`effective_catalog_xmin`, candidate fields for two-phase persistence,
`inactive_since`, `slotsync_skip_reason`. Persistent fields: `name`,
`db`, `persistency`, `xmin`, `catalog_xmin`, `restart_lsn`,
`confirmed_flush`, two_phase fields, `failover`, `synced`, `plugin`,
`invalidated`, `last_inactive`.

### `ReplicationSlotInvalidationCause` — bitmask enum (`slot.h:58-69`)

`RS_INVAL_NONE | WAL_REMOVED | HORIZON | WAL_LEVEL | IDLE_TIMEOUT` —
chosen as a bitmask so a single invalidation pass can consider multiple
causes. [verified-by-code] `slot.c:115-121`.

### `ReplicationState` (per-origin, in shmem)

`origin.c:111`. `roident`, `remote_lsn`, `local_lsn`, `acquired_by`
(proc number), `lsn_lock` (LWLock — NOT spinlock because we may hold it
over an XLogInsert). [from-comment] `origin.c:45-63`.

### `LogicalDecodingContext` (`logical.h:88-`)

Central handle for logical decoding. Holds memory ctx, slot,
`XLogReaderState`, `ReorderBuffer`, `SnapBuild`, `fast_forward` flag,
output-plugin callbacks vtable, options, write callbacks
(`accept_writes`/`prepared_write`/`write_location`/`write_xid`),
`streaming`/`twophase`/`twophase_opt_given`, output buffer, plugin
private data, `processing_required`. Both walsender (`StartLogicalReplication`)
and the SQL SRF interface (`logicalfuncs.c`) create one.

### `SnapBuildState` (`snapbuild.h`)

4-state enum: START → BUILDING_SNAPSHOT → FULL_SNAPSHOT → CONSISTENT.
Transitions driven by `xl_running_xacts` records. Diagrammed in
`snapbuild.c:65-96`. [from-comment]

### `ReorderBufferTXN` (per-xid in `reorderbuffer.c`)

The transaction-being-decoded record. Holds dlist of changes (LSN-ordered),
list of subxids, statistics, byte-counters fueling the spill-to-disk
heap. `ReorderBufferTXNByIdEnt` (`reorderbuffer.c:130`) is the xid lookup.

### `ReorderBufferChange`

A single decoded WAL change (INSERT/UPDATE/DELETE/TRUNCATE/MESSAGE etc.)
in pre-output form. Allocated from a SlabContext for O(1) per-allocation
+ O(1) free of whole groups.

### `LogicalRepWorker` (per-worker in `LogicalRepCtx->workers[]`)

`worker_internal.h`. Type (APPLY / TABLESYNC / SEQUENCESYNC /
PARALLEL_APPLY), subid, relid, generation, pid, proc, relstate, last_lsn,
last_send_time, `oldest_nonremovable_xid` (for retain-dead-tuples).

### `LogicalRepRelMapEntry` (`relation.c`)

Subscriber-side mapping: publisher relid → local relid + attrmap +
replica-identity columns + arbiter indexes. Built lazily on first apply
of a remote rel.

### Sync-rep `PGPROC` fields

`PGPROC->waitLSN`, `PGPROC->syncRepState` (NOT_WAITING / WAITING /
WAIT_COMPLETE). Once a walsender flips `syncRepState =
SYNC_REP_WAIT_COMPLETE`, the backend is guaranteed not to see a stale
value (memory-ordering argument at `syncrep.c:280-285`). [from-comment]

## 4. Core algorithms / control flow

### Physical streaming

```
walreceiver                               walsender
─────────────                            ──────────
postmaster forks (startup stuffs        postmaster forks (replication
WalRcvData first)                       connection)
   │                                       │
   ▼                                       ▼
walrcv_connect (libpq)                  InitWalSender + auth
   │                                       │
   ▼                                       ▼
IDENTIFY_SYSTEM + verify cluster        exec_replication_command:2065
   │                                       parses with replication_yyparse
   ▼                                       │
START_REPLICATION lsn=...               StartReplication:844
   │                                    or StartLogicalReplication:1492
   ▼                                       │
walrcv_receive loop:                    WalSndLoop:3008
  XLogWalRcvWrite → pg_wal                XLogSendPhysical:3322  or
  periodic XLogWalRcvFlush                XLogSendLogical:3632
  XLogWalRcvSendReply ──────────────────► ProcessRepliesIfAny:2321
  XLogWalRcvSendHSFeedback                  ├─ ProcessStandbyReplyMessage:2505
                                            │   PhysicalConfirmReceivedLocation
                                            └─ ProcessStandbyHSFeedbackMessage
                                                PhysicalReplicationSlotNewXmin
update WalRcv->flushedUpto                Sync-rep wakeup:
wake startup                               SyncRepReleaseWaiters
```

[verified-by-code] `walsender.c:844, :1492, :2065, :2321, :3008`,
`walreceiver.c`.

**MAX_SEND_SIZE = 128 KB** (`XLOG_BLCKSZ * 16`, `walsender.c:118`) caps
per-message payload. `wal_sender_timeout = 60s` triggers keepalive +
liveness check.

### Shutdown choreography (the README's load-bearing claim)

[from-README] + [verified-by-code]:

1. Postmaster does NOT wait for walsenders before the shutdown checkpoint
   — treats them like `pgarch`.
2. After shutdown checkpoint is written, postmaster signals walsenders at
   `PM_WAIT_XLOG_ARCHIVAL`.
3. `PROCSIG_WALSND_INIT_STOPPING` from checkpointer drives walsender into
   `WALSNDSTATE_STOPPING` (rejects further commands).
4. `SIGUSR2` from postmaster tells walsender to stream the last bytes and
   exit. `wal_sender_shutdown_timeout` caps this wait.

**Reason: we want standbys to receive the shutdown checkpoint record.**
[from-README] `README:24-29`.

### Replication slots

#### Lifecycle

`ReplicationSlotCreate` (`slot.c:378`) — validate name, check
failover/standby rules, take Allocation + Control locks, scan for name
collision and free slot, init persistent + in-memory data,
`CreateSlotOnDisk`, flip `in_use` and `active_proc = MyProcNumber`,
create pgstat entry if logical, broadcast `active_cv`.

`ReplicationSlotAcquire` (`slot.c:629`) — find slot, refuse if it's the
internal `pg_conflict_detection` reserved slot (line 659-663), wait on
`active_cv` for current owner unless `nowait`.

`ReplicationSlotRelease` (`slot.c:769`) — release ownership, save dirty,
broadcast.

#### Locking model [from-comment] `slot.c:29-32`

- `ReplicationSlotAllocationLock` (LWLock, exclusive) — allocate/free
  a slot.
- `ReplicationSlotControlLock` — shared to iterate, exclusive to flip
  `in_use`.
- Per-slot `mutex` (spinlock) — protects mutable fields.
- Per-slot `active_cv` — wait for slot to be released.

#### Required-xmin / required-LSN aggregation

`ReplicationSlotsComputeRequiredXmin` (`slot.c:1220`) — aggregate xmin
over all in-use slots; feeds the vacuum horizon (the canonical reason
slots block vacuum).

`ReplicationSlotsComputeRequiredLSN` (`slot.c:1302`) — aggregate
`restart_lsn` for WAL retention.

`ReplicationSlotsComputeLogicalRestartLSN` (`slot.c:1372`) — logical-only
variant.

#### Invalidation [HIGH-RISK]

`InvalidatePossiblyObsoleteSlot` (`slot.c:1974`) — the load-bearing
invalidator. If the slot is unacquired, mark `data.invalidated`, persist
immediately. If acquired, signal owner with SIGTERM (or
`RECOVERY_CONFLICT_LOGICALSLOT` if we're the startup process) and wait on
`active_cv`, retry. Race-aware: rechecks the cause after re-acquiring the
lock, because xmin/restart_lsn can advance under us.

`InvalidateObsoleteReplicationSlots` (`slot.c:2214`) — checkpoint-driven
wrapper that iterates all slots and applies the cause bitmask. Skips
logical slots during binary upgrade. If it invalidates the last logical
slot, requests disabling logical decoding.

A walsender for an invalidated slot is signalled and the invalidated
state is fsync'd **before** the slot is released. [verified-by-code]
`slot.c:2156-2180`.

### Synchronous replication

`SyncRepWaitForLSN(lsn, commit)` (`syncrep.c:149`) — called by user
backends in `CommitTransaction` while interrupts are held. Fast-paths:

- `SYNC_STANDBY_INIT` cleared OR `SYNC_STANDBY_DEFINED` cleared → no wait.
- `lsn <= WalSndCtl->lsn[mode]` → no wait.

Otherwise: insert into queue sorted by LSN (`SyncRepQueueInsert`
`:382` — reverse-iterates the dlist; queue invariant is ascending
waitLSN, so most inserts append), sleep on `MyLatch`.

**Cancel-but-warn semantics** [from-comment] `syncrep.c:289-318`: the
wait is uncancellable in the normal sense. `ProcDiePending` or
`QueryCancelPending` only issue a WARNING and terminate the connection
— they do NOT roll back. The local commit is already durable; the
contract was about replication, so we don't lie by aborting.

`SyncRepReleaseWaiters` (`syncrep.c:484`) — walsender entry; recomputes
which standbys are sync candidates and pops everyone with `waitLSN <=`
the just-confirmed LSN.

`SyncRepGetSyncRecPtr` / `GetOldestSyncRecPtr` / `GetNthLatestSyncRecPtr`
(`syncrep.c:596, :670, :703`) — compute the global flush LSN considering
FIRST (priority) vs ANY (quorum) semantics.

### Logical decoding pipeline

```
WAL on primary
  │
  │  XLogReader feeds decode.c
  ▼
LogicalDecodingProcessRecord(ctx, record)         decode.c:89
  ├─ if has top xid: ReorderBufferAssignChild     reorderbuffer.c:1100
  └─ dispatch via rmgr_table[rmid].rm_decode →
       xlog_decode / xact_decode / heap_decode /
       heap2_decode / standby_decode / logicalmsg_decode
       │
       ▼
ReorderBufferQueueChange (per-xid stream)         reorderbuffer.c:811
       │
       │  meanwhile snapbuild tracks running xacts
       ▼
SnapBuildProcessRunningXacts(builder, lsn, rxact) snapbuild.c:1140
       SnapBuildFindSnapshot drives the state machine:
       START → BUILDING → FULL → CONSISTENT
       │
       ▼
On COMMIT:
  DecodeCommit:                                   decode.c:52
    SnapBuildCommitTxn(builder, lsn, xid, ...)    snapbuild.c:944
    ReorderBufferCommit(rb, xid, ...)             reorderbuffer.c:2882
      → ReorderBufferReplay
        → ReorderBufferProcessTXN                 reorderbuffer.c:2212
          → drive k-way merge iterator:
            ReorderBufferIterTXNInit/Next/Finish  reorderbuffer.c:1285/1413/1505
          → for each change: call output-plugin
            callback via logical.c wrapper
              (begin_cb → change_cb × N → commit_cb)
       │
       ▼
Output bytes via WalSndWriteData                  walsender.c:1612
       │
       ▼
walsender ships to walreceiver (apply worker)
```

[verified-by-code] `decode.c:89`, `reorderbuffer.c:2212-2882`,
`snapbuild.c:944-1242`.

### ReorderBuffer spill-to-disk

[from-comment] `reorderbuffer.c:13-83`:

When total RB memory exceeds `logical_decoding_work_mem`, the **largest
transaction** is serialized to disk and freed from RAM. A max-heap keyed
by per-txn size finds the victim in O(log n). Transactions of size 0
not in the heap. Uses BufFiles (`storage/file/buffile.c`).

**Two specialized contexts:** SlabContext for fixed-size structs
(`ReorderBufferChange`, `ReorderBufferTXN`); GenerationContext for
variable txn payload — chosen so freeing whole groups is O(1).

**Reload bounded by `max_changes_in_memory`** (not the global memory
limit) because substreams are loaded independently.

**Toast reassembly** — toast chunks immediately precede the row record in
WAL within a single top-level txn, so we buffer them until the main row
arrives. `ReorderBufferToast*` functions.

**Invalidation overflow** — per-txn cap of 8 MB of distributed
invalidation messages; over that, mark `RBTXN_DISTR_INVAL_OVERFLOWED`
and force full cache invalidation.

### Historic snapshot building — `snapbuild.c`

[from-comment] `snapbuild.c:40-96`. Why catalog snapshots are special:
catalog tuples have `cmin`/`cmax` but those are reset on crash recovery,
and combocids exist only in the originating backend's RAM. Solution:
heapam writes `XLOG_HEAP2_NEW_CID` records for catalog modifications;
`reorderbuffer` keeps a `(rlocator, ctid) → (cmin, cmax)` map; visibility
checks consult that map instead of the tuple.

State machine:

1. **START → BUILDING_SNAPSHOT** on first `xl_running_xacts` whose xmin
   is above the safe horizon (or directly to CONSISTENT if no running
   xacts).
2. **BUILDING → FULL** on next running_xacts after all initially-running
   xacts have finished. Newly-started xacts can be decoded end-to-end.
3. **FULL → CONSISTENT** when the previously-running xacts from step 2
   have all finished. Only commits after CONSISTENT will be replayed.

`SnapBuildSerialize` / `Restore` (`snapbuild.c:1501, :1845`) — persist /
reconstruct snapshot state to `pg_logical/snapshots/` so subsequent
decoding sessions don't have to walk WAL from scratch.
`CheckPointSnapBuild` (`:1974`) periodically prunes old serialized
snapshot files.

`SnapBuildExportSnapshot` (`:542`) produces a snapshot id that an
ordinary backend can `SET TRANSACTION SNAPSHOT` against — used by
`pg_dump` parallelism AND by tablesync's initial COPY.

### Apply worker

`ApplyWorkerMain` (entry; called by the bgworker harness) → handshake,
acquire slot, enter `LogicalRepApplyLoop` (`worker.c:4003`).

`LogicalRepApplyLoop` receives `XLogData` / `PrimaryKeepalive` /
`PrimaryStatusUpdate` from publisher; dispatches via `apply_dispatch`
(`worker.c:3797`); sends feedback (`send_feedback` `:4319`) periodically.

`apply_dispatch` switches over `LogicalRepMsgType` byte:
- `B` BEGIN, `C` COMMIT, `I` INSERT, `U` UPDATE, `D` DELETE, `T` TRUNCATE,
  `R` RELATION, `Y` TYPE, `M` MESSAGE.
- Stream messages: `S` STREAM_START, `E` STREAM_STOP, `A` STREAM_ABORT,
  `p` STREAM_PREPARE, `c` STREAM_COMMIT.
- 2PC: `b` BEGIN_PREPARE, `P` PREPARE, `K` ROLLBACK_PREPARED, `r`
  COMMIT_PREPARED.

DML appliers (`apply_handle_insert/update/delete/truncate`) call
`FindReplTupleInLocalRel` (`worker.c:3196`) — uses replica-identity
columns to find the local row, then call into the executor.

`slot_store_data` / `slot_modify_data` (`worker.c:1024, :1131`) convert
remote `LogicalRepTupleData` → local `TupleTableSlot` through
`LogicalRepRelMapEntry.attrmap`.

### Streamed transactions (PG 14+)

Two strategies on `subscription.streaming`:

1. **`= on`** — spill to BufFiles. BufFile chosen over plain tempfiles
   because (a) > 2 GB support, (b) automatic cleanup on error, (c)
   survives across local-xact boundaries via FileSet. Filenames embed
   remote XID + subscription OID. Subxact aborts truncate via tracked
   offsets. [from-comment] `worker.c:23-55`.
2. **`= parallel`** — hand off to a parallel apply worker via shm_mq.
   See applyparallelworker section below.

### Parallel apply [from-comment] `applyparallelworker.c:1-148`

When `streaming = parallel`, the leader apply (LA) hands each streamed
transaction off to a parallel apply worker (PA) via 16 MB shm_mq. Worker
pool retained at half of `max_parallel_apply_workers_per_subscription`.

**Deadlock prevention** — two session-level lmgr locks expose LA↔PA
waits to the deadlock detector:

- **Stream lock** (`pa_lock_stream`) — LA holds AccessExclusive while
  sending `STREAM_STOP`; PA briefly takes AccessShare after `STREAM_STOP`
  and `STREAM_ABORT(sub)`. This creates a wait edge from PA to LA in
  lmgr so when LA is stuck on a unique-key conflict caused by PA's
  earlier insert, lmgr sees the cycle.
- **Transaction lock** (`pa_lock_transaction`) — PA holds AccessExclusive
  for the lifetime of the txn; LA takes AccessShare at xact-finish to
  preserve commit order.

`XactLockTableWait()` is NOT used because it considers prepared txns as
in-progress, so the lock would not release after PA's PREPARE.
[from-comment] `applyparallelworker.c:131-134`.

**Buffer-full handling** — if the LA→PA shm_mq is full, LA serializes
pending messages to a file and tells PA to read it for the rest. The
transaction lock still preserves commit ordering. [from-comment]
`applyparallelworker.c:137-148`.

### Tablesync (initial-data synchronization)

Per-table state machine (`pg_subscription_rel.srsubstate`):

```
INIT → DATASYNC → FINISHEDCOPY → SYNCWAIT → CATCHUP → SYNCDONE → READY
```

First three live in `pg_subscription_rel`; SYNCWAIT and CATCHUP are
in-memory only. After SYNCDONE the apply worker flips to READY once it
reaches the synced LSN. [from-comment] `tablesync.c:29-91`.

Each tablesync worker creates a temporary logical slot on the publisher
with `CRS_USE_SNAPSHOT` to inherit the slot-creation snapshot, does
a consistent `COPY` via the slot's snapshot, then catches up via
streaming until SYNCDONE. Slot dropped at SYNCDONE.

Replication-origin name is `pg_<suboid>_sync_<relid>_<sysid>` so its
progress LSN is tracked independently of the main apply origin.

### Two-phase logical replication

Subscription `two_phase` is tri-state: DISABLED / PENDING / ENABLED.
PENDING is startup-only — we delay enabling until ALL tablesyncs are
READY (so we can't produce an "empty prepare" because an apply skipped
inserts during initial copy). [from-comment] `worker.c:63-127`.

GID format: `pg_gid_<suboid>_<xid>` so cross-subscription deadlocks on
the same publisher don't happen.

### Replication origins

[from-comment] `origin.c:11-43`. Names a remote node; replicated
transactions are tagged with their source. **Two-byte internal id**
because origins are emitted into WAL on every replicated commit; max
~65k nodes.

**Key insight** — storing `remote_lsn` in the local commit record lets
us recover apply progress precisely after crash recovery WITHOUT
requiring `synchronous_commit`. Apply can run async (good for
throughput); next startup will know exactly where to resume from each
origin. [from-comment] `origin.c:28-37`.

`replorigin_session_*` is the per-session API the apply worker uses so
progress is implicit in commits.

### Output-plugin callback chain (`logical.c`)

Every callback (begin/commit/change/truncate/message/prepare/
commit_prepared/rollback_prepared/stream_*) has a `*_wrapper` that:

1. Sets up `errcontext` via `LogicalErrorCallbackState` so an output
   plugin's `ereport(ERROR)` is decorated with "during commit_cb / lsn
   X/Y".
2. Switches into the ctx's memory context.
3. Calls the actual plugin callback (`ctx->callbacks.commit_cb` etc.).

These wrappers are installed onto `ctx->reorder->{begin,commit,...}`
so `reorderbuffer` calls uniformly. [from-comment] `logical.c:50-58`.

### Failover-slot sync (PG 17+, `slotsync.c`)

Local mirror slots are `RS_TEMPORARY` until "sync-ready", then flipped
to `RS_PERSISTENT`. Sync-ready requires:

1. Standby flushed WAL ≥ remote slot's `confirmed_flush_lsn`.
2. Standby's catalog xmin not behind remote slot's needs (no rows
   missing).
3. Standby can build a consistent snapshot at `restart_lsn` before
   reaching `confirmed_flush_lsn` (otherwise post-promotion decoding
   could lose changes — corrupt-snapshot scenario at `slotsync.c:28-35`).

[from-comment]. Skip reasons map 1:1 to `SlotSyncSkipReason`
(`slot.h:80-90`).

`ReplSlotSyncWorkerMain` — bgworker entry; auto if
`sync_replication_slots=on`. Alternative: SQL function
`pg_sync_replication_slots()`. `ShutDownSlotSync` is promotion-time
teardown by startup process.

### Conflict detection (PG 18, `conflict.c`)

8 conflict types (`ConflictType`, `conflict.h:31-62`): `insert_exists`,
`update_origin_differs`, `update_exists`, `update_missing`,
`delete_origin_differs`, `update_deleted`, `delete_missing`,
`multiple_unique_conflicts`.

`GetTupleTransactionInfo` (`conflict.c:64`) — pull xmin + commit
timestamp + origin from a local tuple (requires `track_commit_timestamp`).

`ReportApplyConflict` (`conflict.c:105`) — main reporter. Builds an
`errdetail` combining info about all conflicting local rows (a single
INSERT can hit multiple unique indexes), formats key column values, uses
ereport at the elevel chosen by caller (LOG normally, ERROR for
`multiple_unique_conflicts` etc.).

`InitConflictIndexes` — set up `ri_arbiter_indexes` from the local rel
so apply DML can use `ExecCheckIndexConstraints`.

### Retain dead tuples (PG 18, in `worker.c`)

If `retain_dead_tuples=true`, the apply worker maintains an
`oldest_nonremovable_xid` in shared memory so vacuum can't reclaim
versions still needed for `update_deleted` and `*_origin_differs`
detection. The launcher (`launcher.c:1448` `compute_min_nonremovable_xid`)
aggregates per-apply-worker xmins into the internal
`pg_conflict_detection` slot (created by `CreateConflictDetectionSlot`
at `launcher.c:1569`).

Five-phase RDT state machine [from-comment] `worker.c:136-227`:

`GET_CANDIDATE_XID` → `REQUEST_PUBLISHER_STATUS` →
`WAIT_FOR_PUBLISHER_STATUS` → `WAIT_FOR_LOCAL_FLUSH` → loop;
`STOP_CONFLICT_INFO_RETENTION` / `RESUME_CONFLICT_INFO_RETENTION` when
`max_retention_duration` would be exceeded.

Not supported when publisher is a physical standby or has its own
subscriptions.

## 5. Invariants

- INV-rep-1: **Walreceiver/libpq split** — libpq lives in
  `libpqwalreceiver/` as a dynamically loaded module so the main server
  binary stays libpq-free. [from-README] `README:14-20`.
- INV-rep-2: **Postmaster does NOT wait for walsenders before shutdown
  checkpoint.** Walsenders are stopped AFTER the shutdown checkpoint
  record is written, so standbys receive it. [from-README] `README:24-29`.
- INV-rep-3: **Walsender registers "am I a walsender" via PMSignal**,
  because postmaster can't know at fork time. [from-README].
- INV-slot-1: **`pg_conflict_detection` is the only reserved slot name.**
  `ReplicationSlotAcquire` refuses to bind it. [verified-by-code]
  `slot.c:659-663`, `slot.h:28`.
- INV-slot-2: **Invalidation states (`RS_INVAL_*`) are a BITMASK**, so a
  single pass can consider multiple causes. [from-comment]
  `slot.c:115-121`, `slot.h:58-69`.
- INV-slot-3: **A walsender for an invalidated slot is signalled AND
  the invalidated state is fsync'd BEFORE the slot is released.**
  [verified-by-code] `slot.c:2156-2180`.
- INV-slot-4: **`restart_lsn` is cleared on `RS_INVAL_WAL_REMOVED`.**
  [verified-by-code] `slot.c:2065-2069`.
- INV-slot-5: **Synced slots are inactive for idle-timeout purposes**
  because they don't decode locally. [verified-by-code] `slot.c:1860-1872`.
- INV-syncrep-1: **`SyncRepWaitForLSN` is uncancellable in the normal
  sense.** Cancel only WARNs and disconnects, doesn't roll back. The
  local commit is already durable. [from-comment] `syncrep.c:289-318`.
- INV-syncrep-2: **The sync-rep queue invariant is ascending `waitLSN`,
  so `SyncRepQueueInsert` reverse-iterates the dlist.** Most inserts are
  monotonic appends. [verified-by-code] `syncrep.c:382`.
- INV-syncrep-3: **Memory ordering for `syncRepState = WAIT_COMPLETE`**:
  once walsender flips it, the waiter is guaranteed not to see stale
  value. [from-comment] `syncrep.c:280-285`.
- INV-snap-1: **Logical decoding protects ONLY catalog rows via the
  slot's `catalog_xmin`**; user-table rows can still be removed.
  [from-comment] `snapbuild.c:1-27`.
- INV-snap-2: **Historic catalog visibility uses the `(rlocator, ctid)
  → (cmin, cmax)` map** kept by `reorderbuffer`, populated from
  `XLOG_HEAP2_NEW_CID` records. [from-comment] `snapbuild.c:40-53`.
- INV-snap-3: **`CONSISTENT` is the only state in which commits are
  replayed.** Earlier states discard commits — they're for catching up
  with running xacts. [from-comment] `snapbuild.c:65-96`.
- INV-rb-1: **Spill-to-disk picks the LARGEST txn**, found in
  O(log n) via a max-heap. Size-0 txns are NOT in the heap. [from-comment]
  `reorderbuffer.c:52-73`.
- INV-rb-2: **Reload at replay time uses `max_changes_in_memory`, NOT
  the global limit**, because substreams reload independently.
  [from-comment] `reorderbuffer.c:75-83`.
- INV-rb-3: **Toast chunks always immediately precede their row record
  in WAL within a single top-level txn.** Reorderbuffer relies on this
  ordering for reassembly. [from-comment] `reorderbuffer.c:39-45`.
- INV-rb-4: **Invalidation messages cap at 8 MB per txn**; over that,
  RBTXN_DISTR_INVAL_OVERFLOWED → full cache invalidation.
  [from-comment] `reorderbuffer.c:118-127`.
- INV-rb-5: **Commits emit in COMMIT-LSN order** via a k-way merge over
  per-xid streams. [from-comment] `reorderbuffer.c:13-31`.
- INV-decode-1: **`fast_forward` mode bumps LSN/xmin bookkeeping
  without calling output plugin.** Used by slot advance. [from-comment]
  `decode.c:84-87`.
- INV-decode-2: **`DecodeTXNNeedSkip` filters by db (logical slots are
  DB-scoped), origin, and snapbuild state.** [verified-by-code]
  `decode.c:68`.
- INV-origin-1: **Replication-origin id is 2 bytes** because it's
  emitted into WAL on every replicated commit. Max ~65k nodes.
  [from-comment] `origin.c:11-43`.
- INV-origin-2: **`remote_lsn` stored in the local commit record means
  async apply is crash-safe** without requiring `synchronous_commit`.
  [from-comment] `origin.c:28-37`.
- INV-origin-3: **`DoNotReplicateId = PG_UINT16_MAX` is the sentinel
  origin** that suppresses re-replication. [verified-by-code]
  `origin.h:34`.
- INV-origin-4: **Origin lsn_lock is LWLock not spinlock** because we
  may hold it over an XLogInsert. [from-comment] `origin.c:45-63`.
- INV-pa-1: **Parallel-apply LA↔PA waits expose to the deadlock
  detector via lmgr stream/transaction locks.** Avoiding
  `XactLockTableWait` because of prepared-txn behavior. [from-comment]
  `applyparallelworker.c:60-148`.
- INV-tablesync-1: **Tablesync workers create temporary slots on the
  publisher with `CRS_USE_SNAPSHOT`** so the initial COPY is consistent
  with the streamed catch-up. [verified-by-code] `tablesync.c`.
- INV-tablesync-2: **READY flip happens on the apply side**, not the
  tablesync side. Tablesync stops at SYNCDONE. [from-comment]
  `tablesync.c:29-91`.
- INV-twophase-1: **two-phase logical replication is delayed until ALL
  tablesyncs reach READY** to avoid empty PREPAREs. [from-comment]
  `worker.c:63-127`.
- INV-slotsync-1: **Local mirror slots stay `RS_TEMPORARY` until
  sync-ready** (standby flushed past confirmed_flush, snapshot consistent,
  catalog xmin sufficient). Only then flipped to `RS_PERSISTENT`.
  [from-comment] `slotsync.c:11-35`.
- INV-failover-1: **Physical walsenders holding slots in
  `synchronized_standby_slots` ping logical walsenders** when standbys
  confirm an LSN, so logical decoding doesn't outrun the failover
  guarantee. [verified-by-code] `walsender.c:1801`,
  `PhysicalWakeupLogicalWalSnd`.
- INV-rdt-1: **`pg_conflict_detection` is created at the first
  subscription with `retain_dead_tuples=true`** by launcher and
  receives an aggregate xmin from all RDT-enabled apply workers.
  [verified-by-code] `launcher.c:1448, :1569`.

## 6. Entry points (how the rest of the backend calls in)

External callers (`tcop`, `commands`, `executor`, `postmaster`):

- `exec_replication_command(cmd)` (`walsender.c:2065`) — called by
  `PostgresMain` when running on a replication connection.
- `SyncRepWaitForLSN(lsn, commit)` (`syncrep.c:149`) — called by every
  commit in `xact.c:CommitTransaction` when sync rep is configured.
- `SyncRepInitConfig`, `SyncRepUpdateSyncStandbysDefined` — called by
  postmaster / checkpointer at config reload.
- `ReplicationSlotCreate/Acquire/Release/Drop` — called by SQL via
  `slotfuncs.c`; also by walsender directly for
  `CREATE_REPLICATION_SLOT`.
- `ReplicationSlotsComputeRequiredXmin` (`slot.c:1220`) — called by
  `procarray.c:GetSnapshotData` and friends to honor slot xmins.
- `CheckPointReplicationSlots` (`slot.c:2318`) — called by checkpointer.
- `StartupReplicationSlots` (`slot.c:2396`) — called once at backend
  startup.
- `LogicalDecodingProcessRecord` (`decode.c:89`) — called by both
  walsender's `XLogSendLogical` AND the SRF interface in `logicalfuncs.c`.
- `replorigin_session_setup`, `replorigin_session_advance`,
  `replorigin_session_origin_lsn` — called by apply workers in `worker.c`.
- `pgoutput_startup` / `pgoutput_*_cb` — registered as the default
  output plugin in `pgoutput.c`, called via `logical.c` wrappers.

Internal entry points (called only within `replication/`):

- `WalSndLoop`, `XLogSendPhysical`, `XLogSendLogical`,
  `WalSndWaitForWal`, `WalSndDone` (`walsender.c`).
- `ApplyLauncherMain` (`launcher.c:1205`) — bgworker entry.
- `ApplyWorkerMain` (worker.c) — bgworker entry.
- `ParallelApplyWorkerMain` (declared in `logicalworker.h:20`,
  implementation called via `applyparallelworker.c`).
- `ReplSlotSyncWorkerMain` (`slotsync.c`).
- `WalReceiverMain` (`walreceiver.c`) — auxiliary-process entry.
- All `Sync*` and `Async*` slot helpers.

## 7. What the tests tell us

### Regression (`src/test/regress/`)

- `rules.sql` (not specific to replication but exercises logical-decoding
  test harness when run with `wal_level=logical`).
- Most replication tests live in TAP because they need multi-node setup.

### TAP (`src/test/recovery/t/`, `src/test/subscription/t/`)

- `src/test/recovery/t/` — physical replication, slot invalidation,
  failover-slot sync, standby behavior under primary failure.
  - `001_stream_rep` — basic streaming.
  - `004_timeline_switch` — promotion.
  - `006_logical_decoding` — basic logical decoding via SQL SRF.
  - `019_replslot_limit` — `max_slot_wal_keep_size` enforcement.
  - `035_standby_logical_decoding` — logical decoding on standby
    (failover slots).
- `src/test/subscription/t/` — logical replication end-to-end.
  - `001_rep_changes` — basic publish/subscribe.
  - `015_stream` / `016_stream_subxact` — streamed-xact paths (spill
    + parallel).
  - `024_add_drop_pub` — publication changes.
  - `029_on_error` — apply error handling.
  - `031_column_list`, `032_subscribe_use_index`, `033_run_as_table_owner`
    — various features.
  - `034_temporal_replication` (PG 18) — RDT + conflict detection.

### Isolation (`src/test/isolation/`)

- Limited — sync-rep behavior under concurrent commits isn't
  isolation-tested directly. Some `pg_logical/` specs exercise
  catalog-row visibility during decoding.

### Modules (`src/test/modules/`)

- `test_logical_replication_workers` — bgworker-spawn semantics.
- `test_decoding` — output-plugin smoke tests; built-in pgoutput is
  exercised via subscription tests.

## 8. Gotchas / sharp edges

- **`SyncRepWaitForLSN` cancel semantics** — Cancel just WARNs +
  disconnects, doesn't abort. Backends that loop on Ctrl-C expecting a
  rollback get the connection torn down instead.
- **Sync-rep `lsn[mode]` fast path** is per-mode; switching
  `synchronous_commit` mid-session can produce surprising no-wait
  behavior on a recently-acked LSN.
- **`MAX_SEND_SIZE = 128 KB`** caps walsender payload — long records that
  exceed it are split across messages. Receivers must handle partial-record
  reads.
- **Logical decoding on standby** requires `wal_level=logical` on the
  primary AND on the standby; the failover-slot mechanism only synchronizes
  slot state, NOT wal_level.
- **Reorderbuffer spill is per-LARGEST-txn**, not per-oldest — comment at
  `reorderbuffer.c:64-68` notes that LSN-age might be a better heuristic
  but isn't implemented.
- **Toast reassembly assumes per-txn locality**: changes from a single
  top-level txn arrive in WAL order. Concurrent toast operations from
  different xacts don't interleave because the toast TID is unique.
  Don't break this when adding a new toast emitter.
- **`ReorderBufferAssignChild` is called before dispatch**, so even an
  rmgr with no `rm_decode` callback still gets subxact tracking.
  [verified-by-code] `decode.c:108-118`.
- **`DecodeTXNNeedSkip`** is the central skip predicate — wrong DB
  (logical slots are DB-scoped), wrong origin (`filter_by_origin_cb`), or
  snapbuild not yet consistent. Forgetting it in a new decode path leaks
  changes to the wrong slot.
- **`replorigin_session_setup` MUST be called before applying anything**,
  otherwise the commit record won't carry the origin and apply progress
  is lost on crash.
- **`replorigin_session_origin_lsn` is the remote LSN you'd resume from**
  — not the local LSN. Easy to confuse in custom apply code.
- **Tablesync workers must use `CRS_USE_SNAPSHOT`** to start their
  temporary slot — `CRS_EXPORT_SNAPSHOT` would export to the wrong
  session. `tablesync.c` enforces this.
- **READY flip happens on the apply side**, not the tablesync side. A
  tablesync worker that wrote SYNCDONE but exits before apply notices
  will be re-spawned and skip ahead, but the relation stays SYNCDONE
  until apply reaches the synced LSN.
- **Two-phase logical replication GID is `pg_gid_<suboid>_<xid>`** —
  custom GIDs from `PREPARE TRANSACTION 'foo'` get rewritten by the
  apply worker. Don't depend on user-provided GIDs surviving logical
  replication.
- **Parallel-apply lmgr locks** — never replace with a plain LWLock; the
  deadlock detector relies on session-level lmgr visibility.
- **PA does NOT use `XactLockTableWait`** because prepared txns count as
  in-progress there. [from-comment] `applyparallelworker.c:131-134`.
- **`pg_conflict_detection` is created lazily** at the first subscription
  with `retain_dead_tuples=true`. Dropping the last such subscription
  does NOT drop the slot — it stays as a tombstone.
- **`OprCache` and friends elsewhere don't affect replication**, but
  output plugins that build tuples directly should watch out for
  catalog version mismatches across the primary↔subscriber.
- **`DoNotReplicateId` (PG_UINT16_MAX)** is the sentinel for "don't
  replicate this change downstream" — custom output plugins must honor
  it via `filter_by_origin_cb`.

## 9. Open questions

- O1: **Walreceiver reconnection state machine** — comment at
  `walreceiver.c:22-26` mentions WAITING state when the primary stream
  ends without disconnect, but the exact `WalReceiverMain` state-machine
  details weren't traced. [unverified]
- O2: **`two_phase_at` LSN semantics in failover-slot edge cases** —
  added (PG 14) to delay 2PC PREPARE decoding until catalogs catch up;
  interaction with `slotsync.c` skip reasons not exhaustively verified.
  [unverified] (from `snapbuild.c.md`).
- O3: **Slot-sync demotion** — `stopSignaled` is documented as not reset
  because demotion isn't supported. If demotion ever lands, this becomes
  a hazard. [from-comment] `slotsync.c`.
- O4: **`InvalidatePossiblyObsoleteSlot` race recheck** — code rechecks
  the invalidation cause after re-acquiring the lock; the exact set of
  races that motivate this isn't fully enumerated. Likely
  xmin/restart_lsn advance, but there may be others. [unverified]
- O5: **`restart_lsn` preservation alongside `invalidated`** — XXX
  comment at `slot.c:2061-2064` flags this as an open design point.
  [from-comment]
- O6: **Reorderbuffer eviction policy** — comment at
  `reorderbuffer.c:64-68` notes that LSN-age might be a better victim
  heuristic. No empirical study referenced. [from-comment]

## 10. Related subsystems

- **Calls into:**
  - `access/transam/xlog*.c` — WAL reading (XLogReader), WAL emission
    (`XLogInsert` for `XLOG_REPLORIGIN_SET/DROP`, sync-rep wait inside
    commit records).
    [via `knowledge/subsystems/access-transam.md`]
  - `storage/lmgr` — slot LWLocks; parallel-apply session-lock
    deadlock-detector visibility.
    [via `knowledge/subsystems/storage-lmgr.md`]
  - `storage/ipc/procarray` — `ReplicationSlotsComputeRequiredXmin`
    feeds the vacuum horizon.
    [via `knowledge/subsystems/storage-ipc.md`]
  - `storage/file/buffile` — Reorderbuffer spill files; streamed-xact
    spill on subscriber.
  - `utils/cache/relcache` + `syscache` — `LogicalRepRelMap`,
    apply-side relation lookups, historic-catalog access via
    `snapbuild`/`reorderbuffer`.
    [via `knowledge/subsystems/utils-cache.md`]
  - `executor` — apply DML via `ExecModifyTable`-style invocations.
    [via `knowledge/subsystems/executor.md`]
  - `commands/subscriptioncmds.c` + `publicationcmds.c` — DDL → slot ops
    → launcher wakeup.
  - `postmaster/bgworker.c` + `bgwriter.c` + `checkpointer.c` — bgworker
    lifecycle for launcher / apply / tablesync / PA / slotsync.
  - `libpq` (loaded as `libpqwalreceiver` module).

- **Called by:**
  - `tcop/postgres.c:PostgresMain` — `exec_replication_command`
    dispatch on replication connections.
  - `xact.c:RecordTransactionCommit` — emits the synchronous-replication
    LSN into the commit record, then calls `SyncRepWaitForLSN`.
  - `xact.c:XactLogCommitRecord` — emits origin LSN if
    `replorigin_session_origin != InvalidRepOriginId`.
  - `commands/copy.c` — tablesync uses `COPY ... FROM STDIN` via the
    apply worker's connection.
  - `pg_basebackup` — uses `BASE_BACKUP` replication command (parsed by
    `walsender.c:exec_replication_command`).
  - `pg_receivewal` — uses physical `START_REPLICATION`.

- **Sibling:**
  - **`backup/`** — overlapping concerns (basebackup); see
    `subsystems/main.md` for `pg_basebackup` driver.
  - **`utils/activity`** — `pg_stat_replication`,
    `pg_stat_subscription`, `pg_replication_slots` views read shmem
    that this subsystem writes.

## 11. Source pointers — most-cited file:line summary

| Anchor | What it establishes |
|---|---|
| `README:14-37` | walreceiver/libpq split + walsender shutdown ordering |
| `walsender.c:844` | `StartReplication` (physical) |
| `walsender.c:1492` | `StartLogicalReplication` |
| `walsender.c:1801` | `PhysicalWakeupLogicalWalSnd` (failover-slot sync) |
| `walsender.c:1886` | `WalSndWaitForWal` (logical-side blocking wait) |
| `walsender.c:2065` | `exec_replication_command` (dispatcher) |
| `walsender.c:2321` | `ProcessRepliesIfAny` (feedback) |
| `walsender.c:3008` | `WalSndLoop` (main service loop) |
| `walsender.c:3322` | `XLogSendPhysical` (physical send callback) |
| `walsender.c:3632` | `XLogSendLogical` (logical send callback) |
| `slot.c:115-121` | Invalidation-cause bitmask lookup table |
| `slot.c:378` | `ReplicationSlotCreate` |
| `slot.c:629, :659-663` | `ReplicationSlotAcquire` + `pg_conflict_detection` refuse |
| `slot.c:769` | `ReplicationSlotRelease` |
| `slot.c:1220` | `ReplicationSlotsComputeRequiredXmin` |
| `slot.c:1974` | `InvalidatePossiblyObsoleteSlot` (the load-bearing invalidator) |
| `slot.c:2156-2180` | Invalidated-state fsync-before-release |
| `slot.c:2214` | `InvalidateObsoleteReplicationSlots` (checkpoint-driven) |
| `slot.c:2318` | `CheckPointReplicationSlots` |
| `syncrep.c:149` | `SyncRepWaitForLSN` |
| `syncrep.c:280-318` | Memory ordering + cancel-but-warn semantics |
| `syncrep.c:382` | `SyncRepQueueInsert` (queue invariant) |
| `syncrep.c:484` | `SyncRepReleaseWaiters` |
| `decode.c:84-118` | `LogicalDecodingProcessRecord` + `fast_forward` |
| `decode.c:52` | `DecodeCommit` |
| `decode.c:68` | `DecodeTXNNeedSkip` (filter) |
| `snapbuild.c:40-96` | Historic-snapshot design + 4-state machine |
| `snapbuild.c:944, :1140, :1242` | `SnapBuildCommitTxn`, `SnapBuildProcessRunningXacts`, `SnapBuildFindSnapshot` |
| `reorderbuffer.c:13-83` | Spill-to-disk design + contexts |
| `reorderbuffer.c:2212-2882` | `ReorderBufferProcessTXN`, `ReorderBufferCommit` |
| `worker.c:23-227` | Streamed-xact + 2PC + RDT design sections |
| `worker.c:3797, :4003` | `apply_dispatch`, `LogicalRepApplyLoop` |
| `applyparallelworker.c:60-148` | Parallel-apply deadlock-detector lmgr locks |
| `tablesync.c:29-91` | Tablesync 7-state machine |
| `origin.c:11-43` | Origin design (2-byte id + crash-safe progress) |
| `origin.c:45-63` | Per-slot lsn_lock is LWLock not spinlock |
| `slotsync.c:11-35` | Failover-slot sync design + corrupt-snapshot scenario |
| `conflict.c:31-62` | 8 conflict types |
| `conflict.c:105` | `ReportApplyConflict` |
| `launcher.c:1448, :1569` | RDT xmin aggregation + `pg_conflict_detection` creation |
| `logical.c:50-58` | Callback-wrapper errcontext design |

## Synthesized over

This synthesis distills the 28 per-file docs under
`knowledge/files/src/backend/replication/{,logical/}` plus the omnibus
header doc at `knowledge/files/src/include/replication/headers.md`. See
[[knowledge/architecture/replication.md]] for the high-level
architecture narrative, [[knowledge/subsystems/access-transam.md]] for
the WAL infrastructure this builds on, and the
[[replication-overview]] skill for the operational orientation.
