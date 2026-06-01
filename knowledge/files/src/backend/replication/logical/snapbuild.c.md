# `src/backend/replication/logical/snapbuild.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** 2080
- **Source:** `source/src/backend/replication/logical/snapbuild.c`

## Purpose

Builds "historic" MVCC snapshots over catalog tables by interpreting the
WAL stream, so logical decoding can read catalog rows as they appeared at
the LSN of any record being decoded. Reuses Hot-Standby visibility infra
but customized for decoding's needs. Only catalog rows are protected
(via the slot's catalog xmin); user-table rows can still be removed.
[from-comment] (`snapbuild.c:1-27`)

## State machine

`SnapBuildState`: START → BUILDING_SNAPSHOT → FULL_SNAPSHOT →
CONSISTENT. Transitions driven by `xl_running_xacts` records:

1. **START → BUILDING_SNAPSHOT** on first `xl_running_xacts` whose xmin
   is above the safe horizon (or directly to CONSISTENT if no running
   xacts).
2. **BUILDING → FULL** on next running_xacts after all initially-running
   xacts have finished. Now any *newly-started* xact can be decoded end
   to end.
3. **FULL → CONSISTENT** when the previously-running xacts from step 2
   have all finished. Only commits after CONSISTENT will be replayed.

State diagram is drawn in the top-of-file comment (`:65-96`). [from-comment]

## Why a special snapshot?

Catalog rows have `cmin`/`cmax` in their tuples but those are reset on
crash recovery, and combocids only exist in the originating backend's
RAM. Solution: heapam writes `XLOG_HEAP2_NEW_CID` records for catalog
modifications; reorderbuffer keeps a `(ctid → cmin/cmax)` map; visibility
checks consult that map instead of the tuple. (`:40-53`) [from-comment]

## Spine functions

- `AllocateSnapshotBuilder` (`:189`) — at slot creation, with
  `xmin_horizon`, `start_lsn`, and (since PG 14) `two_phase_at`.
- `SnapBuildProcessRunningXacts` (`:1140`) — drives the state machine.
- `SnapBuildFindSnapshot` (`:1242`) — main transition logic given a
  `running_xacts` record.
- `SnapBuildCommitTxn` (`:944`) — on each commit, decide whether the xid
  modified catalogs (and thus enters the committed-cat-xacts list).
- `SnapBuildProcessNewCid` (`:692`) — feed cmin/cmax mapping into RB.
- `SnapBuildProcessChange` (`:642`) — pre-decoded-tuple hook; returns
  true if the change should be enqueued.
- `SnapBuildBuildSnapshot` (`:364`) — assemble a `Snapshot` struct from
  the tracked committed-cat-xacts set.
- `SnapBuildSerialize` / `Restore` (`:1501`, `:1845`) — persist /
  reconstruct snapshot state to `pg_logical/snapshots/` so subsequent
  decoding sessions don't have to walk WAL from scratch.
- `CheckPointSnapBuild` (`:1974`) — drive periodic serialization,
  prune old serialized snapshot files.
- `SnapBuildExportSnapshot` (`:542`) — produces a snapshot id that an
  ordinary backend can `SET TRANSACTION SNAPSHOT` against — used by
  `pg_dump` parallelism and initial COPY in subscriptions.

## Static state

- `SavedResourceOwnerDuringExport` (`:154`) — saved/restored because
  starting a transaction for export wipes the resowner.
- `ExportInProgress` flag.

## Open questions

- The `two_phase_at` LSN was added to delay decoding of 2PC PREPAREs
  until catalogs caught up. Exact semantics in failover-slot edge cases
  not verified here. [unverified]
