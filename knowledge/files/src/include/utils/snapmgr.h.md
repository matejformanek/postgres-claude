# snapmgr.h

- **Source path:** `source/src/include/utils/snapmgr.h`
- **Lines:** 148
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `utils/snapshot.h` (SnapshotData), `backend/utils/time/snapmgr.c`

## Purpose

Declarations for snapmgr.c plus the three statically allocated special snapshots (`SnapshotSelf`, `SnapshotAny`, `SnapshotToast` — TOAST is now retrieved through `get_toast_snapshot()` per header note line 35) and the helper macros for the two snapshot types that must be locally allocated by the caller (`InitDirtySnapshot`, `InitNonVacuumableSnapshot`). [verified-by-code]

## Top-of-file comment

> "snapmgr.h — POSTGRES snapshot manager" — one-liner. [from-comment, snapmgr.h:3-5]

## Exported globals

- `FirstSnapshotSet` (22) — has the current xact taken its first snapshot? Used by snapmgr.c to decide whether to copy on first call.
- `TransactionXmin`, `RecentXmin` (24-25) — updated by `GetSnapshotData`; the latest "all xids before this are surely committed" lower bound.
- `SnapshotSelfData`, `SnapshotAnyData`, `SnapshotToastData` (28-30) — static templates accessed via the `SnapshotSelf`/`SnapshotAny` macros (TOAST is not directly exposed because callers should use `get_toast_snapshot()`).

## Macros

- `InitDirtySnapshot(s)` (42) — sets `snapshot_type = SNAPSHOT_DIRTY`. The struct must be a local because DIRTY snapshots get xmin/xmax/speculativeToken written into them as output.
- `InitNonVacuumableSnapshot(s, vistestp)` (50) — sets `snapshot_type = SNAPSHOT_NON_VACUUMABLE` and `vistest = vistestp`.
- `IsMVCCSnapshot(s)`, `IsHistoricMVCCSnapshot(s)`, `IsMVCCLikeSnapshot(s)` (59, 67, 74) — type predicates.

## Exported functions

(Grouped by purpose; all defined in snapmgr.c.)

- **Take/refresh:** `GetTransactionSnapshot`, `GetLatestSnapshot`, `SnapshotSetCommandId`.
- **Catalog:** `GetCatalogSnapshot`, `GetNonHistoricCatalogSnapshot`, `InvalidateCatalogSnapshot`, `InvalidateCatalogSnapshotConditionally`.
- **Active stack:** `PushActiveSnapshot`, `PushActiveSnapshotWithLevel`, `PushCopiedSnapshot`, `UpdateActiveSnapshotCommandId`, `PopActiveSnapshot`, `GetActiveSnapshot`, `ActiveSnapshotSet`.
- **Registered:** `RegisterSnapshot`, `UnregisterSnapshot`, `RegisterSnapshotOnOwner`, `UnregisterSnapshotFromOwner`.
- **Xact lifecycle:** `AtSubCommit_Snapshot`, `AtSubAbort_Snapshot`, `AtEOXact_Snapshot`.
- **Import/export:** `ImportSnapshot`, `XactHasExportedSnapshots`, `DeleteAllExportedSnapshotFiles`, `ExportSnapshot`.
- **Probes:** `WaitForOlderSnapshots`, `ThereAreNoPriorRegisteredSnapshots`, `HaveRegisteredOrActiveSnapshot`.
- **GlobalVis** (declared here but implemented in `storage/ipc/procarray.c` — header note at lines 112-114): `GlobalVisTestFor`, `GlobalVisTestIsRemovableXid` (and full-xid variant), `GlobalVisCheckRemovableXid` (full-xid variant), `GlobalVisTestXidConsideredRunning`.
- **Table-AM helper:** `XidInMVCCSnapshot` (133).
- **Historic / logical decoding:** `HistoricSnapshotGetTupleCids`, `SetupHistoricSnapshot`, `TeardownHistoricSnapshot`, `HistoricSnapshotActive`.
- **Parallel-worker transfer:** `EstimateSnapshotSpace`, `SerializeSnapshot`, `RestoreSnapshot`, `RestoreTransactionSnapshot`.

## Cross-references

- GlobalVis* live in procarray.c per the header's note ("they're intimately linked to the procarray contents, but thematically they better fit into snapmgr.h", lines 112-114). This is a deliberate split.
- Every function listed has a deep-dive at `knowledge/files/src/backend/utils/time/snapmgr.c.md`.

## Open questions

- None — header is a pure declaration surface.

## Confidence tag tally

`[verified-by-code]=2 [from-comment]=3 [from-readme]=0 [inferred]=0 [unverified]=0`

## Synthesized by
<!-- backlinks:auto -->
- [data-structures/snapshot-lifecycle.md](../../../../data-structures/snapshot-lifecycle.md)
- [idioms/snapshot-acquisition.md](../../../../idioms/snapshot-acquisition.md)
