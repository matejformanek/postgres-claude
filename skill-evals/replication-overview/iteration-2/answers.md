# Iteration 2 — answers (with_skill vs baseline)

Re-run after applying edits 1, 2, 3, 5 from iteration-1/proposed-edits.md to
SKILL.md.

## Eval 1 — Trace a COMMIT through physical streaming to a hot standby reader (with synchronous_commit=remote_apply)

### with_skill answer

Primary side:
1. Backend executes COMMIT. It writes a commit WAL record into the WAL
   buffers, then calls `XLogFlush` to push it to disk (fsync per
   `synchronous_commit=local`/`on`).
2. With `synchronous_commit=remote_apply`, after the local flush the backend
   enqueues itself on `SyncRepQueue` keyed by its commit LSN and goes to
   sleep (`source/src/backend/replication/syncrep.c:5-66`).
3. A **walsender** backend (one per connected standby;
   `source/src/backend/replication/walsender.c`) is sitting in
   `START_REPLICATION PHYSICAL ...` mode. It reads WAL from `pg_wal/` and
   batches up to `MAX_SEND_SIZE = XLOG_BLCKSZ * 16` (~128 KB at default 8K
   blocks; `walsender.c:110-118`), shipping COPY-protocol data messages
   over libpq.

Standby side:
4. The **walreceiver** auxiliary process (`walreceiver.c`, libpq loaded via
   the dynamic `libpqwalreceiver/` module so the main server binary stays
   libpq-free) receives the batch, writes it to local `pg_wal/`, fsyncs,
   and advances `WalRcv->flushedUpto`.
5. Walreceiver periodically sends a **feedback message** back to the primary
   carrying `write_lsn`, `flush_lsn`, `apply_lsn`.
6. The **startup process** (in hot-standby mode) sees `flushedUpto` advance,
   redoes the commit record, marks the xact committed in `clog`, updates
   the shared snapshot — at that moment a hot-standby reader can see the row.
7. After replay, walreceiver's next feedback message reports `apply_lsn`
   advanced past the commit LSN.

Back on primary:
8. The walsender that received that feedback walks `SyncRepQueue` and wakes
   the committing backend whose commit LSN is now covered by `apply_lsn`.
   This is what makes the wait specifically *remote_apply*: `on` would wake
   on `flush_lsn`, `remote_write` on `write_lsn`.
9. COMMIT returns to the client.

Notes:
- `synchronous_standby_names` must list the standby (FIRST N or ANY N) AND
  the standby must already be **caught up** to count toward the policy —
  configuration alone is insufficient (syncrep.c:32-58).
- Standby never knows it serves in sync mode; syncrep is entirely a
  primary-side wait queue.
- At shutdown, postmaster waits for walsenders *after* the shutdown
  checkpoint is written — opposite of normal backends — so the standby
  receives the shutdown checkpoint record (README:39-70).

### baseline answer

A COMMIT writes a commit WAL record on the primary; XLogFlush flushes it.
The walsender process streams WAL bytes over libpq to the standby's
walreceiver, which writes WAL locally and the startup process replays it.
With `synchronous_commit=remote_apply`, the primary backend waits until
the standby has actually applied (not just received or flushed) the commit
LSN before returning to the client; this is implemented via a wait queue
that walsender wakes on feedback messages from the standby. The standby's
hot-standby reader sees the row once the startup process has replayed the
commit. Feedback levels are roughly: `remote_write` (OS-written on standby),
`on` (fsynced on standby), `remote_apply` (replayed on standby). I don't
remember the exact batch-size constant or file:line offsets.

---

## Eval 2 — Logical decoding pipeline

### with_skill answer

The pipeline lives in `source/src/backend/replication/logical/` and runs
inside a walsender (or a SQL SRF consumer such as
`pg_logical_slot_get_changes`):

1. **`decode.c`** walks WAL via `XLogReadRecord` and dispatches per record
   type to `DecodeInsert`, `DecodeUpdate`, `DecodeDelete`, `DecodeTruncate`,
   `DecodeMultiInsert`, `DecodeSpecConfirm`, `DecodeCommit`, `DecodeAbort`,
   `DecodePrepare`. Even non-data records still call
   `ReorderBufferProcessXid()` so the reorder buffer keeps the subxact-tree
   consistent.

2. **`reorderbuffer.c`** reassembles. PG writes WAL in **record order**,
   not transaction order, so subxacts and concurrent xids interleave on the
   stream. The reorder buffer collects per-xid change streams keyed by xid;
   at the commit record it folds subxacts into the toplevel txn and calls
   the output plugin's `change_cb` in (xid, lsn) order via
   `ReorderBufferCommit()` (reorderbuffer.c:13-83).

3. **Memory pressure**: reorder buffer uses two memory contexts — a
   `SlabContext` (fixed-size change/txn structs) and a `GenerationContext`
   (variable-length payloads). The per-reorderbuffer ceiling is the
   `logical_decoding_work_mem` GUC (default 64MB; SKILL.md cheatsheet,
   guc_parameters.dat:1928). When exceeded, the **largest** in-progress
   transaction is serialized to disk, selected via a max-heap keyed by
   size. Toast chunks are reassembled inline — within a toplevel txn
   nothing else appears between a row's toast chunks and the row itself.

4. **Streaming mode** (`streaming=on` or `streaming=parallel`) ships
   in-progress transactions to the consumer before commit, using the
   optional `stream_start_cb`, `stream_stop_cb`, `stream_commit_cb`, etc.

