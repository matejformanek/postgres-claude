# README (access/transam)

- **Source path:** `source/src/backend/access/transam/README`
- **Lines:** 913
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** every `.c` in `source/src/backend/access/transam/`, plus
  `source/src/include/access/{xact,xlog,xloginsert,xlogrecord,xlogreader,xlogrecovery,clog,multixact,subtrans,transam,slru,commit_ts,twophase,parallel,rmgr,generic_xlog,xlogwait}.h`.

## Purpose

The README is the canonical narrative for the `access/transam` subsystem.
It is the single highest-signal document anchoring three intertwined topics:
the transaction state machine (xact.c), the WAL/XLOG protocol (xlog*.c +
xloginsert.c), and the SLRU-backed transaction-status caches (clog.c,
subtrans.c, multixact.c, commit_ts.c).
[from-README] `source/src/backend/access/transam/README:1-913`.

## Top-of-file comment (verbatim)

The README has no top-of-file comment in the C-style; the document title and
section headers play that role. Section list (verbatim headings, exact line
numbers):

- `The Transaction System` — `README:3` [from-README]
- `Subtransaction Handling` — `README:148` [from-README]
- `Transaction and Subtransaction Numbering` — `README:190` [from-README]
- `Interlocking Transaction Begin, Transaction End, and Snapshots` — `README:224` [from-README]
- `pg_xact and pg_subtrans` — `README:342` [from-README]
- `Write-Ahead Log Coding` — `README:399` [from-README]
- `Constructing a WAL record` — `README:489` [from-README]
- `Writing a REDO routine` — `README:607` [from-README]
- `Writing Hints` — `README:629` [from-README]
- `Write-Ahead Logging for Filesystem Actions` — `README:666` [from-README]
- `Skipping WAL for New RelFileLocator` — `README:745` [from-README]
- `Asynchronous Commit` — `README:777` [from-README]
- `Transaction Emulation during Recovery` — `README:887` [from-README]

## Public surface

The README is documentation, not code. It calls out the *public surface of
xact.c that postgres.c depends on*: `StartTransactionCommand`,
`CommitTransactionCommand`, `AbortCurrentTransaction`, and the SQL-driven
toplevel routines `BeginTransactionBlock`, `EndTransactionBlock`,
`UserAbortTransactionBlock`, `DefineSavepoint`, `RollbackToSavepoint`,
`ReleaseSavepoint`. These dispatch to the low-level functions
`StartTransaction`, `CommitTransaction`, `AbortTransaction`,
`CleanupTransaction`, `StartSubTransaction`, `CommitSubTransaction`,
`AbortSubTransaction`, `CleanupSubTransaction`. [from-README] `README:11-39`.

For WAL it lists the five-function record-construction API:
`XLogBeginInsert`, `XLogResetInsertion`, `XLogEnsureRecordSpace`,
`XLogRegisterBuffer`, `XLogRegisterData`, `XLogRegisterBufData`,
`XLogInsert`. [from-README] `README:499-605`.

## Key types / structs

The README is type-light; it names but does not define `TransactionState`
(stack, in xact.c), `XLogRecData` chain (assembled by xloginsert.c), `XID`,
`VXID` (procNumber + counter), `SubTransactionId`, `MultiXactMember`, and
`LSN`. Concrete struct definitions live in the headers (see companion
header docs). [from-README] `README:151`, `README:205-221`,
`README:411-417` (timeline mention), `README:407-414` (LSN).

## Key invariants and locking

Captured in this file because the README is where they are stated as
prose. Each is the canonical statement; redo routines and snapshot code
in other subsystems must respect them.

1. **WAL-before-data.** "Each data page is marked with the LSN of the
   latest XLOG record affecting the page. Before the bufmgr can write
   out a dirty page, it must ensure that xlog has been flushed to disk
   at least up to the page's LSN." [from-README] `README:411-415`.

2. **Critical-section WAL pattern.** Steps 1-7 in `README:437-469`
   prescribe pin → exclusive-lock → `START_CRIT_SECTION` → mutate
   buffers → `MarkBufferDirty` (before XLogInsert) → `XLogInsert` →
   `PageSetLSN` → `END_CRIT_SECTION` → unlock/unpin. Failure inside
   the critical section must PANIC. [from-README] `README:439-469`.

3. **MarkBufferDirty must happen before XLogInsert** "see notes in
   SyncOneBuffer()". [from-README] `README:451-452`.

4. **Snapshot/commit serialization.** "no transaction may exit the
   set of currently-running transactions between the time we fetch
   latestCompletedXid and the time we finish building our snapshot."
   Enforced by `ProcArrayEndTransaction` taking `ProcArrayLock`
   exclusive on commit/abort, while `GetSnapshotData` takes it
   shared. [from-README] `README:246-270`.

5. **Read-only transactions can exit without `ProcArrayLock`.**
   They don't affect anyone else's snapshot. [from-README]
   `README:267-270`.

6. **XidGenLock interlock.** `GetNewTransactionId` must store the
   new XID into shared ProcArray before releasing `XidGenLock`.
   Otherwise `latestCompletedXid` could advance past a not-yet-visible
   XID, breaking `ComputeXidHorizons`. [from-README] `README:272-285`.

7. **Atomic XID fetch/store.** `GetNewTransactionId` stores XID into
   `ProcGlobal->xids[]` without `ProcArrayLock`, relying on atomic
   read/store; readers must fetch once and use volatile pointers.
   [from-README] `README:286-294`.

