# Storage / Buffer Manager

## Owners (as of 2026-06-12)

- **Top committers (last 24mo):** Andres Freund (62), Peter Eisentraut (19), Michael Paquier (12), Noah Misch (7)
- **Top reviewers (last 24mo):** Melanie Plageman (22), Andres Freund (20), Noah Misch (13), Matthias van de Meent (8)
- **Recent landmark commits (12mo):**
  - `e18b0cb7344 (Michael Paquier, 2026-06-10): Fix MarkBufferDirtyHint() to not call GetBufferDescriptor() for local buffers`
  - `c75ebc657ff (Andres Freund, 2025-11-06): bufmgr: Allow some buffer state modifications while holding header lock`
  - `c819d1017dd (Andres Freund, 2025-10-09): bufmgr: Fix valgrind checking for buffers pinned in StrategyGetBuffer()`

See `knowledge/personas/domain-ownership.md` for the cross-subsystem index, methodology, and committer/reviewer affinity clusters.

---


- **Source path:** `source/src/backend/storage/buffer/`
- **Header path:** `source/src/include/storage/` (`bufmgr.h`, `buf_internals.h`, `buf.h`, `bufpage.h`)
- **Last verified commit:** `ef6a95c7c64de07dff4dd1f1da88ffae7b086ef3` (2026-06-01)
- **README anchor:** `source/src/backend/storage/buffer/README`

## 1. Purpose

The buffer manager is the cache between PostgreSQL backends and the storage manager (`smgr`): it owns the shared-memory pool of `BLCKSZ` page buffers, maps `(tablespace, db, rel, fork, blocknum)` tuples to those buffers, and arbitrates concurrent read/write/eviction. Access control happens at two layers — *pin counts* (you may not touch a buffer you have not pinned) and *content locks* (shared/share-exclusive/exclusive on the page contents) — with a third level (relation locks) assumed to be held by callers `[from-README]` (`README:1-10`). Replacement uses a clock sweep with per-strategy rings for bulk workloads `[from-README]` (`README:172-247`).

## 2. Mental model

- **Shared buffer pool** — `NBuffers` page-sized blocks in `BufferBlocks` plus `NBuffers` `BufferDesc` headers in `BufferDescriptors`, allocated in shmem during `BufferManagerShmemInit` `[verified-by-code]` (`buf_init.c:24-145`). Each buffer also has a sibling `ConditionVariable` in `BufferIOCVArray` used to wait on I/O.
- **BufferDesc** — fixed-size header holding `tag` (page identity), `buf_id`, an atomic 64-bit `state` packing refcount/usagecount/flags/content-lock state, plus a per-buffer `proclist_head lock_waiters` and `PgAioWaitRef io_wref` `[verified-by-code]` (`buf_internals.h:326-359`). Engineered to stay ≤ 64 bytes (one cache line) `[from-comment]` (`buf_internals.h:318-324`).
- **State variable** — the 64-bit atomic `state` packs 18 bits refcount, 4 bits usagecount, 12 bits flags, and 20 bits of content-lock state (shared-lock count + share-exclusive bit + exclusive bit). The header spinlock is itself bit `BM_LOCKED` inside `state`, so many operations can be done as a single CAS instead of taking the spinlock `[verified-by-code]` (`buf_internals.h:33-86, 267-310`).
- **Buffer mapping table** — a partitioned hash table (`SharedBufHash`, `NUM_BUFFER_PARTITIONS` partitions, sized `NBuffers + NUM_BUFFER_PARTITIONS` entries) from `BufferTag → buf_id`, served by `BufTableLookup/Insert/Delete` and gated by per-partition LWLocks `BufMappingPartitionLock(hashcode)` `[verified-by-code]` (`buf_table.c:47-167`, `buf_internals.h:241-264`).
- **Clock sweep + freelist control** — a single `BufferStrategyControl` shmem object holds the spinlock `buffer_strategy_lock`, the atomic `nextVictimBuffer` clock hand, `completePasses`, an allocation counter, and the bgwriter procnumber `[verified-by-code]` (`freelist.c:32-67`). There is no real "free list" — buffers are picked by sweeping; the name is historical.
- **Backend-private ref-count cache** — `PrivateRefCountEntry`s track this backend's pins so a repeat pin doesn't bump the shared refcount; `lockmode` is also tracked per buffer per backend `[verified-by-code]` (`bufmgr.c:101-130, 3286-3372`).
- **BufferAccessStrategy rings** — small per-scan ring buffers (BAS_BULKREAD ≈ 256 KB, BAS_VACUUM tuneable via GUC, BAS_BULKWRITE 16 MB capped at NBuffers/8) reuse a fixed cycle of buffers so VACUUM/seqscan/COPY don't blow out the cache `[from-README]` (`README:206-247`); allocation in `GetAccessStrategy` `[verified-by-code]` (`freelist.c:425-541`).

