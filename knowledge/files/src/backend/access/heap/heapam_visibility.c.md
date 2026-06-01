# heapam_visibility.c

- **Source path:** `source/src/backend/access/heap/heapam_visibility.c`
- **Lines:** 1753
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `htup_details.h` (the bit semantics it interprets), `heapam.h` (its prototypes), `storage/procarray.c` (xact-in-progress), `access/transam/transam.c` (commit-log), `utils/time/snapmgr.c` (snapshots)

## Purpose

Implements every MVCC visibility test in PostgreSQL. Given a `HeapTuple` and a `Snapshot`, decides whether the snapshot can see the tuple. Updates "hint bits" on the tuple as a side effect when a referenced xact's commit/abort status is newly known. This file is the canonical authority on heap MVCC semantics — most subtle bugs in the database land here. [from-comment, heapam_visibility.c:163-228]

## Top-of-file comment
> Long (65-line) block (heapam_visibility.c:163-228). Key claims:
> - "all the HeapTupleSatisfies routines will update the tuple's 'hint' status bits if we see that the inserting or deleting transaction has now committed or aborted (and it is safe to set the hint bits). If the hint bits are changed, MarkBufferDirtyHint is called…"
> - "The caller must hold not only a pin, but at least shared buffer content lock on the buffer containing the tuple."
> - Race-condition order: "must check `TransactionIdIsInProgress` (which looks in the PGPROC array) before `TransactionIdDidCommit` (which look in pg_xact)" — otherwise a just-committed xact may look crashed.
> - Enumerates the 8 `HeapTupleSatisfies*` routines and their contracts.

## Public surface (non-static functions)

- `HeapTupleSetHintBits` (line 212) — externally callable hint-bit setter.
- `HeapTupleSatisfiesSelf` (297) — visible to current xact, current command.
- `HeapTupleSatisfiesAny` (430) — always visible (used by bootstrap, REINDEX, etc.).
- `HeapTupleSatisfiesToast` (452) — for TOAST chunks: visible unless inserted by an aborted vacuum-rewrite.
- `HeapTupleSatisfiesUpdate` (511) — used by `heap_update`/`heap_delete`/`heap_lock_tuple` to decide TM_Ok / TM_Updated / TM_Deleted / TM_BeingModified / TM_Invisible / TM_SelfModified.
- `HeapTupleSatisfiesDirty` (759) — sees own + in-progress xacts; used by referential integrity and EvalPlanQual.
- `HeapTupleSatisfiesMVCC` (939) — the workhorse for ordinary SELECT.
- `HeapTupleSatisfiesVacuum` (1113), `HeapTupleSatisfiesVacuumHorizon` (1147), `HeapTupleSatisfiesNonVacuumable` (1345) — VACUUM's eyes.
- `HeapTupleIsSurelyDead` (1381) — fast pre-check, no buffer lock needed beyond pin.
- `HeapTupleHeaderIsOnlyLocked` (1437) — like the inline `HEAP_XMAX_IS_LOCKED_ONLY` but also checks whether the updater xact was aborted.
- `HeapTupleSatisfiesHistoricMVCC` (1504) — logical-decoding visibility (sees catalog state at a specified xid).
- `HeapTupleSatisfiesMVCCBatch` (1690) — batched MVCC for page-at-a-time scans.
- `HeapTupleSatisfiesVisibility` (1732) — dispatcher: switches on `snapshot->snapshot_type` to one of the above.

## Static helpers

- `SetHintBitsExt` (142) / `SetHintBits` (199) — the actual hint-bit writer, ensures WAL flush before setting `HEAP_XMIN/XMAX_COMMITTED` if the WAL of the committing xact may not yet be on disk (the "Lsn must be flushed" rule for hint-bit setting).
- `HeapTupleCleanMoved` (232) — strip `HEAP_MOVED_OFF/IN` legacy bits if seen.
- `TransactionIdInArray` (1483) — helper for snapshot xip array lookups.

## Key types / structs

None defined here; consumes `HeapTupleData`, `Snapshot`, `Buffer`. The `TM_Result` enum returned by `HeapTupleSatisfiesUpdate` lives in `tableam.h`. The `HTSV_Result` enum returned by `HeapTupleSatisfiesVacuum` lives in `heapam.h:136`.

## Key invariants and locking [critical — high-risk section]

