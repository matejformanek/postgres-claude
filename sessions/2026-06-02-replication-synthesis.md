# 2026-06-02 — replication spine synthesis

**Type:** interactive (worktree `ft_corpus_replication`).
**Outcome:** `knowledge/subsystems/replication.md`, 979 lines, 70
confidence-tagged cites, verified against source commit `4b0bf0788b0`.

## What this session did

Closed the priority-13 spine gap from `pg-claude-plan.md` §5.3. The
replication subsystem had 28 per-file docs + headers omnibus already
(`README`, `walsender.c`, `walreceiver.c`, `slot.c`, `syncrep.c`,
plus 18 docs under `logical/`), but no directory-level synthesis.

The synthesis covers:

1. **Four layered services** (physical streaming, sync rep, logical
   decoding, logical replication apply) framed as one progression with
   replication slots as the crash-safe state object underneath all of
   them.
2. **Four PG18-era additions** that bulked up the synthesis: failover
   slots, conflict detection (8 conflict types), retain dead tuples
   (5-phase state machine in apply worker), sequence sync.
3. **All key data structures** with header anchors: `WalSnd`,
   `WalSndCtl`, `WalRcvData`, `ReplicationSlot`, `ReplicationState`
   (origin), `LogicalDecodingContext`, `SnapBuildState`,
   `ReorderBufferTXN`/`ReorderBufferChange`, `LogicalRepWorker`,
   `LogicalRepRelMapEntry`, sync-rep `PGPROC` fields.
4. **30 invariants** tagged INV-rep-* / INV-slot-* / INV-syncrep-* /
   INV-snap-* / INV-rb-* / INV-decode-* / INV-origin-* / INV-pa-* /
   INV-tablesync-* / INV-twophase-* / INV-slotsync-* / INV-failover-* /
   INV-rdt-*. Most load-bearing:
   - INV-rep-2: postmaster does NOT wait for walsenders before shutdown
     checkpoint — they stop after, so standbys get the checkpoint record.
   - INV-syncrep-1: `SyncRepWaitForLSN` is uncancellable — cancel only
     WARNs + disconnects, never rolls back.
   - INV-snap-1: logical decoding protects ONLY catalog rows via
     `catalog_xmin`; user-table rows can still be removed.
   - INV-snap-3: CONSISTENT is the only state in which commits are
     replayed.
   - INV-rb-1: spill-to-disk picks the LARGEST txn (O(log n) max-heap).
   - INV-rb-3: toast chunks always immediately precede their row in WAL
     within a top-level txn.
   - INV-origin-1: 2-byte id because origins go into every commit
     record's WAL.
   - INV-origin-2: `remote_lsn` in commit record means async apply is
     crash-safe without `synchronous_commit`.
   - INV-pa-1: parallel-apply uses session-level lmgr locks so LA↔PA
     waits are visible to deadlock detector; deliberately NOT
     `XactLockTableWait` (prepared txns count as in-progress).
   - INV-slot-3: invalidated state fsync'd BEFORE slot release.
   - INV-rdt-1: `pg_conflict_detection` slot created lazily by launcher
     at first subscription with `retain_dead_tuples=true`.
5. **Full control flow** for each service: physical streaming sequence
   diagram, slot lifecycle, sync-rep wait/release, logical decoding
   pipeline (decode → snapbuild → reorderbuffer → output plugin →
   walsender), apply worker dispatch, streamed-xact strategies, parallel
   apply, tablesync 7-state machine, two-phase, failover-slot sync,
   conflict detection.
6. **Most-cited file:line table** (§11) — 50+ anchors.
7. **§9 Open Questions** — 6 items (walreceiver reconnection,
   `two_phase_at` in failover edge cases, slot-sync demotion, etc.).

## Verification

