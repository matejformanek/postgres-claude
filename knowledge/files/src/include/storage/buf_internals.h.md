# `include/storage/buf_internals.h`

- **Source:** `source/src/include/storage/buf_internals.h` (~625 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Companion docs:** `knowledge/data-structures/bufferdesc-state.md`,
  `knowledge/subsystems/storage-buffer.md`,
  `knowledge/files/src/backend/storage/buffer/bufmgr.c.md`

## 1. Purpose

Internal header shared by `bufmgr.c`, `freelist.c`, `buf_table.c`, `buf_init.c`,
and `localbuf.c`. Defines the canonical layout of the buffer descriptor
(`BufferDesc`), the on-the-wire identity of a page (`BufferTag`), the packed
64-bit `state` word that combines refcount + usagecount + flags + content-lock
state, all `BM_*` flag macros, the per-partition buffer-mapping LWLock
accessors, the per-backend `WritebackContext`, the `CkptSortItem` checkpoint
sort key, and forward declarations for every public-to-buffer-mgr function
across `bufmgr.c`/`freelist.c`/`buf_table.c`/`localbuf.c`. Anything outside the
buffer manager should include `storage/bufmgr.h` instead.

## 2. The packed `state` word

`pg_atomic_uint64 state` packs four logical fields. Layout is fixed by the
`BUF_*_BITS` macros and a `StaticAssertDecl` at line 54 that the four widths
sum to ≤ 64 `[verified-by-code]` (`buf_internals.h:49-55`):

| bits | width | meaning | macro |
|---|---|---|---|
| 0..17  | 18 | shared refcount      | `BUF_REFCOUNT_BITS`, mask `BUF_REFCOUNT_MASK` |
| 18..21 | 4  | usage count (clock)  | `BUF_USAGECOUNT_BITS`, shift `BUF_USAGECOUNT_SHIFT` |
| 22..33 | 12 | flag bits            | `BUF_FLAG_BITS`, shift `BUF_FLAG_SHIFT` |
| 34..63 | 20 | content-lock state   | `BUF_LOCK_BITS` (= 18+2): N-bit shared count + share-exclusive bit + exclusive bit |

`[verified-by-code]` (`buf_internals.h:33-86`).

`BUF_REFCOUNT_ONE = 1`; `BUF_USAGECOUNT_ONE = 1 << BUF_REFCOUNT_BITS`; flag
macros are emitted by `BUF_DEFINE_FLAG(n) = (1 << (BUF_FLAG_SHIFT + n))`
`[verified-by-code]` (`buf_internals.h:58-103`). `BM_LOCK_VAL_SHARED`,
`BM_LOCK_VAL_SHARE_EXCLUSIVE`, `BM_LOCK_VAL_EXCLUSIVE` parameterise the
shared-count/SE-bit/X-bit positions inside the content-lock subfield
`[verified-by-code]` (`buf_internals.h:77-86`).

Two `StaticAssertDecl`s constrain `MAX_BACKENDS_BITS` so the shared-lock
counter and shared refcount can both index every backend
`[verified-by-code]` (`buf_internals.h:130-133`).

### 2.1 Flag bits (12 budget, 11 defined, bit 6 unused)

`[verified-by-code]` (`buf_internals.h:106-127`).

- `BM_LOCKED` (bit 0) — header spinlock; whoever sets this bit owns the
  buffer header lock. `[from-comment]` (`buf_internals.h:105`).
- `BM_DIRTY` (bit 1) — page contents differ from disk.
- `BM_VALID` (bit 2) — page contents are valid (I/O succeeded).
- `BM_TAG_VALID` (bit 3) — "there is a buffer hashtable entry associated
  with the buffer's tag" `[from-comment]` (`buf_internals.h:98-100`).
- `BM_IO_IN_PROGRESS` (bit 4) — read or write running; quasi-lock per §6.
- `BM_IO_ERROR` (bit 5) — last I/O failed; cleared on next successful I/O.
- bit 6 — unused (`/* flag bit 6 is not used anymore */`) `[from-comment]`
  (`buf_internals.h:117`).
- `BM_PIN_COUNT_WAITER` (bit 7) — one backend is parked waiting for refcount
  to drop to 1 (cleanup-lock waiter); `wait_backend_pgprocno` holds its
  procnumber. `[from-comment]` (`buf_internals.h:118`).
- `BM_CHECKPOINT_NEEDED` (bit 8) — checkpointer should write this buffer.
- `BM_PERMANENT` (bit 9) — permanent (logged) relation, not unlogged and not
  init-fork. Gates `XLogFlush` in `FlushBuffer`. `[from-comment]`
  (`buf_internals.h:122-123`).
- `BM_LOCK_HAS_WAITERS` (bit 10) — somebody is queued on `lock_waiters` for
  the content lock.
- `BM_LOCK_WAKE_IN_PROGRESS` (bit 11) — waiter has been signalled but not
  yet run; prevents redundant wakeups. `[from-comment]`
  (`buf_internals.h:126-127`).

### 2.2 Accessors

`BUF_STATE_GET_REFCOUNT(state)` and `BUF_STATE_GET_USAGECOUNT(state)` mask
and shift `[verified-by-code]` (`buf_internals.h:89-93`).

`BM_MAX_USAGE_COUNT = 5` — clock-sweep cap; trade-off between accuracy and
how long the sweep takes to find a victim `[from-comment]`
(`buf_internals.h:136-147`).

## 3. `BufferTag` — page identity

```c
typedef struct buftag {
    Oid           spcOid;     // tablespace
    Oid           dbOid;      // database
    RelFileNumber relNumber;  // relation
    ForkNumber    forkNum;    // fork
    BlockNumber   blockNum;   // 0-based block in fork
} BufferTag;
```

`[verified-by-code]` (`buf_internals.h:161-168`).

Used directly as a hash key. Pad bytes would corrupt hashing, so
`InitBufferTag` zeroes the whole struct via `ClearBufferTag` then sets
fields `[from-comment]` (`buf_internals.h:158-160`)
`[verified-by-code]` (`buf_internals.h:202-219`).

Accessors: `BufTagGetRelNumber`, `BufTagGetForkNum`,
`BufTagSetRelForkDetails`, `BufTagGetRelFileLocator`, `BufferTagsEqual`,
`BufTagMatchesRelFileLocator` `[verified-by-code]` (`buf_internals.h:170-238`).

## 4. Buffer mapping partition lock

`BufTableHashPartition(hashcode) = hashcode % NUM_BUFFER_PARTITIONS`
`[verified-by-code]` (`buf_internals.h:247-251`).
`BufMappingPartitionLock(hashcode)` returns
`&MainLWLockArray[BUFFER_MAPPING_LWLOCK_OFFSET + partition].lock`
`[verified-by-code]` (`buf_internals.h:253-264`).

`NUM_BUFFER_PARTITIONS` must be a power of two and is defined in `lwlock.h`
`[from-comment]` (`buf_internals.h:241-246`). When multiple partitions are
held simultaneously, callers must take them in partition-number order
(rule lives in the `storage/buffer/README`, not this header) — see
`subsystems/storage-buffer.md` §6.

## 5. `BufferDesc` — the per-buffer header

```c
typedef struct BufferDesc {
    BufferTag         tag;                   // page identity (header spinlock)
    int               buf_id;                // 0-based array index, immutable
    pg_atomic_uint64  state;                 // packed (see §2)
    int               wait_backend_pgprocno; // cleanup-lock waiter (header spinlock)
    PgAioWaitRef      io_wref;               // valid iff AIO is in progress
    proclist_head     lock_waiters;          // content-lock waiters (header spinlock)
} BufferDesc;
```

`[verified-by-code]` (`buf_internals.h:326-359`).

### Per-field locking rules (from the giant comment block 267-325)

- **`tag`** — "can only be changed by the backend holding the buffer header
  lock" `[from-comment]` (`buf_internals.h:281-282`). But: "if we have the
  buffer pinned, its tag can't change underneath us, so we can examine the
  tag without locking the buffer header" `[from-comment]`
  (`buf_internals.h:291-294`).
- **`buf_id`** — set once at init, never changes `[from-comment]`
  (`buf_internals.h:334-338`).
- **`state`** — atomic. Multi-field updates use the header spinlock (set
  `BM_LOCKED`, modify, clear via `UnlockBufHdr*`); single-field updates
  (e.g. refcount inc/dec) use CAS to avoid the spinlock. Pin **release**
  while another backend holds the spinlock is permitted via atomic
  subtraction `[from-comment]` (`buf_internals.h:283-294`).
- **`wait_backend_pgprocno`** — header spinlock `[from-comment]`
  (`buf_internals.h:346-350`).
- **`lock_waiters`** — header spinlock `[from-comment]`
  (`buf_internals.h:354-358`).
- **`io_wref`** — written by the AIO submitter, read by `WaitIO`; safe
  read requires the header spinlock (see `bufmgr.c:7170-7177` `WaitIO`).
- **Content lock (the high 20 bits of `state`)** — used to be an LWLock;
  promoted into `state` for race-free AIO interlock and for atomic
  unlock+unpin `[from-comment]` (`buf_internals.h:303-310`).

### Size & alignment

"Be careful to avoid increasing the size of the struct... Keeping it below
64 bytes (the most common CPU cache line size) is fairly important for
performance" `[from-comment]` (`buf_internals.h:318-321`). Enforced by
`BufferDescPadded` (a union with a 64-byte char pad on 64-bit, 1-byte pad
on 32-bit) and the `BUFFERDESC_PAD_TO_SIZE` macro
`[verified-by-code]` (`buf_internals.h:381-387`).

Local buffer descriptors (`LocalBufferDescriptors`) use the same struct but
**not** the padding union — single-backend access, no false sharing
`[from-comment]` (`buf_internals.h:373-374`).

## 6. Header-spinlock primitives

- `LockBufHdr(BufferDesc *)` — defined in `bufmgr.c:7527`; spins until
  `BM_LOCKED` is acquired, returns the state word `[verified-by-code]`
  (`buf_internals.h:449`, `bufmgr.c:7527-7565`).
- `UnlockBufHdr(BufferDesc *)` — inline; asserts `BM_LOCKED` is set,
  atomically subtracts it. Only valid when the caller did **not** modify
  the rest of the state word `[verified-by-code]` (`buf_internals.h:457-463`).
- `UnlockBufHdrExt(desc, old_buf_state, set_bits, unset_bits, refcount_change)`
  — inline CAS loop that atomically applies flag changes + a refcount delta
  and clears `BM_LOCKED` in one step. Used everywhere the unlock needs to
  also change the buffer. Cannot handle usagecount because that field must
  be capped at `BM_MAX_USAGE_COUNT` `[from-comment]` (`buf_internals.h:465-497`).
- `WaitBufHdrUnlocked(buf)` — defined in `bufmgr.c:7575`; spin-waits for
  `BM_LOCKED` to clear, returns the observed state. Used in CAS loops in
  `MarkBufferDirty`, `PinBuffer`, etc. `[verified-by-code]`
  (`buf_internals.h:499`, `bufmgr.c:7575-7593`).

## 7. Forward declarations grouped by `.c` file

### bufmgr.c (lines 547-577)

`WritebackContextInit`, `IssuePendingWritebacks`,
`ScheduleBufferTagForWriteback`, `TrackNewBufferPin`,
`StartBufferIO`, `StartSharedBufferIO`, `TerminateBufferIO`. Also exposes
the `StartBufferIOResult` enum `{ALREADY_DONE, IN_PROGRESS, READY_FOR_IO}`
"to make it easier to write tests" `[from-comment]`
(`buf_internals.h:556-573`).

### freelist.c (lines 580-588)

`IOContextForStrategy`, `StrategyGetBuffer`, `StrategyRejectBuffer`,
`StrategySyncStart`, `StrategyNotifyBgWriter`.

### buf_table.c (lines 590-594)

`BufTableHashCode`, `BufTableLookup`, `BufTableInsert`, `BufTableDelete`.
Thin partitioned-hash wrapper; caller must hold the right partition lock.

### localbuf.c (lines 596-623)

`PinLocalBuffer`, `UnpinLocalBuffer{,NoOwner}`, `PrefetchLocalBuffer`,
`LocalBufferAlloc`, `ExtendBufferedRelLocal`, `MarkLocalBufferDirty`,
`StartLocalBufferIO`, `TerminateLocalBufferIO`, `FlushLocalBuffer`,
`InvalidateLocalBuffer`, `DropRelationLocalBuffers`,
`DropRelationAllLocalBuffers`, `AtEOXact_LocalBuffers`.

## 8. Other declarations

- `WritebackContext` + `PendingWriteback` (`buf_internals.h:393-410`) —
  coalesces writeback hints (`sync_file_range`/`posix_fadvise`); per-backend
  (`BackendWritebackContext`) plus checkpointer's own. `max_pending` is
  pointer-to-GUC so live tuning works.
- `CkptSortItem` (`buf_internals.h:509-516`) — packed sort key (tablespace,
  rel, fork, block, buf_id) used by `BufferSync` to write checkpointed
  buffers in file-physical order.
- `BufferDescriptors` (extern) — pointer to the `BufferDescPadded` array
  (`buf_internals.h:413`).
- `BufferIOCVArray` (extern) — per-buffer `ConditionVariableMinimallyPadded`
  used for sync-IO waiters; kept outside `BufferDesc` to control struct
  size `[from-comment]` (`buf_internals.h:322-324, 414`).
- `LocalBufferDescriptors` (extern) — backend-private array
  (`buf_internals.h:418`).
- `buffer_io_resowner_desc`, `buffer_resowner_desc` + four inline
  `ResourceOwnerRemember/Forget` wrappers (`buf_internals.h:520-544`).

## 9. Invariants worth knowing

1. **State-word layout is frozen at compile time** — the `StaticAssertDecl`
   at `buf_internals.h:54` will fail the build if the four field widths
   ever exceed 64. Adding a flag means stealing from one of the other
   fields. `[verified-by-code]`.
2. **`BM_LOCKED` is bit 0 of the flag block** because the spinlock-via-state
   pattern uses `pg_atomic_fetch_or` to set just that bit; needing a
   compound mask would defeat the optimisation `[inferred]` from the
   `LockBufHdr` implementation at `bufmgr.c:7540`.
3. **`buf_id` is read without any lock** everywhere because it's
   write-once-at-init `[from-comment]` (`buf_internals.h:334-338`).
4. **A pinned buffer's tag is stable** even without the header spinlock —
   this is what makes the post-pin tag re-check in `BufferAlloc`'s hit
   path correct `[from-comment]` (`buf_internals.h:291-294`).
5. **Local buffers never call `LockBufHdr`** — `LockBufHdr` asserts
   `!BufferIsLocal(...)` at `bufmgr.c:7531` `[verified-by-code]`. Local
   buffers manipulate `state` with the unlocked atomic ops only.
6. **`BM_PIN_COUNT_WAITER` allows at most one waiter** — `LockBufferForCleanup`
   `ERROR`s if it sees the flag already set `[verified-by-code]`
   (`bufmgr.c:6738-6743`).

## 10. Cross-references

- `bufmgr.c` — implements `LockBufHdr`, `WaitBufHdrUnlocked`, and every
  function declared here for the shared path.
- `freelist.c` — clock sweep + `BufferAccessStrategy`.
- `buf_table.c` — `SharedBufHash` partitioned hash wrapper.
- `localbuf.c` — temp-table backend-local equivalent.
- `buf_init.c` — shmem allocation of `BufferDescriptors`,
  `BufferIOCVArray`, `BackendWritebackContext`, `CkptBufferIds`.
- `storage/bufmgr.h` — the **public** API (what callers outside the buffer
  manager see); this header is private to the subsystem.
- `storage/lwlock.h` — `MainLWLockArray`, `BUFFER_MAPPING_LWLOCK_OFFSET`,
  `NUM_BUFFER_PARTITIONS`.
- `storage/buf.h` — defines the opaque `Buffer` integer type and
  `InvalidBuffer`.

## 11. Tag tally

- `[verified-by-code]`: 18
- `[from-comment]`: 17
- `[inferred]`: 1

## Synthesized by
<!-- backlinks:auto -->
- [data-structures/bufferdesc-state.md](../../../../../data-structures/bufferdesc-state.md)
- [subsystems/storage-buffer.md](../../../../../subsystems/storage-buffer.md)
