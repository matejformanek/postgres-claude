# Session: 2026-06-01 — storage/buffer calibration doc

## What I did

- Read `source/src/backend/storage/buffer/README` end-to-end (the 278-line canonical narrative on pins, content locks, BufMappingLock partitioning, clock sweep, ring strategies, bgwriter).
- Read all four `.c` files under `storage/buffer/` plus the surrounding headers (`buf_internals.h`, `bufmgr.h`). `bufmgr.c` is ~9 kLOC; I jumped to the principal entry points listed at `bufmgr.c:15-34` and to the spine functions: `BufferAlloc` (2197), `GetVictimBuffer` (2547), `InvalidateBuffer` (2369), `InvalidateVictimBuffer` (2471), `PinBuffer` (3281), `UnpinBuffer` (3465), `FlushBuffer` (4512), `DropRelationBuffers` (4774), `LockBufferForCleanup` (6679), `StartSharedBufferIO` (7250), `WaitIO` (7148), `LockBufHdr` (7527), and the `BufferLockAcquire/Unlock` family (5907+).
- Wrote `knowledge/subsystems/storage-buffer.md` to the §3 template. 96 tagged claims total:
  verified-by-code=49, from-README=27, from-comment=15, inferred=0, unverified=5.
- Logged 6 open questions in §9 and the coverage row.

## What I learned

- The `state` field in `BufferDesc` is now a single 64-bit atomic packing refcount, usagecount, 12 flag bits, and the content-lock state (formerly an LWLock). `BM_LOCKED` is itself a flag bit; many manipulations are CAS loops rather than spinlock acquires. This is a meaningful change from older PG.
- The README's "BufMappingLock" name is purely historical — it has been NUM_BUFFER_PARTITIONS LWLocks since 8.2.
- The clock sweep is monotonic-add-then-modulo (`nextVictimBuffer` is uint32 that just keeps growing); wraparound increments `completePasses` under `buffer_strategy_lock` so `StrategySyncStart` can read a consistent pair.
- `GetVictimBuffer` uses *conditional* share-exclusive lock acquisition specifically to avoid a known concurrent-btree-split deadlock (comment at `bufmgr.c:2592-2611`).

## What I'm unsure about

- The total ordering between content lock and `BufMappingLock` partition lock — `BufferAlloc` clearly takes mapping first and never co-holds with content, but no README/comment states the global rule.
- Whether `BM_IO_IN_PROGRESS` can ever be set while holding a partition lock (code suggests no).
- Real in-tree callers that hold two `BufMappingLock` partitions simultaneously (README says they must use partition-number order, but I didn't find an actual caller in this subsystem).
- Whether AIO is exercised for local buffers via `StartLocalBufferIO` or only for shared.

## Pointers for next time

- If the human reviewer flags any wrong claim, the §6 ordering bullets are most at risk — re-grep the relevant function names against the source before patching.
- Next subsystem per the plan: `access/heap`. Spine is `heapam.c` + `pruneheap.c` + `vacuumlazy.c`; READMEs in `access/heap/README.HOT` and `README.tuplock`.
- Consider whether §7 should grow a back-pointer to the heap/index AM consumers once those docs exist.
