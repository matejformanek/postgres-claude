# Transaction management + WAL machinery

## Owners (as of 2026-06-12)

- **Top committers (last 24mo):** Michael Paquier (67), Heikki Linnakangas (33), Alexander Korotkov (31), Peter Eisentraut (25)
- **Top reviewers (last 24mo):** Chao Li (24), Michael Paquier (23), Andres Freund (19), Bertrand Drouvot (14)
- **Recent landmark commits (12mo):**
  - `65f4976189b (Michael Paquier, 2025-11-04): Add assertion check for WAL receiver state during stream-archive transition`
  - `351265a6c7f (Fujii Masao, 2026-02-16): Remove recovery.signal at recovery end when both signal files are present.`
  - `03facc1211b (Michael Paquier, 2026-03-10): Switch to FATAL error for missing checkpoint record without backup_label`

See `knowledge/personas/domain-ownership.md` for the cross-subsystem index, methodology, and committer/reviewer affinity clusters.

---


- **Source path:** `source/src/backend/access/transam/`
- **Header path:** `source/src/include/access/` (`xact.h`, `xlog.h`, `xloginsert.h`, `xlogrecord.h`, `xlogreader.h`, `xlogrecovery.h`, `clog.h`, `multixact.h`, `subtrans.h`, `twophase.h`, `slru.h`, `transam.h`, `parallel.h`, `rmgr.h`, `xlogdefs.h`, `xlog_internal.h`)
- **Last verified commit:** `ef6a95c7c64de07dff4dd1f1da88ffae7b086ef3` (2026-06-01)
- **README anchor:** `source/src/backend/access/transam/README`

## 1. Purpose

`access/transam` is the union of three intertwined subsystems: the
**transaction state machine** (`xact.c` + `twophase.c` + `subtrans.c`),
the **write-ahead-log protocol** (the `xlog*.c` family), and the
**SLRU-backed transaction-status caches** (`clog.c`, `commit_ts.c`,
`multixact.c`, `subtrans.c` over `slru.c`). The README opens with
"transactions" and "WAL" treated as the same chapter for a reason —
durable commit requires an XLOG record on disk *before* dirty data
pages may be flushed (the WAL-before-data rule), and the commit
record's bits are what `pg_xact` (`clog.c`) eventually persists.
[from-README] (`README:411-415`, `README:1-913` overall) [via
knowledge/files/src/backend/access/transam/README.md].

## 2. Mental model

- **Transaction lifecycle + subtransactions.** Each backend keeps a
  `TransactionState` stack (`xact.c:195-223` [verified-by-code]).
  `StartTransactionCommand` / `CommitTransactionCommand` /
  `AbortCurrentTransaction` are the three middle-layer entries called
  by `postgres.c` per statement; they dispatch to the low-level
  `StartTransaction`, `CommitTransaction`, `AbortTransaction`,
  `CleanupTransaction`, and their `SubTransaction` variants
  [from-README] (`README:11-39`). Subxacts push a new stack node;
  XIDs are assigned lazily by `AssignTransactionId` (`xact.c:637`
  [verified-by-code]), and the invariant **child XID > parent XID** is
  maintained by always assigning the parent first [from-README]
  (`README:194-198`).

- **XID + VirtualXID.** A `VirtualTransactionId` (`procNumber +
  LocalTransactionId`) is what gets advertised at `StartTransaction`
  (`xact.c:2204-2217` [verified-by-code]). A real (full) `XID` is
  taken later, only if the transaction actually writes — via
  `varsup.c:GetNewTransactionId` under exclusive `XidGenLock`, which
  also extends CLOG/CommitTs/SUBTRANS and stores into
  `ProcGlobal->xids[]` before releasing the lock [verified-by-code]
  (`varsup.c:68-277`).

- **WAL record + LSN.** A WAL record is assembled by the
  `XLogBeginInsert → XLogRegister{Buffer,Data,BufData} → XLogInsert`
  API in `xloginsert.c`, which calls down to `xlog.c:XLogInsertRecord`
  (`xlog.c:784` [verified-by-code]). The producer-side scratch
  (`registered_buffer[]`, `registered_data[]`) is folded into an
  `XLogRecData` chain by `XLogRecordAssemble`; the returned `LSN` is
  stored on every dirtied buffer via `PageSetLSN`. WAL space is
  reserved using the "usable byte position" encoding that strips page
  headers (`XLogBytePosToRecPtr`, `xlog.c:1899`).

