---
name: buffer-manager
description: PostgreSQL's shared-buffer manager — `src/backend/storage/buffer/bufmgr.c` — the 8 KB shared-memory page cache underneath every heap/index read. Covers pin/unpin lifecycle, BufferDesc + hash table, clock-sweep replacement, BufferAccessStrategy (ring buffers for VACUUM / bulk read / bulk write), local buffers for temp tables, and pinning discipline. Loads when the user asks about `shared_buffers` sizing, pin/unpin semantics, buffer-pin deadlock scenarios, adding a new BufferAccessStrategy ring, `BufferDesc` state bits (VALID / DIRTY / IO_IN_PROGRESS), the clock-sweep replacement algorithm, or debugging "buffer leak" WARNINGs. Skip when the ask is about the AIO layer sitting between shmem and disk (see `aio-readstream`) or about visibility/hint bits (see the sibling idiom `hint-bits-setbufferdirty`).
when_to_load: Understand pin/unpin discipline; add or extend a BufferAccessStrategy; investigate clock-sweep / eviction behavior; touch pgstat_bgwriter counters; debug pin-leak WARNINGs or `LOG: incorrect resource manager data` on ProcessedBuffer.
companion_skills:
  - locking
  - vacuum-autovacuum
  - aio-readstream
---

# buffer-manager — the shared-memory page cache

Every read of any heap or index page in PG goes through the buffer manager. It maintains an in-memory cache (sized by `shared_buffers`) of 8 KB pages, indexed by `(rlocator, forknum, blocknum)`. Pins reserve a buffer for a caller; refcount → 0 lets the clock-sweep evictor pick it as a replacement candidate.

Getting pin/unpin discipline right is critical — leaks cause `WARNING: buffer refcount leak` and eventually OOM.

## The file map

| File | KB | Role |
|---|---:|---|
| `storage/buffer/bufmgr.c` | ~180 | The main file. Public API: `ReadBuffer`, `ReleaseBuffer`, `LockBuffer`, `MarkBufferDirty`, `FlushBuffer`, all the strategy-aware variants, clock-sweep, sync writer coordination. |
| `storage/buffer/freelist.c` | ~30 | Free-buffer list + clock sweep (`StrategyGetBuffer`). |
| `storage/buffer/localbuf.c` | ~20 | Local buffers for temp tables — per-backend, no shmem. |
| `storage/buffer/bufmgr_internals.h` | — | `BufferDesc` struct definition, buffer table primitives. |
| `storage/smgr/*` | — | The layer BELOW bufmgr — talks to actual file storage. |

## The buffer pool

A fixed-size array of `NBuffers` (from `shared_buffers`) buffers in shared memory. Each buffer is:

- A **BufferDesc** — the metadata (state, pin count, etc.).
- The **buffer page** — 8 KB of actual data.

Buffers are addressed by **buffer number** (1-indexed into the pool). NEGATIVE numbers refer to LOCAL buffers (temp tables).

## The BufferDesc state

Each BufferDesc holds packed state bits:

- `BM_LOCKED` — someone holds the internal spinlock.
- `BM_DIRTY` — page has changes not yet flushed.
- `BM_VALID` — the page content is loaded (not just an allocated slot).
- `BM_TAG_VALID` — the (rlocator, forknum, blocknum) tag is set.
- `BM_IO_IN_PROGRESS` — a read or write is happening; wait via CV.
- `BM_IO_ERROR` — the I/O failed; retry may be needed.
- `BM_JUST_DIRTIED` — was dirty AND has been written since; needs re-dirty check.
- **Refcount** — number of pins.
- **Usage count** — clock-sweep priority (0-5).
- **Wait backend PID** — for pin-waiting.

All state changes are atomic via `pg_atomic_*` since PG 12.

## Pin / unpin

```c
Buffer buf = ReadBuffer(rel, blocknum);  // + pin
LockBuffer(buf, BUFFER_LOCK_SHARE);      // + share content lock
/* ... use page ... */
UnlockReleaseBuffer(buf);                // - lock, - pin
```

The two-part lifetime: **pin** (reservation — prevents eviction) + **content lock** (SHARE / EXCLUSIVE — prevents concurrent modification). Both can be held OR released independently, though a common shortcut releases both.

Refcount management is via **ResourceOwner** — a subtransaction rollback releases all its pins. See `resource-owners` skill.

## Clock-sweep replacement

When a caller needs a buffer for a NEW page and the free list is empty:

1. `StrategyGetBuffer` runs the clock sweep starting at the last position.
2. Each buffer visited: if refcount > 0, skip. If usage_count > 0, decrement + continue. If usage_count = 0 AND refcount = 0, pick it.
3. If the picked buffer is dirty, flush it (may block on I/O).
4. Return the pinned + free buffer.

Usage count is incremented on every ReleaseBuffer up to a cap. New buffers start at 1. The algorithm approximates LRU without the strict-LRU overhead of maintaining a linked list.

## BufferAccessStrategy — the ring buffer pattern

For scans that would otherwise trash the whole buffer cache (VACUUM, big SELECTs, bulk-load COPY), the code uses a **BufferAccessStrategy** — a small ring of buffers that keep getting reused instead of evicting other backends' hot buffers.

Types (in `include/access/heapam.h`):
- `BAS_NORMAL` — no strategy; use the whole pool.
- `BAS_BULKREAD` — for full-table SELECTs. ~256 KB ring.
- `BAS_BULKWRITE` — for COPY / CREATE TABLE AS. Bigger ring, 16 MB.
- `BAS_VACUUM` — VACUUM. Distinct ring so vacuum doesn't evict user data.

