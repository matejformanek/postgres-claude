# `storage/sinvaladt.h`

- **Source:** `source/src/include/storage/sinvaladt.h` (38 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** full-read

Tiny header exposing the **shared queue layer** of sinval. Only the
plumbing between `sinval.c` (the API users see) and the impl in
`sinvaladt.c` (the queue itself).

## API

- `SharedInvalBackendInit(sendOnly)` — claim our slot. `sendOnly`
  is true only for the Startup process during recovery (it sends invals
  but has no catalog cache to invalidate).
- `SIInsertDataEntries(data, n)` — writer.
- `SIGetDataEntries(data, datasize)` — reader; returns count, 0 for
  empty, -1 for reset.
- `SICleanupQueue(callerHasWriteLock, minFree)` — GC + catchup-signal
  the furthest-behind backend.
- `GetNextLocalTransactionId()` — allocate next per-backend LXID for
  the VXID (lock-free; LXIDs are unique within a backend's slot
  occupancy).

Header says nothing else. **Don't call these directly** — use the
`sinval.c` API instead, unless you're inside core invalidation/recovery
code that needs the lower-level interface.

## Synthesized by
<!-- backlinks:auto -->
- [idioms/sinvaladt-broadcast.md](../../../../idioms/sinvaladt-broadcast.md)