## 3. Key files

- `bufmgr.c` — public API plus all hot paths: `ReadBuffer*`, `StartReadBuffers/WaitReadBuffers`, `BufferAlloc`, `GetVictimBuffer`, `PinBuffer`/`UnpinBuffer`, `LockBuffer*`, `FlushBuffer`, `MarkBufferDirty`, `DropRelationBuffers`, `CheckPointBuffers`, `BgBufferSync` `[verified-by-code]` (`bufmgr.c:15-34` lists principal entry points).
- `freelist.c` — clock-sweep victim selection and BufferAccessStrategy ring management `[verified-by-code]` (`freelist.c:1-14`).
- `buf_table.c` — thin wrapper around the shared partitioned hash (`SharedBufHash`); does no locking of its own — caller must hold the right partition lock `[from-comment]` (`buf_table.c:6-11`).
- `buf_init.c` — registers shmem segments (`Buffer Descriptors`, `Buffer Blocks`, `Buffer IO Condition Variables`, `Checkpoint BufferIds`) and initialises buffer headers `[verified-by-code]` (`buf_init.c:73-145`).
- `localbuf.c` — parallel implementation for *temp-table* local buffers in backend-private memory: `LocalBufferAlloc`, `PinLocalBuffer`, `DropRelationLocalBuffers`, etc. No locks needed (single-backend) `[verified-by-code]` (`buf_internals.h:596-623`).
- `README` — the canonical narrative for access rules and replacement strategy (`README`, 15 KB).

## 4. Key data structures

- `BufferTag` (`buf_internals.h:161-168`) — `(spcOid, dbOid, relNumber, forkNum, blockNum)`. Used directly as a hash key; `InitBufferTag` zeros it carefully because pad bytes would corrupt hashing `[from-comment]` (`buf_internals.h:158-160`).
- `BufferDesc` (`buf_internals.h:326-359`) — the per-buffer header. Locking rules:
  - `tag` is mutable only by the holder of the buffer header spinlock (`BM_LOCKED`), except that pinning the buffer pins the tag for read since identity can't change while a pin is held `[from-comment]` (`buf_internals.h:281-294`).
  - `state` is updated atomically; flags and refcount are manipulated with CAS loops or with the header spinlock held; usagecount is *not* combined into single-op updates because it must be capped at `BM_MAX_USAGE_COUNT = 5` `[from-comment]` (`buf_internals.h:136-147`, `buf_internals.h:465-497`).
  - `buf_id` is set once and never changes after init `[from-comment]` (`buf_internals.h:334-338`).
  - `lock_waiters` is protected by the buffer header spinlock `[from-comment]` (`buf_internals.h:354-358`).
  - `wait_backend_pgprocno` (cleanup-lock waiter) is protected by the header spinlock `[from-comment]` (`buf_internals.h:346-350`).
- `BufferStrategyControl` (`freelist.c:32-56`) — shmem singleton; `nextVictimBuffer` is atomic, `completePasses` is bumped under `buffer_strategy_lock` `[verified-by-code]` (`freelist.c:109-166`).
- `BufferAccessStrategyData` (`freelist.c:74-94`) — palloc'd in caller's memory context, not shared. Holds ring index + buffer numbers. Per-backend, so unsynchronised.
- `PrivateRefCountEntry` / array+hash hybrid (`bufmgr.c:101-150` and surrounding helpers) — backend-local; tracks pins and current content-lock mode per pinned buffer.
- `BufferLookupEnt` (`buf_table.c:27-32`) — entry in `SharedBufHash` mapping tag → buffer id.
- `WritebackContext` / `PendingWriteback` (`buf_internals.h:393-410`) — coalesces sync_file_range / posix_fadvise hints; one per backend (`BackendWritebackContext`) plus checkpointer's own.