- **Redo.** Every WAL record carries an `RmgrId`; on replay
  `xlogrecovery.c:ApplyWalRecord` dispatches via the global
  `RmgrTable[]` (built in `rmgr.c:50-52` from `access/rmgrlist.h`) to
  `RmgrTable[rmid].rm_redo` (`xlogrecovery.c:1883` [verified-by-code]).
  Redo handlers fetch the relevant page with `xlogutils.c`'s
  `XLogReadBufferForRedo*`, which returns `BLK_NEEDS_REDO` /
  `BLK_DONE` / `BLK_RESTORED` / `BLK_NOTFOUND` so the handler can
  decide whether to apply the delta, skip (page already past the
  record's LSN), use the FPI, or accept a missing relation.

- **SLRU caches.** `slru.c` is the per-bank-locked,
  wraparound-aware page buffer pool used by `pg_xact`,
  `pg_subtrans`, `pg_multixact` (offsets + members), `pg_commit_ts`,
  `pg_notify`, `pg_serial`. Each bank has its own control LWLock plus
  per-buffer I/O LWLocks; `latest_page_number` is lock-free atomic;
  the latest page is never evicted [from-comment]
  (`slru.c:3-49`).

- **Recovery + checkpoint.** `xlog.c:StartupXLOG` (`xlog.c:5846`
  [verified-by-code]) drives crash/archive/standby bootstrap by
  reading `pg_control`, locating the redo-start checkpoint, then
  handing off to `xlogrecovery.c:PerformWalRecovery` (`xlogrecovery.c:1612`)
  which runs the `ReadRecord → ApplyWalRecord` loop. Checkpoints
  themselves are produced by `CreateCheckPoint` / `CreateRestartPoint`
  (in `xlog.c`, not deep-read; see §9), which call into each SLRU's
  `CheckPoint*` flush function plus `CheckPointTwoPhase` and the
  buffer-pool checkpoint.

## 3. Key files

### WAL machinery

- `xlog.c` (10195 lines) — WAL runtime spine: `XLogInsertRecord`,
  `XLogFlush`, `XLogBackgroundFlush`, `XLogSetAsyncXactLSN`,
  `WaitXLogInsertionsToFinish`, segment-file lifecycle, control file
  (`pg_control`), `StartupXLOG`, `RecoveryInProgress`. [from-comment]
  (`xlog.c:3-25`) [via knowledge/files/src/backend/access/transam/xlog.c.md].
- `xloginsert.c` (1441 lines) — Producer-side record assembly:
  `XLogBeginInsert`, `XLogRegister{Buffer,Block,Data,BufData}`,
  `XLogInsert`, `XLogRecordAssemble`, `log_newpage*`,
  `XLogSaveBufferForHint`. [from-comment] (`xloginsert.c:3-9`)
  [via xloginsert.c.md].
- `xlogrecovery.c` (5111 lines) — Replay state machine:
  `InitWalRecovery`, `PerformWalRecovery`, `ApplyWalRecord`,
  `ReadRecord`, `WaitForWALToBecomeAvailable`, recovery-target stop
  conditions, pause, `verifyBackupPageConsistency`. [from-comment]
  (`xlogrecovery.c:3-14`) [via xlogrecovery.c.md].
- `xlogreader.c` (2218 lines) — Portable WAL decoder (front-end +
  backend): `XLogReadRecord`, `DecodeXLogRecord`, `RestoreBlockImage`,
  CRC validation. No `ereport`. [from-comment] (`xlogreader.c:3-15`)
  [via xlogreader.c.md].
- `xlogutils.c` (1034 lines) — Redo-side helpers:
  `XLogReadBufferForRedo*`, invalid-page hash, fake relcache,
  drop/truncate forwarding, `read_local_xlog_page*`. [from-comment]
  (`xlogutils.c:3-7`) [via xlogutils.c.md].

### Transaction lifecycle

- `xact.c` (6503 lines) — Three-layer transaction system + commit/abort
  WAL records (`XactLogCommitRecord`, `XactLogAbortRecord`, `xact_redo`).
  [from-comment] (`xact.c:3-6`) [via xact.c.md].
- `twophase.c` (2878 lines) — `PREPARE TRANSACTION` /
  `COMMIT PREPARED` / `ROLLBACK PREPARED`: gxact slots,
  `pg_twophase/<fxid>` files, redo bookkeeping, dummy PGPROC.
  [from-comment] (`twophase.c:12-69`) [via twophase.c.md].
- `subtrans.c` (448 lines) — Per-XID parent pointer SLRU for resolving
  subxid → top when a backend's subxid cache has overflowed. **No
  XLOG**; re-zeroed at startup. [from-comment] (`subtrans.c:3-20`)
  [via subtrans.c.md].

### SLRU-backed status caches

- `clog.c` (1125 lines) — pg_xact: 2 bits/xact commit status; group
  commit; async-commit page LSN cache. [from-comment] (`clog.c:3-26`)
  [via clog.c.md].
- `commit_ts.c` (1035 lines) — commit timestamp + replication origin
  per xact, gated on `track_commit_timestamp`. [from-comment]
  (`commit_ts.c:3-13`) [via commit_ts.c.md].
- `multixact.c` (3014 lines) — pg_multixact: two SLRUs (OFFSETs,
  MEMBERs) for variable-length `MultiXactMember[]` per MXID. Used by
  shared row locks in heap. [from-comment] (`multixact.c:3-49`)
  [via multixact.c.md].
- `slru.c` (1905 lines) — Generic per-bank-locked Simple-LRU page
  buffer pool underneath all of the above. [from-comment]
  (`slru.c:3-35`) [via slru.c.md].

### Auxiliary

- `timeline.c` (593 lines) — Read/write `<tli>.history` files.
  [via timeline.c.md].
- `rmgr.c` (170 lines) — Builds `RmgrTable[]` from `rmgrlist.h`,
  hosts `RegisterCustomRmgr` for extensions. [via rmgr.c.md].
- `varsup.c` (704 lines) — XID + OID counter management
  (`GetNewTransactionId`, `SetTransactionIdLimit`, `GetNewObjectId`).
  [via varsup.c.md].
- `parallel.c` (1673 lines) — Parallel-worker bridge: DSM segment,
  `SerializeTransactionState`, `LaunchParallelWorkers`,
  `WaitForParallelWorkersToFinish`. [via parallel.c.md].
- `generic_xlog.c` (544 lines) — Delta-record API for extensions
  (canonical user: `contrib/bloom`). [via generic_xlog.c.md].
- `transam.c` (341 lines) — High-level `TransactionIdDidCommit` /
  `…DidAbort` over `clog.c`, with single-item per-backend cache.
  [via transam.c.md].
- `twophase_rmgr.c` (58 lines) — Static 2PC callback dispatch tables
  (Lock, pgstat, MultiXact, PredicateLock). [via twophase_rmgr.c.md].

### Tooling

- `xlogfuncs.c` (860 lines) — SQL UI (`pg_backup_start/stop`,
  `pg_switch_wal`, `pg_promote`, `pg_wal_replay_pause/resume`,
  `pg_current_wal_lsn`, …). [via xlogfuncs.c.md].
- `xlogarchive.c` (726 lines) — `RestoreArchivedFile`,
  `XLogArchiveNotify*` (`.ready`/`.done` markers). [via xlogarchive.c.md].
- `xlogbackup.c` (92 lines) — `backup_label` / `.backup` history file
  formatting. [via xlogbackup.c.md].
- `xlogstats.c` (96 lines) — Per-rmgr counters for `pg_waldump` /
  `pg_walinspect`. [via xlogstats.c.md].
- `xlogprefetcher.c` (1106 lines) — Drop-in `XLogReader` wrapper that
  issues async `PrefetchBuffer` for upcoming redo blocks. [via
  xlogprefetcher.c.md].
- `xlogwait.c` (495 lines) — `WaitForLSN`: pairing-heap per
  `WaitLSNType` (REPLAY/WRITE/FLUSH/INSERT). [via xlogwait.c.md].

## 4. Key data structures

- **`XLogRecData`** (defined in `xlogrecord.h`) — chain produced by
  `XLogRecordAssemble` (`xloginsert.c:621`) and consumed by
  `XLogInsertRecord`. Carries `xl_rmid`, `xl_info`, `xl_tot_len`,
  `xl_xid`, body, then per-buffer `XLogRecordBlockHeader` + optional
  `BkpImage` + per-buffer data. [verified-by-code]
  [via xloginsert.c.md].

- **`XLogReaderState`** (`xlogreader.h`) — decoder state, owned by a
  single caller (startup process, walreceiver, `pg_waldump`). Contains
  `DecodedXLogRecord` queue, current `ReadRecPtr`/`EndRecPtr`,
  callback table (`page_read`, `segment_open`, `segment_close`), and
  an error-state buffer (no `ereport`). Single-threaded; no internal
  locking. [verified-by-code] [via xlogreader.c.md].

- **`XLogCtlData`** (`xlog.c:430-540`, not deep-read in detail) — big
  shared-memory blob holding `Insert` (`XLogCtlInsert`), `LogwrtRqst`,
  per-WAL-page descriptors (`xlblocks[]`), `xlogCtlBufLwLocks[]`,
  `InsertTimeLineID`, `SharedRecoveryState`, `asyncXactLSN`. The
  insertion-side `XLogCtlInsert` (`xlog.c:403`) holds
  `insertpos_lck` (spinlock), `CurrBytePos`/`PrevBytePos`, `RedoRecPtr`,
  `fullPageWrites`, `runningBackups`. [verified-by-code]
  [from-comment] [via xlog.c.md]. **`XLogCtlData` cache-line layout
  not re-derived — see §9.**

- **`WALInsertLock`** (`xlog.c:374-379`) — `{ LWLock lock;
  pg_atomic_uint64 insertingAt; XLogRecPtr lastImportantAt; }`, padded
  to a cache line as `WALInsertLockPadded` (`xlog.c:388-392`). There
  are exactly **`NUM_XLOGINSERT_LOCKS = 8`** of them
  (`xlog.c:157`). Normal records take one; `XLOG_SWITCH` /
  `XLOG_CHECKPOINT_REDO` take all eight. [verified-by-code]
  [via xlog.c.md].

- **`SlruShared` / `SlruCtl`** (declared in `slru.h`) — per-SLRU
  control with page array, dirty flags, page numbers, bank LWLocks
  (one per bank; bank = `pageno >> nBuffersPerBank_shift`), per-buffer
  I/O LWLocks, segment-file naming callbacks, page-precedes callback,
  `latest_page_number` atomic. Reads/writes of bank state require
  exclusive bank lock except the `SimpleLruReadPage_ReadOnly` fast
  path (shared). [from-comment] (`slru.c:18-35`) [via slru.c.md].

- **`TransactionStateData`** (`xact.c:195-223`) — stack node:
  `fullTransactionId`, `subTransactionId`, `nestingLevel`,
  `gucNestLevel`, `curTransactionContext` / `priorContext` /
  `curTransactionOwner`, `childXids[]` (sorted subcommitted-child XIDs),
  `startedInRecovery`, `didLogXid`, `topXidLogged`,
  `parallelModeLevel`, `parallelChildXact`, `parent`.
  [verified-by-code] [via xact.c.md].

- **`GlobalTransactionData`** (declared in `twophase.h` /
  `twophase_rmgr.h`) — shared-memory entry per active gxact: fxid,
  GID string, `prepare_start_lsn`, `inredo`/`ondisk`/`valid` flags,
  dummy PGPROC pointer (which keeps the prepared XID "running" in
  the ProcArray). [from-comment] (`twophase.c:12-69`) [via
  twophase.c.md].

- **MultiXact state.** `MultiXactMember = { TransactionId xid;
  MultiXactStatus status; }` (`multixact.h`). Two SLRUs:
  OFFSETs (fixed-size, indexed by MXID) and MEMBERs (variable-length,
  indexed by offset). Per-backend caches `OldestMemberMXactId[]` /
  `OldestVisibleMXactId[]` register the oldest MXID a backend could
  look at. Thresholds `MULTIXACT_MEMBER_LOW_THRESHOLD = 2 * 10^9`,
  `_HIGH_THRESHOLD = 4 * 10^9` (`multixact.c:99-100`).
  [verified-by-code] [via multixact.c.md].

- **`CommitTimestampEntry`** (`commit_ts.c:55-59`) —
  `{ TimestampTz time; ReplOriginId nodeid; }`, 10 bytes per xact.
  [verified-by-code] [via commit_ts.c.md].

- **`RmgrData`** (declared in `xlog_internal.h`) — `{ name, redo,
  desc, identify, startup, cleanup, mask, decode }`. The global
  `RmgrTable[RM_MAX_ID + 1]` (`rmgr.c:50-52`) is built by
  `#include`-ing `rmgrlist.h` with `PG_RMGR` macro expansion.
  [verified-by-code] [via rmgr.c.md].

## 5. Control flow — the common paths

### 5.1 `XLogInsert → XLogInsertRecord` (with FPI race)

1. Caller fills `registered_buffer[]` / `registered_data[]` via
   `XLogBeginInsert` + `XLogRegister*` (`xloginsert.c:153-464`)
   [verified-by-code].
2. `XLogInsert(rmid, info)` (`xloginsert.c:482`) sanity-checks info
   bits (`XLR_RMGR_INFO_MASK`, `XLR_SPECIAL_REL_UPDATE`,
   `XLR_CHECK_CONSISTENCY`; other bits PANIC, `xloginsert.c:491-497`)
   [verified-by-code]. Loops: `GetFullPageWriteInfo` → `XLogRecordAssemble`
   → `XLogInsertRecord` [verified-by-code] (`xloginsert.c:522-535`).
3. `XLogRecordAssemble` (`xloginsert.c:621`) walks each registered
   buffer; if it's dirty since `RedoRecPtr` it attaches a `BkpBlock`
   header + (compressed) page image (`PGLZ`/`LZ4`/`ZSTD` dispatched on
   `wal_compression`). Builds the chained `XLogRecData` and computes
   CRC over everything except `xl_crc`. [verified-by-code]
   [unverified] full walk-through.
4. `xlog.c:XLogInsertRecord` (`xlog.c:784`) [verified-by-code] enters
   `START_CRIT_SECTION`, dispatches on `WalInsertClass`:
   - **`WALINSERT_NORMAL`** — `WALInsertLockAcquire` (one of eight),
     `ReserveXLogInsertLocation`. If `Insert->RedoRecPtr` has advanced
     past our cached `RedoRecPtr`, or `doPageWrites` flipped because
     `runningBackups` went non-zero, the function releases and
     returns `InvalidXLogRecPtr` — the caller re-assembles with FPIs
     attached. [verified-by-code] [from-comment] (`xlog.c:858-907`,
     `xloginsert.c:522-535`).
   - **`WALINSERT_SPECIAL_SWITCH`** — `WALInsertLockAcquireExclusive`
     (all 8); `ReserveXLogSwitch` may decide the record is unnecessary
     at a segment boundary (`inserted = false`).
     [verified-by-code] (`xlog.c:908-924`).
   - **`WALINSERT_SPECIAL_CHECKPOINT`** — all 8 locks; updates
     `Insert->RedoRecPtr = StartPos` while holding them all.
     [verified-by-code] (`xlog.c:925-942`).
5. CRC finalized over the header (`xlog.c:950-953`), then
   `CopyXLogRecordToWAL` writes the bytes (`xlog.c:959-961`).
   `lastImportantAt` is updated unless the caller passed
   `XLOG_MARK_UNIMPORTANT` (`xlog.c:968-973`). [verified-by-code]
   [via xlog.c.md].

### 5.2 `CommitTransaction → RecordTransactionCommit` (with `DELAY_CHKPT_IN_COMMIT` barrier)

1. `CommitTransaction` (`xact.c:2270`) drains deferred triggers,
   closes portals (`xact.c:2299-2313`); calls
   `XACT_EVENT_PRE_COMMIT` callbacks and parallel-worker cleanup.
2. `smgrDoPendingSyncs(true, …)` — fsyncs WAL-skipped relfilenumbers
   **before** the commit record (the README §"Skipping WAL" rule)
   (`xact.c:2360`) [verified-by-code].
3. `state = TRANS_COMMIT`; `RecordTransactionCommit()`
   (`xact.c:1345`) [verified-by-code]:
   - `START_CRIT_SECTION`; sets `MyProc->delayChkptFlags |=
     DELAY_CHKPT_IN_COMMIT` (`xact.c:1469-1490`) [verified-by-code].
     The README requires this assignment + the WAL insert to be
     uninterruptible, because a concurrent checkpoint that captured
     `latestCompletedXid` before our XID appears in pg_xact would lose
     the commit on crash. [from-comment] (`xact.c:1448-1454`).
     A `pg_write_barrier()` orders the flag store before the WAL
     reservation. [inferred from delay-chkpt protocol]
   - `XactLogCommitRecord(...)` (`xact.c:5870`) assembles the
     variable-format `XLOG_XACT_COMMIT` record (header + optional
     `xl_xact_xinfo`, `xl_xact_dbinfo`, `xl_xact_subxacts`,
     `xl_xact_relfilelocators`, `xl_xact_stats_items`,
     `xl_xact_invals`, `xl_xact_twophase`, `xl_xact_origin`) and calls
     `XLogInsert(RM_XACT_ID, …)`. `XLR_SPECIAL_REL_UPDATE` bit is set
     when files will be dropped. [verified-by-code] (`xact.c:5939`).
   - `TransactionTreeSetCommitTsData(xid, nsubxids, subxids, ts,
     nodeid)` (`commit_ts.c:150`) writes the timestamp SLRU rows.
   - `XLogFlush(XactLastRecEnd)` if `synchronous_commit`, or
     `nrels > 0` (always sync when files will be unlinked at commit,
     `xact.c:1532-1544`), or `forceSyncCommit`; otherwise
     `XLogSetAsyncXactLSN(XactLastRecEnd)` advertises to walwriter
     (`xlog.c:2630`) [verified-by-code].
   - `TransactionIdCommitTree(xid, nchildren, children)`
     (`transam.c:240` → `clog.c:TransactionIdSetTreeStatus`,
     `clog.c:192`) marks pg_xact atomically (two-phase across pages —
     see §5.4).
   - `ProcArrayEndTransaction(MyProc, latestXid)` clears the XID
     under `ProcArrayLock` exclusive; the README's snapshot
     interlocking rule (`README:246-270`) requires this **after**
     RecordTransactionCommit and **before** locks are released
     (`xact.c:2427-2431`) [from-comment].
   - Clears `DELAY_CHKPT_IN_COMMIT`; `END_CRIT_SECTION`.
   - `SyncRepWaitForLSN` for synchronous replication (window after
     barrier cleared — [unverified] ordering re-derivation).
4. Resource-owner release in three phases
   (`RESOURCE_RELEASE_BEFORE_LOCKS`, `_LOCKS`, `_AFTER_LOCKS`).
5. `smgrDoPendingDeletes(true)` — unlinks dropped files post-WAL
   (the README §"Filesystem Actions" rule). [verified-by-code]
   [via xact.c.md].

Parallel workers skip steps 3-5 of `RecordTransactionCommit` and
instead `ParallelWorkerReportLastRecEnd(XactLastRecEnd)` to feed the
leader's `XactLastRecEnd` via DSM atomic (`xact.c:2409-2422`,
`parallel.c:1594`) [verified-by-code].

