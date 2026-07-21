# Storage / Inter-Process Communication (shmem, sinval, latches, DSM, procsignal)

## Owners (as of 2026-06-12)

- **Top committers (last 24mo):** Heikki Linnakangas (50), Peter Eisentraut (17), Nathan Bossart (15), Álvaro Herrera (11)
- **Top reviewers (last 24mo):** Andres Freund (22), Chao Li (14), Matthias van de Meent (12), Ashutosh Bapat (12)
- **Recent landmark commits (12mo):**
  - `2dd506b859c (Nathan Bossart, 2025-11-26): Revert "Teach DSM registry to ERROR if attaching to an uninitialized entry."`
  - `3e2a1496bae (Andrew Dunstan, 2026-04-14): Rework signal handler infrastructure to pass sender info as argument.`
  - `01a80f06214 (Álvaro Herrera, 2026-05-23): Revert "Allow logical replication snapshots to be database-specific"`

See `knowledge/personas/domain-ownership.md` for the cross-subsystem index, methodology, and committer/reviewer affinity clusters.

---


- **Source path:** `source/src/backend/storage/ipc/`
- **Header path:** `source/src/include/storage/` (`shmem.h`, `shmem_internal.h`, `ipc.h`, `sinval.h`, `sinvaladt.h`, `latch.h`, `waiteventset.h`, `dsm.h`, `dsm_impl.h`, `dsm_registry.h`, `procsignal.h`, `pmsignal.h`, `procarray.h`, `barrier.h`, `shm_mq.h`, `shm_toc.h`, `standby.h`, `subsystemlist.h`)
- **Last verified commit:** `ef6a95c7c64de07dff4dd1f1da88ffae7b086ef3` (2026-06-01)
- **README anchor:** no dedicated `README` in `storage/ipc`; the canonical anchors are the top-of-file comments and `src/include/storage/subsystemlist.h`. The closest narrative texts live in `access/transam/README` (snapshot read protocol) and per-file headers cited below.

## 1. Purpose

This directory is the **shared-state plumbing for PG's multi-process backend
model**. The fork-per-connection executor model means every cooperating
process has its own address space; everything they share — the buffer pool,
the lock table, MVCC snapshot state, cache invalidations, parallel-query
tuple queues — lives in one of two memory regions managed here: the
**main shared-memory segment** (created once at postmaster startup by
`ipci.c`/`shmem.c`) and **dynamic shared memory segments** (created and
destroyed at runtime by `dsm.c`). On top of those, this directory provides
the wakeup primitives (`latch.c` + `waiteventset.c`), the cross-backend
signal multiplexer (`procsignal.c`), the children→postmaster signal channel
(`pmsignal.c`), the cache-invalidation broadcast bus (`sinval.c` +
`sinvaladt.c`), the running-transaction array that drives MVCC
(`procarray.c`), and a few helpers (`barrier.c`, `shm_mq.c`, `shm_toc.c`,
`standby.c`, `signalfuncs.c`). `[from-comment]` per-file headers cited
below.

## 2. Mental model

Six concepts to hold in your head when reading this directory:

- **Main shmem layout is now subsystemlist-driven.** `subsystemlist.h` is a
  single X-macro list that defines `PG_SHMEM_SUBSYSTEM(x)` for each builtin
  area (LWLocks first, then DSM, XLOG, CLOG, BufferManager, LockManager,
  ProcArray, SharedInval, ProcSignal, …). The historic giant chain of
  explicit `XXXShmemInit()` calls in `ipci.c::CreateSharedMemoryAndSemaphores`
  has been replaced by `RegisterBuiltinShmemCallbacks()` expanding that
  X-macro `[verified-by-code]` `ipci.c:167-191` `[via knowledge/files/src/backend/storage/ipc/ipci.c.md]`; ordering
  still matters and is encoded by line order in `subsystemlist.h:18-26`
  `[from-comment]`. The allocator itself is a one-way bump pointer in
  `shmem.c:43-46` with a separately-locked `ShmemIndex` hash for name→pointer
  lookup `[verified-by-code]` `shmem.c:224-272` `[via knowledge/files/src/backend/storage/ipc/shmem.c.md]`.
- **ProcArray = MVCC kernel.** `procarray.c` enumerates the running
  transactions as a packed array of `pgxactoff` indexes; `GetSnapshotData`
  is the hottest read in the backend, and its O(1) fast path is the
  `xactCompletionCount` counter trick (see §5). `procarray.c:1-15`
  `[from-comment]`.
- **sinval queue = cache-invalidation broadcast bus.** A 4096-slot
  circular buffer (`MAXNUMMESSAGES`, must be power of 2) of
  `SharedInvalidationMessage` carrying "your cached catalog entry for X is
  stale" notices. Per-backend `nextMsgNum` cursors; backends that fall
  more than `SIG_THRESHOLD = 2048` behind get a `PROCSIG_CATCHUP_INTERRUPT`
  poke `[verified-by-code]` `sinvaladt.c:128-135` `[via knowledge/files/src/backend/storage/ipc/sinvaladt.c.md]`. The locking is
  unusual — see §6.
- **Latches = the reliable wakeup primitive.** A `Latch` is a one-bit
  flag with two memory-barriered states (`is_set`, `maybe_sleeping`); the
  OS-level wait happens in a `WaitEventSet` (`waiteventset.c`) that
  multiplexes epoll/kqueue/poll/Win32. **The cross-process wake signal is
  `SIGURG`, not `SIGUSR1`** (SIGUSR1 is reserved for procsignal-multiplexed
  reasons), and on Linux the signal is consumed via a `signalfd` registered
  into the epoll set rather than via a self-pipe trick `[from-comment]`
  `waiteventset.c:30-33` `[via knowledge/files/src/backend/storage/ipc/waiteventset.c.md]`.
- **DSM = runtime-allocatable shared memory.** Used by parallel query and
  by extensions that need to grow shared state after `shared_preload_libraries`
  has closed. The `dsm_control_header` (a separate, small DSM segment owned
  by the postmaster) is the refcount table for every live segment; segment
  handles are *random even uint32s* and the low bit is reserved to mean
  "this is a slot index into the preallocated main-region slab"
  `[from-comment]` `dsm.c:216-228, 1270-1294` `[via knowledge/files/src/backend/storage/ipc/dsm.c.md]`.
