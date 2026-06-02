# Iteration 1 — answers (with_skill vs baseline)

## Eval 1 — Trace a COMMIT through physical streaming to a hot standby reader (with synchronous_commit=remote_apply)

### with_skill answer

Primary side:
1. Backend executes COMMIT. It writes a commit WAL record into the WAL buffers, then calls `XLogFlush` to push the record to disk (fsync per `synchronous_commit=local`/`on`).
2. With `synchronous_commit=remote_apply`, after the local flush the backend enqueues itself on `SyncRepQueue` keyed by its commit LSN and goes to sleep (`syncrep.c`).
3. A **walsender** backend (one per connected standby; `source/src/backend/replication/walsender.c`) is sitting in `START_REPLICATION PHYSICAL ...` mode. It reads from `pg_wal/` (or the WAL buffers if caught up), batches up to `MAX_SEND_SIZE` (16 * XLOG_BLCKSZ = 128 KB) and ships COPY-protocol data messages over libpq.

Standby side:
4. The **walreceiver** auxiliary process (`source/src/backend/replication/walreceiver.c`, with libpq loaded via the dynamic `libpqwalreceiver/` module) receives the batch, writes it to local `pg_wal/`, optionally fsyncs (per `wal_receiver_status_interval`), then bumps `WalRcv->flushedUpto` so the startup process knows it can replay.
5. Walreceiver sends a **feedback message** back to the primary carrying `write_lsn`, `flush_lsn`, `apply_lsn`.
6. The **startup process** (in hot-standby mode) sees `flushedUpto` advance, redoes the commit record, marks the xact as committed in `clog`, and updates the shared snapshot — at that point a hot-standby reader can see the row.
7. After replay, walreceiver's next feedback message reports `apply_lsn` >= commit LSN.

Back on primary:
8. The walsender that received that feedback walks `SyncRepQueue` and wakes the committing backend whose commit LSN has been covered by `apply_lsn` (this is what makes it `remote_apply` specifically — `remote_write` would wake on `write_lsn`, `on` on `flush_lsn`).
9. COMMIT returns to the client.

Notes:
- `synchronous_standby_names` must list the standby (FIRST N or ANY N) and the standby must already be **caught up** to count toward the policy — configuration alone isn't sufficient (syncrep.c:60-65).
- The standby never knows it's serving in sync mode; syncrep is entirely a primary-side wait queue (syncrep.c:5-66).
- At shutdown, postmaster waits for walsenders *after* the shutdown checkpoint is written — opposite of normal backends — so the standby gets the shutdown checkpoint record (README:42-49).

### baseline answer

A COMMIT writes a commit WAL record on the primary; XLogFlush flushes it. The walsender process streams WAL bytes over libpq to the standby's walreceiver, which writes the WAL locally and replays it (or hands it to the startup process for replay). With `synchronous_commit=remote_apply`, the primary backend waits until the standby has actually applied (not just flushed) the commit LSN before returning to the client; this is implemented via a wait queue that walsender wakes up on feedback messages from the standby. The standby's hot-standby reader sees the row once the startup process has replayed the commit. Feedback levels: `remote_write` (OS-written on standby), `on` (fsynced on standby), `remote_apply` (replayed). I don't remember the exact file names or constants like MAX_SEND_SIZE off the top of my head.

---

## Eval 2 — Logical decoding pipeline: WAL → output plugin events

### with_skill answer

The pipeline lives in `source/src/backend/replication/logical/` and runs inside a walsender (or a SQL SRF consumer like `pg_logical_slot_get_changes`):

1. **`decode.c`** walks WAL via `XLogReadRecord` and dispatches per record type to `DecodeInsert`, `DecodeUpdate`, `DecodeDelete`, `DecodeTruncate`, `DecodeMultiInsert`, `DecodeSpecConfirm`, `DecodeCommit`, `DecodeAbort`, `DecodePrepare`. Even records without data changes still call `ReorderBufferProcessXid()` so the reorder buffer keeps subxact trees consistent. (decode.c:1-26,72-80)

2. **`reorderbuffer.c`** does the reassembly. PG writes WAL in **record order**, not transaction order, so subxacts and concurrent xids are interleaved. The reorder buffer collects per-xid change streams keyed by xid; at the commit record it folds subxacts into the toplevel txn and calls the output plugin's `change_cb` in (xid, lsn) order via `ReorderBufferCommit()`. (reorderbuffer.c:13-31)

3. **Memory pressure**: reorder buffer uses two memory contexts — a `SlabContext` for fixed-size change/txn structs, a `GenerationContext` for variable-length payloads. There's a per-reorderbuffer memory limit (the `logical_decoding_work_mem` GUC). When exceeded, the **largest** in-progress transaction is serialized to disk — selected via a max-heap keyed by size. (reorderbuffer.c:33-83) Toast chunks are reassembled inline; within a toplevel txn nothing else appears between a row's toast chunks and the row itself.

4. **Streaming mode** (`streaming=on` or `streaming=parallel` on the subscription) ships in-progress transactions to the consumer before commit, using the optional streaming callbacks (`stream_start_cb`, `stream_stop_cb`, `stream_commit_cb`, etc.).

