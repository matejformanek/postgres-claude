# `storage/buffer/bufmgr.c`

- **Source:** `source/src/backend/storage/buffer/bufmgr.c` (8 967 lines)
- **Header:** `source/src/include/storage/bufmgr.h` (public),
  `source/src/include/storage/buf_internals.h` (private)
- **README:** `source/src/backend/storage/buffer/README`
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)

## 1. Purpose

The buffer manager façade. Owns the shared-buffer cache between PostgreSQL
backends and `smgr`. From the top-of-file comment `[from-comment]`
(`bufmgr.c:15-34`):

> Principal entry points:
> `ReadBuffer()`, `StartReadBuffer()`, `StartReadBuffers()`,
> `WaitReadBuffers()`, `ReleaseBuffer()`, `MarkBufferDirty()`.
>
> See also: `freelist.c` (victim selection), `buf_table.c` (lookup table).

Everything else in this file falls into one of: lookup/allocation
(`BufferAlloc`, `GetVictimBuffer`, `InvalidateBuffer`), pin management
(`PinBuffer`, `UnpinBuffer`, `PrivateRefCount*`), content locking
(`BufferLockAcquire`, `BufferLockUnlock`, `BufferLockConditional` and the
cleanup-lock helpers), I/O coordination (`StartSharedBufferIO`, `WaitIO`,
`TerminateBufferIO`, `AbortBufferIO`, `FlushBuffer`), bulk operations
(`DropRelationBuffers`, `FlushRelationBuffers`, `CheckPointBuffers`,
`BgBufferSync`), the header spinlock (`LockBufHdr`, `WaitBufHdrUnlocked`),
and the AIO read-stream callbacks (`shared_buffer_readv_*` + helpers).

## 2. Public surface (header `bufmgr.h`)

| Category | Functions |
|---|---|
| Read/extend | `ReadBuffer`, `ReadBufferExtended`, `ReadBufferWithoutRelcache`, `ReadRecentBuffer`, `ExtendBufferedRel`, `ExtendBufferedRelBy`, `ExtendBufferedRelTo` (`bufmgr.c:818-1031`) |
| Streaming read | `StartReadBuffer`, `StartReadBuffers`, `WaitReadBuffers` (`bufmgr.c:1617-1759`) |
| Prefetch | `PrefetchBuffer`, `PrefetchSharedBuffer` (`bufmgr.c:697-787`) |
| Release | `ReleaseBuffer`, `UnlockReleaseBuffer`, `ReleaseAndReadBuffer`, `IncrBufferRefCount` (`bufmgr.c:3220-, 5595-, 5679-`) |
| Dirtying | `MarkBufferDirty`, `MarkBufferDirtyHint`, `BufferBeginSetHintBits`, `BufferFinishSetHintBits`, `BufferSetHintBits16` (`bufmgr.c:3156, 5830, 7051-7148`) |
| Locking | `LockBufferInternal` (wrapped by `LockBuffer` macro), `UnlockBuffer`, `ConditionalLockBuffer`, `LockBufferForCleanup`, `ConditionalLockBufferForCleanup`, `IsBufferCleanupOK`, `CheckBufferIsPinnedOnce` (`bufmgr.c:6567-6910`) |
| Tag / introspection | `BufferGetBlockNumber`, `BufferGetTag`, `BufferIsPermanent`, `BufferGetLSNAtomic`, `BufferIsDirty`, `BufferIsLockedByMe{,InMode}`, `DebugPrintBufferRefcount` (`bufmgr.c:3069-3122, 4398, 4455-, 4686-, 4722-`) |
| Bulk drop / flush | `DropRelationBuffers`, `DropRelationsAllBuffers`, `DropDatabaseBuffers`, `FlushRelationBuffers`, `FlushRelationsAllBuffers`, `FlushDatabaseBuffers`, `FlushOneBuffer`, `CreateAndCopyRelationData` (`bufmgr.c:4774-, 4894-, 5124-, 5171-, 5259-, 5471-, 5535-, 5575-`) |
| Checkpointer / bgwriter | `CheckPointBuffers`, `BufferSync` (static), `BgBufferSync`, `SyncOneBuffer` (static) (`bufmgr.c:4441, 3561, 3840, 4138`) |
| Resource-owner integration | `AtEOXact_Buffers`, `AtProcExit_Buffers`, `CheckForBufferLeaks`, `InitBufferManagerAccess`, `AssertBufferLocksPermitCatalogRead` (`bufmgr.c:4207-4364`) |
| Test/debug | `EvictUnpinnedBuffer`, `EvictAllUnpinnedBuffers`, `EvictRelUnpinnedBuffers`, `MarkDirtyUnpinnedBuffer`, `MarkDirtyRelUnpinnedBuffers`, `MarkDirtyAllUnpinnedBuffers` (`bufmgr.c:7900-8290`) |
| Pin-limit helpers | `GetPinLimit`, `GetAdditionalPinLimit`, `LimitAdditionalPins` (`bufmgr.c:2695-2750`) |
| Writeback | `WritebackContextInit`, `ScheduleBufferTagForWriteback`, `IssuePendingWritebacks` (`bufmgr.c:7687-7831`) |
| AIO callbacks | `shared_buffer_readv_stage`, `shared_buffer_readv_complete{,_local}`, `local_buffer_readv_*` + the `buffer_*` helpers (`bufmgr.c:8290-8967`) |
| Recovery helper | `HoldingBufferPinThatDelaysRecovery` (`bufmgr.c:6826`) |
| Header spinlock | `LockBufHdr`, `WaitBufHdrUnlocked` (`bufmgr.c:7527-7593`) |
| Aux | `BufferIO` Start/Terminate/Abort (see §3.7), `RelationGetNumberOfBlocksInFork` (`bufmgr.c:4654`) |