- **procsignal = multiplexed SIGUSR1 between backends.** Backends raise
  `SIGUSR1` on each other after setting a per-reason flag in their target's
  `ProcSignalSlot`; the SIGUSR1 handler in `tcop/postgres.c` walks the
  flag array and dispatches. The same struct also carries the
  `ProcSignalBarrier` generation counter used for system-wide state-change
  propagation (e.g. checksum-mode toggle) `[verified-by-code]`
  `procsignal.c:295-313, 368-455` `[via knowledge/files/src/backend/storage/ipc/procsignal.c.md]`.

## 3. Key files

Grouped by concern.

### shmem / startup

- `shmem.c` (1298 lines) — the shared-memory bump allocator + named-area
  registry (`ShmemIndex`), both `ShmemRequestStruct`/`RegisterShmemCallbacks`
  (modern) and `ShmemInitStruct`/`RequestAddinShmemSpace` (legacy)
  interfaces. Top-of-file at `shmem.c:1-30`. `[via knowledge/files/src/backend/storage/ipc/shmem.c.md]`.
- `ipci.c` (223 lines) — `CreateSharedMemoryAndSemaphores`,
  `AttachSharedMemoryStructs`, and crucially `RegisterBuiltinShmemCallbacks`
  which is the subsystemlist.h driver. `ipci.c:1-30, 167-191`.
  `[via knowledge/files/src/backend/storage/ipc/ipci.c.md]`.
- `ipc.c` (446 lines) — **not** about IPC any more; this is the exit-time
  cleanup machinery (`proc_exit`, `shmem_exit`, the three callback
  registries `on_proc_exit`/`on_shmem_exit`/`before_shmem_exit`). Top
  comment at `ipc.c:6-9`. `[via knowledge/files/src/backend/storage/ipc/ipc.c.md]`.

### procarray / cross-backend signals

- `procarray.c` (5299 lines) — running-xid enumeration; `GetSnapshotData`
  with the `xactCompletionCount` fast-path; group-commit xid clear;
  `KnownAssignedXids` on hot standby. `procarray.c:1-30, 2113-2435`.
  `[via knowledge/files/src/backend/storage/ipc/procarray.c.md]`.
- `procsignal.c` (809 lines) — `SendProcSignal`,
  `EmitProcSignalBarrier`/`ProcessProcSignalBarrier`, query-cancel key
  matching, SIGUSR1 plumbing. `procsignal.c:1-30`.
  `[via knowledge/files/src/backend/storage/ipc/procsignal.c.md]`.
- `signalfuncs.c` (317 lines) — SQL-callable thin wrappers
  (`pg_cancel_backend`, `pg_terminate_backend`, `pg_reload_conf`,
  `pg_rotate_logfile`) using raw `kill(2)` plus the privilege matrix in
  `pg_signal_backend`. `[via knowledge/files/src/backend/storage/ipc/signalfuncs.c.md]`.
- `pmsignal.c` (431 lines) — children→postmaster signaling
  (`PMSignalFlags`), per-child slot state machine
  (`UNUSED→ASSIGNED→ACTIVE→…`), `PostmasterIsAlive` dead-man-switch.
  `pmsignal.c:14-65`. `[via knowledge/files/src/backend/storage/ipc/pmsignal.c.md]`.

### sinval

- `sinval.c` (202 lines) — façade: `SendSharedInvalidMessages`,
  `ReceiveSharedInvalidMessages` (with the recursion-safe static buffer),
  `HandleCatchupInterrupt`/`ProcessCatchupInterrupt`, daisy-chain wake of
  the next furthest-behind backend. `sinval.c:27-32, 126-133`.
  `[via knowledge/files/src/backend/storage/ipc/sinval.c.md]`.
- `sinvaladt.c` (714 lines) — actual queue: `SISeg`, `ProcState`,
  `SIInsertDataEntries`, `SIGetDataEntries`, `SICleanupQueue`, the
  `msgnumLock` spinlock-as-memory-barrier idiom, the SHARED-mode reader
  pattern. `sinvaladt.c:30-50, 91-102, 459-465`.
  `[via knowledge/files/src/backend/storage/ipc/sinvaladt.c.md]`.
- `standby.c` (1528 lines) — hot-standby AccessExclusiveLock replay
  (using a dummy PGPROC), `RunningXacts` ingestion, recovery-conflict
  resolution. `standby.c:3-9, 45-53`. `[via knowledge/files/src/backend/storage/ipc/standby.c.md]`.

### latch / waiteventset / barrier

- `latch.c` (389 lines) — `InitLatch`/`OwnLatch`/`DisownLatch`, the
  `SetLatch`/`ResetLatch` memory-barrier dance, the singleton
  `LatchWaitSet`. `latch.c:3-9, 289-330, 374-388`.
  `[via knowledge/files/src/backend/storage/ipc/latch.c.md]`.
- `waiteventset.c` (2039 lines) — `WaitEventSet` impl over epoll / kqueue
  / poll(+self-pipe) / Win32; SIGURG-via-signalfd on Linux;
  `WL_POSTMASTER_DEATH` via the postmaster self-pipe. `waiteventset.c:20-33,
  88-100`. `[via knowledge/files/src/backend/storage/ipc/waiteventset.c.md]`.
- `barrier.c` (333 lines) — process-barrier synchronization primitive
  (static + dynamic-Phaser-like). **Not** memory barriers; those live in
  `port/atomics.h`. `barrier.c:9-78`.
  `[via knowledge/files/src/backend/storage/ipc/barrier.c.md]`.

### DSM and friends

- `dsm.c` (1311 lines) — convenience layer: lifecycle (`dsm_create`,
  `dsm_attach`, `dsm_detach`), `dsm_segment` resowner integration, control
  segment management, **handle = `pg_prng_uint32 << 1` (even-only); odd =
  main-region slot**. `dsm.c:6-16, 216-228, 1270-1294`.
  `[via knowledge/files/src/backend/storage/ipc/dsm.c.md]`.
- `dsm_impl.c` (1054 lines) — OS backends: POSIX `shm_open`+`mmap`, SysV
  `shmget`, Windows `CreateFileMapping`, file-backed `mmap` in
  `pg_dynshmem/`. Dispatch through `dsm_impl_op`.
  `[via knowledge/files/src/backend/storage/ipc/dsm_impl.c.md]`.