All called-out line numbers checked with `grep -n` against the live
source at commit `4b0bf0788b0`:
- `walsender.c`: `StartReplication:844`, `StartLogicalReplication:1492`,
  `WalSndWaitForWal:1886`, `exec_replication_command:2065`,
  `ProcessRepliesIfAny:2321`, `WalSndLoop:3008`, `XLogSendPhysical:3322`,
  `XLogSendLogical:3632`.
- `slot.c`: `ReplicationSlotCreate:378`, `Acquire:629`, `Release:769`,
  `ReplicationSlotsComputeRequiredXmin:1220`,
  `InvalidatePossiblyObsoleteSlot:1974`, `Invalidate*:2214`,
  `CheckPointReplicationSlots:2318`.
- `decode.c:89` `LogicalDecodingProcessRecord`.
- `snapbuild.c:944, :1140, :1242` (`CommitTxn`, `ProcessRunningXacts`,
  `FindSnapshot`).
- `reorderbuffer.c:2212, :2882` (`ProcessTXN`, `Commit`).
- `worker.c:3797, :4003` (`apply_dispatch`, `LogicalRepApplyLoop`).

## What I did NOT do

- Did not register new rows in `files-examined.md` — all 28 files +
  headers already in the registry from the original deep-read pass.
- Did not run replication tests, set up subscribers, or attach to a
  cluster.
- Did not deeply trace `walreceiver.c:WalReceiverMain` state machine
  (O1 in Open Questions).
- Did not trace cross-version (PG 14 → 15 → 16 → 17 → 18) on-the-wire
  protocol differences — just noted the structural feature additions.

## Ledger updates

- `progress/coverage.md` — appended `replication` row.
- `progress/STATE.md` — bumped subsystem count 16→19 (23 incl.
  data-structures), updated Phase + Last-activity, added this session
  log + the earlier parser-rewrite + nbtree sessions to Recent.

## Followup candidates

- §9 O1: trace `WalReceiverMain` state machine end-to-end; produce a
  small data-structures doc on `WalRcvData` lifecycle.
- §9 O2: read `slotsync.c` skip-reason interactions with `two_phase_at`
  in detail.
- §9 O4: enumerate the races behind `InvalidatePossiblyObsoleteSlot`'s
  cause-recheck.
- Spike: add a `knowledge/data-structures/replication-slot.md` zooming
  in on the slot ↔ catalog_xmin ↔ vacuum-horizon interaction (the
  single most-mentioned mechanism in this subsystem).
- Spike: cross-link `knowledge/architecture/replication.md` to this new
  subsystem doc — the architecture doc is the high-level narrative;
  this doc is the directory-level deep dive.

## Why this matters

Replication is the second-largest source of subtle "confident-but-wrong"
claims (after locking) — operationally because the four services
interact in non-obvious ways, and architecturally because every PG
release has added features here (logical replication PG 10, streamed
xacts PG 14, two-phase logical PG 14, parallel apply PG 16, failover
slots PG 17, conflict detection PG 18, RDT PG 18, sequence sync PG 18).

Concrete mistakes this synthesis is structured to catch:

- Treating `SyncRepWaitForLSN` cancel as ordinary cancel (it's WARN +
  disconnect, never rollback).
- Claiming logical decoding protects user-table rows from vacuum (it
  doesn't — only catalog).
- Confusing physical-slot `restart_lsn` semantics with logical-slot
  `confirmed_flush_lsn`.
- Assuming reorderbuffer evicts oldest txn (it evicts largest).
- Building a parallel-apply replacement using a plain LWLock (would
  hide LA↔PA deadlocks from the detector).
- Citing `XactLockTableWait` for parallel-apply ordering (deliberately
  avoided because of prepared-txn semantics).
- Treating the apply worker's `replorigin_session_origin_lsn` as a
  LOCAL LSN (it's the REMOTE LSN you'd resume from).
- Forgetting that tablesync uses `CRS_USE_SNAPSHOT`, not
  `CRS_EXPORT_SNAPSHOT`.
- Treating `pg_conflict_detection` as a user-creatable slot
  (`ReplicationSlotAcquire` refuses to bind it).
