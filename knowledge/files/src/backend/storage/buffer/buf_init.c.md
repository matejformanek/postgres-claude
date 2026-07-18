# `src/backend/storage/buffer/buf_init.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~153
- **Source:** `source/src/backend/storage/buffer/buf_init.c`

Bootstrap of the shared buffer pool. Defines and exports the four
load-bearing globals (`BufferDescriptors`, `BufferBlocks`,
`BufferIOCVArray`, `CkptBufferIds`) plus
`BackendWritebackContext`, registers their shmem requests, and runs
once-per-postmaster initialization of all `NBuffers` headers. The
file's leading block comment is the canonical pithy summary of the
buffer-manager's lookup / replacement / IO-in-progress / refcount
contract. [verified-by-code]

## API / entry points

- `BufferManagerShmemCallbacks` — `ShmemCallbacks` registration
  triple `{request_fn, init_fn, attach_fn}` consumed by the shmem
  bootstrap (lines 34-38). [verified-by-code]
- `BufferManagerShmemRequest(void *arg)` (static) — reserves four
  separate shmem regions:
  - "Buffer Descriptors": `NBuffers * sizeof(BufferDescPadded)`,
    cacheline-aligned via `PG_CACHE_LINE_SIZE` (lines 79-84).
  - "Buffer Blocks": `NBuffers * BLCKSZ`, `PG_IO_ALIGN_SIZE`-aligned
    so direct-IO reads can land DMA into the buffers (lines 86-91).
  - "Buffer IO Condition Variables": one CV per buffer, cacheline
    aligned (lines 93-98).
  - "Checkpoint BufferIds": `NBuffers * sizeof(CkptSortItem)` — the
    sort area for checkpoint scheduling. Comment at lines 100-106
    explains why this isn't `palloc`'d at checkpoint time: an OOM
    mid-checkpoint would be painful, so we eat the shmem.
    [verified-by-code]
- `BufferManagerShmemInit(void *arg)` (static) — runs once in the
  postmaster (or stand-alone backend). Per-buffer init: clear tag,
  zero atomic `state`, set `wait_backend_pgprocno = INVALID_PROC_NUMBER`,
  assign monotonic `buf_id`, clear `io_wref`, init the
  per-buffer lock-waiter proclist and the IO CV. Then initialises
  per-backend writeback context (lines 142-145). [verified-by-code]
- `BufferManagerShmemAttach(void *arg)` (static) — only re-initialises
  per-backend writeback context; the shared headers were set up by
  the postmaster (lines 147-153). [verified-by-code]

## Notable invariants / details

- Block comment at lines 40-70 is the project's canonical brief on the
  buffer manager's three pillars: lookup table must be updated *before*
  IO starts (else two backends race-allocate the same block);
  replacement details live in `freelist.c`; `BM_IO_IN_PROGRESS` and
  refcount are independent gates. [from-comment]
- `BufferDescPadded` (cacheline-padded `BufferDesc`) is what the array
  actually contains, so the cacheline alignment request matters for
  false-sharing avoidance under concurrent
  `BufferDescriptorGetBuffer`/`PinBuffer` traffic. [verified-by-code]
- IO alignment (`PG_IO_ALIGN_SIZE`) is needed by `io_method=io_uring`
  and direct IO (`io_direct`) — the underlying pread/pwrite syscalls
  reject misaligned buffers under O_DIRECT. [inferred]
- `CkptBufferIds` is the moral equivalent of a per-checkpoint scratch
  array; allocating it once at startup avoids fragmenting shmem later.
  [from-comment]
- All four shmem regions are bound to **named** entries via
  `ShmemRequestStruct(.name = ...)` — the names also drive the
  `pg_shmem_allocations` view's display. [verified-by-code]
- `BackendWritebackContext` is a per-backend global (lives in BSS, not
  shmem) but is initialised both in `Init` (postmaster) and `Attach`
  (each backend that wasn't forked from postmaster — i.e. on
  EXEC_BACKEND platforms). [inferred]

## Potential issues

- No serious issues. The file is small and well-trodden. One minor:
  `BufferManagerShmemInit` does *not* re-zero `BufferDescriptors`
  beyond the per-field initialisation in the loop; it relies on
  `ShmemRequestStruct` zeroing or the postmaster's `mmap` semantics for
  the rest. If a future field is added to `BufferDesc` and the per-loop
  init forgets to set it, it'll silently start as zero. [ISSUE-undocumented-invariant:
  per-field init in BufferManagerShmemInit must cover all non-zero-default
  BufferDesc fields; relies on caller zero-fill for the rest (nit)]
- Line 132. `buf->wait_backend_pgprocno = INVALID_PROC_NUMBER;` is
  written as a raw field (not via atomic) because shmem is single-threaded
  at this point. Fine, but a comment noting "called only during
  postmaster startup" would help. [verified-by-code]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `storage-buffer`](../../../../../issues/storage-buffer.md)
<!-- issues:auto:end -->

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/storage-buffer.md](../../../../../subsystems/storage-buffer.md)