State flags worth knowing (`buf_internals.h:106-127`): `BM_LOCKED` (header spinlock), `BM_DIRTY`, `BM_VALID`, `BM_TAG_VALID` (entry exists in mapping hash), `BM_IO_IN_PROGRESS`, `BM_IO_ERROR`, `BM_PIN_COUNT_WAITER`, `BM_CHECKPOINT_NEEDED`, `BM_PERMANENT`, `BM_LOCK_HAS_WAITERS`, `BM_LOCK_WAKE_IN_PROGRESS`.

## 5. Control flow — the common paths

### 5.1 ReadBuffer hit/miss path

1. `ReadBuffer(reln, blknum)` → `ReadBufferExtended(reln, MAIN_FORKNUM, blknum, RBM_NORMAL, NULL)` `[verified-by-code]` (`bufmgr.c:879-940`).
2. `ReadBuffer_common` validates the relation, dispatches `P_NEW` to `ExtendBufferedRel`, special-cases `RBM_ZERO_AND_LOCK[_CLEANUP]` (which goes via `PinBufferForBlock` + `ZeroAndLockBuffer`), and otherwise calls `StartReadBuffer` + `WaitReadBuffers` with `READ_BUFFERS_SYNCHRONOUSLY` `[verified-by-code]` (`bufmgr.c:1276-1368`).
3. `StartReadBuffer(s)` resolves the descriptor by calling `BufferAlloc` (via `PinBufferForBlock` → `BufferAlloc` for shared, or `LocalBufferAlloc` for temp) and, if the page was not already valid, sets up an AIO read; with `READ_BUFFERS_SYNCHRONOUSLY` the caller then `WaitReadBuffers` immediately `[verified-by-code]` (`bufmgr.c:1223-1657, 1759-`).
4. `BufferAlloc` — the heart of the lookup `[verified-by-code]` (`bufmgr.c:2197-2351`):
   - Build `newTag`, compute `newHash = BufTableHashCode`, pick the partition lock `newPartitionLock = BufMappingPartitionLock(newHash)` (`bufmgr.c:2216-2220`).
   - **Hit path:** acquire `newPartitionLock` in `LW_SHARED`, `BufTableLookup`. If found, `PinBuffer` the existing descriptor and only then release the partition lock — pinning *under* the mapping lock is what the README requires `[from-README]` (`README:123-134`). Return with `*foundPtr = true`; `valid = false` only if the page is mid-read by another backend (`bufmgr.c:2222-2255`).
   - **Miss path:** release the share-mode partition lock, call `GetVictimBuffer(strategy, io_context)` to obtain a pinned, *invalid* buffer (`bufmgr.c:2257-2269`).
   - Reacquire `newPartitionLock` **exclusive**, `BufTableInsert`. If somebody else raced and inserted first, unpin the victim and fall back to the hit path (`bufmgr.c:2271-2317`).
   - Otherwise: lock the buffer header (`LockBufHdr`), assign `victim_buf_hdr->tag = newTag`, set `BM_TAG_VALID | BUF_USAGECOUNT_ONE` (+ `BM_PERMANENT` if applicable), drop the header spinlock via `UnlockBufHdrExt`, then drop the partition lock (`bufmgr.c:2319-2350`). Return with `*foundPtr = false`; caller is now responsible for filling the page.

### 5.2 Victim selection (`GetVictimBuffer` → `StrategyGetBuffer` → clock sweep)