- `dsm_registry.c` (492 lines) — named DSM segments (a `dshash` table
  inside a DSA) so extensions can lazily allocate shared state without
  going through `shared_preload_libraries`.
  `[via knowledge/files/src/backend/storage/ipc/dsm_registry.c.md]`.
- `shm_mq.c` (1330 lines) — single-reader, single-writer shared-memory
  ring buffer. Lock-free cursors `mq_bytes_read`/`mq_bytes_written` +
  memory barriers; PGPROC latches for blocking. Primary user: parallel
  query tuple queues + error queues. `shm_mq.c:5-9, 31-71`.
  `[via knowledge/files/src/backend/storage/ipc/shm_mq.c.md]`.
- `shm_toc.c` (279 lines) — table-of-contents inside a (typically DSM)
  segment; lets workers look up named subregions by `uint64 key`. Used by
  every parallel query context.
  `[via knowledge/files/src/backend/storage/ipc/shm_toc.c.md]`.

## 4. Key data structures

- **`PGShmemHeader` + `ShmemAllocatorData`** (`shmem.c:224-272`) — the
  first thing in the main shmem segment: bump pointer (`free_offset`,
  `slock_t shmem_lock`), `ShmemIndex` HTAB pointer, plus a separate
  `LWLock index_lock` (`ShmemIndexLock`). Allocator is one-way; cannot
  free `[from-comment]` `shmem.c:43-46`.
- **`ShmemCallbacks`** (`shmem_internal.h` / referenced by `shmem.c:872-892`)
  — `{ request_fn, init_fn, attach_fn, flags }`; one `static const` per
  subsystem, registered via the X-macro expansion of `subsystemlist.h`.
  `[verified-by-code]`.
- **`ProcArrayStruct`** (`procarray.c:76-105`) — dense `pgprocnos[]` of
  active PGPROC indexes plus parallel arrays in `ProcGlobal` (`xids[]`,
  `subxidStates[]`, `statusFlags[]`); each PGPROC carries `pgxactoff`
  giving its current position. Ordering invariant: dense, can shift on
  `ProcArrayRemove`. `[from-comment]` `procarray.c:608-627` (the
  "Keep the PGPROC array sorted" `memmove` shift-down + the
  "Adjust pgxactoff of following procs" readjust loop).
- **`PGPROC`** — defined in `storage/proc.h`. Carries `xid`, `xmin`,
  subxid cache, `procLatch`, `delayChkptFlags`; pointed to by both
  ProcArray and ProcSignal slots. The PGPROC is the lock-holder identity
  used by `lmgr`. `[inferred]`.
- **`ProcSignalSlot`** (`procsignal.c`, top of file) — per-process record
  of `pss_pid`, `pss_signalFlags[NUM_PROCSIGNALS]`, `pss_mutex` spinlock,
  cancel key, plus the `pss_barrierGeneration` / `pss_barrierCheckMask`
  pair used by `ProcSignalBarrier`. Index = ProcNumber + auxiliary slot
  range. `[verified-by-code]`.
- **`SISeg`** (`sinvaladt.c:165-197`) — the sinval shared header:
  `minMsgNum` (lower bound, lazy), `maxMsgNum` (writer cursor),
  `nextThreshold`, `msgnumLock` spinlock, `buffer[4096]`, plus a dense
  `pgprocnos[]` listing active sinval clients. Lock rules in §6.
- **`ProcState`** (`sinvaladt.c:137-163`) — per-backend sinval slot:
  `nextMsgNum` (reader cursor), `resetState` (true ⇒ must drop all
  caches), `signaled` (catchup interrupt already in flight),
  `hasMessages` (fast-path flag), `sendOnly` (startup process), `nextLXID`
  (preserved across slot reuse).
- **`Latch`** (`latch.h`) — `{ sig_atomic_t is_set; sig_atomic_t
  maybe_sleeping; bool is_shared; pid_t owner_pid; HANDLE event /*Win32*/ }`.
  Per-process `MyLatch`; per-PGPROC `procLatch` for cross-backend wakeups.
- **`WaitEventSet`** (`waiteventset.h`) — opaque; carries the OS fd
  (epoll/kqueue), the slot array, and on Linux a signalfd for SIGURG.
- **`dsm_control_header` + `dsm_control_item`** (`dsm.c:80-97`;
  `dsm_control_item` 80-88, `dsm_control_header` 91-97) — refcount
  table for live DSM segments; lives in the postmaster-created control
  segment whose handle is stashed in `PGShmemHeader->dsm_control`.
  `maxitems = PG_DYNSHMEM_FIXED_SLOTS (64) + PG_DYNSHMEM_SLOTS_PER_BACKEND
  (5) * MaxBackends` (`dsm.c:53-54`, computed `:205-206`).
- **`dsm_segment`** (`dsm.c:67-77`) — per-backend descriptor; bound to a
  `ResourceOwner` so segments auto-detach on transaction abort. `on_detach`
  slist holds cleanup callbacks (used by `shm_mq` detach, DSA detach…).
- **`shm_mq`** (`shm_mq.c:73-83`) — ring with lock-free atomic cursors;
  `mq_receiver`/`mq_sender` PGPROC pointers; `mq_detached` flag flips
  monotonically.
- **`shm_toc`** (`shm_toc.c:26-34`) — magic + spinlock + entry array
  growing from start, allocations from the end.
- **`ConditionVariable`** (`storage/condition_variable.h`, used here in
  `procsignal.c` `pss_barrierCV`, `barrier.c`, and the per-buffer I/O CVs
  in the buffer manager) — proclist + sleep on procLatch.

## 5. Control flow — common paths

### 5.1 Server startup: building shared memory

1. Postmaster runs `RegisterBuiltinShmemCallbacks()` (`ipci.c:167-191`),
   which `#include`s `subsystemlist.h` with `PG_SHMEM_SUBSYSTEM(x) →
   RegisterShmemCallbacks(&x)` once. Order matters: LWLocks first (so
   later init_fn callbacks can take LWLocks), DSM second, etc.
   `[from-comment]` `subsystemlist.h:18-26` `[via …/ipci.c.md]`.