## 3. Functions of note (control flow)

### 3.1 `ReadBuffer` family (`bufmgr.c:879-1368`)

`ReadBuffer(reln, blknum)` → `ReadBufferExtended(reln, MAIN_FORKNUM, blknum, RBM_NORMAL, NULL)` `[verified-by-code]` (`bufmgr.c:879-940`).
`ReadBufferExtended` dispatches `P_NEW` to `ExtendBufferedRel`, then calls
`ReadBuffer_common`. `ReadBuffer_common` is the pinch point that:

1. resolves the `SMgrRelation` and persistence;
2. validates the block number against the fork size;
3. special-cases `RBM_ZERO_*` (calls `PinBufferForBlock` then
   `ZeroAndLockBuffer`);
4. for normal reads, calls `StartReadBuffer` + `WaitReadBuffers` with the
   `READ_BUFFERS_SYNCHRONOUSLY` flag.

`[verified-by-code]` (`bufmgr.c:1275-1368`).

### 3.2 `BufferAlloc` (`bufmgr.c:2197-2351`) — heart of the lookup

`pg_attribute_always_inline`. Returns a pinned `BufferDesc` and `*foundPtr`.
Algorithm (line cites in `subsystems/storage-buffer.md` §5.1; summary):

1. Build `BufferTag`; `BufTableHashCode(&newTag) → newHash`; partition lock
   `BufMappingPartitionLock(newHash)`.
2. **Hit path** — acquire partition lock SHARED, `BufTableLookup`. If found,
   `PinBuffer` the descriptor *before* releasing the partition lock (README
   rule) `[from-README]` (`README:127-134`).
3. **Miss path** — release the share lock, call `GetVictimBuffer` to get a
   pinned, invalid victim; re-acquire partition lock EXCLUSIVE,
   `BufTableInsert`. If somebody raced and inserted first, unpin our
   victim and fall back to the hit branch.