### 5.3 Recovery main loop (`xlogrecovery.c:PerformWalRecovery`)

1. `StartupXLOG` (`xlog.c:5846`) reads `pg_control`, locates the
   redo-start checkpoint, calls `InitWalRecovery` (which sets up
   `xlogreader` + `xlogprefetcher`, parses `recovery.signal` /
   `backup_label`, returns `RedoStartLSN`, `CheckPointLoc`).
2. `PerformWalRecovery` (`xlogrecovery.c:1612`) [verified-by-code]:
   initializes `XLogRecoveryCtl->{lastReplayed*, replayEnd*}`,
   `PMSIGNAL_RECOVERY_STARTED`, opens the prefetcher at
   `RedoStartLSN`. If `RedoStartLSN < CheckPointLoc`, the record at
   `RedoStartLSN` **must** be `XLOG_CHECKPOINT_REDO` — otherwise
   FATAL (`xlogrecovery.c:1674-1678`) [verified-by-code]. Calls
   `RmgrStartup()` (`rmgr.c:58`).
3. Inner loop: `ReadRecord` (`xlogrecovery.c:3108`) → `ApplyWalRecord`
   (`xlogrecovery.c:1883`) → `recoveryStopsBefore/After` →
   pause/delay.
4. **`ApplyWalRecord`** per-record sequence [verified-by-code]
   (`xlogrecovery.c:1883`):
   a. `AdvanceNextFullTransactionIdPastXid(record->xl_xid)` before
      dispatch (`xlogrecovery.c:1897`) so `nextXid` is monotone past
      every replayed XID.
   b. For `XLOG_CHECKPOINT_SHUTDOWN` / `XLOG_END_OF_RECOVERY`, detect
      TLI switch and update `replayTLI` **before** the redo runs
      (`xlogrecovery.c:1899-1940`) [from-comment] — any writes from the
      redo will carry the new TLI. [unverified] — exact branch detail
      not re-derived here.
   c. `replayEndRecPtr` is bumped **before** `rm_redo` so that an
      `XLogFlush` issued inside redo (which redirects to
      `UpdateMinRecoveryPoint` because `XLogInsertAllowed()` is false)
      sees the right value (`xlogrecovery.c:1942-1949`) [from-comment].
   d. If `standbyState >= STANDBY_INITIALIZED`, call
      `RecordKnownAssignedTransactionIds(xid)`
      (`xlogrecovery.c:1954-1956`).
   e. Either dispatch directly via `xlogrecovery_redo` for
      `XLOG_BACKUP_END`, `XLOG_END_OF_RECOVERY`,
      `XLOG_OVERWRITE_CONTRECORD`, `XLOG_CHECKPOINT_REDO`, or call
      `RmgrTable[record->xl_rmid].rm_redo(xlogreader)`.