2. `CalculateShmemSize()` sums `100000` bytes slack +
   `ShmemGetRequestedSize()` (sum of all `ShmemRequestStruct`s collected
   from each subsystem's `request_fn`) + `RequestAddinShmemSpace`, then
   rounds up to 8 KiB. `ipci.c:56-80`.
3. `PGSharedMemoryCreate(size, &shim)` — port-specific
   shmget/mmap/CreateFileMapping.
4. `InitShmemAllocator(seghdr)` builds the bump allocator + `ShmemIndex`
   hash inside the freshly-created segment (`shmem.c:636-736`).
5. `ShmemInitRequested()` walks `pending_shmem_requests`, calls
   `ShmemAllocRaw` for each area, sets the caller's pointer variable,
   then runs every `init_fn` in registration order. `shmem.c:423-453`.
6. `dsm_postmaster_startup(shim)` creates the DSM control segment (random
   even `dsm_handle = pg_prng_uint32() << 1`). `dsm.c:216-228`.
7. `shmem_startup_hook` fires for extensions.

### 5.2 `GetSnapshotData` — the lock-free read fast path

The hottest read in PG (`procarray.c:2113`).

1. **Take `ProcArrayLock` SHARED.** `procarray.c:2178`.
2. **`GetSnapshotDataReuse`** (`procarray.c:2033-2078`): if
   `TransamVariables->xactCompletionCount` has not changed since this
   snapshot's `snapXactCompletionCount`, the running set is identical
   — re-install `MyProc->xmin` and return the cached snapshot. **This is
   the secret of PG's read scaling**: back-to-back snapshot reads on an
   idle system are O(1). The counter is bumped *under exclusive
   ProcArrayLock* in `ProcArrayEndTransactionInternal` at
   `procarray.c:768`, so two SHARED readers cannot miss a relevant
   commit. `[from-comment]` `procarray.c:2049-2058` `[via …/procarray.c.md]`.
3. Else: `xmax = TransamVariables->latestCompletedXid + 1`; walk
   `pgprocnos[0..numProcs)`, doing `xid =
   UINT32_ACCESS_ONCE(other_xids[pgxactoff])` per slot — single volatile
   read, the writer side (`GetNewTransactionId`) publishes with a
   `pg_write_barrier` `[from-comment]` `procarray.c:2223, 2302` (the
   write-side pairing in `transam/varsup.c` is referenced but not
   re-verified here, see §9).
4. Skip own xid, `xid ≥ xmax`, `PROC_IN_LOGICAL_DECODING |
   PROC_IN_VACUUM` backends; collect into `xip[]`. Subxid cache is
   `memcpy`'d when not overflowed.
5. Read `replication_slot_xmin` / `_catalog_xmin` while still under
   lock. Install `MyProc->xmin` (safe under SHARED because each backend
   only writes its own slot). `procarray.c:2357-2361`.
6. Release `ProcArrayLock` — release acts as a full memory barrier
   publishing `MyProc->xmin`. `procarray.c:2363`.
7. Update `GlobalVis*Rels.definitely_needed` / `maybe_needed` *unlocked*
   from values gathered under the lock.

### 5.3 Cache invalidation broadcast (`SIInsertDataEntries` →
`SIGetDataEntries` → catchup)

Writer (`sinvaladt.c:371`):
1. Batch in groups of ≤ `WRITE_QUANTUM = 64`. Take `SInvalWriteLock` EX.
2. Cleanup-if-needed (`SICleanupQueue`).
3. Write into `buffer[max % MAXNUMMESSAGES]`.
4. Advance `maxMsgNum` under the `msgnumLock` spinlock — spinlock here
   is **for memory-barrier semantics**, not atomicity (`sinvaladt.c:96-102`).
5. Set `hasMessages = true` on every active backend, unlocked — the
   subsequent `LWLockRelease(SInvalWriteLock)` provides the publishing
   barrier.

Reader (`sinvaladt.c:474`):
1. Unlocked check `if (!stateP->hasMessages) return 0`.
2. Take `SInvalReadLock` **SHARED** — but **modify our own `ProcState`**
   under it. This is the non-standard interpretation; see §6.
3. Reset `hasMessages = false` *before* reading `maxMsgNum` (otherwise
   a message arriving between the two ops would be lost; comment
   `sinvaladt.c:501-509`).
4. Drain into caller's buffer, advance `nextMsgNum`. If we caught up,
   clear our `signaled` flag.

Cleanup + catchup (`SICleanupQueue` at `sinvaladt.c:578`): takes BOTH
LWLocks EX, computes `minMsgNum`, marks too-far-behind backends with
`resetState = true`, picks the furthest-behind *unsignaled* backend,
**drops the LWLocks**, then `SendProcSignal(…, PROCSIG_CATCHUP_INTERRUPT,
…)` outside the lock. `sinvaladt.c:662-666`.

The catchup signal triggers `HandleCatchupInterrupt` →
`ProcessCatchupInterrupt` → `AcceptInvalidationMessages` later (outside
signal context); the receiver, after fully catching up, calls
`SICleanupQueue(false, 0)` to **daisy-chain** the signal to the *next*
furthest-behind backend, avoiding thundering-herd wakes
(`sinval.c:126-133`).

### 5.4 `WaitLatch` / `SetLatch` — the memory-barrier dance

Waiter (`latch.c:172` → `waiteventset.c::WaitEventSetWait`): before the
OS sleep, `WaitEventSetWaitBlock` sets `latch->maybe_sleeping = true` and
issues a memory barrier; on Linux, the wait is `epoll_wait` on a set
that includes a signalfd registered for `SIGURG` and the postmaster
`pm_alive` self-pipe `[from-comment]` `waiteventset.c:30-33` `[via …/waiteventset.c.md]`.

`SetLatch(latch)` (`latch.c:289-330`):
```c
pg_memory_barrier();
if (latch->is_set) return;
latch->is_set = true;
pg_memory_barrier();
if (!latch->maybe_sleeping) return;
/* now actually wake the owner */
WakeupOtherProc(owner_pid);   /* kill(owner_pid, SIGURG) */
```