4. Otherwise: `LockBufHdr`, assign tag, `UnlockBufHdrExt(...,
   BM_TAG_VALID|BUF_USAGECOUNT_ONE, 0, 0)`, release partition lock.

Returns with `*foundPtr=false`; caller fills the page via the AIO read path.

### 3.3 `GetVictimBuffer` (`bufmgr.c:2547-2693`)

Orchestrates clock-sweep eviction:

1. `ReservePrivateRefCountEntry` and `ResourceOwnerEnlarge`.
2. `StrategyGetBuffer(strategy, &buf_state, &from_ring)` → returns a pinned
   buffer (clock-sweep in `freelist.c`).
3. If `BM_DIRTY`: try **conditional** `BUFFER_LOCK_SHARE_EXCLUSIVE`; on
   failure unpin and restart — this avoids the documented two-backend
   btree-split deadlock `[from-comment]` (`bufmgr.c:2584-2611`).
4. If ring buffer + permanent rel + `!XLogNeedsFlush(LSN)`,
   `StrategyRejectBuffer` lets us skip the WAL flush.
5. `FlushBuffer(buf, NULL, IOOBJECT_RELATION, io_context)` to write out.
6. If `BM_TAG_VALID`, `InvalidateVictimBuffer` re-acquires the *old* partition
   lock exclusive, takes header spinlock, re-verifies refcount=1 and
   !dirty, `BufTableDelete`s the mapping. If any check fails, unpin and
   restart `[verified-by-code]` (`bufmgr.c:2461-2545, 2664-2673`).

### 3.4 `PinBuffer` (`bufmgr.c:3280-3372`)

Lock-free pin via CAS. Backend-local `PrivateRefCount` is consulted first
— a repeat pin only bumps the local refcount + `ResourceOwnerRememberBuffer`.
First-time pin walks a CAS loop on the shared `state` word: skip while
`BM_LOCKED`, then `state += BUF_REFCOUNT_ONE`; bump usagecount unless capped
at `BM_MAX_USAGE_COUNT=5` (or set to 1 for strategy rings, since rings
shouldn't evict other backends' buffers) `[verified-by-code]`
(`bufmgr.c:3299-3345`). Returns whether the buffer is `BM_VALID`.

Caller contract: "`ResourceOwnerEnlarge()` and `ReservePrivateRefCountEntry()`
must have been done already" `[from-comment]` (`bufmgr.c:3272-3274`).

### 3.5 `PinBuffer_Locked` (`bufmgr.c:3396-3417`)

Spinlock variant — caller has already set `BM_LOCKED` and wants to release
it while bumping refcount in one atomic step (via `UnlockBufHdrExt`).
Asserts no pre-existing private pin from this backend, so it can skip the
private-refcount lookup `[from-comment]` (`bufmgr.c:3387-3394`).

### 3.6 `UnpinBuffer` / `UnpinBufferNoOwner` (`bufmgr.c:3465-3514`)

Decrement the private refcount first. Only when it reaches zero do we touch
shared state: `VALGRIND_MAKE_MEM_NOACCESS`, assert no content lock held
(`!BufferLockHeldByMe(buf)`), `pg_atomic_fetch_sub_u64(&state, BUF_REFCOUNT_ONE)`,
and if the old state had `BM_PIN_COUNT_WAITER` set, `WakePinCountWaiter(buf)`
`[verified-by-code]` (`bufmgr.c:3486-3513`).

### 3.7 I/O coordination — `StartSharedBufferIO`, `WaitIO`, `TerminateBufferIO`, `AbortBufferIO` (`bufmgr.c:7148-7466`)