5. **Historical catalog**: `snapbuild.c` builds and maintains **historical MVCC snapshots** at the LSN of each change, so when the plugin asks "what columns does this relation have?" it sees the catalog as it looked then, not now. This is why logical slots pin `catalog_xmin` — VACUUM cannot remove catalog tuples a snapshot still needs.

6. **Output plugin contract** (`source/src/include/replication/output_plugin.h:33-243`): the shared library exports `_PG_output_plugin_init(OutputPluginCallbacks *cb)` and fills `startup_cb`, `begin_cb`, `change_cb`, `truncate_cb`, `commit_cb`, optional `message_cb`, optional streaming and two-phase callbacks, and `shutdown_cb`. The plugin sees rows as `HeapTuple` + `Relation` and writes to a `StringInfo` provided by `logical.c`; the walsender or SRF then ships that buffer.

Canonical example plugin: `contrib/test_decoding`. Built-in plugin used by logical replication: `pgoutput` (`source/src/backend/replication/pgoutput/`).

### baseline answer

Logical decoding reads WAL and turns it into row-level change events for an output plugin. The decoder (decode.c) reads each WAL record and feeds insert/update/delete events into a reorder buffer (reorderbuffer.c). Because WAL is in commit-LSN-of-each-record order rather than per-transaction, the reorder buffer must group changes by xid and emit them at the corresponding commit record. Subtransactions are tracked separately and folded into their parent at commit. When the buffer exceeds memory limits (logical_decoding_work_mem), large transactions spill to disk. For catalog metadata, decoding uses historical snapshots (snapbuild.c) so columns dropped after the change is recorded are still visible to the decoder. The output plugin implements callbacks like begin/change/commit (and optional streaming/two-phase variants); test_decoding and pgoutput are the canonical examples. I'm not sure of the exact spill policy (largest txn? oldest?) or the specific memory context names.

---

## Eval 3 — Failover slot mechanism (v17+), the sync gate, and synchronized_standby_slots

### with_skill answer

**Goal**: a logical subscription survives a primary failover without re-snapshotting. Pre-v17, logical slots existed only on the primary; failover meant the standby had no slot to resume from. v17 added **slot sync**.

**Mechanism**:
- On the primary, create a logical slot with `failover=true` (a field on `ReplicationSlotPersistentData`, see `slot.h:95-162`).
- On the standby, run with `sync_replication_slots=on` (or call `pg_sync_replication_slots()` manually). A **slot-sync worker** (`source/src/backend/replication/logical/slotsync.c`) periodically pulls the primary's failover-eligible slots and mirrors them locally.
- Local mirrors start as `RS_TEMPORARY`. They flip to `RS_PERSISTENT` and get the `synced=true` flag set only when **sync-ready** — three conditions (slotsync.c:11-35):
  1. Standby's flushed WAL is past the remote slot's `confirmed_flush_lsn`.
  2. Standby's catalog xmin is not behind the remote's needs.
  3. A consistent snapshot can be built at `restart_lsn` before reaching `confirmed_flush_lsn` (otherwise post-promotion decoding could silently lose changes).
- Synced slots are treated as inactive for idle-timeout purposes — they don't decode locally (slot.c:1860-1872).

**The gate — `synchronized_standby_slots`**:
This GUC on the primary names physical replication slots that **must have caught up** before any logical failover slot may advance its `confirmed_flush`. Without it, the primary could ack a logical consumer past changes the standby hadn't yet received, leaving the post-failover slot stuck behind data the consumer thinks it already got.

Wire-up:
- A logical walsender holding a failover slot calls `WalSndWaitForWal`, whose predicates `NeedToWaitForStandbys` / `NeedToWaitForWal` consult the `synchronized_standby_slots` list (walsender.c:1801-1886).
- When a physical walsender receives a standby reply confirming a new flush LSN, it calls `PhysicalWakeupLogicalWalSnd`, which signals the condition variable `WalSndCtl->wal_confirm_rcv_cv`, releasing logical walsenders blocked at the gate.
- Net effect: the logical consumer is held behind a physical-standby ACK chain even though the two sides don't talk directly.

Implementation: parsed into `SyncStandbySlotsConfigData`; gate functions `StandbySlotsHaveCaughtup`, `WaitForStandbyConfirmation` (slot.c:95-104, 3107, 3255).

**After failover**: the subscriber's `primary_conninfo` is repointed at the promoted standby; the synced slot is already at the right `confirmed_flush_lsn`, so streaming resumes without re-snapshotting.

### baseline answer

In recent PG versions, logical slots can be marked `failover=true` so that they are synchronized from the primary to a standby; this way after a failover the subscriber can be repointed at the new primary and continue without resnapshotting. A slot-sync worker on the standby pulls slot state from the primary periodically. The `synchronized_standby_slots` GUC on the primary, I believe, lists physical replication slots that need to have caught up before a logical slot can advance — to prevent the logical slot getting ahead of the standby, which would lose data after failover. There are conditions about the standby's WAL/catalog being far enough along before the synced slot can be considered usable. I don't remember the exact function names or the three preconditions in detail.