A callable gets a strategy from `GetAccessStrategy(BAS_...)`. Passes it to `ReadBufferExtended` — the manager uses ring slots first.

The scenario `add-new-buffer-strategy` covers extending this.

## Local buffers (temp tables)

Temp tables + WITHOUT LOGGING relations use LOCAL buffers, not shared. In `localbuf.c`:

- Per-backend, in the backend's local memory.
- No shmem contention.
- Not visible to other backends (correct — temp tables are backend-private).
- Not flushed to disk on `WITH ...` transactions (unlogged); flushed on TEMP-TABLE with `ON COMMIT PRESERVE`.

## Synchronous writer coordination

- **bgwriter** — background writer. Scans the buffer pool for dirty buffers, writes them out to smooth checkpoint I/O.
- **checkpointer** — the checkpointer process — the OWNER of the sync writes. Flushes ALL dirty buffers at checkpoint.
- **Backends** — will FLUSH a buffer on eviction if it's dirty.

The three-way race is coordinated via `LATCH_WAIT` + spinlocks on individual BufferDescs.

## Common patch shapes

### Add a new BufferAccessStrategy ring

Scenario `add-new-buffer-strategy` covers this. Short:
- New enum value in `include/access/heapam.h` (BAS_...).
- Ring size + policy in `freelist.c` (`StrategyGetBuffer`'s strategy dispatch).
- Caller passes new strategy via `GetAccessStrategy`.

### Debug "buffer refcount leak WARNING"

- Log identifies the buffer + scope.
- Common cause: code path pins buffer, early-exits without releasing.
- ResourceOwner is the safety net (releases on scope exit) but shouldn't be relied on — should ReleaseBuffer explicitly.
- PIN_HINT can also be misread — hint bits alone aren't a pin.

### Change `shared_buffers` sizing recommendations

Not really a code change — but understanding: memory usage is roughly `NBuffers * 8KB` for pages plus BufferDesc structs (~80 bytes each). Adjust `shared_buffers` for the workload; ~25% of system memory is a common rule.

### Extend BufferDesc state bits

Very rare, dangerous. Requires:
- Coordinated update of `pg_atomic_*` operations.
- Backward-compat: never reuse a bit position without on-disk file format bump.
- Audit every state-checking site.

## Pitfalls

- **Pin leak on error paths** — a code path that pins then encounters ereport(ERROR) needs to be inside a ResourceOwner scope or explicit PG_TRY.
- **Buffer content lock ordering** — always acquire in a defined order (typically block-number order) to avoid deadlocks. See relevant per-AM code for the discipline.
- **DIRTY without LOCK EXCLUSIVE is wrong** — modifying a buffer's content requires EXCLUSIVE. Share-lock + modify is a classic bug source.
- **`MarkBufferDirty` vs `MarkBufferDirtyHint`** — the former is for WAL-logged changes; the latter is for hint-bit-style optimistic updates. Hint updates are lost on crash by design.
- **Local buffers aren't in shmem** — code that assumes "all buffers are in the shared pool" misses temp-table buffers. Handle both sides in bufmgr consumers.
- **Ring buffers can starve** — if a scan is much bigger than the ring, it constantly re-evicts its own pages. The ring is a trade-off, not a solution for arbitrary sizes.
- **Clock-sweep prefers old data** — if `shared_buffers` is undersized for the workload, clock-sweep will churn constantly. `pg_stat_bgwriter` + `pg_buffercache` show the pressure.
- **`pg_buffercache` contrib is O(N)** — scanning `shared_buffers` shows every buffer. On huge systems this can pause query dispatch.
- **`SyncOneBuffer` returns early on eviction race** — a caller assuming "sync happened" needs to check the return value.
- **BufferPin can outlive its content lock** — locking behavior split by design; consumers must understand the difference.

## Related corpus

- **Idioms** (multiple hits): `hint-bits-setbufferdirty` (hint updates), `spinlock-discipline` (bufhdrspinlock semantics), `gin-fastupdate-pending` (fastupdate uses a special buffer), `wal-buffer-state` (WAL buffers — sibling system, not shared), `xlog-region-replay` (XLogReadBufferForRedo interaction).
- **Subsystems**: `storage-buffer` (this skill's home), `storage-ipc` (LWLocks used for BM_IO_IN_PROGRESS waits), `access-heap` (primary caller).
- **Data structure**: `bufferdesc-state` (definitive BufferDesc struct doc).
- **Scenario**: `add-new-buffer-strategy` (the ring-buffer patch shape).
- **README**: `source/src/backend/storage/buffer/README` — authoritative design doc; shorter than this skill.

## Corpus-chain shortcut

```
python3 scripts/corpus-chain.py --scenario add-new-buffer-strategy
python3 scripts/corpus-chain.py --file src/backend/storage/buffer/bufmgr.c
```

## Boundary

**Use this skill** for `bufmgr.c` internals + BufferAccessStrategy + pin/unpin discipline.

**Don't use** for:
- **`storage/smgr/`** — the storage-media layer BELOW bufmgr. Different concerns.
- **AIO / read_stream** — sits BETWEEN bufmgr and smgr in the read path. See `aio-readstream`.
- **Visibility map / freespace map** — separate forks; use `free-space-map` etc.
- **`pg_buffercache`** — contrib module for introspection.
- **WAL buffers** — separate system (WAL is written to a different shmem area). See `wal-buffer-state` idiom.
