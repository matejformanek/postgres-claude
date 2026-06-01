# `storage/ipc/ipci.c`

- **Source:** `source/src/backend/storage/ipc/ipci.c` (223 lines)
- **Header:** `source/src/include/storage/ipc.h`
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** deep-read

## Purpose

Coordinates the **creation of the main shared-memory segment** at
postmaster startup. The historical "long list of `XXXShmemInit()`
calls" is gone — it has been replaced by a callback-table mechanism
driven by `subsystemlist.h`. `[verified-by-code]`.

## CreateSharedMemoryAndSemaphores (`ipci.c:119`)

Called once by postmaster (assert `!IsUnderPostmaster`):

1. `CalculateShmemSize()` — sums `100000` bytes slack + `ShmemGetRequestedSize()`
   (sum of all registered `ShmemRequestStruct` calls) + extension
   request via `RequestAddinShmemSpace`, rounded up to 8 KiB.
   `:56-80`.
2. `PGSharedMemoryCreate(size, &shim)` — port-specific shmget/mmap/CreateFileMapping.
3. `InitShmemAllocator(seghdr)` — sets up `ShmemAllocator` + `ShmemIndex`
   inside the segment. (See `shmem.c`.)
4. `ShmemInitRequested()` — walks the `pending_shmem_requests` list,
   carves each chunk out of the segment, sets the caller's pointer
   variable, then calls every `init_fn`. `:149-150`.
5. `dsm_postmaster_startup(shim)` — sets up the DSM control segment.
6. `shmem_startup_hook` — extension hook.

## RegisterBuiltinShmemCallbacks (`ipci.c:167`)

This is the new mechanism. It expands `subsystemlist.h` (which is
`#include`d with a per-use `PG_SHMEM_SUBSYSTEM(x)` macro) once with
`PG_SHMEM_SUBSYSTEM(x) → RegisterShmemCallbacks(&x)`. The list is in
`source/src/include/storage/subsystemlist.h` and is *ordered* (LWLocks
first, then DSM, then xlog/clog/buffers, then lock-manager, then
proc/sinval, etc.). [from-comment] `subsystemlist.h:18-26`.

The callback table is `const ShmemCallbacks` instances scattered across
the codebase — one per subsystem (e.g. `BufferManagerShmemCallbacks`,
`LockManagerShmemCallbacks`, `ProcArrayShmemCallbacks`,
`SharedInvalShmemCallbacks`).

**This is a recent architectural refactor.** Older PG versions had
`CreateSharedMemoryAndSemaphores` containing a giant explicit list of
calls like `BufferManagerShmemInit()`, `LockManagerShmemInit()`, etc.
Now `ipci.c` is only 223 lines and `subsystemlist.h` (88 lines) is the
canonical inventory of what lives in shared memory.

## AttachSharedMemoryStructs (EXEC_BACKEND only)

Recomputes fast-path-lock groups (since the count isn't inherited
in EXEC_BACKEND), then `ShmemAttachRequested()`, then the
`shmem_startup_hook`. `:91-112`.

## InitializeShmemGUCs (`ipci.c:189`)

Sets the runtime-computed GUCs `shared_memory_size`,
`shared_memory_size_in_huge_pages`, and `num_os_semaphores` so the
admin can see what the server actually allocated.

## RequestAddinShmemSpace (`ipci.c:44`)

Only callable from `shmem_request_hook` (loaded library's pre-startup
hook). Accumulates extra space for legacy `ShmemInitStruct` users.
**New extension code should use `ShmemRequestStruct` via
`RegisterShmemCallbacks` instead.** `[from-comment]` in `shmem.c:79-83`.

## The subsystemlist.h order matters

Top-of-file comment: "Note: there are some inter-dependencies between
these, so the order of some of these matter." `[from-comment]`. LWLocks
must come first so other init_fn callbacks can safely call
`LWLockAcquire` (though no one is running concurrently, the comment
notes "we nevertheless allow it"). DSM is second so other subsystems
can stash registry handles. The dependency list contains: LWLocks,
DSM, DSMRegistry, Varsup, XLOG (+Prefetch +Recovery), CLOG, CommitTs,
Subtrans, MultiXact, BufferManager, StrategyCtl, BufTable, LockManager,
PredicateLock, ProcGlobal, ProcArray, BackendStatus, TwoPhase,
BackgroundWorker, SharedInval, PMSignal, ProcSignal, Checkpointer,
AutoVacuum, ReplicationSlots, ReplicationOrigin, WalSnd, WalRcv,
WalSummarizer, PgArch, ApplyLauncher, SlotSync, BTree, SyncScan,
Async, Stats, WaitEventCustom, [InjectionPoint], WaitLSN,
LogicalDecodingCtl, DataChecksums, Aio. `[verified-by-code]`.

## Cross-references

- Caller: `postmaster.c::PostmasterMain` (once, before forking),
  `postinit.c` in EXEC_BACKEND mode.
- Calls every subsystem's `ShmemCallbacks` via `shmem.c`.

## Open questions

- The old `CreateSharedMemoryAndSemaphores` code had explicit dependency
  comments next to each init call. After the callback refactor, those
  dependencies live only as comments in `subsystemlist.h`. Are there
  hidden ordering requirements that the new mechanism does not capture?
  `[unverified]` — would require diffing against the pre-refactor commit.

## See also

- `knowledge/architecture/process-model.md` §"What they share" — list
  of major shmem residents.
- `knowledge/files/src/backend/storage/ipc/shmem.c.md`.
