# xlogwait.h

- **Source path:** `source/src/include/access/xlogwait.h`
- **Lines:** 109
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `xlogwait.c`.

## Purpose

Public interface to `xlogwait.c`: the `WaitLSNType` / `WaitLSNResult`
enums, the `WaitLSNProcInfo` / `WaitLSNState` shared-memory structs,
and the four entry-point prototypes. [from-comment] `xlogwait.h:3-4`.

## Top-of-file comment (verbatim)

```
xlogwait.h
   Declarations for WAL flush, write, and replay waiting routines.
```
[verified-by-code] `xlogwait.h:3-4`.

## Key types

### `WaitLSNResult` (`xlogwait.h:25-31`) [verified-by-code]

`WAIT_LSN_RESULT_SUCCESS`, `_NOT_IN_RECOVERY`, `_TIMEOUT`.

### `WaitLSNType` (`xlogwait.h:36-45`) [verified-by-code]

Standby-side: `WAIT_LSN_TYPE_STANDBY_REPLAY`, `_STANDBY_WRITE`,
`_STANDBY_FLUSH`. Primary-side: `WAIT_LSN_TYPE_PRIMARY_FLUSH`.
`WAIT_LSN_TYPE_COUNT = PRIMARY_FLUSH + 1`. [verified-by-code]
`xlogwait.h:47`.

### `WaitLSNProcInfo` (`xlogwait.h:54-73`) [verified-by-code]

`{ XLogRecPtr waitLSN; WaitLSNType lsnType; ProcNumber procno;
bool inHeap; pairingheap_node heapNode; }`. One per PGPROC.

### `WaitLSNState` (`xlogwait.h:78-98`) [verified-by-code]

`{ pg_atomic_uint64 minWaitedLSN[WAIT_LSN_TYPE_COUNT];
pairingheap waitersHeap[WAIT_LSN_TYPE_COUNT];
WaitLSNProcInfo procInfos[FLEX]; }`. Pointed-to by `waitLSNState`.

## Public surface

- Extern `waitLSNState`. [verified-by-code] `xlogwait.h:101`.
- `GetCurrentLSNForWaitType(WaitLSNType)` — `xlogwait.h:103`
  [verified-by-code]
- `WaitLSNWakeup(WaitLSNType, currentLSN)` — `xlogwait.h:104`
  [verified-by-code]
- `WaitLSNCleanup(void)` — `xlogwait.h:105` [verified-by-code]
- `WaitForLSN(WaitLSNType, targetLSN, timeout)` — `xlogwait.h:106-107`
  [verified-by-code]

## Key invariants

1. **`minWaitedLSN` is atomic and lock-free for readers.** Writers
   take `WaitLSNLock`. [from-comment] `xlogwait.h:80-84`.

2. **`waitersHeap` per type is pairing-heap.** Protected by
   `WaitLSNLock`. [from-comment] `xlogwait.h:87-90`.

3. **A process can wait for only one LSN type at a time.**
   `inHeap` is a single boolean; `lsnType` records which heap.
   [from-comment] `xlogwait.h:66-69`.

## Cross-references

- `xlogwait.c` is the implementation.
- `xlogfuncs.c` exposes `pg_wait_for_replay_lsn` etc. on top.
- `xlog.c` (after flush) and `xlogrecovery.c` (after replay) call
  `WaitLSNWakeup`.

## Confidence tag tally

- `[verified-by-code]`: 13
- `[from-comment]`: 4