5. **Historical catalog**: `snapbuild.c` builds and maintains historical
   MVCC snapshots **at the LSN of each change**, so when the plugin asks
   "what columns does this relation have?" it sees the catalog as it
   looked then, not as it looks now. This is why a logical slot pins
   `catalog_xmin` — VACUUM cannot remove catalog tuples a historical
   snapshot still needs.

6. **Output plugin contract**
   (`source/src/include/replication/output_plugin.h:36,216-243`): the
   shared library exports `_PG_output_plugin_init(OutputPluginCallbacks
   *cb)` and fills `startup_cb`, `begin_cb`, `change_cb`, `truncate_cb`,
   `commit_cb`, optional `message_cb`, optional streaming and two-phase
   callbacks, and `shutdown_cb`. The plugin sees rows as `HeapTuple` +
   `Relation` and writes to a `StringInfo` provided by `logical.c`; the
   walsender or SRF then ships that buffer.

7. **Canonical plugins**: `contrib/test_decoding` (reference; text format)
   and `src/backend/replication/pgoutput/` (built-in; used by logical
   replication's PUB/SUB).

### baseline answer

Logical decoding lives in `src/backend/replication/logical/`. The decoder
reads WAL records, hands them to a reorder buffer that groups changes by
xid (since WAL is in record order, with concurrent xids interleaved), and
at commit time emits them in transaction order to an output plugin. The
output plugin produces the actual user-facing event stream (test_decoding
in contrib is the canonical example; `pgoutput` is the built-in one used
by logical replication). Historical catalog snapshots are built by
snapbuild.c so the plugin sees the right column definitions at each
change's LSN. When memory fills up, the reorder buffer spills transactions
to disk; the relevant GUC is `logical_decoding_work_mem` (default 64MB).
I don't recall the exact rule for which txn is spilled or the two memory
context types.

---

## Eval 3 — Failover slots and synchronized_standby_slots

### with_skill answer

Introduced in PG **17** so that a logical subscriber can keep consuming
after a standby is promoted, without having to re-create the slot and
re-snapshot the publisher.

Setup:
- On the primary, the logical slot is created with the `failover=true`
  flag. The flag is persisted in slot state
  (`source/src/include/replication/slot.h:95-162`).
- On a physical standby, set `sync_replication_slots = on`. The
  **slot-sync worker** in `source/src/backend/replication/logical/slotsync.c`
  periodically pulls failover-tagged slot state from the primary and
  creates mirror slots locally.

**Three sync-ready preconditions** (slotsync.c:11-40, surfaced in
SKILL.md's slotsync bullet):
1. The standby has flushed WAL **past** the remote slot's
   `confirmed_flush_lsn` — otherwise after promotion the slot would point
   to WAL the standby doesn't have.
2. The standby's catalog xmin horizon is not behind the remote
   `catalog_xmin` — otherwise required catalog tuples could already have
   been vacuumed.
3. A **consistent snapshot** can be built at the slot's `restart_lsn`
   before reaching `confirmed_flush_lsn` — without this, decoding from the
   synced slot after promotion would miss changes before the consistent
   point.

Until all three hold, the mirror slot is `RS_TEMPORARY`. When all hold it
flips to `RS_PERSISTENT` with `synced=true` (slot.h:95-162). Synced slots
are treated as inactive for the idle-timeout invalidation cause
(`RS_INVAL_IDLE_TIMEOUT`, slot.h:68) so they don't get invalidated for
"not being consumed" while waiting for failover.

**`synchronized_standby_slots`** (GUC on the primary): names physical
standbys whose physical slots must have **received** WAL before the
primary lets the logical slot's `confirmed_flush_lsn` advance past that
WAL. This prevents the situation where the logical consumer has acked
data that the failover-target standby hasn't yet received — i.e. after
promotion the new primary would not have that WAL and the logical
subscription would be stuck.

The wakeup chain that connects the two halves lives in walsender.c:
`WalSndWaitForWal` blocks the logical walsender until the named physical
standbys catch up; the physical walsender, on receiving feedback,
calls `PhysicalWakeupLogicalWalSnd` which signals the
`wal_confirm_rcv_cv` condition variable that the logical walsender is
sleeping on. (See `knowledge/architecture/replication.md` §2 for the
detailed trace.)

### baseline answer

PG 17 added the ability to keep logical replication slots in sync between
a primary and physical standbys, so that if the primary fails and a
standby is promoted, the logical subscriber can continue from the new
primary without a full resnapshot. You mark a logical slot with
`failover=true`, and on the standby you enable `sync_replication_slots`
(or call `pg_sync_replication_slots()`). A slot-sync worker on the
standby pulls slot state (`restart_lsn`, `confirmed_flush_lsn`,
`catalog_xmin`) from the primary and creates a mirror slot locally. The
mirror is initially temporary until certain conditions are met (the
standby has the WAL, the catalog horizon is fine), then it becomes
persistent.

`synchronized_standby_slots` is a GUC on the primary that lists physical
standby slots which must have received WAL before the primary lets a
logical slot's `confirmed_flush_lsn` advance past it — preventing the
case where the logical consumer is ahead of the failover-target standby.
I don't remember the exact wakeup-chain function names or the third
sync-ready precondition (something about consistent snapshot at
restart_lsn).