5. End-of-recovery: `FinishWalRecovery` (`xlogrecovery.c:1417`)
   cleans up; `StartupXLOG` writes a new-timeline checkpoint and sets
   `SharedRecoveryState = RECOVERY_STATE_DONE`.
[via xlogrecovery.c.md, xlog.c.md].

### 5.4 CLOG sub-commit-then-commit two-phase

`TransactionIdSetTreeStatus(xid, nsubxids, subxids, status, lsn)`
(`clog.c:192`) [verified-by-code]:

- If status is COMMITTED **and** the parent + subxid bitmap spans more
  than one CLOG page, the function first marks the subxacts on the
  *other* pages as `SUB_COMMITTED`, then writes the parent's page with
  `COMMITTED` atomically (this is the single page that determines
  observable committed-ness), then upgrades the other pages to
  `COMMITTED` (`clog.c:211-256`) [verified-by-code] [from-comment]
  [from-README] (`README:357-368`).
- Single-page case skips sub-commit entirely (`clog.c:214-221`).
- Abort is always marked immediately (one pass).
- Group update (`TransactionGroupUpdateXidStatus`, `clog.c:450`) is
  used when subxids fit on the parent page and below
  `THRESHOLD_SUBTRANS_CLOG_OPT ≤ PGPROC_MAX_CACHED_SUBXIDS`
  (`clog.c:310`); a single process updates the bits for many
  concurrent committers under one bank-lock acquisition.
