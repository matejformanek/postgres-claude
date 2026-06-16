# `src/backend/storage/buffer/localbuf.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~1046
- **Source:** `source/src/backend/storage/buffer/localbuf.c`

Backend-private buffer pool used for temporary tables (and the
session's portion of temp work-files via `BufFile`). Mirrors the
shared-buffer API surface (`PinLocalBuffer`, `MarkLocalBufferDirty`,
`StartLocalBufferIO`, etc.) but skips all the locking: each backend
owns its own `LocalBufferDescriptors[]`, `LocalBufferBlockPointers[]`,
`LocalRefCount[]`, and `LocalBufHash` HTAB. Buffers are lazily
allocated, parallel workers can never touch them, and the clock-sweep
is dramatically simpler than the shared-buffer variant. [verified-by-code]

## API / entry points

- `PrefetchLocalBuffer(smgr, fork, blockNum)` — prefetch a temp-rel
  block via `smgrprefetch`; no-op when `USE_PREFETCH` is disabled or
  `io_direct` includes `IO_DIRECT_DATA`. Returns `recent_buffer` if
  the page is already cached (lines 71-107). [verified-by-code]
- `LocalBufferAlloc(smgr, fork, blockNum, *foundPtr)` — find-or-create
  per the shared-buffer API. Lazy-inits the per-backend pool on first
  call (line 132). Adds to ResourceOwner. On miss, picks a victim via
  `GetLocalVictimBuffer` and installs the tag (lines 118-177).
  [verified-by-code]
- `FlushLocalBuffer(bufHdr, reln)` — write a single dirty local buffer
  via `smgrwrite`. Sets the page checksum (line 203); accounts the IO
  time under `IOOBJECT_TEMP_RELATION`/`IOCONTEXT_NORMAL`. Comment notes
  temp-table IO does not use access strategies (line 214). [verified-by-code]
- `GetLocalVictimBuffer(void)` (static) — clock-sweep over local
  buffers using `nextFreeLocalBufId`; flushes dirty victims and frees
  the hash entry. `LocalRefCount[]` (not the atomic state's refcount)
  is the primary "pinned?" check (lines 224-304). [verified-by-code]
- `GetLocalPinLimit(void)`, `GetAdditionalLocalPinLimit(void)`,
  `LimitAdditionalLocalPins(*additional_pins)` — mirror the shared-buffer
  pin-limit API. Default cap is `num_temp_buffers / 4` "leaving headroom
  for concurrent pin-holders" within the same query (lines 306-348).
  [verified-by-code]
- `ExtendBufferedRelLocal(bmr, fork, flags, extend_by, extend_upto,
  buffers[], *extended_by)` — temp-rel equivalent of
  `ExtendBufferedRel`. Picks `extend_by` victims, then for each new
  block: zero-fill, install tag, raise `BM_TAG_VALID`,
  `StartLocalBufferIO(forInput=true)`; finally calls `smgrzeroextend`
  for all blocks at once. Handles the case where a victim's tag still
  matches an existing entry (concurrent-extension impossible for temp
  rels, but bookkeeping symmetric). (Lines 354-493) [verified-by-code]
- `MarkLocalBufferDirty(buffer)`, `StartLocalBufferIO(...)`,
  `TerminateLocalBufferIO(...)`, `InvalidateLocalBuffer(...)` — direct
  parallels to the shared-buffer counterparts (lines 499-675).
  [verified-by-code]
- `DropRelationLocalBuffers(rlocator, forkNum[], nforks, firstDelBlock[])`,
  `DropRelationAllLocalBuffers(rlocator)` — invalidate temp-rel pages
  at relation drop / truncate (lines 688-743). [verified-by-code]
- `InitLocalBuffers(void)` (static) — first-use allocator for
  `LocalBufferDescriptors[]` etc. Errors with
  `"cannot access temporary tables during a parallel operation"` if
  `IsParallelWorker()` (lines 766-769) — the cheap parallel-worker
  backstop. [verified-by-code]
- `PinLocalBuffer(buf_hdr, adjust_usagecount)`,
  `UnpinLocalBuffer(buffer)`, `UnpinLocalBufferNoOwner(buffer)` —
  refcount + resowner bookkeeping (lines 828-895). [verified-by-code]
- `check_temp_buffers(*newval, **extra, source)` — GUC check hook;
  rejects `SET temp_buffers` once buffers are allocated (lines 900-913).
  [verified-by-code]
- `GetLocalBufferStorage(void)` (static) — lazy per-block memory
  allocation. Doubles request size each time, capped at the remaining
  buffer count and `MaxAllocSize / BLCKSZ`. Uses a dedicated
  `LocalBufferContext` for easy MemoryContextStats visibility
  (lines 924-986). [verified-by-code]
- `AtEOXact_LocalBuffers(isCommit)`, `AtProcExit_LocalBuffers()` —
  pin-leak detection. Both call `CheckForLocalBufferLeaks` (only active
  under `USE_ASSERT_CHECKING`). [verified-by-code]

## Notable invariants / details

- Buffer-IDs for local buffers are *negative*: `BufferDesc.buf_id = -i - 2`
  (line 793), and the user-facing `Buffer` handle is `-buf_id - 1`. The
  off-by-two trick lets `BufferDescriptorGetBuffer` add 1 uniformly to
  shared (≥0) and local (≤-1) IDs. Negation is the discriminator (see
  `BufferIsLocal`). [from-comment]
- `LocalBufHdrGetBlock` (line 42-43) uses `LocalBufferBlockPointers[-(buf_id+2)]`
  — the negation reverses the ID layout above. Comment warns "this
  macro only works on local buffers, not shared ones!". [from-comment]
- `nextFreeLocalBufId` is the per-backend equivalent of
  `StrategyControl->nextVictimBuffer`; no atomics needed (single-writer).
  [verified-by-code]
- Lazy block allocation in `GetLocalBufferStorage` (lines 924-986):
  16-buffer chunks, doubling, in a dedicated MemoryContext. Comment at
  916-922 explains the chunking: we never return a temp buffer to the
  memory manager once allocated, so per-buffer palloc would waste
  overhead. Chunks are I/O aligned (`PG_IO_ALIGN_SIZE`) via
  `MemoryContextAllocAligned` for direct-IO / io_uring compatibility.
  [from-comment]
- Local buffers do not use `BM_IO_IN_PROGRESS`, `BM_PIN_COUNT_WAITER`,
  or the IO condition variable (comments at 575, 593, 613-615). They do
  participate in AIO via `io_wref` — Comment at 537-540 explains the
  AIO-in-progress path: two scans of the same temp rel can both try to
  read the same block, and the second sees `pgaio_wref_valid` and
  joins the existing IO. [from-comment]
- Pin tracking: `LocalRefCount[bufid]` is the canonical pin count;
  `BUF_STATE_GET_REFCOUNT(state)` in the atomic is used *only* by the
  AIO subsystem to mark "this buffer has IO active, don't reuse"
  (lines 654-657). Both must be zero before invalidation. [verified-by-code]
- `PinLocalBuffer` increments shared `state` refcount (line 840) only
  when `LocalRefCount` transitions 0→1; further pins from the same
  backend bump only `LocalRefCount`. Mirrors the
  `PrivateRefCount`/shared-refcount distinction from `bufmgr.c`.
  [verified-by-code]
- Concurrency safety of "unlocked" atomic writes: throughout this file,
  state writes use `pg_atomic_unlocked_write_u64` because there is only
  one mutator (this backend). The atomic is still used for AIO callers
  who genuinely read concurrently. [verified-by-code]
- `IsParallelWorker()` check in `InitLocalBuffers` (line 766) is the
  "convenient low-cost backstop" — comment at 758-765 says it's
  acceptable to allow parallel workers to read catalog metadata about
  temp tables, just not their data. So the check is at first-buffer-use
  rather than at planner time. [from-comment]
- `FlushLocalBuffer` calls `StartLocalBufferIO(forInput=false, wait=true)`
  and errors if the result is not `BUFFER_IO_READY_FOR_IO`. Comment at
  192-194: "there currently are no reasons for StartLocalBufferIO to
  return anything other than BUFFER_IO_READY_FOR_IO" — the error is
  a "should never happen" guard for future AIO behaviour. [from-comment]
- `ExtendBufferedRelLocal` handles `found == true` from the hash insert
  at line 426-448: this case means the tag for the new block already
  existed in the hash (shouldn't happen for temp rels since no concurrent
  writer can extend), but the code defensively unpins the victim and
  pins the existing buffer. Comment at 437-447 walks through the
  recovery: clear `BM_VALID`, `StartLocalBufferIO`, proceed.
  [from-comment]
- `check_temp_buffers` (line 900) allows `SET` to fail with a
  user-facing error after the local buffer pool is created — the GUC
  is effectively per-session and immutable after first use. [verified-by-code]

## Potential issues

- Line 772-778. `calloc()` plus a `FATAL` ereport on failure. `calloc`
  is one of very few raw libc allocators called in PG backend code
  (palloc would charge the wrong context). The ereport at FATAL is
  correct because we can't recover, but the message is just "out of
  memory" with no context (which struct ran out). Cosmetic. [verified-by-code]
- Lines 257-263. The `BUF_STATE_GET_REFCOUNT(buf_state) > 0` branch in
  `GetLocalVictimBuffer` is an empty body comment-only branch ("This
  can be reached if the backend initiated AIO for this buffer and then
  errored out"). The result is the clock sweep simply moves on without
  decrementing `trycounter` — so if a backend leaks an AIO ref after
  abort, those slots stay un-recyclable until the backend exits.
  [ISSUE-leak: orphaned AIO ref on local buffer can permanently skip
  that buffer in clock sweep until backend exit (maybe)]
- Line 274. "no empty local buffer available" — like the shared
  counterpart, no hint about how to diagnose. [ISSUE-doc-drift: error
  message lacks errhint (nit)]
- Lines 822-826. `XXX: We could have a slightly more efficient version
  of PinLocalBuffer() that does not support adjusting the usagecount`
  — stale TODO, low priority. [ISSUE-stale-todo: open XXX about an
  unrealized micro-optimisation (nit)]
- Line 793. `buf->buf_id = -i - 2;` initialisation depends on the
  conventions in `BufferDescriptorGetBuffer` and `BufferIsLocal`; the
  comment block (787-794) is good but the off-by-two is fragile if
  someone refactors the shared-buffer ID layout. [verified-by-code]
- Lines 797-802. Comment: "Intentionally do not initialize the buffer's
  atomic variable (besides zeroing the underlying memory above). That
  way we get errors on platforms without atomics, if somebody
  (re-)introduces atomic operations for local buffers." A clever
  belt-and-suspenders against an anti-pattern, but only catches it on
  weird platforms. [from-comment]
- `LocalBufferContext` (line 931) is a static-local. It lives in
  TopMemoryContext and is never freed during the backend's lifetime —
  intentional ("we'll never give back a local buffer once it's created
  within a particular process"). A backend that creates and drops many
  temp tables will not give back the local buffer storage until exit.
  [from-comment] [ISSUE-leak: temp-buffer storage permanently retained
  for backend lifetime even after all temp tables dropped (maybe)]
- Line 442-444. `Assert(buf_state & BM_TAG_VALID); Assert(!(buf_state &
  BM_DIRTY));` after a `hash_search HASH_ENTER` returned `found = true`
  — this path is reachable in theory only if there's a stale entry,
  but no comment explains how that could happen for temp rels. The
  defensive code is correct; the puzzle is whether the hash entry
  could ever legitimately predate the buffer slot. [ISSUE-undocumented-invariant:
  `found = true` branch in ExtendBufferedRelLocal undocumented (nit)]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `storage-buffer`](../../../../../issues/storage-buffer.md)
<!-- issues:auto:end -->
