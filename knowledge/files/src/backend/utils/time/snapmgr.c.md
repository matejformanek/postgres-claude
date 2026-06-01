# snapmgr.c

- **Source path:** `source/src/backend/utils/time/snapmgr.c`
- **Lines:** 1971
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `source/src/include/utils/snapmgr.h`, `source/src/include/utils/snapshot.h`, `storage/ipc/procarray.c` (GetSnapshotData, XidInMVCCSnapshot's xip data source), `access/heap/heapam_visibility.c` (the principal consumer), `utils/resowner/resowner.c` (registered-snapshot lifetime)

## Purpose

PostgreSQL's snapshot manager. Owns the *lifecycle* and *visibility-stamp identity* of every `SnapshotData` a backend uses: takes them (delegating actual xid-array population to `procarray.c::GetSnapshotData`), tracks two parallel sets of live snapshots (the ActiveSnapshot stack and the RegisteredSnapshots pairing-heap), bumps and drops `MyProc->xmin` as the oldest snapshot changes, and serializes snapshots across parallel workers and across backends (`pg_export_snapshot` / `SET TRANSACTION SNAPSHOT`). [from-comment, snapmgr.c:1-104]

## Top-of-file comment (verbatim, key passages)

> "The following functions return an MVCC snapshot that can be used in tuple visibility checks: GetTransactionSnapshot, GetLatestSnapshot, GetCatalogSnapshot, GetNonHistoricCatalogSnapshot. Each of these functions returns a reference to a statically allocated snapshot. The statically allocated snapshot is subject to change on any snapshot-related function call, and should not be used directly. Instead, call PushActiveSnapshot() or RegisterSnapshot() to create a longer-lived copy and use that." [from-comment, snapmgr.c:6-18]
>
> "We keep track of snapshots in two ways: those 'registered' by resowner.c, and the 'active snapshot' stack. All snapshots in either of them live in persistent memory. When a snapshot is no longer in any of these lists (tracked by separate refcounts on each snapshot), its memory can be freed." [from-comment, snapmgr.c:20-23]
>
> "These arrangements let us reset MyProc->xmin when there are no snapshots referenced by this transaction, and advance it when the one with oldest Xmin is no longer referenced. For simplicity however, only registered snapshots not active snapshots participate in tracking which one is oldest; we don't try to change MyProc->xmin except when the active-snapshot stack is empty." [from-comment, snapmgr.c:88-94]

## Public surface

- `GetTransactionSnapshot` (271) — workhorse: returns the per-transaction snapshot for the current isolation level; on first call in xact, copies into `FirstXactSnapshot` and registers it. [verified-by-code]
- `GetLatestSnapshot` (353) — refresh `SecondarySnapshot`; rejected during parallel mode. [verified-by-code]
- `GetCatalogSnapshot` / `GetNonHistoricCatalogSnapshot` (384, 406) — special snapshot used for syscache scans; lifetime managed via `pairingheap_add` directly (no resowner, see comment at 421-438). [verified-by-code]
- `InvalidateCatalogSnapshot` (454), `InvalidateCatalogSnapshotConditionally` (476) — drop the catalog snapshot when sinval messages indicate catalog change, or at idle.
- `SnapshotSetCommandId` (490) — propagate CCI into the static snapshots.
- `PushActiveSnapshot` / `PushActiveSnapshotWithLevel` / `PushCopiedSnapshot` (681, 695, 731) — push onto active stack.
- `UpdateActiveSnapshotCommandId` (743) — refcount-asserted in-place CID bump (forbidden in parallel mode).
- `PopActiveSnapshot` (774), `GetActiveSnapshot` (799), `ActiveSnapshotSet` (811).
- `RegisterSnapshot` / `RegisterSnapshotOnOwner` / `Unregister*` (823, 836, 865, 878) — resowner-tracked references; ResourceOwner callback `ResOwnerReleaseSnapshot` (1967) calls `UnregisterSnapshotNoOwner`.
- `AtSubCommit_Snapshot`, `AtSubAbort_Snapshot`, `AtEOXact_Snapshot` (960, 981, 1015) — xact lifecycle hooks.
- `ExportSnapshot` (1114) / `pg_export_snapshot` (1291) / `ImportSnapshot` (1386) — text-format exchange via `pg_snapshots/` files.
- `XactHasExportedSnapshots`, `DeleteAllExportedSnapshotFiles`, `ThereAreNoPriorRegisteredSnapshots`, `HaveRegisteredOrActiveSnapshot` (1573-1643).
- `SetupHistoricSnapshot`, `TeardownHistoricSnapshot`, `HistoricSnapshotActive`, `HistoricSnapshotGetTupleCids` (1668-1702) — logical-decoding hooks; switches `GetCatalogSnapshot` to a fixed historic one.
- `EstimateSnapshotSpace`, `SerializeSnapshot`, `RestoreSnapshot`, `RestoreTransactionSnapshot` (1711-1853) — parallel-worker / shared-mem snapshot transfer (uses `SerializedSnapshotData`).
- `XidInMVCCSnapshot` (1868) — the test consumed by every visibility routine; uses `pg_lfind32` over `xip` / `subxip`; falls back to `SubTransGetTopmostTransaction` when subxip overflowed.

## Static helpers / types

- `ActiveSnapshotElt` (173) — stack node holding `as_snap`, `as_level`, `as_next`. Stack invariant: as_level non-increasing toward stack bottom; list NULL-terminated. [from-comment, snapmgr.c:170-172]
- `pairingheap RegisteredSnapshots` (190) — keyed on `xmin` via static `xmin_cmp` (909).
- `FirstXactSnapshot` (200) — saved RR/SERIALIZABLE first snapshot; pseudo-registered (not in any resowner).
- `ExportedSnapshot` + `exportedSnapshots` List (206-213) — exported snapshots are pseudo-registered too.
- `SerializedSnapshotData` (251) — the subset of fields shipped across processes (xmin, xmax, xcnt, subxcnt, suboverflowed, takenDuringRecovery, curcid).
- `snapshot_resowner_desc` (224) — ResourceOwner descriptor; `release_phase = RESOURCE_RELEASE_AFTER_LOCKS`, `release_priority = RELEASE_PRIO_SNAPSHOT_REFS`.

## Key invariants

- **Statically allocated snapshots (`CurrentSnapshotData`, `SecondarySnapshotData`, `CatalogSnapshotData`) are clobbered by any snapshot-taking call.** Callers that need the snapshot to outlive subsequent calls must `PushActiveSnapshot` (which calls `CopySnapshot` because `!snapshot->copied`) or `RegisterSnapshot` (which copies if not already copied). [verified-by-code, snapmgr.c:705-713, 845]
- **A snapshot's storage is freed when `regd_count == 0 && active_count == 0`.** Checked in `PopActiveSnapshot`, `UnregisterSnapshotNoOwner`, `AtSubAbort_Snapshot`. [verified-by-code, snapmgr.c:785-787, 898-902, 998-1000]
- **`RegisteredSnapshots` is a pairing-heap keyed on `xmin`.** Top is smallest xmin; `SnapshotResetXmin` reads `pairingheap_first` to advance `MyProc->xmin` upward but never backward. [verified-by-code, snapmgr.c:909-921, 936-955]
- **`MyProc->xmin` is only re-evaluated when the active stack is empty.** "we don't try to change MyProc->xmin except when the active-snapshot stack is empty." This means an active-only snapshot's xmin keeps procarray honest until popped, but you do *not* see xmin advance mid-stack. [from-comment, snapmgr.c:91-94; verified-by-code, snapmgr.c:941-942]
- **`PushActiveSnapshotWithLevel` requires `snap_level >= ActiveSnapshot->as_level`.** Stack must be in non-decreasing nest level order from top. [verified-by-code, snapmgr.c:701]
- **CatalogSnapshot, FirstXactSnapshot, and exported snapshots are in `RegisteredSnapshots` but NOT owned by any ResourceOwner** — they are "pseudo-registered" via direct `pairingheap_add` and removed by hand in their respective teardown paths. [from-comment, snapmgr.c:65-87; verified-by-code, 426-438, 327-328, 1188-1189]
- **Catalog snapshot must be invalidated whenever a system catalog change occurs**, and is invalidated at the top of `GetTransactionSnapshot` to keep it no older than the xact snapshot. [from-comment, snapmgr.c:134-136; verified-by-code, snapmgr.c:300, 341]
- **First-snapshot copy is mandatory under `IsolationUsesXactSnapshot()` (REPEATABLE READ / SERIALIZABLE)** because the snapshot must live to xact end. [verified-by-code, snapmgr.c:316-329]
- **Snapshots cannot be taken during parallel mode (`GetTransactionSnapshot`, `GetLatestSnapshot`)**: the parallel leader exports its snapshot via `Serialize`/`Restore` and workers call `RestoreTransactionSnapshot`. [verified-by-code, snapmgr.c:305-307, 360-362]
- **`XidInMVCCSnapshot` does NOT include the caller's own top xid / subxids** — comment at 1862-1867 says callers must check `TransactionIdIsCurrentTransactionId` first (or know the xid can't be theirs). This is the same ordering rule that `heapam_visibility.c` documents at lines 177-198: check current-xact, then in-progress (here: `XidInMVCCSnapshot`), then committed. [from-comment, snapmgr.c:1861-1867]
- **`ImportSnapshot` requires `xmin` and `xmax` to be normal xids and same database** (vacuum's per-DB OldestXmin would otherwise allow data loss). [verified-by-code, snapmgr.c:1525-1563]

## Functions of note (deep-read)

1. **`GetTransactionSnapshot`** (271) — branches on `HistoricSnapshotActive`, on `!FirstSnapshotSet` (first call: clear catalog snapshot, assert empty heap, special-case xact-snapshot isolation by copying + registering), else returns `CurrentSnapshot` directly (RR/SER) or refreshes via `GetSnapshotData` (RC). [verified-by-code]
2. **`SetTransactionSnapshot`** (510) — static; the actual installer used by both `ImportSnapshot` and `RestoreTransactionSnapshot`. Calls `GetSnapshotData` first to set up arrays + GlobalVis state, then overwrites xmin/xmax/xip/subxip from the source snapshot, then calls `ProcArrayInstallRestoredXmin` or `ProcArrayInstallImportedXmin` to *atomically* re-install xmin without letting global xmin go backwards. **The "xmin backwards" guard is the load-bearing safety property here.** [verified-by-code, snapmgr.c:550-577]
3. **`CopySnapshot`** (607) — single palloc in TopTransactionContext for `SnapshotData` + `xip[]` + (conditional) `subxip[]`; subxip skipped if overflowed AND not taken during recovery (recovery snapshots store everything in subxip — see comments at 641-651, 1928-1932).
4. **`PushActiveSnapshot`** (681) — *always* copies if the snap is static or `!copied`, *never* copies an already-active or already-registered (`copied=true`) snapshot — just bumps `active_count`. This is the load-bearing rule for snapshot reuse across portals.
5. **`SnapshotResetXmin`** (937) — only runs when active stack empty; reads `pairingheap_first` of `RegisteredSnapshots` and advances `MyProc->xmin` forward (`TransactionIdPrecedes` guard prevents going backward). Storing an xid is assumed atomic (no lock). [from-comment, snapmgr.c:923-934]
6. **`ExportSnapshot`** (1114) — disallows subtransactions (importer can't tell if a subxact is still running, snapmgr.c:1149-1156); writes `vxid/pid/dbid/iso/ro/xmin/xmax/xip/sof/sxp/rec` lines to `pg_snapshots/<vxidProcNumber>-<vxidLxid>-<seq>`. Files are not fsync'd ("file need not survive a system crash"). Includes the exporter's own topXid in xip[] because `GetSnapshotData` excluded it.
7. **`XidInMVCCSnapshot`** (1868) — fast-path range check on xmin/xmax; otherwise `pg_lfind32` over `subxip` (if not overflowed) then `xip`; on overflow falls back to `SubTransGetTopmostTransaction(xid)` to compare top-level only. In-recovery snapshots store all xids in subxip (xip is empty).

## Snapshot lifecycle (mental model)

Five overlapping sets of snapshots a backend may hold; each has a different freeing rule.

- **Statically allocated** (`CurrentSnapshotData`, `SecondarySnapshotData`, `CatalogSnapshotData`, plus `SnapshotSelfData/AnyData/ToastData`): never freed; clobbered on next snapshot-taking call. Cannot be pushed/registered without first being copied (PushActiveSnapshot/RegisterSnapshot detect `!copied` and copy).
- **Active-only** (`active_count > 0`, `regd_count == 0`): freed when popped; ResetXmin runs after pop but does nothing because stack is non-empty in general — only the *final* pop drops `MyProc->xmin`.
- **Registered-only** (`regd_count > 0`, `active_count == 0`): listed in `RegisteredSnapshots` heap; freed when last `UnregisterSnapshot*` runs or ResourceOwner releases. Their xmins govern `MyProc->xmin` after the active stack is empty.
- **Both active and registered**: freed only when both refcounts hit zero.
- **Pseudo-registered** (FirstXactSnapshot under RR/SER, CatalogSnapshot, exported snapshots): in `RegisteredSnapshots` (so they restrain `MyProc->xmin`) but no ResourceOwner edge. Their memory rides on `TopTransactionContext` reset at xact end.

## Cross-references

- **MVCC visibility:** `heapam_visibility.c::HeapTupleSatisfiesMVCC` (line 939) is the principal consumer of snapshots. Its top comment (heapam_visibility.c:177-198) states the canonical xid-vs-snapshot ordering: check `TransactionIdIsCurrentTransactionId`, then `XidInMVCCSnapshot` (which this file implements at 1868), then `TransactionIdDidCommit`. Snapmgr's `XidInMVCCSnapshot` is the in-progress predicate in that chain. Cross-link to `knowledge/files/src/backend/access/heap/heapam_visibility.c.md` §"Key invariants and locking". [verified-by-code]
- **GetSnapshotData:** lives in `storage/ipc/procarray.c`; reads ProcArray under `ProcArrayLock` to fill xmin/xmax/xip[]/subxip[] and to update `MyProc->xmin`. Snapmgr's calls at 322/331/343/374/424/530 are the points where this happens.
- **ResourceOwner integration:** descriptor at snapmgr.c:224; callback at 1967. See `utils/resowner/resowner.c` and the lmgr knowledge doc.
- **Parallel workers:** `Serialize/Restore/RestoreTransactionSnapshot` plus `ProcArrayInstallRestoredXmin` (procarray.c) form the leader→worker xmin handoff.
- **Logical decoding:** `SetupHistoricSnapshot` + the `tuplecid_data` HTAB serve `HeapTupleSatisfiesHistoricMVCC` (heapam_visibility.c:1504) and `ResolveCminCmaxDuringDecoding` (reorderbuffer.c).
- **Predicate locking:** `GetSerializableTransactionSnapshot` / `SetSerializableTransactionSnapshot` (predicate.c) wrap snapmgr's first-snapshot path under SSI. Cross-link `knowledge/files/src/backend/storage/lmgr/predicate.c.md`.

## Open questions

- The `SnapshotSetCommandId` end-of-comment "Should we do the same with CatalogSnapshot?" (line 499) is left unanswered in code; behavior currently is that catalog snapshots do not get CID propagation. [unverified — whether any consumer relies on this]
- Exact semantics of `snapXactCompletionCount` (set to 0 in Copy/Restore but read by `GetSnapshotData` in procarray.c) — comment at snapshot.h:204-209 says it lets `GetSnapshotData` skip rebuilding a static snapshot when no xacts have completed since. I have not traced procarray.c to confirm. [unverified]
- Whether `HaveRegisteredOrActiveSnapshot` is race-free with concurrent catalog-snapshot invalidation arriving via sinval — comment at 1639-1656 hints it can transition under our feet. [unverified — read-only race only]

## Confidence tag tally

`[verified-by-code]=14 [from-comment]=8 [from-readme]=0 [inferred]=0 [unverified]=3`