- `TransactionIdSetStatusBit` (`clog.c:670`) also updates the page's
  group-LSN cache (the async-commit "one LSN per ~32 xacts" cache
  described in `README:815-854` — group size of 32 [unverified],
  see §9).
- `clog.c` itself emits WAL only for `CLOG_ZEROPAGE` (page
  init) and `CLOG_TRUNCATE`; commit/abort bits are reconstructed on
  redo by replaying the xact-commit record [from-comment]
  (`clog.c:14-25`). Aborts don't update the page LSN (`clog.c:23-25`).
[via clog.c.md].

## 6. Locking and invariants

### WAL insertion (`xlog.c`)

- **Eight `WALInsertLock`s** (`NUM_XLOGINSERT_LOCKS = 8`,
  `xlog.c:157`). To insert a normal record you take **one**; to lock
  out all inserters (e.g. `XLOG_SWITCH`, `XLOG_CHECKPOINT_REDO`,
  cross-segment switch) you take **all eight** via
  `WALInsertLockAcquireExclusive` (`xlog.c:911-941`)
  [verified-by-code].
- **Holding any WALInsertLock pins `RedoRecPtr` and `fullPageWrites`**
  from changing until release [from-comment] (`xlog.c:846-847`).
- **`insertingAt` is updated before sleeping while holding the
  lock**, so other inserters can determine the minimum LSN that is
  guaranteed to have been reached (`WaitXLogInsertionsToFinish`,
  `xlog.c:1545`). Otherwise two inserters could deadlock while each
  waits for the other to release a WAL buffer slot [from-comment]
  (`xlog.c:353-363`) [via xlog.c.md].