The signal is **SIGURG** — `SIGUSR1` is reserved for procsignal-multiplexed
reasons. On Linux, SIGURG is kept blocked and consumed via signalfd, so
the wait returns through epoll, not via a signal handler `[from-comment]`
`waiteventset.c:30-33`. On BSD/macOS it's `EVFILT_SIGNAL` on SIGURG; on
the poll() fallback path it's the self-pipe trick (`waiteventset.c:20-29`).

`ResetLatch` (`latch.c:374-388`): asserts `owner_pid == MyProcPid` and
`maybe_sleeping == false`, sets `is_set = false`, then memory barrier.
Canonical idiom: ResetLatch *first*, then check the work-pending flags,
then WaitLatch — *reset-before-check* is wrong because work set between
check and reset would be missed.

### 5.5 DSM segment create + attach

Create (`dsm.c:524`):
1. If small enough, allocate from `dsm_main_space` — the slab carved out
   of main shmem; handle has **low bit set** to mean "main-region slot".
   `dsm.c:1270-1294`.
2. Else generate a random handle: `pg_prng_uint32() << 1` — even-only,
   leaving odd numbers reserved for the main-region path. `dsm.c:216-228`.
   Call `dsm_impl_op(DSM_OP_CREATE, handle, …)`.
3. Insert refcount=2 entry into the control segment (one for creator,
   one for the "exists" mark).
4. Register `dsm_resource` against `CurrentResourceOwner` so abort
   auto-detaches.

Attach (`dsm.c:673`): find slot by handle, bump refcount,
`dsm_impl_op(DSM_OP_ATTACH, …)`, register with resowner.

Backend exit (`dsm_backend_shutdown` at `dsm.c:765`): hand-called from
`ipc.c::shmem_exit` (not registered as `on_shmem_exit`) so its
progressive-removal loop survives partial errors `[from-comment]`
`ipc.c:254-269`.

### 5.6 `ProcSignalBarrier` — system-wide state-change propagation

Emitter (`procsignal.c:368-413`):
1. For every slot, `pg_atomic_fetch_or_u32(pss_barrierCheckMask, 1<<type)`.
2. `pg_atomic_add_fetch_u64(psh_barrierGeneration, 1)` — mint a new
   generation, returned to caller.
3. For every active slot, set `pss_signalFlags[PROCSIG_BARRIER]` and
   `kill(pid, SIGUSR1)`.