- **Caller must hold pin + at least shared buffer content lock.** [from-comment, heapam_visibility.c:171-173]
- **`TransactionIdIsInProgress` must be checked before `TransactionIdDidCommit`** for non-MVCC snapshots — otherwise a just-committed-but-not-yet-cleared-in-procarray xact can look crashed. `xact.c` records commit in pg_xact *before* clearing `MyProc->xid`, which makes this ordering safe. [from-comment, heapam_visibility.c:177-191]
- **For MVCC snapshots, `XidInMVCCSnapshot` replaces `TransactionIdIsInProgress`** in the same role — same ordering rule. [from-comment, heapam_visibility.c:196-198]
- `TransactionIdDidAbort` cannot be used — it doesn't treat crashed-while-running xids as aborted. Aborted-ness is determined by elimination (not in progress AND not committed). [from-comment, heapam_visibility.c:192-195]
- Hint bits may only be set after the corresponding xact's commit WAL is flushed to disk. `SetHintBitsExt` enforces this by checking `XLogNeedsFlush` for the relevant LSN; if so, it does not set the bit (a later visit will). [verified-by-code, heapam_visibility.c:142-198] **Failing this rule causes data loss after a crash.**
- `HEAP_XMAX_IS_LOCKED_ONLY` does NOT account for the case where the updater xact aborted; `HeapTupleHeaderIsOnlyLocked` does (it consults `TransactionIdDidCommit`/`TransactionIdIsInProgress`). [from-comment, heapam_visibility.c:1437-…]
- MultiXact xmax is resolved via `HeapTupleGetUpdateXid` (in `heapam.c`) which may force MultiXact disk I/O — visibility routines call it lazily.
- For tuples with `HEAP_MOVED_*` (pre-9.0 VACUUM FULL), `HeapTupleCleanMoved` translates them into modern visibility state. [verified-by-code]
- Logical-decoding visibility (`HeapTupleSatisfiesHistoricMVCC`) consults the *combo CID* map provided by the snapshot's `tuplecid_data`; `ResolveCminCmaxDuringDecoding` (in `reorderbuffer.c`) bridges the two. [from-comment in heapam.h:511-519]

## Functions of note (deep-read selection)

1. **`HeapTupleSatisfiesMVCC`** (heapam_visibility.c:939) — Decision tree:
   - If xmin not committed (hint absent): if xmin is current xact's xid, check cmin vs snapshot's curcid; if in progress → not visible; if invalid/aborted → not visible (set HEAP_XMIN_INVALID hint); else committed → set HEAP_XMIN_COMMITTED hint.
   - If xmin in snapshot via `XidInMVCCSnapshot` → not visible.
   - If xmax invalid → visible.
   - If xmax is multi: if all members are locks only or aborted → visible; else resolve update xid.
   - If xmax committed and not in snapshot → not visible; etc.
   The function is the cleanest single piece of "what is MVCC" in PostgreSQL. [verified-by-code]

2. **`HeapTupleSatisfiesUpdate`** (heapam_visibility.c:511) — Returns `TM_Result`. Distinguishes self-modified (different cmin/cmax in same xact) from invisible from being-modified. Crucial for the row-locking state machine in `heap_lock_tuple`. [verified-by-code]

3. **`HeapTupleSatisfiesVacuumHorizon`** (heapam_visibility.c:1147) — Returns one of `HEAPTUPLE_DEAD/LIVE/RECENTLY_DEAD/INSERT_IN_PROGRESS/DELETE_IN_PROGRESS`, plus a `dead_after` xid output that lets the caller compare against a vistest later. The decision is dominated by the comparison of the deleting xact (or the multi update xid) against the OldestXmin horizon. [verified-by-code]

4. **`HeapTupleIsSurelyDead`** (heapam_visibility.c:1381) — Doesn't need buffer content lock; uses only hint bits already set and the `GlobalVisState`. Lets HOT pruning fast-path skip tuples that no snapshot could possibly see. [verified-by-code]

5. **`HeapTupleSatisfiesMVCCBatch`** (heapam_visibility.c:1690) — Operates over `BatchMVCCState` (defined in heapam.h:499). Avoids re-entry into procarray for each tuple by pulling snapshot state into registers once. Returns count of visible tuples and writes their offsets into `vistuples_dense`. [verified-by-code]

## Cross-references

- Called from: every read path (executor scans), `heapam.c` (insert/update/delete/lock), `pruneheap.c` (decide DEAD vs RECENTLY_DEAD), `vacuumlazy.c` (page sweep), `commands/cluster.c`, logical-decoding (`reorderbuffer.c`).
- Calls into: `procarray.c` (`TransactionIdIsInProgress`, `XidInMVCCSnapshot`, `GlobalVisTest*`), `transam.c` (`TransactionIdDidCommit`), `multixact.c` (`MultiXactIdIsRunning`, member lookups), `xlog.c` (`XLogNeedsFlush` for hint bits), `bufmgr.c` (`MarkBufferDirtyHint`).

## Open questions

- Exact rules for setting `HEAP_XMIN_FROZEN` from inside visibility code (vs explicit freeze) — appears in `SetHintBits` but I did not trace the legacy-bits cases fully. [unverified]
- `HeapTupleSatisfiesHistoricMVCC` interaction with sub-transactions inside logical decoding — comment is brief. [unverified]
- Whether all callers of `HeapTupleIsSurelyDead` actually meet the "pin only, no content lock required" precondition. [unverified — high-risk if not]

## Confidence tag tally
`[verified-by-code]=14 [from-comment]=10 [from-readme]=0 [inferred]=0 [unverified]=3`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/access-heap.md](../../../../../subsystems/access-heap.md)
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