1. `GetVictimBuffer` reserves a `PrivateRefCount` slot and a resowner slot, then calls `StrategyGetBuffer(strategy, &buf_state, &from_ring)` `[verified-by-code]` (`bufmgr.c:2547-2576`).
2. `StrategyGetBuffer` first tries `GetBufferFromRing` for strategy-ring scans; ring slots are reusable only if refcount==0 and usagecount ≤ 1 `[verified-by-code]` (`freelist.c:183-204, 622-693`). On miss it bumps `numBufferAllocs`, optionally wakes the bgwriter (latch set via `bgwprocno`), then enters the clock-sweep loop (`freelist.c:206-317`).
3. Clock sweep: `ClockSweepTick` does `pg_atomic_fetch_add_u32(&nextVictimBuffer, 1)` modulo `NBuffers`; on wraparound it briefly takes `buffer_strategy_lock` to bump `completePasses` `[verified-by-code]` (`freelist.c:109-166`).
4. For each candidate: read `state` with `pg_atomic_read_u64`; if `refcount != 0`, skip (and decrement `trycounter`; ERROR "no unpinned buffers available" if every buffer is pinned). If `BM_LOCKED`, `WaitBufHdrUnlocked` and retry. Otherwise, if `usagecount > 0`, CAS-decrement it and reset `trycounter`. If `usagecount == 0`, CAS-increment refcount to 1 — that's the pin — and return the descriptor; if using a strategy, `AddBufferToRing` snapshots it into the ring slot `[verified-by-code]` (`freelist.c:240-317`).
5. Back in `GetVictimBuffer`: if the victim is `BM_DIRTY`, attempt a *conditional* `BUFFER_LOCK_SHARE_EXCLUSIVE`; failure means somebody else has the buffer locked, so unpin and restart (this avoids a documented deadlock when two backends both split btree pages and grab each other's victim) `[from-comment]` (`bufmgr.c:2584-2611`). For ring buffers on permanent rels, `XLogNeedsFlush(BufferGetLSN(...))` lets `StrategyRejectBuffer` discard the slot rather than flush WAL `[verified-by-code]` (`bufmgr.c:2613-2631`, `freelist.c:751-770`).
6. `FlushBuffer(buf, NULL, IOOBJECT_RELATION, io_context)` writes the page out, then unlock; the writeback request is queued via `ScheduleBufferTagForWriteback` `[verified-by-code]` (`bufmgr.c:2633-2638`).
7. Finally, if `BM_TAG_VALID`, `InvalidateVictimBuffer` re-acquires that buffer's *old* partition lock exclusive, takes the header spinlock, verifies refcount is still 1 and not dirty, clears tag/flags/usagecount, and `BufTableDelete`s the old mapping entry. If any of those checks fail (someone re-pinned/dirtied) the caller unpins and goes back to `again:` `[verified-by-code]` (`bufmgr.c:2461-2545, 2664-2673`).

### 5.3 FlushBuffer

1. Caller must already hold `BUFFER_LOCK_EXCLUSIVE` or `BUFFER_LOCK_SHARE_EXCLUSIVE` on the buffer (asserted) `[verified-by-code]` (`bufmgr.c:4520-4521`).
2. `StartSharedBufferIO(buf, forInput=false, wait=true, NULL)` sets `BM_IO_IN_PROGRESS`; if it returns `BUFFER_IO_ALREADY_DONE` somebody else already flushed it and we return `[verified-by-code]` (`bufmgr.c:4524-4529`).
3. Read the LSN under the content lock (so it can't be torn), then `XLogFlush(recptr)` — **but only if `BM_PERMANENT`**, because unlogged-rel "fake" LSNs from `XLogGetFakeLSN` can outrun the WAL insert pointer `[from-comment]` (`bufmgr.c:4547-4571`). This is the WAL-before-data rule.
4. `PageSetChecksum`, then `smgrwrite(reln, fork, blockNum, bufBlock, false)` `[verified-by-code]` (`bufmgr.c:4581-4590`).
5. `TerminateBufferIO(buf, clear_dirty=true, set_flag_bits=0, forget_owner=true, release_aio=false)` clears `BM_DIRTY` + `BM_IO_IN_PROGRESS` and signals the buffer's CV `[verified-by-code]` (`bufmgr.c:4615-4618`).

### 5.4 DropRelationBuffers

Two regimes — picks between them on size relative to `BUF_DROP_FULL_SCAN_THRESHOLD = NBuffers/32` `[verified-by-code]` (`bufmgr.c:95, 4836-4842`):

- **Small drops (known fork sizes, e.g. during recovery):** `FindAndDropRelationBuffers` looks each block up by tag in the partitioned hash — cheap.
- **Large drops or unknown size:** linear scan of all `NBuffers` descriptors. For each, the tag is *pre-checked without a lock* (safe because the caller holds AccessExclusiveLock so no new tag can appear for this rel) `[from-comment]` (`bufmgr.c:4849-4865`); on match, `LockBufHdr`, re-check, `InvalidateBuffer` (which releases the spinlock and goes through the full partition-lock dance, including waiting for in-progress I/O via `WaitIO` and retrying) `[verified-by-code]` (`bufmgr.c:2369-2459, 4845-4882`).

`DropRelationLocalBuffers` is dispatched for temp rels when `RelFileLocatorBackendIsTemp` and the locator's backend matches `MyProcNumber` `[verified-by-code]` (`bufmgr.c:4786-4793`).

## 6. Locking and invariants

The buffer subsystem has six relevant lock/lock-like primitives. Names are taken from the code and README; orderings are stated only where the README or code explicitly establishes them.

1. **Buffer header spinlock** — bit `BM_LOCKED` inside `BufferDesc.state`. Held for "a few instructions" only `[from-README]` (`README:151-155`). Held to: change the tag, modify `wait_backend_pgprocno`, queue/dequeue content-lock waiters, perform multi-field updates that can't be a single CAS. Most reads/decrements of refcount avoid it via CAS `[from-comment]` (`buf_internals.h:267-294`). `LockBufHdr/UnlockBufHdr` in `bufmgr.c`; `UnlockBufHdrExt` lets you release while applying flag changes and a refcount delta atomically.
2. **Buffer content lock** — the share/share-exclusive/exclusive lock in the high bits of `state`, formerly an LWLock. Acquired by `LockBuffer*`/`BufferLockAcquire`, released by `BufferLockUnlock`. Required to be held with a pin first (`README:38-41`). README rules 1–6 spell out which mode is needed for which page op `[from-README]` (`README:43-111`).
3. **Pin (refcount)** — incremented by `PinBuffer`/`PinBuffer_Locked` (and on the cheap backend-local path via `PrivateRefCount`); the *shared* refcount is the one stored in `state` `[verified-by-code]` (`bufmgr.c:3281-3372, 3396-3417`). README: "It is OK to hold a pin for long intervals" `[from-README]` (`README:18-26`).
4. **`buffer_strategy_lock`** — spinlock guarding the clock-sweep control block (`nextVictimBuffer` increments are atomic but `completePasses` and `bgwprocno` need this lock for consistency between `StrategySyncStart` and `ClockSweepTick`). README: "no other locks of any sort should be acquired while buffer_strategy_lock is held" `[from-README]` (`README:144-149`).
5. **`BufMappingLock` (partitioned, NUM_BUFFER_PARTITIONS LWLocks)** — guards entries in `SharedBufHash`. Share mode is enough to look up; exclusive is required to insert or delete. README: **"If it is necessary to lock more than one partition at a time, they must be locked in partition-number order to avoid risk of deadlock."** `[from-README]` (`README:140-143`). I did not find an in-tree call site that takes two partition locks at once in this subsystem; the rule applies if any caller does.
6. **`BM_IO_IN_PROGRESS` + per-buffer condition variable** — used as a lock to serialise reads/writes. Setter is whoever calls `StartSharedBufferIO`; clearer is `TerminateBufferIO`; waiters use `BufferDescriptorGetIOCV` + `BufferDesc.io_wref` `[from-README]` (`README:162-169`) `[verified-by-code]` (`buf_init.c:139`, `bufmgr.c:4524-4618`).

### Orderings the code/comments establish

- **Pin before content-lock** `[from-README]` (`README:40-41`).
- **Hold the partition lock until after pinning the found buffer** `[from-README]` (`README:127-134`); `BufferAlloc` follows this exactly (`bufmgr.c:2237-2240`).
- **Multiple buffer-mapping partition locks** are acquired in partition-number order `[from-README]` (`README:140-143`).
- **Nothing else may be acquired while `buffer_strategy_lock` is held** `[from-README]` (`README:144-149`); cross-checked against `freelist.c` — `StrategyGetBuffer` releases it before doing CAS pins, and `ClockSweepTick` holds it only across the `completePasses++` `[verified-by-code]` (`freelist.c:152-162`).
- **Eviction of a dirty victim uses conditional share-exclusive content lock acquisition** to avoid deadlocks against backends that have already pinned+locked our chosen victim (e.g. concurrent btree splits) `[from-comment]` (`bufmgr.c:2592-2611`).
- **`FlushBuffer` requires `BUFFER_LOCK_EXCLUSIVE` or `BUFFER_LOCK_SHARE_EXCLUSIVE`** `[verified-by-code]` (`bufmgr.c:4520-4521`); the README states share-exclusive is the minimum required for a writeout `[from-README]` (`README:109-111`).
- **Cleanup lock (`LockBufferForCleanup`)**: acquire `BUFFER_LOCK_EXCLUSIVE`, take the header spinlock, check refcount==1; if not, install `BM_PIN_COUNT_WAITER` with our procnumber, release everything, and sleep on a signal from `UnpinBuffer`/`WakePinCountWaiter` `[verified-by-code]` (`bufmgr.c:6678-6800, 3428-3456`). Only one waiter is supported per buffer (asserted on the second waiter) `[from-README]` (`README:103-107`) `[verified-by-code]` (`bufmgr.c:6738-6743`).
- **`InvalidateBuffer` ordering:** caller enters with header spinlock held; the function drops it, then acquires `oldPartitionLock` exclusive, then re-locks the header, then `BufTableDelete`, then releases — the partition lock outlives the second header-lock acquisition `[verified-by-code]` (`bufmgr.c:2369-2459`).

### Things I cannot pin down to a comment or code path → see §9

- Total ordering between content lock and buffer-mapping partition lock when both are held by the same backend.
- Whether `BM_IO_IN_PROGRESS` can be set while the partition lock is held (the code suggests no: `BufferAlloc` releases the partition lock before any I/O), but I did not find an explicit invariant statement.

## 7. Interactions with other subsystems

- **`storage/smgr`** — `FlushBuffer` calls `smgrwrite`; `ReadBuffer` paths eventually call `smgrreadv`/`smgrprefetch` via the AIO callbacks `aio_shared_buffer_readv_cb` declared in `bufmgr.h:185-186` `[verified-by-code]`. `smgrnblocks_cached` is consulted by `DropRelationBuffers` (`bufmgr.c:4820`).
- **`access/transam` (WAL)** — `FlushBuffer` calls `XLogFlush(BufferGetLSN(buf))` to enforce WAL-before-data; `GetVictimBuffer` uses `XLogNeedsFlush` to let bulkread rings reject dirty pages `[verified-by-code]` (`bufmgr.c:4570-4571, 2624-2631`).
- **`storage/aio`** — `BufferDesc.io_wref` and `pgaio_*` integration in `WaitReadBuffers` / `AsyncReadBuffers` / `StartReadBuffersImpl`; the per-buffer CV is used to wait on completion (`bufmgr.c:1759-`, `buf_internals.h:352, 414`).
- **`storage/lmgr`** — buffer manager assumes relation-level locks are held by callers per README `[from-README]` (`README:6-10`).
- **`postmaster/bgwriter` and checkpointer** — `BgBufferSync` (`bufmgr.c:3840-`) and `BufferSync`/`CheckPointBuffers` (`bufmgr.c:3561-, 4441-`) are the writers' entry points; bgwriter wakes itself via `StrategyNotifyBgWriter`/`bgwprocno` set in the clock-sweep loop `[verified-by-code]` (`freelist.c:218-230`, `bufmgr.c:3840+`).
- **`utils/resowner`** — every pin is registered with the current ResourceOwner via `ResourceOwnerRememberBuffer` so it's released at xact end `[verified-by-code]` (`buf_internals.h:520-544`, `bufmgr.c:3469-3471`).
- **`pgstat`** — `pgstat_count_io_op*` calls scattered through eviction and flush; `pgBufferUsage.shared_blks_written++` in `FlushBuffer` (`bufmgr.c:4610-4613`).
- **`access/heap`, all index AMs** — consumers of the API; callers are the ones that distinguish read vs write content-lock modes, hint-bit updates (which use the new `BufferBeginSetHintBits`/`BufferSetHintBits16` share-exclusive helpers per README rule 4), and cleanup locks for VACUUM `[from-README]` (`README:63-107`).

## 8. Tests

- **Regress** (`source/src/test/regress/sql/`) — `vacuum.sql`, `vacuum_parallel.sql` exercise ring-buffer + cleanup-lock paths indirectly. No dedicated `buffer.sql` regress file exists at this commit.
- **Isolation** (`source/src/test/isolation/specs/`) — `vacuum-no-cleanup-lock.spec` exercises `ConditionalLockBufferForCleanup` semantics; `temp-schema-cleanup.spec` touches local-buffer paths `[verified-by-code]` (directory listing).
- **TAP / modules** — `src/test/modules/test_aio/` (`001_aio.pl`, `004_read_stream.pl`, `test_aio.c`) directly drives `StartReadBuffers`/`WaitReadBuffers` and the buffer-AIO callbacks `[verified-by-code]`.

There is no `src/test/modules/test_buffer*` at this commit; coverage is via the above plus the implicit testing every regression test gives the cache.

## 9. Open questions / unverified claims

1. **Total locking order between content lock and BufMappingLock when both are held** — I observed `BufferAlloc` taking the partition lock *first*, pinning, *then* releasing before any content-lock work, but did not find a comment that states the global order. `[unverified]`
2. **Whether `BM_IO_IN_PROGRESS` is ever set under a BufMappingLock partition lock** — code suggests no, but I did not exhaustively grep all I/O-starting paths. `[unverified]`
3. **Exact set of callers that hold two partition locks simultaneously** — README mandates partition-number order but I did not find an in-tree caller that takes two; possibly only synchronous standby / checkpoint paths do. `[unverified]`
4. **Whether `PinBuffer_Locked` is safe to call without `ReservePrivateRefCountEntry` in all paths** — comment at `bufmgr.c:3378-3395` says it requires it, did not audit every caller. `[unverified]`
5. **Local-buffer interactions with AIO** — `localbuf.c` has a `StartLocalBufferIO` but I did not trace whether AIO is actually used for local buffers or only for shared. `[unverified]`
6. **The 12-bit `BUF_FLAG_BITS` budget** — only 11 flag bits are defined and bit 6 is "not used anymore"; safe to ignore but worth flagging if a future flag is added. `[from-comment]` (`buf_internals.h:117`).

## 10. Glossary

- **BufferTag** — 5-tuple `(spcOid, dbOid, relNumber, forkNum, blockNum)` identifying a disk page. `[verified-by-code]` (`buf_internals.h:161-168`).
- **Pin / refcount** — increment of the per-buffer reference count; while held, the buffer's tag can't change underneath you. `[from-README]`.
- **Usage count** — 0–5 counter incremented on pin (capped at `BM_MAX_USAGE_COUNT=5`), decremented by the clock sweep; controls eviction priority. `[from-comment]` (`buf_internals.h:136-144`).
- **Clock sweep** — circular scan of buffers, decrementing usagecount until a buffer with usagecount==0 and refcount==0 is found; that becomes the victim. `[from-README]` (`README:175-203`).
- **BufMappingLock** — historical name for the partitioned LWLocks guarding `SharedBufHash`. `[from-README]` (`README:123-143`).
- **buffer_strategy_lock** — spinlock guarding the clock-sweep control block. `[from-README]` (`README:144-149`).
- **BAS_*** — `BufferAccessStrategyType`s: NORMAL, BULKREAD, BULKWRITE, VACUUM. Determine ring size and eviction behaviour. `[verified-by-code]` (`bufmgr.h:34-41`, `freelist.c:436-498`).
- **ReadBufferMode (RBM_*)** — NORMAL, ZERO_AND_LOCK, ZERO_AND_CLEANUP_LOCK, ZERO_ON_ERROR, NORMAL_NO_LOG. `[verified-by-code]` (`bufmgr.h:44-54`).
- **Hint bits** — commit-status caches (HEAP_XMIN_COMMITTED etc.) that may be updated under share-exclusive content lock without WAL logging (rule 4). `[from-README]` (`README:63-82`).
- **Cleanup lock** — exclusive content lock + observed `refcount == 1`; required to physically remove tuples or compact a page (rule 5). `[from-README]` (`README:83-107`).
- **BM_PERMANENT** — flag distinguishing logged tables (must be written at every checkpoint) from unlogged ones (only at shutdown); also gates `XLogFlush` in `FlushBuffer`. `[verified-by-code]` (`buf_internals.h:122-123`, `bufmgr.c:4570`).
- **BM_IO_IN_PROGRESS** — quasi-lock: the backend that sets it owns the I/O; others sleep on the buffer's CV. `[from-README]` (`README:162-169`).
- **PrivateRefCount** — per-backend tracking of pins+lockmode for buffers this backend has pinned; lets repeat pins skip the shared atomic op. `[verified-by-code]` (`bufmgr.c:101-150`).
- **Strategy ring** — small fixed cycle of buffers reused across a bulk scan to avoid cache pollution. `[from-README]` (`README:206-247`).
- **`nextVictimBuffer`** — atomic monotonically-increasing clock hand; physical buffer index is `nextVictimBuffer % NBuffers`. `[verified-by-code]` (`freelist.c:38-42, 109-166`).
- **`BM_PIN_COUNT_WAITER`** — flag indicating one backend is waiting for refcount to drop to 1 (cleanup lock); only one waiter per buffer allowed. `[from-README]` (`README:103-107`).