Absorber (each backend's `ProcessProcSignalBarrier`, ~`procsignal.c:425-470`):
1. Read shared generation, compare with `pss_barrierGeneration`.
2. Swap `pss_barrierCheckMask → 0`; process each set bit by calling the
   matching `ProcessBarrierFoo` callback.
3. Bump our `pss_barrierGeneration` to the shared value.
4. `ConditionVariableBroadcast(&pss_barrierCV)`.

Waiter (`WaitForProcSignalBarrier`) only reads `pss_barrierGeneration`,
not the mask — and because the mask is cleared *before* absorbing while
the generation is updated *after*, generation==target ⇒ all bit-handlers
have run. `procsignal.c:451-455`.

### 5.7 `proc_exit` cleanup chain

`ipc.c::proc_exit(code)` → `proc_exit_prepare`:
1. Set `proc_exit_inprogress`; clear pending interrupts.
2. `shmem_exit(code)`: `LWLockReleaseAll`, run `before_shmem_exit` LIFO,
   call `dsm_backend_shutdown()` directly, run `on_shmem_exit` LIFO.
3. Run `on_proc_exit` LIFO.
4. `exit(code)`.

Each callback is decremented from its list *before* invocation so a
re-entering `ereport(ERROR)` cannot infinite-loop. `ipc.c:204-211`.

## 6. Locking and invariants

The locks specific to this directory, ordered roughly by visibility.

1. **`ProcArrayLock`** (LWLock) — protects `ProcArray`, `ProcGlobal->xids[]`,
   `subxidStates[]`, `statusFlags[]`, and `KnownAssignedXids`. Acquired
   SHARED by readers (`GetSnapshotData`, `TransactionIdIsInProgress`),
   EX by writers (`ProcArrayAdd`/`Remove`, `ProcArrayEndTransactionInternal`,
   `xactCompletionCount++`). Setting `MyProc->xmin` under SHARED is safe
   *because each backend only writes its own slot* `[from-comment]`
   `procarray.c:2175-2176`.
2. **`XidGenLock`** — protects `nextXid`. Per `access/transam/README`,
   ordering is **`XidGenLock` first, then `ProcArrayLock`** when both
   needed. Stated in `transam/README` only; **not asserted in
   `procarray.c`** `[unverified-here]` (carried forward from
   `…/procarray.c.md` open question 2).
3. **`SInvalReadLock`** (LWLock) — non-standard. SHARED is taken by
   readers that **modify their own `ProcState` slot** (`hasMessages`,
   `nextMsgNum`, `signaled`). The shared mode expresses "each reader
   touches only its own slot"; it is NOT the usual "read-only"
   interpretation. EX is taken by `SICleanupQueue` to do array-wide
   updates. Comment is explicit: *"Note that this is not exactly the
   normal (read-only) interpretation of a shared lock! Look closely at
   the interactions before allowing SInvalReadLock to be grabbed in
   shared mode for any other reason!"* `[from-comment]`
   `sinvaladt.c:459-465` `[via …/sinvaladt.c.md]`.
4. **`SInvalWriteLock`** (LWLock) — EX only; serializes
   `SIInsertDataEntries`, `SharedInvalBackendInit`,
   `CleanupInvalidationState`.
5. **`msgnumLock`** (spinlock, inside `SISeg`) — guards `maxMsgNum` for
   readers that don't hold `SInvalWriteLock`. **Purpose is the memory
   barrier**, not atomicity: writes to `buffer[]` must be visible before
   the new `maxMsgNum`. Rule: read `maxMsgNum` ⇒ hold the spinlock
   *unless* you hold `SInvalWriteLock`; write `maxMsgNum` ⇒ hold *both*
   `[from-comment]` `sinvaladt.c:91-102`.
6. **`ShmemAllocator->shmem_lock`** (spinlock in `shmem.c`) — protects
   the bump-pointer `free_offset`. Held for one allocation.
7. **`ShmemIndexLock`** (LWLock embedded in `ShmemAllocatorData`) —
   protects the `ShmemIndex` HTAB. SHARED for lookups, EX for
   `InitShmemIndexEntry`.
8. **`ProcSignalSlot::pss_mutex`** (spinlock) — serializes
   `SendProcSignal` writing `pss_signalFlags` against the slot's owner
   absorbing them or against another sender; rechecks `pss_pid == pid`
   under the lock to defeat TOCTOU with slot reuse `[verified-by-code]`
   `procsignal.c:295-313`.
9. **DSM control segment lock** — atomic refcount inc/dec on
   `dsm_control_item.refcnt` happens under an internal lock owned by the
   control segment; specific lock not chased here `[unverified-here]`
   (carry from `…/dsm.c.md` open question 2).
10. **`shm_mq::mq_mutex`** (spinlock) — only protects setting
    `mq_sender`/`mq_receiver`; once set those are immutable and read
    lock-free. Cursors (`mq_bytes_read`/`mq_bytes_written`) are lock-free
    atomics with explicit `pg_read_barrier`/`pg_write_barrier` discipline.
11. **`shm_toc::toc_mutex`** (spinlock) — serializes `shm_toc_allocate` +
    `shm_toc_insert`. `shm_toc_lookup` is unsynchronized linear scan
    (entries grow monotonically and are written under the spinlock).

### Orderings established by code or comment

- **`subsystemlist.h` ordering** — LWLocks first, then DSM, then
  XLOG/CLOG/buffers, then lock-manager, then proc/sinval, … `[from-comment]`
  `subsystemlist.h:18-26`. No `init_fn` may depend on a subsystem
  appearing later in the list.
- **`xactCompletionCount` increment under `ProcArrayLock` EX, read under
  SHARED** — `procarray.c:768` (increment), `procarray.c:2049-2078`
  (read in `GetSnapshotDataReuse`). The release of the SHARED lock acts
  as a publishing barrier for `MyProc->xmin`.
- **`pg_read_barrier()` at `procarray.c:2302`** pairs with a
  `pg_write_barrier()` in `GetNewTransactionId` (`access/transam/varsup.c`)
  — comment cross-references `transam/README`; write-side
  not re-verified `[unverified-here]`.
- **sinval writer publish sequence**: `buffer[i] = msg` →
  spinlock-protected `maxMsgNum++` (memory barrier) → `hasMessages = true`
  per backend (unlocked) → `LWLockRelease(SInvalWriteLock)` (memory
  barrier). `[from-comment]` `sinvaladt.c:419-433`.
- **Latch wake sequence**: `SetLatch` does `barrier; if is_set return;
  is_set=true; barrier; if !maybe_sleeping return; kill(SIGURG)`. Pairs
  with `WaitEventSetWaitBlock`'s `maybe_sleeping=true; barrier; check
  is_set` and `ResetLatch`'s `is_set=false; barrier`. `latch.c:298-303,
  383-388`.
- **`SICleanupQueue` drops both LWLocks before `SendProcSignal`** — to
  avoid holding a system-wide lock across an arbitrarily slow `kill(2)`
  `[from-comment]` `sinvaladt.c:662-666`.
- **`EmitProcSignalBarrier` orders the OR-into-mask, then increment
  generation, then SIGUSR1.** Absorber clears mask, then runs handlers,
  then bumps own generation. Waiters check only generation
  `procsignal.c:451-455`.
- **DSM handles are even**; the low bit is reserved for "main-region
  slot index" path; backend code must use `is_main_region_dsm_handle(h)`
  rather than testing the low bit directly. `[from-comment]`
  `dsm.c:220, 1270` `[via …/dsm.c.md]`.
- **`proc_exit_prepare` releases all LWLocks before running callbacks**
  so callbacks can safely re-acquire any lock. `ipc.c:233-238`.

### Items not pinned down here (carried forward from per-file docs)

- Heavyweight partition vs `ProcArrayLock` vs `XidGenLock` ordering is
  not asserted in `procarray.c`; only stated in `transam/README`. See
  §9. `[unverified-here]`.
- `MarkPostmasterChildActive` timing vs shmem attach in non-EXEC_BACKEND
  mode: a crash window between attach and Mark would still look UNUSED
  to postmaster `[unverified]` (carried from `…/pmsignal.c.md`).
- Whether `LWLockRelease` contains a `pg_write_barrier` (relied on by
  sinval writer at `sinvaladt.c:419-433`); strongly believed but not
  verified in `lwlock.c` here. `[unverified-here]`.

## 7. Interactions with other subsystems

- **`postmaster`** — `PostmasterMain` calls
  `CreateSharedMemoryAndSemaphores` exactly once, before forking.
  Children either inherit the segment via fork (Unix) or
  `AttachSharedMemoryStructs` it in EXEC_BACKEND mode. Per-child slots
  live in `pmsignal.c::PMChildFlags[]`; postmaster reads
  `PMSignalFlags[]` each iteration of `ServerLoop`.
- **`storage/lmgr`** — every PGPROC is a lock-holder identity; `procarray.c`
  publishes the xid and `lmgr` uses it for deadlock detection. Hot-standby
  `standby.c` injects AccessExclusiveLocks into the lock table on
  behalf of *primary* xacts using a dummy PGPROC `[from-comment]`
  `standby.c:45-53`.
- **`storage/buffer`** — `BufferDesc[]` lives in main shmem (registered
  via `BufferManagerShmemCallbacks` in the X-macro); the cleanup-lock
  waiter mechanism uses PGPROC procnumbers and `SetLatch`.
- **`access/transam`** — `varsup.c::GetNewTransactionId` is the writer
  side of the snapshot read protocol; commit/abort goes through
  `ProcArrayEndTransaction` which bumps `xactCompletionCount`. Two-phase
  commit installs dummy PGPROCs into ProcArray with `pid == 0`
  `[from-comment]` `procarray.c:17-20`.
- **`utils/cache/inval`** — defines `SharedInvalidationMessage` and the
  per-message dispatch (`LocalExecuteInvalidationMessage`); sinval is just
  the transport.
- **`access/parallel` + executor** — parallel query carves out one DSM
  segment per parallel context, lays out a `shm_toc` inside, and uses
  one `shm_mq` per worker for tuple streaming plus a separate error
  queue. Workers `dsm_attach` to the leader's segment.
- **`replication`** — `replication_slot_xmin` is read inside
  `GetSnapshotData` under `ProcArrayLock` `procarray.c:2357-2358`.
  Walsender uses `procsignal` (`PROCSIG_WALSND_INIT_STOPPING`).
  `walreceiver` + `standby.c` feed `KnownAssignedXids`.
- **`tcop/postgres.c`** — `procsignal_sigusr1_handler` lives there; it
  walks `pss_signalFlags` and dispatches to `Handle*Interrupt` helpers,
  each of which sets a flag + `SetLatch(MyLatch)`. `ProcessClientReadInterrupt`
  invokes `ProcessCatchupInterrupt` when idle.
- **`utils/resowner`** — `dsm_segment`, `shm_mq_handle`, `WaitEventSet`
  are all resowner-aware so abort cleanup is automatic.

## 8. Tests

- **Regress** (`source/src/test/regress/sql/`): no dedicated ipc test
  file. Cache-invalidation correctness is exercised indirectly by every
  DDL test (DROP/ALTER/CREATE force sinval traffic).
- **Isolation** (`source/src/test/isolation/specs/`): several specs
  exercise procsignal barrier (e.g. checksum toggle) and standby conflict
  paths; not enumerated here. `[unverified]` which exact specs cover
  `ProcSignalBarrier` end-to-end.
- **TAP / modules** — `src/test/modules/test_shm_mq/` is the canonical
  driver for `shm_mq`; spawns background workers that exchange messages
  through DSM-hosted queues. `src/test/modules/test_dsm_registry/`
  exercises `dsm_registry`. `src/test/modules/test_aio/` indirectly hits
  `WaitEventSet` and latch paths via `pgaio_*`.

## 9. Open questions / unverified claims

Carried forward from per-file docs and consolidated here.

1. **Write-side barrier pairing in `GetNewTransactionId`** — the
   `pg_read_barrier()` at `procarray.c:2302` is documented to pair with a
   write barrier in `access/transam/varsup.c`. Not re-verified here.
   `[unverified-here]` (`…/procarray.c.md` Q1).
2. **Heavyweight-partition vs `ProcArrayLock` vs `XidGenLock` ordering**
   — `transam/README` states `XidGenLock` first, then `ProcArrayLock`.
   No assertion in `procarray.c`. Cross-tranche order between heavyweight
   lock partitions and `ProcArrayLock` was not investigated.
   `[unverified]` (`…/procarray.c.md` Q2).
3. **`MarkPostmasterChildActive` timing vs shmem attach** — in
   non-EXEC_BACKEND mode the child main_fn runs after attach, but the
   precise position of `MarkPostmasterChildActive` was not pinned down.
   A crash between attach and Mark would still look UNUSED to postmaster
   and no crash-restart would happen. `[unverified]` (`…/pmsignal.c.md`).
4. **`LWLockRelease` write barrier semantics** — sinval's writer ordering
   at `sinvaladt.c:419-433` relies on `LWLockRelease(SInvalWriteLock)`
   acting as a publishing barrier for the unlocked `hasMessages = true`
   writes. Believed true but not verified in `lwlock.c`.
   `[unverified-here]` (`…/sinvaladt.c.md` Q2).
5. **Reusing `SInvalReadLock` for unrelated purposes is unsafe** — the
   shared-mode mutation pattern is invisible from outside; any extension
   that re-uses this lock under the assumption "shared = read-only" would
   silently violate isolation. The comment at `sinvaladt.c:459-465` warns
   exactly this. `[from-comment]`.
6. **DSM control segment refcount race** — comment at `dsm.c:80-88` says
   `refcnt 1 = moribund, 0 = gone`. The atomic inc/dec is under the
   control segment's internal lock; that lock wasn't chased here.
   `[unverified-here]` (`…/dsm.c.md` Q2).
7. **POSIX/SysV DSM leaks across OS reboot** — `dsm_cleanup_using_control_segment`
   needs the old control segment to be attachable; if the OS rebooted
   in between, leftover OS segments would only be reaped by the OS
   itself. `[verified-by-code]` `dsm.c:260-268`.
8. **epoll edge-triggered vs level-triggered** in `waiteventset.c`:
   default appears to be level-triggered. `[unverified]`.
9. **signalfd inheritance across EXEC_BACKEND re-exec**: not chased.
   `[unverified-here]` (`…/waiteventset.c.md`).
10. **`shm_mq` zero-copy receive pointer stability across re-entry**
    when the message wraps around the ring end. `[unverified]`
    (`…/shm_mq.c.md`).
11. **Subsystemlist ordering completeness** — the old explicit chain in
    `CreateSharedMemoryAndSemaphores` had per-call dependency comments;
    after the X-macro refactor those live only in
    `subsystemlist.h:18-26`. Whether the new mechanism captures every
    hidden ordering would require diffing against the pre-refactor
    commit. `[unverified]` (`…/ipci.c.md`).

## 10. Glossary

- **ProcArray** — packed array of running-transaction PGPROC indexes
  (`pgprocnos[]`) plus parallel `xids[] / subxidStates[] / statusFlags[]`
  in `ProcGlobal`. The kernel of MVCC. `[from-comment]` `procarray.c:9-15`.
- **`xactCompletionCount`** — uint64 in `TransamVariables`, bumped under
  `ProcArrayLock` EX on every xid-having commit/abort. Watched under
  SHARED by `GetSnapshotDataReuse` to skip a full ProcArray scan.
  `procarray.c:768, 2049-2058`.
- **`KnownAssignedXids`** — circular buffer of xids the primary
  advertised over WAL; used on hot standby in lieu of per-PGPROC xids.
  `procarray.c:22-30`.
- **sinval** — *shared invalidation*: a cache-coherency broadcast bus;
  every backend reads and applies messages to drop stale
  relcache/syscache entries. `sinval.c`.
- **SISeg** — the sinval shared header + ring buffer (`MAXNUMMESSAGES =
  4096`). `sinvaladt.c:165-197`.
- **`PROCSIG_CATCHUP_INTERRUPT`** — procsignal reason used by
  `SICleanupQueue` to nudge the furthest-behind idle backend before the
  ring overflows. `sinval.c:27-32`.
- **Latch** — one-bit reliable wakeup primitive (`is_set` +
  `maybe_sleeping`), per-process `MyLatch` and per-PGPROC `procLatch`.
  Wake signal is SIGURG. `latch.c:3-9`.
- **WaitEventSet** — `epoll`/`kqueue`/`poll`/Win32 multiplexer behind
  `WaitLatch`/`WaitEventSetWait`. `waiteventset.c:88-100`.
- **SIGURG** — the latch wake signal; chosen specifically because it's
  not otherwise used by PG and doesn't go through
  `procsignal_sigusr1_handler`. On Linux it's consumed via signalfd in
  the epoll set. `waiteventset.c:30-33`.
- **DSM** — *dynamic shared memory*; runtime-allocatable shared segments,
  refcounted via the control segment. Handles are even uint32s; odd =
  main-region slot. `dsm.c:6-16, 220, 1270`.
- **DSM control segment** — small DSM segment created at postmaster
  startup, holds `dsm_control_header` (refcount table for all live
  segments). Its own handle is stashed in `PGShmemHeader->dsm_control`.
- **`dsm_main_space`** — slab carved out of *main* shmem for allocating
  small DSM segments cheaply, avoiding `shm_open`. Slot indexes are
  flagged by the low bit of the dsm_handle.
- **procsignal slot** — `ProcSignalSlot` per ProcNumber; carries the
  multiplexed `pss_signalFlags[NUM_PROCSIGNALS]` and the
  `pss_barrierGeneration` / `pss_barrierCheckMask` pair.
- **ProcSignalBarrier** — system-wide state-propagation handshake: emitter
  bumps a global generation and signals every backend; each absorbs and
  bumps its own generation; waiters spin on generation equality.
  `procsignal.c:368-455`.
- **`shm_mq`** — single-reader/single-writer ring buffer with lock-free
  cursors; one per parallel worker. `shm_mq.c:31-71`.
- **`shm_toc`** — table of contents for sub-regions within a DSM segment;
  workers look up named pieces by `uint64 key`. `shm_toc.c:29-37`.
- **`subsystemlist.h`** — the X-macro list driving builtin shmem-callback
  registration; replaces the historical explicit `XXXShmemInit()` chain
  in `ipci.c`. `subsystemlist.h:18-26`.
- **PMSignal slot** — children → postmaster signaling +
  `UNUSED→ASSIGNED→ACTIVE→…` per-child state machine; how postmaster
  detects "child died after attaching to shmem ⇒ crash restart".
  `pmsignal.c:14-65`.

## Files owned
<!-- files-owned:auto -->

*Files under this subsystem's owned paths (by slug derivation + include-header filters). Auto-refreshed by `scripts/populate-subsystem-files.py`.*

**31 files.**

| File |
|---|
| [`src/backend/storage/ipc/barrier.c`](../files/src/backend/storage/ipc/barrier.c.md) |
| [`src/backend/storage/ipc/dsm.c`](../files/src/backend/storage/ipc/dsm.c.md) |
| [`src/backend/storage/ipc/dsm_impl.c`](../files/src/backend/storage/ipc/dsm_impl.c.md) |
| [`src/backend/storage/ipc/dsm_registry.c`](../files/src/backend/storage/ipc/dsm_registry.c.md) |
| [`src/backend/storage/ipc/ipc.c`](../files/src/backend/storage/ipc/ipc.c.md) |
| [`src/backend/storage/ipc/ipci.c`](../files/src/backend/storage/ipc/ipci.c.md) |
| [`src/backend/storage/ipc/latch.c`](../files/src/backend/storage/ipc/latch.c.md) |
| [`src/backend/storage/ipc/pmsignal.c`](../files/src/backend/storage/ipc/pmsignal.c.md) |
| [`src/backend/storage/ipc/procarray.c`](../files/src/backend/storage/ipc/procarray.c.md) |
| [`src/backend/storage/ipc/procsignal.c`](../files/src/backend/storage/ipc/procsignal.c.md) |
| [`src/backend/storage/ipc/shm_mq.c`](../files/src/backend/storage/ipc/shm_mq.c.md) |
| [`src/backend/storage/ipc/shm_toc.c`](../files/src/backend/storage/ipc/shm_toc.c.md) |
| [`src/backend/storage/ipc/shmem.c`](../files/src/backend/storage/ipc/shmem.c.md) |
| [`src/backend/storage/ipc/shmem_hash.c`](../files/src/backend/storage/ipc/shmem_hash.c.md) |
| [`src/backend/storage/ipc/signalfuncs.c`](../files/src/backend/storage/ipc/signalfuncs.c.md) |
| [`src/backend/storage/ipc/sinval.c`](../files/src/backend/storage/ipc/sinval.c.md) |
| [`src/backend/storage/ipc/sinvaladt.c`](../files/src/backend/storage/ipc/sinvaladt.c.md) |
| [`src/backend/storage/ipc/standby.c`](../files/src/backend/storage/ipc/standby.c.md) |
| [`src/backend/storage/ipc/waiteventset.c`](../files/src/backend/storage/ipc/waiteventset.c.md) |
| [`src/include/storage/ipc.h`](../files/src/include/storage/ipc.h.md) |
| [`src/include/storage/latch.h`](../files/src/include/storage/latch.h.md) |
| [`src/include/storage/pg_shmem.h`](../files/src/include/storage/pg_shmem.h.md) |
| [`src/include/storage/pmsignal.h`](../files/src/include/storage/pmsignal.h.md) |
| [`src/include/storage/procarray.h`](../files/src/include/storage/procarray.h.md) |
| [`src/include/storage/procsignal.h`](../files/src/include/storage/procsignal.h.md) |
| [`src/include/storage/shm_mq.h`](../files/src/include/storage/shm_mq.h.md) |
| [`src/include/storage/shm_toc.h`](../files/src/include/storage/shm_toc.h.md) |
| [`src/include/storage/shmem.h`](../files/src/include/storage/shmem.h.md) |
| [`src/include/storage/shmem_internal.h`](../files/src/include/storage/shmem_internal.h.md) |
| [`src/include/storage/sinval.h`](../files/src/include/storage/sinval.h.md) |
| [`src/include/storage/sinvaladt.h`](../files/src/include/storage/sinvaladt.h.md) |

<!-- /files-owned:auto -->