- **Insertion CRC is computed only after `xl_prev` is filled.**
  `ReserveXLogInsertLocation` sets `xl_prev`; CRC happens at
  `xlog.c:946-953` because `xl_prev` is part of the CRC payload.
- **Critical section straddles reserve + copy.** `START_CRIT_SECTION`
  wraps both `ReserveXLogInsertLocation`/`ReserveXLogSwitch` and
  `CopyXLogRecordToWAL` (`xlog.c:824-857`) [verified-by-code].
- **`XLogInsertAllowed()` is false in recovery** — `XLogInsertRecord`
  ereports if called (`xlog.c:815`). Recovery uses
  `UpdateMinRecoveryPoint` (`xlog.c:2721`) instead [via xlog.c.md].
- **`XLogFlush` short-circuits if record ≤ cached `LogwrtResult.Flush`**;
  otherwise it enters `START_CRIT_SECTION`, uses
  `LWLockAcquireOrWait(WALWriteLock)` so group-commit piggybacks form,
  plus `WaitXLogInsertionsToFinish` to know when WAL pages are safe
  to write (`xlog.c:2820-2880`).

### Snapshot / commit serialization

- **`XidGenLock` exclusive** is held by `GetNewTransactionId` across
  `ExtendCLOG/ExtendCommitTs/ExtendSUBTRANS`, the `nextXid` advance,
  and the store into `ProcGlobal->xids[]`. The README invariant: the
  new XID must be in the shared ProcArray **before** `XidGenLock` is
  released, so `latestCompletedXid` cannot advance past a not-yet-
  visible XID and break `ComputeXidHorizons`. [from-README]
  (`README:272-285`) [verified-by-code] (`varsup.c:211-274`).
  `LWLockRelease` provides the release barrier.
