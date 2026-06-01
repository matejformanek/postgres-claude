# xlogwait.c

- **Source path:** `source/src/backend/access/transam/xlogwait.c`
- **Lines:** 495
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `source/src/include/access/xlogwait.h`,
  `xlog.c`, `xlogrecovery.c`, `replication/walreceiver.c`.

## Purpose

Implements blocking waits for WAL operations to reach specific LSNs,
on both primary (insert/write/flush) and standby (replay). Backends
publish their target LSN to shared memory; the responsible process
(walwriter / startup / walreceiver) wakes them once the LSN has been
reached. Per-type pairing heap allows O(log n) "least awaited" lookup.
[from-comment] `xlogwait.c:3-29`.

## Top-of-file comment (verbatim)

```
xlogwait.c
   Implements waiting for WAL operations to reach specific LSNs.

NOTES
    This file implements waiting for WAL operations to reach specific LSNs
    on both physical standby and primary servers. The core idea is simple:
    every process that wants to wait publishes the LSN it needs to the
    shared memory, and the appropriate process (startup on standby,
    walreceiver on standby, or WAL writer/backend on primary) wakes it
    once that LSN has been reached.

    The shared memory used by this module comprises a procInfos
    per-backend array with the information of the awaited LSN for each
    of the backend processes.  The elements of that array are organized
    into pairing heaps (waitersHeap), one for each WaitLSNType, which
    allows for very fast finding of the least awaited LSN for each type.

    In addition, the least-awaited LSN for each type is cached in the
```
[verified-by-code] `xlogwait.c:3-29`.

## Public surface

- `GetCurrentLSNForWaitType(WaitLSNType)` — `xlogwait.c:99`
  [verified-by-code]
- `WaitLSNShmemRequest(*arg)` / `WaitLSNShmemInit(*arg)` —
  `xlogwait.c:146, 160` [verified-by-code]
- `WaitForLSN(WaitLSNType, targetLSN, timeout)` — `xlogwait.c:403`
  [verified-by-code]
- `WaitLSNWakeup(WaitLSNType, currentLSN)` — `xlogwait.c:344`
  [verified-by-code]
- `WaitLSNCleanup(void)` — `xlogwait.c:366` [verified-by-code]
- `WaitLSNTypeRequiresRecovery(WaitLSNType)` — `xlogwait.c:387`
  [verified-by-code]

Internal:

- `waitlsn_cmp` — `xlogwait.c:179` (pairing-heap comparator)
  [verified-by-code]
- `updateMinWaitedLSN` — `xlogwait.c:196` [verified-by-code]
- `addLSNWaiter` / `deleteLSNWaiter` — `xlogwait.c:218, 243`
  [verified-by-code]
- `wakeupWaiters` — `xlogwait.c:283` [verified-by-code]

## Key types

- `WaitLSNState` — shared-memory module state:
  `pairingheap waitersHeap[WAIT_LSN_TYPE_COUNT]`,
  `pg_atomic_uint64 minWaitedLSN[WAIT_LSN_TYPE_COUNT]`,
  per-PGPROC `procInfos[]` entry array, spinlock.
  [verified-by-code] (struct declared in `xlogwait.h`).
- `WaitLSNType` — enum: `WAIT_LSN_TYPE_REPLAY`,
  `_WRITE`, `_FLUSH`, `_INSERT` (counts up to `WAIT_LSN_TYPE_COUNT`).
- `WaitLSNWaitEvents[]` — array of `pgstat_wait_event` per type.
  [verified-by-code] `xlogwait.c:91`.

## Key invariants and locking

1. **Per-type pairing heap.** Each `WaitLSNType` has its own heap of
   waiters keyed by LSN; min element is the next backend to wake.
   [from-comment] `xlogwait.c:18-22`.

2. **Cached `minWaitedLSN` atomic per type.** Producers (the
   walwriter / startup process) read this atomic; if their current
   LSN < cached min, no shared-state work needed.
   [from-comment] `xlogwait.c:24-…`.

3. **`WAIT_LSN_TYPE_REPLAY` only valid in recovery.**
   `WaitLSNTypeRequiresRecovery` returns true for it. [verified-by-code]
   `xlogwait.c:387`.

4. **Cleanup on backend exit.** `WaitLSNCleanup` removes any
   leftover heap entry; called from `xact.c` (typically via
   process-exit hook). [verified-by-code] `xlogwait.c:366`.

5. **`pg_wait_for_replay_lsn` SQL function** is one user; logical
   replication apply workers, sync standbys also use this.
   [inferred] from typical use.

## Functions of note

### `WaitForLSN` — `xlogwait.c:403` [verified-by-code]

Computes current LSN via `GetCurrentLSNForWaitType`; if not yet
reached, adds the backend to the heap, sets process latch, sleeps
in `WaitLatchOrSocket` / `WaitEventSetWait` until either
`WaitLSNWakeup` removes us or `timeout` expires.

### `WaitLSNWakeup` — `xlogwait.c:344` [verified-by-code]

Called by the producer (e.g. `xlog.c` after a flush) when LSN
advances past the heap's min. Pops all waiters at LSNs ≤
`currentLSN` and sets their latches.

## Cross-references

- `xlog.c` (and `walwriter`) call `WaitLSNWakeup(WAIT_LSN_TYPE_FLUSH,
  …)` after `XLogFlush`.
- `xlogrecovery.c:ApplyWalRecord` (or a near caller) calls
  `WaitLSNWakeup(WAIT_LSN_TYPE_REPLAY, replayEndRecPtr)` after
  each record.
- `xlogfuncs.c` exposes SQL: `pg_wait_for_replay_lsn`.

## Open questions

- The detailed handshake when a backend's PGPROC is reused before
  `WaitLSNCleanup` runs (slot reuse race) not deep-read. [unverified]

## Confidence tag tally

- `[verified-by-code]`: 17
- `[from-comment]`: 4
- `[inferred]`: 1
- `[unverified]`: 1