8. **Child XID > parent XID.** When assigning XIDs to nested
   subtransactions, the parent is always assigned first; "child
   transactions have XIDs later than their parents". This invariant is
   assumed in many places. [from-README] `README:194-198`.

9. **Two-phase clog commit when status spans pages.** When commit
   status of a top xact + its subxacts spans multiple CLOG pages,
   subxacts are marked sub-committed first, then top + subxacts marked
   committed atomically (single-page case skips sub-commit). Subxact
   abort is always marked immediately. [from-README] `README:357-368`.

10. **Async-commit CLOG LSN tracking.** For each CLOG page we
    remember the LSN of the latest commit affecting it (actually a
    small set: one LSN per 32 transactions, the "group" cache).
    [from-README] `README:815-854`.

11. **Hint-bit deferral for async commit.** A transaction-committed
    hint bit cannot be set on a heap page if its commit LSN has not
    yet been flushed; hint setting is deferred until WAL is flushed
    past the commit LSN. [from-README] `README:822-830`.

12. **PD_ALL_VISIBLE special case.** It is treated as both a durable
    change (clearing) and a hint (setting under no-checksum,
    no-wal_log_hints). Setting without WAL must not update the page
    LSN. [from-README] `README:648-665`.

13. **Skipping WAL for new relfilenumbers requires fsync at commit.**
    Under `wal_level=minimal`, in-tree access methods writing to a
    relfilenumber that ROLLBACK would unlink skip WAL. `CommitTransaction()`
    writes and fsyncs affected blocks before recording the commit.
    [from-README] `README:745-775`.

14. **No serialization of replay vs hot-standby reads.** Only
    Startup process modifies data blocks during recovery; redo can call
    `PageGetLSN()` without locking, all others need exclusive buffer
    lock or shared + buffer header lock. [from-README] `README:620-626`.

## Functions of note (≥3 ≤8)

The README itself does not implement code, but it pins down the
behavior contract for these:

1. **`StartTransactionCommand`/`CommitTransactionCommand`** —
   state-smart middle layer called by postgres.c before/after each
   query. [from-README] `README:11-17`, `README:84-88`. Implementation
   in `xact.c`.

2. **`XLogInsert`** — assemble + insert a WAL record, returns the LSN
   that callers store via `PageSetLSN`. [from-README] `README:457-465`.
   Implementation in `xloginsert.c` (xact-level entry) over
   `xlog.c:XLogInsertRecord`.

3. **`XLogRegisterBuffer`** — declares a modified buffer; XLogInsert
   may decide to attach a full-page image. Flag set governs FPI
   behavior: `REGBUF_FORCE_IMAGE`, `REGBUF_NO_IMAGE`,
   `REGBUF_WILL_INIT`, `REGBUF_STANDARD`, `REGBUF_KEEP_DATA`.
   [from-README] `README:555-588`.

4. **`MarkBufferDirtyHint`** — used when writing hint bits, may
   insert `XLOG_FPI_FOR_HINT` to protect from torn pages under
   checksums. [from-README] `README:636-647`.

5. **`GetSnapshotData` / `ProcArrayEndTransaction` /
   `ComputeXidHorizons`** — the snapshot/commit dance described in
   detail. [from-README] `README:251-339`.

6. **`GetNewTransactionId`** — allocates XID, stores into
   `ProcGlobal->xids[]`, then releases XidGenLock. [from-README]
   `README:274-285`. Implementation in `varsup.c`.

## Cross-references

- `xact.c` (`source/src/backend/access/transam/xact.c`) implements the
  state machine.
- `xlog.c`, `xloginsert.c`, `xlogrecovery.c`, `xlogreader.c`,
  `xlogutils.c` implement the WAL machinery described in §"Write-Ahead
  Log Coding" through §"Asynchronous Commit".
- `clog.c`, `subtrans.c`, `multixact.c`, `commit_ts.c` implement the
  SLRU-backed transaction-status caches described in §"pg_xact and
  pg_subtrans".
- `varsup.c` implements XID/OID allocation.
- `procarray.c` (in `storage/ipc/`) is the partner that the snapshot
  serialization rules talk about; the README defers details there.
  [from-README] `README:390-391`.
- `parallel.c` is the parallel-worker bridge — README does not cover
  it; see `README.parallel` for parallel-mode semantics.
- `twophase.c` implements `PREPARE TRANSACTION`.
- `timeline.c` handles timeline history files.
- `generic_xlog.c` implements a delta-record API for extensions.

## Open questions

- The README's description of the async-commit hint-bit LSN cache
  (`README:837-854`) says "we choose to store a smaller number of
  LSNs per page". The actual group size of 32 must be verified in
  `clog.c`. [unverified]
- "We are thereby relying on fetch/store of an XID to be atomic"
  (`README:289-294`) — the README does not name the C type guarantee;
  `TransactionId` is `uint32`, so on all supported targets this is a
  naturally atomic store. [inferred]
- §"Transaction Emulation during Recovery" (`README:887-913`) leaves
  the detailed lock-rmgr behavior to comments in lock-rmgr code;
  cross-check with `storage/lmgr/`. [unverified]

## Confidence tag tally

- `[verified-by-code]`: 0 (README is documentation, not code).
- `[from-README]`: 27.
- `[from-comment]`: 0.
- `[from-readme]` (skill alias): 0.
- `[inferred]`: 1.
- `[unverified]`: 3.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/access-transam.md](../../../../../subsystems/access-transam.md)
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