- **`ProcArrayEndTransaction`** takes `ProcArrayLock` exclusive on
  commit/abort; `GetSnapshotData` takes it shared. Read-only
  transactions may exit without `ProcArrayLock` (they don't affect
  anyone's snapshot) [from-README] (`README:246-270`).
- **VXID lock acquired before XID announcement.**
  `VirtualXactLockTableInsert(vxid)` precedes `MyProc->vxid.lxid =
  vxid.localTransactionId` (`xact.c:2204-2217`) [verified-by-code]
  [via xact.c.md].

### `DELAY_CHKPT_IN_COMMIT`

A concurrent `CreateCheckPoint` will not finish while any backend has
`MyProc->delayChkptFlags & DELAY_CHKPT_IN_COMMIT` set. The barrier is
the small window inside `RecordTransactionCommit` between "WAL record
inserted" and "pg_xact + ProcArray updated" — if a checkpoint chose
its redo point inside that window without waiting, a crash could
recover a state where the WAL record is replayed but the commit isn't
visible because the system thinks the snapshot horizon already moved
past us. `START_CRIT_SECTION` + the flag together guarantee
atomicity. [from-comment] (`xact.c:1448-1490`) [verified-by-code]
[via xact.c.md].

### Async commit + CLOG LSN cache

For each CLOG page, the latest commit LSN affecting it is remembered
(actually a **group cache: one LSN per ~32 xacts**, see `README:837-854`
and `clog.c:670` — exact constant `CLOG_LSNS_PER_PAGE` not located
[unverified]). Before evicting/writing a CLOG page, the SLRU layer
ensures WAL has been flushed at least to the page's tracked LSN —
this restores the WAL-before-data rule that async commits would
otherwise break. Aborts never update the LSN (failure on crash is
indistinguishable from abort). Hint-bit setting on heap pages is
deferred until the commit LSN has flushed [from-README]
(`README:822-830`) [from-comment] (`clog.c:14-25`).

### Multixact ignoring WAL-before-data

`multixact.c` **ignores the WAL-before-data rule for its own pages**;
it relies on the fact that the heap update that places the MXID in
`xmax` already follows the rule (so on crash, replay of the heap
record will trigger MXID lookup which can be reconstructed from WAL).
`CheckPointMultiXact` (`multixact.c:2039`) flushes/syncs all dirty
OFFSETs/MEMBERs pages **before** the checkpoint record is written so
that on crash, replay starts after a known-good state.
[from-comment] (`multixact.c:27-49`) [verified-by-code]
[via multixact.c.md].

### SLRU per-bank locking

- **Per-bank control LWLock**: bank = `pageno >> nBuffersPerBank_shift`;
  exclusive required for state mutation, shared allowed for
  `SimpleLruReadPage_ReadOnly`.
- **Per-buffer I/O LWLock**: a process performing physical I/O on a
  page takes the per-buffer lock and **releases the bank lock**; other
  waiters acquire the per-buffer lock in shared mode and immediately
  release. [from-comment] (`slru.c:18-49`) [via slru.c.md].
- **`latest_page_number` lock-free atomic** read/written via
  `pg_atomic_*`.
- **The latest page is never evicted.**
- **Re-dirtying during write is permitted** (mirrors bufmgr).

### Two-phase commit

- **GID reservation precedes WAL** so duplicate-GID rejection happens
  before any durable state [from-comment] (`twophase.c:17-22`).
- **Dummy PGPROC** keeps the prepared XID "running" in the ProcArray
  so `TransactionIdIsInProgress` still sees it after `PREPARE`
  [from-comment] (`twophase.c:24-26`).
- **State lifecycle WAL → `pg_twophase/<fxid>` at checkpoint.**
  `CheckPointTwoPhase(redo_horizon)` (`twophase.c:1828`) writes any
  gxact whose `prepare_start_lsn` is behind the redo horizon to its
  state file and flips `ondisk = true`. Commit/abort before checkpoint
  reads from WAL via `XlogReadTwoPhaseData`; after checkpoint reads
  from the file [from-comment] (`twophase.c:37-62`) [via twophase.c.md].

## 7. Interactions with other subsystems

- **`access/heap` + every index AM** — heap is rmgr `RM_HEAP_ID` (10)
  and `RM_HEAP2_ID` (11); every AM has its own rmgr + `rm_redo` (btree,
  hash, gin, gist, brin, spgist). All callers go through
  `xloginsert.c:XLogInsert` and redo via the dispatch in
  `xlogrecovery.c:ApplyWalRecord` → `RmgrTable[]` [via rmgr.c.md,
  xlogrecovery.c.md].
- **`storage/buffer`** — `FlushBuffer` calls `XLogFlush(BufferGetLSN)`
  to enforce WAL-before-data; `XLogNeedsFlush` lets bulkread rings
  reject dirty pages without flushing. Redo handlers use
  `xlogutils.c:XLogReadBufferForRedo*` to fetch pages [via
  xlogutils.c.md].
- **`storage/ipc/procarray`** — partner to `varsup.c` and `xact.c`
  for snapshot/commit interlocking (`ProcArrayEndTransaction`,
  `ComputeXidHorizons`, `TransactionIdIsInProgress`,
  `RecordKnownAssignedTransactionIds` during recovery) [from-README]
  (`README:251-339`).
- **`replication/`** — `walsender` reads WAL via the
  `read_local_xlog_page*` callbacks in `xlogutils.c`; `walreceiver`
  hands incoming bytes to `xlogrecovery.c`; `SyncRepWaitForLSN` runs
  inside `RecordTransactionCommit`. Logical decoding also uses
  `XLogReader` directly with `read_local_xlog_page*`.
- **`postmaster/checkpointer`** — calls `CreateCheckPoint` /
  `CreateRestartPoint` (in `xlog.c`, not deep-read here, §9). These
  call each SLRU's `CheckPoint*` and `CheckPointTwoPhase` and the
  buffer-pool checkpoint. The `DELAY_CHKPT_IN_COMMIT` /
  `DELAY_CHKPT_START` flags are read here.
- **`postmaster/walwriter`** — consumes `XLogBackgroundFlush`; honors
  `asyncXactLSN` advertised by `XLogSetAsyncXactLSN`.
- **`postmaster/pgarch`** — consumes `archive_status/<seg>.ready`
  markers created by `xlogarchive.c:XLogArchiveNotify`.
- **`storage/lmgr`** — registers per-prepare lock state via
  `lock_twophase_*` callbacks routed through `twophase_rmgr.c`.
- **`utils/activity/pgstat`** — `pgstat_twophase_*` callbacks for
  stats reconciliation on 2PC.

## 8. Tests

- **Recovery TAP suite** — `source/src/test/recovery/t/*.pl` covers
  the bulk of crash/archive/standby/promotion paths,
  `recovery_target_*`, two-phase commit recovery, prefetcher,
  invalid-page detection, replication.
- **`src/test/modules/test_slru`** — drives `slru.c` primitives
  directly (read, write, truncate, page-precedes wraparound) [via
  slru.c.md cross-ref].
- **`src/test/modules/xid_wraparound`** — exercises the
  `SetTransactionIdLimit` / `xidVacLimit` / `xidWarnLimit` /
  `xidStopLimit` machinery in `varsup.c` [via varsup.c.md cross-ref].
- **Regress** — `src/test/regress/sql/{transactions.sql,
  prepared_xacts.sql}` covers `BEGIN`/`COMMIT`/`SAVEPOINT` and the
  `PREPARE TRANSACTION` SQL surface.
- **Isolation** — `src/test/isolation/specs/` covers serialization,
  predicate locks, prepared transactions interacting with vacuum.
- **`contrib/test_decoding`, `contrib/pg_walinspect`** — exercise
  `xlogreader.c` + `xlogstats.c` in non-startup contexts.

## 9. Open questions / unverified claims

Carried forward from per-file docs. Highest risk first.

1. **`CreateCheckPoint` and `CreateRestartPoint`** are defined in
   `xlog.c` but not deep-read in the file-level pass. These are
   central to the durability story; the ordering of "flush WAL →
   write checkpoint record → fsync each SLRU → fsync buffer-pool →
   update `pg_control`" needs a follow-up. [unverified] [via
   xlog.c.md §Open].
2. **Detailed FPI compression dispatch** in `XLogRecordAssemble`
   (`pglz_compress` / `LZ4_compress*` / `ZSTD_compress*`) not
   re-derived. [unverified] [via xloginsert.c.md].
