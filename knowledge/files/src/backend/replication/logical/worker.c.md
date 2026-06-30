# `src/backend/replication/logical/worker.c`

- **Last verified commit:** `031904048aa2`
- **Lines:** 6435 (largest in subsystem; the apply-worker behemoth)
- **Source:** `source/src/backend/replication/logical/worker.c`

## Purpose

The **apply worker** on the subscriber side of logical replication. Talks
walsender protocol to the publisher via libpqwalreceiver, decodes the
incoming `logicalrep` message stream, and applies row changes through
the executor. Also coordinates the table-sync workers, the
parallel-apply workers, and the conflict-detection xid retention machinery.
[from-comment] (`worker.c:1-21`)

## Architectural sub-systems within this file

The top-of-file comment partitions the code into named sections (`STREAMED
TRANSACTIONS`, `TWO_PHASE TRANSACTIONS`, `FAILOVER`, `RETAIN DEAD
TUPLES`). [from-comment]

### Streamed transactions (PG 14+)

Two strategies for streamed-from-publisher large xacts:

1. **Spill to BufFiles** (`subscription.streaming = on`). BufFile
   chosen over plain tempfiles for (a) >2GB support, (b) automatic
   cleanup on error, (c) survives across local-xact boundaries via
   FileSet so a stream can stay open between START/STOP. Filenames
   embed both the remote XID and the subscription OID to disambiguate
   workers. Subxact aborts truncate the file using tracked offsets.
   (`worker.c:23-55`)
2. **Parallel apply** (`subscription.streaming = parallel`). Hand off
   to a parallel apply worker via shm_mq. See
   `applyparallelworker.c.md`. (`worker.c:57-61`)

### Two-phase transactions

Subscription `two_phase` is tri-state: DISABLED, PENDING, ENABLED.
PENDING is a startup-only state: even if user requested `two_phase=on`,
we delay enabling until *all* tablesyncs are READY (so we can't get an
"empty prepare" because an apply skipped the inserts during initial copy).
ProcessSyncingTablesForApply restarts the worker when the flip is due.
Unique-per-subscription GID: `(suboid, xid)` to avoid cross-subscription
deadlocks when one publisher has many subscriptions on one subscriber.
(`worker.c:63-127`) [from-comment]

### Failover slot integration (PG 17+)

`failover=true` on CREATE SUBSCRIPTION arranges for the logical slot to
be synced to physical standbys, so promotion preserves the subscription
position. (`worker.c:129-135`)

### Retain Dead Tuples (PG 18+)

If `retain_dead_tuples=true`, the apply worker maintains an
`oldest_nonremovable_xid` in shared memory so vacuum can't reclaim
versions still needed for `update_deleted` and origin-differs conflict
detection. The launcher aggregates per-worker xmins into the internal
`pg_conflict_detection` slot. Five-phase RDT state machine
(GET_CANDIDATE_XID → REQUEST_PUBLISHER_STATUS →
WAIT_FOR_PUBLISHER_STATUS → WAIT_FOR_LOCAL_FLUSH → loop;
STOP/RESUME_CONFLICT_INFO_RETENTION when `max_retention_duration` would
be exceeded). Not supported when publisher is a physical standby or
has its own subscriptions. (`worker.c:136-227`)

## Spine functions

- `ApplyWorkerMain` (entry; called by bgworker harness) — handshake,
  acquire slot, enter `LogicalRepApplyLoop`.
- `LogicalRepApplyLoop` (`:4003`) — receive `XLogData`/`PrimaryKeepalive`/
  `PrimaryStatusUpdate` messages from publisher; dispatch via
  `apply_dispatch`; send_feedback periodically.
- `apply_dispatch` (`:3797`) — switch over `LogicalRepMsgType` byte (B,
  C, I, U, D, T, R, Y, M, S/E/A/p/c for stream messages, b/P/K/r for
  2PC).
- `apply_handle_{begin,commit,prepare,…}` (`:1228+`) — per-message
  appliers.
- `apply_handle_{insert,update,delete,truncate}` (`:2650`, `:2807`,
  `:3034`, `:3669`) — DML executor invocations through
  `apply_handle_*_internal` and `FindReplTupleInLocalRel` (`:3196`).
- `apply_handle_tuple_routing` (`:3373`) — partitioned-table fanout.
- `handle_streamed_transaction` (`:784`) — spill-to-disk path for
  streamed xacts.
- `slot_store_data` / `slot_modify_data` (`:1024`, `:1131`) — convert
  remote LogicalRepTupleData → local TupleTableSlot through
  `LogicalRepRelMapEntry.attrmap`.
- `should_apply_changes_for_rel` (`:688`) — per-rel filter during the
  state where some tables are still tablesyncing.
- RDT state-machine pieces: `maybe_advance_nonremovable_xid` (`:4409`),
  `get_candidate_xid` (`:4475`), `request_publisher_status` (`:4538`),
  `wait_for_publisher_status` (`:4577`), `wait_for_local_flush` (`:4636`),
  `stop_conflict_info_retention` (`:4826`), `resume_conflict_info_retention`
  (`:4864`).
- `send_feedback` (`:4319`) — emit `r` standby-status messages to
  publisher.

## Origins

Each subscription has a replication origin named via
`ReplicationOriginNameForLogicalRep(suboid, relid)` (`:648`) — for
apply-worker it's per-sub; tablesync workers use per-(sub,rel) names so
their progress can be tracked individually.

## Coupling

- Calls `pa_*` in `applyparallelworker.c` to fan out streamed xacts.
- Calls into `tablesync.c` for initial copy + state transitions.
- Calls into `conflict.c` to report conflicts and set up arbiter indexes.
- Talks libpqwalreceiver (loaded module) for the network side.

## Synthesized by
<!-- backlinks:auto -->
- [architecture/replication.md](../../../../../architecture/replication.md)
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
- [subsystems/replication.md](../../../../../subsystems/replication.md)
- [idioms/apply-handlers-insert-update-delete.md](../../../../../idioms/apply-handlers-insert-update-delete.md)
- [idioms/apply-streaming-and-parallel.md](../../../../../idioms/apply-streaming-and-parallel.md)
- [idioms/apply-worker-loop-and-dispatch.md](../../../../../idioms/apply-worker-loop-and-dispatch.md)
- [idioms/apply-worker-loop.md](../../../../../idioms/apply-worker-loop.md)

## Appears in scenarios

<!-- scenarios:auto:begin -->

- [Scenario — Add a new replication / logical-decoding message](../../../../../scenarios/add-new-replication-message.md)

<!-- scenarios:auto:end -->

