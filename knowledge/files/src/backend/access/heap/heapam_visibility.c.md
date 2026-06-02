---
path: src/backend/access/heap/heapam_visibility.c
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
loc: 1753
depth: deep
---

# heapam_visibility.c

- **Source path:** `source/src/backend/access/heap/heapam_visibility.c`
- **Lines:** 1753
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422` (re-verified 2026-06-02; previously `ef6a95c7c64`)
- **Companion files:** `htup_details.h` (the bit semantics it interprets), `heapam.h` (its prototypes, `BatchMVCCState`, `HTSV_Result`), `storage/bufmgr.h` (the new hint-bit API: `BufferBeginSetHintBits`/`BufferFinishSetHintBits`/`BufferSetHintBits16`), `storage/procarray.c` (xact-in-progress, `XidInMVCCSnapshot`, `GlobalVisTest*`), `access/transam/transam.c` (commit-log), `utils/time/snapmgr.c` (snapshots)

## Purpose

Implements every MVCC visibility test in PostgreSQL. Given a `HeapTuple` and a `Snapshot`, decides whether the snapshot can see the tuple. Updates "hint bits" on the tuple as a side effect when a referenced xact's commit/abort status is newly known. This file is the canonical authority on heap MVCC semantics — most subtle bugs in the database land here. [from-comment, heapam_visibility.c:6-36]

## Top-of-file comment
> Long block (heapam_visibility.c:6-57). Key claims:
> - "all the HeapTupleSatisfies routines will update the tuple's 'hint' status bits if we see that the inserting or deleting transaction has now committed or aborted (and it is safe to set the hint bits). If the hint bits are changed, MarkBufferDirtyHint is called…" [from-comment, heapam_visibility.c:6-11] — NB: the underlying mechanism is now the `BufferBeginSetHintBits`/`BufferSetHintBits16` API (see below); the comment's "MarkBufferDirtyHint" is the conceptual end-effect (the buffer ends up dirtied-for-hint).
> - "The caller must hold not only a pin, but at least shared buffer content lock on the buffer containing the tuple." [from-comment, heapam_visibility.c:10-11]
> - Race-condition order: "must check `TransactionIdIsInProgress` (which looks in the PGPROC array) before `TransactionIdDidCommit` (which look in pg_xact)" — otherwise a just-committed xact may look crashed. `xact.c` records commit in pg_xact *before* unsetting `MyProc->xid`. [from-comment, heapam_visibility.c:13-28]
> - For MVCC snapshots, `XidInMVCCSnapshot` takes the role of `TransactionIdIsInProgress`, same ordering rule. [from-comment, heapam_visibility.c:33-35]
> - Enumerates the 8 `HeapTupleSatisfies*` routines and their contracts. [from-comment, heapam_visibility.c:38-56]

## Public surface (non-static functions)

- `HeapTupleSetHintBits` (line 212) — externally callable hint-bit setter; asserts the caller holds the buffer **exclusive** (`BufferIsLockedByMeInMode(buffer, BUFFER_LOCK_EXCLUSIVE)`), because the heapam.c uses rely on the update succeeding. [verified-by-code, heapam_visibility.c:211-223]
- `HeapTupleSatisfiesUpdate` (511) — used by `heap_update`/`heap_delete`/`heap_lock_tuple` to decide TM_Ok / TM_Updated / TM_Deleted / TM_BeingModified / TM_Invisible / TM_SelfModified.
- `HeapTupleSatisfiesVacuum` (1113), `HeapTupleSatisfiesVacuumHorizon` (1147) — VACUUM's eyes; the latter returns a `dead_after` xid for caller-side horizon comparison.
- `HeapTupleIsSurelyDead` (1381) — fast pre-check, consults neither procarray nor CLOG (relies on already-set hint bits + `GlobalVisState`).
- `HeapTupleHeaderIsOnlyLocked` (1437) — like the inline `HEAP_XMAX_IS_LOCKED_ONLY` macro but also verifies the updater xact did not abort (for the multi case).
- `HeapTupleSatisfiesMVCCBatch` (1690) — batched MVCC for page-at-a-time scans; the only caller that uses the amortized hint-bit path.
- `HeapTupleSatisfiesVisibility` (1732) — dispatcher: switches on `snapshot->snapshot_type` to the right static routine (passes `state = NULL` for the single-tuple SNAPSHOT_MVCC path). [verified-by-code, heapam_visibility.c:1731-1753]

## Static helpers / spine

- `HeapTupleSatisfiesMVCC` (939, `static inline`) — the workhorse for ordinary SELECT; now takes a `SetHintBitsState *state` so the batch path can amortize hint-bit acquisition. [verified-by-code, heapam_visibility.c:938-940]
- `HeapTupleSatisfiesSelf` (297) — visible to current xact, current command.
- `HeapTupleSatisfiesAny` (430) — always visible (bootstrap, REINDEX, etc.).
- `HeapTupleSatisfiesToast` (452) — for TOAST chunks: visible unless inserted by an aborted/canceled speculative insertion or interrupted vacuum-rewrite.
- `HeapTupleSatisfiesDirty` (759) — sees own + in-progress xacts; abuses `snapshot` as an *output* arg (`snapshot->xmin`/`xmax`/`speculativeToken`). Used by RI checks and EvalPlanQual.
- `HeapTupleSatisfiesNonVacuumable` (1345) — Snapshot-style wrapper over `HeapTupleSatisfiesVacuumHorizon` using `snapshot->vistest`.
- `HeapTupleSatisfiesHistoricMVCC` (1504) — logical-decoding visibility; catalog tuples only; resolves combo CIDs via `ResolveCminCmaxDuringDecoding`.
- `SetHintBitsExt` (142, `static inline`) / `SetHintBits` (199, `static inline`) — the actual hint-bit writers (see the hint-bit machinery section below).
- `HeapTupleCleanMoved` (232) — strip legacy `HEAP_MOVED_OFF/IN` bits (pre-9.0 VACUUM FULL); returns false if the row ought to be invisible.
- `TransactionIdInArray` (1483) — `bsearch` over a snapshot xip/subxip array.

## Hint-bit machinery [CHANGED since ef6a95c7c64 — high-risk]

The single-shot `MarkBufferDirtyHint` model has been replaced by a **page-level "right to set hint bits"** protocol. Three rules now govern hint-bit setting:

1. **Don't set a hint while the page is under IO.** "the page must not be undergoing IO at this time (otherwise we e.g. could corrupt PG's page checksum or even the filesystem's, as is known to happen with btrfs)." The right is acquired page-wide via `BufferBeginSetHintBits()`; **only a single backend holds it at a time.** [from-comment, heapam_visibility.c:106-113]
2. **Commit-hint LSN interlock (unchanged in spirit).** A `HEAP_XMIN/XMAX_COMMITTED` hint may only be set if the committing xact's WAL is guaranteed on disk before the buffer. `SetHintBitsExt` checks, for a permanent buffer, `XLogNeedsFlush(commitLSN) && BufferGetLSNAtomic(buffer) < commitLSN` → if so it **refrains** (a later visitor will set it). Temp/unlogged buffers (`!BufferIsPermanent`) skip the check. [verified-by-code, heapam_visibility.c:152-166] **Violating this loses data after a crash.**
3. **Abort hints are always safe** to set (some heapam.c code relies on it). [from-comment, heapam_visibility.c:124-125]

The `SetHintBitsState` enum (`SHB_INITIAL` / `SHB_DISABLED` / `SHB_ENABLED`, heapam_visibility.c:91-99) is the amortization state passed to `SetHintBitsExt`:

- **`state == NULL` (single-tuple path):** write via `BufferSetHintBits16(&tuple->t_infomask, …, buffer)` — cheaper than a `Begin`/`Finish` pair for a one-off. [verified-by-code, heapam_visibility.c:174-179]
- **`state != NULL` (batch path):** on first need, call `BufferBeginSetHintBits(buffer)`; on failure set `*state = SHB_DISABLED` and never retry on that page (IO is likely still going); on success set `*state = SHB_ENABLED` and thereafter just OR the bits into `t_infomask` directly. The batch caller pairs this with a single `BufferFinishSetHintBits()` at the end. [verified-by-code, heapam_visibility.c:149-191]

`HeapTupleSatisfiesMVCCBatch` is the lone amortizing caller: it declares `SetHintBitsState state = SHB_INITIAL`, threads `&state` through every `HeapTupleSatisfiesMVCC`, and finishes with `if (state == SHB_ENABLED) BufferFinishSetHintBits(buffer, true, true)`. [verified-by-code, heapam_visibility.c:1689-1719]

## Key types / structs

None defined here. Consumes `HeapTupleData`, `Snapshot`, `Buffer`. `TM_Result` (returned by `HeapTupleSatisfiesUpdate`) lives in `tableam.h`; `HTSV_Result` (returned by the Vacuum routines) lives in `heapam.h`; `BatchMVCCState` (consumed by `HeapTupleSatisfiesMVCCBatch`) lives in `heapam.h`. The `SetHintBitsState` enum is private to this file. [verified-by-code, heapam_visibility.c:91-99]

## Key invariants and locking [critical — high-risk section]

- **Caller must hold pin + at least shared buffer content lock.** [from-comment, heapam_visibility.c:10-11] The exported `HeapTupleSetHintBits` is stricter: it asserts an **exclusive** content lock. [verified-by-code, heapam_visibility.c:220]
- **`TransactionIdIsInProgress` before `TransactionIdDidCommit`** for non-MVCC snapshots; **`XidInMVCCSnapshot` before `TransactionIdDidCommit`** for MVCC snapshots — never consult pg_xact until after deciding the xact is no longer in progress. [from-comment, heapam_visibility.c:13-35]
- `TransactionIdDidAbort` is unusable — it doesn't treat crashed-while-running xids as aborted. Aborted-ness is determined by elimination (not in progress AND not committed). [from-comment, heapam_visibility.c:29-31]
- Hint-bit LSN interlock + page-IO interlock as detailed in the hint-bit section above. [verified-by-code, heapam_visibility.c:101-192]
- `HEAP_XMAX_IS_LOCKED_ONLY` (the infomask macro) does NOT account for an aborted updater in the multi case; `HeapTupleHeaderIsOnlyLocked` does, by resolving `HeapTupleGetUpdateXid` and consulting commit/in-progress state. [verified-by-code, heapam_visibility.c:1436-1477]
- MultiXact xmax is resolved via `HeapTupleGetUpdateXid` (in `heapam.c`), which may force MultiXact I/O — visibility routines call it lazily, only after the infomask-only checks fail. [verified-by-code, heapam_visibility.c:1173-1176]
- For tuples with `HEAP_MOVED_*` (pre-9.0 VACUUM FULL), `HeapTupleCleanMoved` translates them into modern visibility state; the path `elog(ERROR)`s if such a tuple is seen as current or in-progress. [verified-by-code, heapam_visibility.c:231-273]
- Logical-decoding visibility (`HeapTupleSatisfiesHistoricMVCC`) consults the combo-CID map via `ResolveCminCmaxDuringDecoding` (in `reorderbuffer.c`); an unresolved combo CID for xmin means "not visible yet", for xmax means "still visible". [from-comment, heapam_visibility.c:1536-1552, 1624-1642]

## Functions of note (deep-read selection)

1. **`HeapTupleSatisfiesMVCC`** (939) — Decision tree, in order: xmin-not-committed branch (current xact → cmin vs `snapshot->curcid`; `XidInMVCCSnapshot` → invisible; commit/abort → set hint) → xmin-committed-but-maybe-in-snapshot branch (frozen xmin skips the check, heapam_visibility.c:1021-1023) → xmax checks mirroring xmin (multi, current, in-snapshot, committed). The cleanest single statement of "what is MVCC" in PostgreSQL. [verified-by-code, heapam_visibility.c:938-1096]
2. **`HeapTupleSatisfiesUpdate`** (511) — Returns `TM_Result`. Distinguishes self-modified (cmax ≥ curcid in same xact) from invisible from being-modified; carefully handles the case where our own just-created tuple is key-share-locked by *other* xacts via a multi. [verified-by-code, heapam_visibility.c:510-736]
3. **`HeapTupleSatisfiesVacuumHorizon`** (1147) — Returns `HEAPTUPLE_{DEAD,LIVE,RECENTLY_DEAD,INSERT_IN_PROGRESS,DELETE_IN_PROGRESS}` plus a `dead_after` xid output for later horizon comparison; for a committed multi updater it sets `*dead_after = xmax` even if lockers still run, so pruning below the horizon is not blocked. [verified-by-code, heapam_visibility.c:1146-1329]
4. **`HeapTupleIsSurelyDead`** (1381) — Assumes hint bits were just set by a prior visibility check; if no hint bit is set it conservatively returns "alive". Lets HOT pruning fast-path skip clearly-dead tuples without touching procarray/CLOG. [verified-by-code, heapam_visibility.c:1380-1425]
5. **`HeapTupleSatisfiesMVCCBatch`** (1690) — Loops `HeapTupleSatisfiesMVCC` over `BatchMVCCState->tuples`, records per-tuple visibility in `->visible[]` and dense offsets in `vistuples_dense[]`; amortizes the hint-bit `Begin`/`Finish` across the page (see hint-bit machinery). Returns the visible count. [verified-by-code, heapam_visibility.c:1689-1719]

## Cross-references

- Called from: every read path (executor scans), `heapam.c` (insert/update/delete/lock), `pruneheap.c` (DEAD vs RECENTLY_DEAD), `vacuumlazy.c` (page sweep), `commands/cluster.c`, logical decoding (`reorderbuffer.c`).
- Calls into: `procarray.c` (`TransactionIdIsInProgress`, `XidInMVCCSnapshot`, `GlobalVisTestIsRemovableXid`), `transam.c` (`TransactionIdDidCommit`), `multixact.c` (`MultiXactIdIsRunning`), `bufmgr.c` (`BufferBeginSetHintBits`/`BufferFinishSetHintBits`/`BufferSetHintBits16`/`BufferGetLSNAtomic`/`BufferIsPermanent`), `xlog.c` (`XLogNeedsFlush`, `TransactionIdGetCommitLSN`).
- See also: `knowledge/idioms/locking-overview.md` (buffer pin/content-lock layer), `knowledge/data-structures/heap-tuple-layout.md`, `knowledge/data-structures/snapshot-lifecycle.md`, `knowledge/subsystems/access-heap.md`.

## Open questions

- `HeapTupleSatisfiesHistoricMVCC` interaction with sub-transactions inside *streaming* logical decoding — the `XXX` comments (heapam_visibility.c:1542-1552) flag combo-CID resolution gaps for in-progress decode but don't fully specify behaviour. [unverified]
- Whether every caller of `HeapTupleIsSurelyDead` truly meets the "hint bits already set" precondition; if not, it silently treats live tuples as alive (safe) but can mis-skip dead ones (also safe — conservative). [inferred, heapam_visibility.c:1370-1379]
- The exact failure/retry cadence when `BufferBeginSetHintBits` returns false under sustained page IO (does a heavily-read hot page ever converge to having hints set?). [unverified]

## Confidence tag tally
`[verified-by-code]=16 [from-comment]=10 [from-readme]=0 [inferred]=1 [unverified]=3`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/access-heap.md](../../../../../subsystems/access-heap.md)
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