3. **`xact_redo_commit` step ordering** (clog before commit_ts? before
   sinval delivery?) not re-derived line-by-line; assumed to mirror
   live `RecordTransactionCommit` but cross-check pending.
   [unverified] [via xact.c.md].
4. **`SetTransactionIdLimit` margin constants** (≈ 3M / 11M / 1M /
   `MaxTransactionId/2`) — exact derivation of the vac/warn/stop
   thresholds not deep-read. [unverified] [via varsup.c.md].
5. **TLI-switch detail in `xlogrecovery.c:ApplyWalRecord`** — the
   exact branches that detect `XLOG_CHECKPOINT_SHUTDOWN` /
   `XLOG_END_OF_RECOVERY` and update `replayTLI` not re-derived from
   code; relied on comments. [unverified] [via xlogrecovery.c.md].
6. **Async-commit CLOG LSN group size of ~32** stated in the README
   (`README:837-854`) and reflected in code at `clog.c:670` is not
   pinned to a named constant (`CLOG_LSNS_PER_PAGE` or similar in
   `clog.h` — not located). [unverified] [via README.md, clog.c.md].
7. **Total locking order between WALInsertLock and other LWLocks**
   (e.g. buffer content lock, buffer mapping lock) not stated as a
   single comment; depends on the WAL-emitting AM's own discipline.
   [unverified].
8. **MultiXact lock ordering** (`MultiXactGenLock` vs
   `MultiXactOffsetSLRULock` / `MembersSLRULock`) not re-derived from
   a single comment. [unverified] [via multixact.c.md].
9. **`XLogBackgroundFlush` async-commit interaction** with
   `asyncXactLSN` is described in README but not re-derived from
   code. [unverified] [via xlog.c.md].
10. **`SyncRepWaitForLSN` window** inside `RecordTransactionCommit`
    after `DELAY_CHKPT_IN_COMMIT` is cleared — exact ordering not
    deep-read. [unverified] [via xact.c.md].

## 10. Glossary

- **LSN** — `XLogRecPtr`, 64-bit byte position in the logical WAL
  stream (skipping page headers via "usable byte position" encoding,
  `xlog.c:1899`). Monotonically increasing; printed as `X/Y`.
- **Redo** — replay of a WAL record's effect on data pages via
  `RmgrTable[xl_rmid].rm_redo`. The replayed state must be
  byte-identical to the pre-crash state for `wal_consistency_checking`
  to pass.
- **FPI (Full Page Image, BkpBlock)** — page-sized image attached
  to a WAL record when the page was dirtied since the last checkpoint
  (`RedoRecPtr`). Protects against torn-page hazards. The
  `REGBUF_STANDARD` flag triggers the `pd_lower..pd_upper` hole
  optimization to skip the unused middle of the page.
- **rmgr (Resource Manager)** — `RmgrId` + `RmgrData` callbacks
  (`redo`, `desc`, `identify`, `startup`, `cleanup`, `mask`, `decode`)
  registered in `RmgrTable[]`. Built-in IDs are compile-time
  (`rmgrlist.h`); extensions add into `[RM_MIN_CUSTOM_ID..
  RM_MAX_CUSTOM_ID]` via `RegisterCustomRmgr` during
  `shared_preload_libraries` only.
- **SLRU (Simple LRU)** — page-buffer cache for permanent files
  indexed by counters that wrap (XID, MXID, OID-style). Per-bank
  control LWLock + per-buffer I/O LWLock; the latest page is never
  evicted; `latest_page_number` is lock-free atomic.
- **Async commit** — `synchronous_commit = off` mode where
  `RecordTransactionCommit` returns after WAL insert without waiting
  for `XLogFlush`. The walwriter flushes; the CLOG-page LSN cache
  guarantees that the commit bit can't reach disk before its WAL
  record.
- **MXID (MultiXactId)** — alternative `xmax` for tuples that have
  multiple lockers (or lockers + an updater); points into pg_multixact
  OFFSETs which in turn point into MEMBERs holding the
  `MultiXactMember[]`.
- **2PC (Two-Phase Commit)** — `PREPARE TRANSACTION` writes
  `XLOG_XACT_PREPARE` with all per-rmgr state (Lock, MultiXact,
  PredicateLock, pgstat), reserves a `GlobalTransaction` slot with a
  dummy PGPROC. `COMMIT PREPARED` / `ROLLBACK PREPARED` later finishes
  via `XLOG_XACT_COMMIT_PREPARED` / `_ABORT_PREPARED`. Migrated to
  `pg_twophase/<fxid>` at checkpoint.
- **XID epoch** — high 32 bits of a `FullTransactionId`, advanced on
  XID wraparound. `nextXid` is stored as full XID so wraparound is
  observable without ambiguity.
- **Timeline (TLI)** — 32-bit counter incremented at each promotion /
  recovery branch point. `<tli>.history` files record parent TLI +
  switchpoint LSN; recovery uses them to decide which TLI a target
  LSN belongs to (`tliOfPointInHistory`, `tliSwitchPoint`).
- **`DELAY_CHKPT_IN_COMMIT`** — bit in `MyProc->delayChkptFlags` that
  blocks the next checkpoint from finishing while a backend is between
  "commit WAL inserted" and "pg_xact + ProcArray updated". Sister flag
  `DELAY_CHKPT_START` exists for slightly different windows.
- **VXID** — `VirtualTransactionId = (procNumber, LocalTransactionId)`.
  Cheap, always present; promoted to a real XID by
  `AssignTransactionId` only when the transaction writes.
- **Group XID-status update** — `clog.c`'s
  `TransactionGroupUpdateXidStatus`: one process updates the commit
  bits for several queued concurrent committers under a single SLRU
  bank-lock acquisition. Only enabled when subxids fit on the parent's
  page.