- `StartSharedBufferIO(buf, forInput, wait, io_wref)` — sets
  `BM_IO_IN_PROGRESS` on a pinned buffer. Three return values:
  `BUFFER_IO_READY_FOR_IO` (we own the I/O), `BUFFER_IO_ALREADY_DONE`
  (someone finished it while we waited), `BUFFER_IO_IN_PROGRESS` (someone
  else is doing it; we may have been handed an `io_wref` to wait on async).
  Wait modes: pass `io_wref != NULL` to get the AIO wait reference back;
  `wait=true` plus `io_wref=NULL` falls back to synchronous `WaitIO`. Must
  `pgaio_submit_staged()` before waiting to avoid deadlocks
  `[from-comment]` (`bufmgr.c:7211-7248`) `[verified-by-code]`
  (`bufmgr.c:7250-7322`).
- `WaitIO(buf)` (`bufmgr.c:7148-7208`) — uses the buffer's
  `ConditionVariable` (`BufferIOCVArray`) plus, if the I/O is AIO, the
  buffer's `io_wref`. Re-reads `state` under `LockBufHdr` each iteration
  because the spinlock is essential for correctness here
  `[from-comment]` (`bufmgr.c:7165-7170`).
- `TerminateBufferIO(buf, clear_dirty, set_flag_bits, forget_owner, release_aio)`
  (`bufmgr.c:7366-7413`) — clears `BM_IO_IN_PROGRESS | BM_IO_ERROR` (and
  optionally `BM_DIRTY | BM_CHECKPOINT_NEEDED`), applies caller's
  `set_flag_bits` (e.g. `BM_VALID` after a successful read), broadcasts the
  CV. If `release_aio` and the cleared state shows `BM_PIN_COUNT_WAITER`,
  `WakePinCountWaiter` (covers the case where this backend was completing
  another backend's AIO and the AIO pin was the last non-waiter pin).
- `AbortBufferIO(buffer)` (`bufmgr.c:7428-`) — called from
  `AtProcExit_Buffers` / abort cleanup; sets `BM_IO_ERROR` if a write was
  interrupted; emits notice on repeated failures.

### 3.8 `FlushBuffer` (`bufmgr.c:4512-4628`)

WAL-before-data writer:

1. Asserts content lock held in `BUFFER_LOCK_EXCLUSIVE` or
   `SHARE_EXCLUSIVE` `[verified-by-code]` (`bufmgr.c:4520-4521`).
2. `StartSharedBufferIO(buf, false, true, NULL)` — returns
   `BUFFER_IO_ALREADY_DONE` ⇒ somebody else flushed, return.
3. Read LSN under the (share-exclusive minimum) content lock so it can't be
   torn `[from-comment]` (`bufmgr.c:4547-4551`).
4. **Only if `BM_PERMANENT`**: `XLogFlush(recptr)`. Unlogged rels have
   "fake LSNs" from `XLogGetFakeLSN` that can outrun the WAL insert
   pointer, so flushing them would `PANIC` `[from-comment]`
   (`bufmgr.c:4553-4569`).
5. `PageSetChecksum`, `smgrwrite(reln, fork, blockNum, bufBlock, false)`,
   `pgstat_count_io_op_time`, `pgBufferUsage.shared_blks_written++`.
6. `TerminateBufferIO(buf, true, 0, true, false)` — clears `BM_DIRTY` and
   `BM_IO_IN_PROGRESS`.

`FlushUnlockedBuffer` (`bufmgr.c:4634-`) wraps `FlushBuffer` with a
share-exclusive `BufferLockAcquire`/release.

### 3.9 `MarkBufferDirty` (`bufmgr.c:3156-3205`)

Asserts pinned + `BUFFER_LOCK_EXCLUSIVE`. CAS loop on `state`:
if `BM_LOCKED`, `WaitBufHdrUnlocked`; otherwise OR in `BM_DIRTY` and CAS.
If the buffer wasn't already dirty, bumps `pgBufferUsage.shared_blks_dirtied`
and (if VACUUM cost accounting) `VacuumCostBalance` `[verified-by-code]`
(`bufmgr.c:3180-3204`).

The hint-bit path (`MarkBufferDirtyHint` at `bufmgr.c:5830`) is the
"dirty without WAL" variant for things like `HEAP_XMIN_COMMITTED`; uses
share-exclusive content lock via `SharedBufferBeginSetHintBits` /
`BufferFinishSetHintBits` and skips WAL when checksums are off (full-page
writes would be required to make hint-bit changes safe against torn pages
if checksums are on).

### 3.10 Content-lock primitives (`bufmgr.c:5907-6534`)

The content lock lives in the **top 20 bits of `state`** since PG 18 (it
used to be an LWLock). Modes:

- `BUFFER_LOCK_SHARE`
- `BUFFER_LOCK_SHARE_EXCLUSIVE` (the "writeout in progress" mode that
  allows concurrent share readers but blocks new exclusive)
- `BUFFER_LOCK_EXCLUSIVE`

`BufferLockAcquire(buffer, buf_hdr, mode)` (`bufmgr.c:5907-6017`):

1. Lookup the `PrivateRefCountEntry`; assert no double-lock.
2. `HOLD_INTERRUPTS()` to keep cancel from leaving a hung waiter.
3. CAS-attempt the lock via `BufferLockAttempt`.
4. On contention: `BufferLockQueueSelf` (adds self to `lock_waiters`
   under header spinlock; sets `BM_LOCK_HAS_WAITERS`), retry the CAS once
   (to close the wakeup race), then `PGSemaphoreLock(MyProc->sem)` in a loop
   while `MyProc->lwWaiting != LW_WS_NOT_WAITING`. On wakeup,
   clear `BM_LOCK_WAKE_IN_PROGRESS` so `BufferLockReleaseSub` can wake
   the next waiter `[verified-by-code]` (`bufmgr.c:5938-6007`).

`BufferLockUnlock` (`bufmgr.c:6022-6045`): atomically subtract the
mode-specific value via `BufferLockReleaseSub`; on contention edge, call
`BufferLockProcessRelease` to dequeue and signal a waiter. `RESUME_INTERRUPTS`.

`BufferLockConditional` (`bufmgr.c:6058-6093`): try once via
`BufferLockAttempt`; if blocked, drop interrupt hold-off and return false.
Refuses if this backend already holds the lock — "we currently do not have
space to track multiple lock ownerships of the same buffer within one
backend" `[from-comment]` (`bufmgr.c:6051-6057`).

Public wrappers: `UnlockBuffer` (`6567`), `LockBufferInternal` (`6583`,
called by the `LockBuffer` macro with `mode` passed as a literal so the
compiler specialises per-mode), `ConditionalLockBuffer` (`6625`, hard-codes
`BUFFER_LOCK_EXCLUSIVE`).

### 3.11 Cleanup-lock dance — `LockBufferForCleanup` (`bufmgr.c:6678-6818`)

"Items may be deleted from a disk page only when the caller (a) holds an
exclusive lock on the buffer and (b) has observed that no other backend
holds a pin on the buffer" `[from-comment]` (`bufmgr.c:6664-6671`).

Loop:

1. `LockBuffer(buffer, BUFFER_LOCK_EXCLUSIVE)`.
2. `LockBufHdr(bufHdr)` — read `state`.
3. If `BUF_STATE_GET_REFCOUNT(buf_state) == 1` — we're the only pinner,
   `UnlockBufHdr` and return.
4. Otherwise: if `BM_PIN_COUNT_WAITER` already set,
   `ERROR "multiple backends attempting to wait for pincount 1"`
   `[verified-by-code]` (`bufmgr.c:6738-6743`). Write `MyProcNumber` to
   `wait_backend_pgprocno`, `UnlockBufHdrExt(..., BM_PIN_COUNT_WAITER, 0, 0)`,
   release the content lock, `ProcWaitForSignal(WAIT_EVENT_BUFFER_CLEANUP)`
   (or `ResolveRecoveryConflictWithBufferPin` in hot standby).
5. On wake: retake the header spinlock; if we're still the waiter, clear
   `BM_PIN_COUNT_WAITER`. Loop back to step 1.

`UnpinBuffer` calls `WakePinCountWaiter` (`bufmgr.c:3428-3456`) when the
unpinned buffer's `BM_PIN_COUNT_WAITER` is set and the post-unpin refcount
is 1; that helper re-reads `wait_backend_pgprocno` under header spinlock,
clears the flag in one CAS, and `ProcSendSignal(pgprocno)`.

`ConditionalLockBufferForCleanup` (`bufmgr.c:6852-6899`): single-shot
non-blocking version. Used by VACUUM where it must give up if cleanup
isn't immediately available.

`IsBufferCleanupOK` (`bufmgr.c:6910-`): caller already has exclusive
content lock; just sample the refcount under header spinlock.

### 3.12 `DropRelationBuffers` (`bufmgr.c:4774-4892`)

Two regimes selected by `BUF_DROP_FULL_SCAN_THRESHOLD = NBuffers/32`
`[verified-by-code]` (`bufmgr.c:95, 4836-4842`):

- **Small drop, fork sizes known** → `FindAndDropRelationBuffers` does a
  per-block lookup in the partitioned hash (cheap).
- **Large drop or unknown size** → linear scan of all `NBuffers`
  descriptors. Tag pre-check is **lockless** — safe because the caller
  must hold `AccessExclusiveLock`, so no new tag for this rel can appear
  while we scan `[from-comment]` (`bufmgr.c:4849-4865`). On match,
  `LockBufHdr`, re-check tag, `InvalidateBuffer`.

`InvalidateBuffer` (`bufmgr.c:2369-2459`) is entered with header spinlock
held; it drops the spinlock, acquires `oldPartitionLock` exclusive, retakes
the spinlock, double-checks tag and that refcount == 0, clears
tag/flags/usagecount, `BufTableDelete`s, releases. Concurrent activity
(re-pin) is handled by retry.

`DropRelationLocalBuffers` is dispatched when `RelFileLocatorBackendIsTemp`
and the locator's backend matches `MyProcNumber`.

### 3.13 Checkpoint writers — `CheckPointBuffers`, `BufferSync`, `BgBufferSync` (`bufmgr.c:4441, 3561, 3840`)

`CheckPointBuffers(flags)` is the entry point invoked by the checkpointer.
It calls `BufferSync(flags)` (static), which:

1. Sweeps all `NBuffers` descriptors marking dirty ones `BM_CHECKPOINT_NEEDED`.
2. Builds a sorted `CkptSortItem` array (sort key = tablespace, rel, fork,
   block) so writes go out in physical order across tablespaces, with
   round-robin progress between tablespaces via a binary heap keyed by
   `ts_ckpt_progress_comparator` (`bufmgr.c:7664-`).
3. For each victim: `SyncOneBuffer` (`bufmgr.c:4137-`) which takes
   share-exclusive lock and calls `FlushBuffer`.
4. Throttles per `checkpoint_completion_target`.

`BgBufferSync(wb_context)` (`bufmgr.c:3839-`) is the bgwriter's loop body —
runs the LRU-style cleaning sweep ahead of the clock hand. Adaptive: it
tracks recent allocation rate and aims to keep enough clean buffers ahead
of the sweep.

### 3.14 Header spinlock — `LockBufHdr` / `WaitBufHdrUnlocked` (`bufmgr.c:7527-7593`)

`LockBufHdr` uses `pg_atomic_fetch_or_u64(&desc->state, BM_LOCKED)` once
without spin infrastructure (the common case), then enters a spin loop with
`init_local_spin_delay` / `perform_spin_delay` only on contention
`[verified-by-code]` (`bufmgr.c:7533-7565`). Asserts `!BufferIsLocal`
(`bufmgr.c:7531`) — local buffers never need the header spinlock.

`WaitBufHdrUnlocked` is the same spin loop but without acquiring the lock;
used inside CAS loops in `PinBuffer`, `MarkBufferDirty`, etc.

### 3.15 AIO read-stream callbacks (`bufmgr.c:8290-8967`)

Registered with the `pgaio` subsystem via `aio_shared_buffer_readv_cb` and
`aio_local_buffer_readv_cb` (declared in `bufmgr.h`). The callback shape:

- `*_readv_stage(ioh, cb_data)` — runs at submit time; mostly delegates to
  `buffer_stage_common`.
- `*_readv_complete(ioh, prior_result, cb_data)` — runs at completion;
  iterates the batched buffers, calls `buffer_readv_complete_one` to set
  `BM_VALID`/`BM_IO_ERROR`, and `TerminateBufferIO(release_aio=true)`.

`buffer_readv_complete_one` is where checksum verification and zero-page
handling for `RBM_ZERO_ON_ERROR` happen `[verified-by-code]`
(`bufmgr.c:8534-`).

### 3.16 Backend-local pin tracking (`bufmgr.c:101-565`)

`PrivateRefCountData` (refcount, lockmode) is held in a small fixed-size
array (`REFCOUNT_ARRAY_ENTRIES`) for fast access plus an overflow hash
(`PrivateRefCountHash`). `ReservedRefCountSlot` is a single slot reserved
to make `PinBuffer_Locked` impossible to fail. `GetPrivateRefCountEntry`,
`NewPrivateRefCountEntry`, `ForgetPrivateRefCountEntry`,
`ReservePrivateRefCountEntry` are the workhorses; documented at length in
the comments around lines 200-400.

## 4. Key invariants

1. **Pin before content-lock.** Every content-lock acquire path asserts
   `BufferIsPinned(buffer)` `[verified-by-code]` (`bufmgr.c:6597, 6630, 6686`).
2. **Hold partition lock until after pinning on the hit path.** `BufferAlloc`
   `PinBuffer`s under the partition lock before releasing it `[from-README]`
   (`README:127-134`).
3. **Header spinlock held for at most a few instructions.** Code never
   sleeps, errors, or allocates with `BM_LOCKED` held. `LockBufHdr`/
   `UnlockBufHdr*` are the only acquire/release; longer multi-step
   sequences use `UnlockBufHdrExt` to combine release with state delta.
4. **`FlushBuffer` requires `BUFFER_LOCK_EXCLUSIVE` or `SHARE_EXCLUSIVE`** —
   asserted at `bufmgr.c:4520-4521`.
5. **`FlushBuffer` only `XLogFlush`es if `BM_PERMANENT`** — fake LSNs on
   unlogged rels could `PANIC` otherwise `[from-comment]`
   (`bufmgr.c:4553-4569`).
6. **`LockBufferForCleanup` allows only one waiter per buffer** — second
   waiter `ERROR`s rather than silently replacing the first's procnumber
   `[verified-by-code]` (`bufmgr.c:6738-6743`).
7. **`MarkBufferDirty` requires `BUFFER_LOCK_EXCLUSIVE`** (`bufmgr.c:3174`);
   the hint-bit path is the only way to dirty under share-exclusive.
8. **`PinBuffer` callers must `ReservePrivateRefCountEntry` +
   `ResourceOwnerEnlarge` first** `[from-comment]` (`bufmgr.c:3272-3274`).
9. **Local buffers bypass the header spinlock and the content-lock
   subfield entirely** — `LockBufHdr` asserts `!BufferIsLocal`, all
   `BufferLock*` paths early-return for local buffers
   `[verified-by-code]` (`bufmgr.c:6598, 7531`).
10. **`UnpinBuffer` asserts the content lock is not held** — must
    `LockBuffer(BUFFER_LOCK_UNLOCK)` first or call `UnlockReleaseBuffer`
    `[verified-by-code]` (`bufmgr.c:3503`).

## 5. Cross-references

- `storage/buffer/freelist.c` — `StrategyGetBuffer`, clock-sweep.
- `storage/buffer/buf_table.c` — `BufTableLookup/Insert/Delete`, locks
  not taken inside.
- `storage/buffer/buf_init.c` — shmem allocation of
  `BufferDescriptors`/`BufferBlocks`/`BufferIOCVArray`/`CkptBufferIds`.
- `storage/buffer/localbuf.c` — backend-local equivalent for temp tables.
- `storage/buffer/README` — canonical narrative for the access protocol
  (rules 1–7) and the strategy-ring design.
- `storage/aio/*` — drives the `*_readv_*` callbacks; `WaitIO` knows
  about `PgAioWaitRef`.
- `storage/smgr/smgr.c` — `smgrread`/`smgrwrite`/`smgrnblocks` called
  from `FlushBuffer`, `ExtendBufferedRel`, etc.
- `access/transam/xlog.c` — `XLogFlush`, `XLogNeedsFlush` consulted by
  `FlushBuffer` and `GetVictimBuffer`.
- `storage/lmgr/lwlock.c` — partition LWLocks live in `MainLWLockArray`.
- `utils/resowner/resowner.c` — `ResourceOwnerRememberBuffer*` registers
  pins and in-progress I/Os for xact-end cleanup.
- `knowledge/files/src/include/storage/buf_internals.h.md` — companion
  doc for the private header (state-word layout, BufferDesc, BM_* flags).
- `knowledge/data-structures/bufferdesc-state.md` — narrative summary of
  the state word and the spinlock-via-state pattern.

## 6. Open questions

1. **Total ordering between content lock and BufMappingLock when both held**
   — `BufferAlloc` takes partition lock, pins, releases partition lock,
   *then* takes content lock; no in-file comment states this as a global
   rule. `[unverified-as-rule]`
2. **Whether `BM_IO_IN_PROGRESS` is ever set while a partition lock is held**
   — code suggests no (the partition lock is dropped before
   `StartSharedBufferIO`) but no explicit invariant. `[unverified]`
3. **Two-partition-lock callers** — README mandates partition-number order;
   I did not find any in-tree caller in `bufmgr.c` that takes two
   simultaneously. Possibly only `DropRelationsAllBuffers`-style bulk paths
   could; not confirmed. `[unverified]`
4. **Hint-bit + checksum interaction** — `MarkBufferDirtyHint` skips the WAL
   FPI when checksums are off, but the exact correctness argument across
   torn-page reads needs `bufpage.c` cross-reference. `[unverified]`
5. **AIO + cleanup-lock race** — `LockBufferForCleanup` comment at
   `bufmgr.c:6691-6696` says "we, so far, only support doing reads via AIO
   and this function can only be called once the buffer is valid", so AIO
   reads can never collide with cleanup. Will need revisiting if AIO writes
   land. `[from-comment]`

## 7. Tag tally

- `[verified-by-code]`: 24
- `[from-comment]`: 13
- `[from-README]`: 2
- `[unverified]` / `[unverified-as-rule]`: 4

## files-examined rows

| path | depth | date | commit | doc |
|---|---|---|---|---|
| source/src/backend/storage/buffer/bufmgr.c | deep-read (selected functions, full function map) | 2026-06-01 | ef6a95c7c64 | knowledge/files/src/backend/storage/buffer/bufmgr.c.md |
| source/src/include/storage/buf_internals.h | read | 2026-06-01 | ef6a95c7c64 | knowledge/files/src/include/storage/buf_internals.h.md |

## Synthesized by
<!-- backlinks:auto -->
- [data-structures/bufferdesc-state.md](../../../../../data-structures/bufferdesc-state.md)
- [subsystems/storage-buffer.md](../../../../../subsystems/storage-buffer.md)
