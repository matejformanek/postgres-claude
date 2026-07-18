# src/include/replication/snapbuild.h

## Purpose

Public interface to the **historic snapshot builder** for logical
decoding. The snapbuild module observes WAL records (commits, aborts,
running-xacts snapshots, new-CID records) to reconstruct, after the
fact, the catalog snapshot that was visible at each LSN — so the
decoding code can look up `pg_class`, `pg_attribute`, type info, etc.
as they appeared when each tuple was originally written. Source pin
`4b0bf0788b066a4ca1d4f959566678e44ec93422`.

## Role in PG

Logical decoding cannot use the *current* catalog because schema can
have changed between the WAL record's commit time and now. Snapbuild
walks the WAL from a slot's `restart_lsn` forward, tracks which xacts
are in-flight, and at each transition through SNAPBUILD_START →
BUILDING_SNAPSHOT → FULL_SNAPSHOT → CONSISTENT publishes a usable
historic snapshot to the decoder (via `SnapBuildGetOrBuildSnapshot`).
The CONSISTENT state is what gates calls to the output plugin's
`begin_cb` / `change_cb` / `commit_cb` — until CONSISTENT, decoded
changes are silently dropped. Periodic checkpoints serialize the
snapbuild state to `pg_replslot/<slot>/snap-<lsn>.snap` for restart.

## Key types/struct fields

- `SnapBuild` (line 22) — opaque forward declaration; the real struct is
  in `snapbuild_internal.h`. [verified-by-code]
- `enum SnapBuildState` (lines 30-59) — `SNAPBUILD_START = -1`,
  `SNAPBUILD_BUILDING_SNAPSHOT = 0`, `SNAPBUILD_FULL_SNAPSHOT = 1`,
  `SNAPBUILD_CONSISTENT = 2`. Comment line 27-29 warns to keep the
  `pg_logicalinspect` extension's `get_snapbuild_state_desc()` in sync.
  Numeric values matter for the extension's display. [from-comment]
- `AllocateSnapshotBuilder` (lines 65-69) — constructor; takes
  `xmin_horizon` (the slot's reserved xmin),`start_lsn`,
  `need_full_snapshot` (vs catalog-only), `in_slot_creation`,
  `two_phase_at`. [verified-by-code]
- `SnapBuildInitialSnapshot` / `SnapBuildExportSnapshot` (lines 74-75) —
  the path that makes `CREATE_REPLICATION_SLOT ... EXPORT_SNAPSHOT`
  work: returns a snapshot whose `xmin/xmax` correspond to the slot's
  consistent point, then exports it to the current transaction so a
  client can `SET TRANSACTION SNAPSHOT 'snapshot-id'` and do an initial
  copy at the same horizon. [from-comment]
- `SnapBuildCommitTxn`, `SnapBuildProcessChange`,
  `SnapBuildProcessNewCid`, `SnapBuildProcessRunningXacts` (lines 86-95)
  — the four WAL-event hooks called by the decoder for each relevant
  record type. [verified-by-code]
- `SnapBuildSerializationPoint` (line 96) — checkpoint hook; writes the
  current `SnapBuild` to a `*.snap` file in `pg_replslot/<slot>/`.
  [verified-by-code]
- `SnapBuildSnapshotExists(XLogRecPtr lsn)` (line 98) — predicate used
  during slot creation to find an already-serialized snapshot to
  fast-start from. [from-comment]
- `SnapBuildGetTwoPhaseAt` / `SnapBuildSetTwoPhaseAt` (lines 83-84) —
  the LSN past which two-phase decoding is active; below this LSN
  prepared xacts are decoded only as monolithic commits.
  [verified-by-code]
- `SnapBuildXactNeedsSkip` (line 82) — predicate that lets the decoder
  drop xacts that committed before `start_decoding_at`.
  [verified-by-code]

## Phase D notes

The path from "raw WAL bytes" to "tuple decoded into the output plugin"
all flows through snapbuild's notion of consistency. A bug that returns
CONSISTENT prematurely would feed the output plugin tuples decoded with
the *wrong* catalog snapshot — fields shifted, types misinterpreted.
This is the class of bug that produces "wrong data, no error" — the
worst kind for downstream subscribers.

The CONSISTENT-state gate is the only thing standing between a
just-created slot and full visibility into ALL ongoing transactions in
the database, including those started by other users. Once CONSISTENT,
the slot's owner sees row-level changes for tables they may not have
SELECT on — logical decoding bypasses row-level security and table
privileges by design (the `pgoutput` plugin partially compensates via
publication filters but custom plugins need not).

`SnapBuildExportSnapshot` is the export that backs
`pg_export_snapshot()` semantics for slot creation; the returned
snapshot id can be passed to a parallel session for initial-sync COPY.
There is no ACL check tying the exported snapshot to the slot's role —
once exported, any backend that knows the id and is in
`REPEATABLE READ` can adopt it.

## Potential issues

- [ISSUE-trust-boundary: any role with REPLICATION can create a logical
  slot which, once CONSISTENT, can decode every row change in the
  database regardless of per-table SELECT privilege or RLS
  (sev=likely)]
- [ISSUE-state-transition: the SnapBuildState enum values are
  load-bearing (the pg_logicalinspect extension parses them as
  integers via `get_snapbuild_state_desc`); reordering or renumbering
  silently breaks the extension across versions (sev=maybe)]
- [ISSUE-undocumented-invariant: header does not state which lock
  protects `SnapBuild`; it's implicitly per-slot (only the slot's
  decoder touches it) but the contract isn't spelled out for future
  multi-reader designs (sev=unlikely)]
- [ISSUE-info-disclosure: exported snapshot id from
  `SnapBuildExportSnapshot` has no per-id ACL beyond the publishing
  role's session lifetime — adopting backend just needs the id string
  (sev=maybe)]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `include-replication`](../../../../issues/include-replication.md)
<!-- issues:auto:end -->

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/replication.md](../../../../subsystems/replication.md)
