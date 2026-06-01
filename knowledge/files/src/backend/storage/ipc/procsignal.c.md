# `storage/ipc/procsignal.c`

- **Source:** `source/src/backend/storage/ipc/procsignal.c` (809 lines)
- **Header:** `source/src/include/storage/procsignal.h`
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## Purpose

**Multiplexed SIGUSR1 signaling between backends.** Allows any backend
to ask another backend to do one of N things (catchup interrupt,
recovery conflict, parallel-message, barrier, …) by setting a flag
in shared memory and raising SIGUSR1. Target's signal handler sees
SIGUSR1, walks the flag array, and dispatches.

Distinct from `pmsignal.c` (children → postmaster) and `latch.c`
(generic wakeup primitive). `procsignal` is **backend ↔ backend**.

## Shared state

`ProcSignal` (`ProcSignalHeader`) holds:
- `psh_barrierGeneration` — global atomic uint64; bumped by
  `EmitProcSignalBarrier`. The "highest barrier generation that
  exists".
- `psh_slot[]` — one `ProcSignalSlot` per `ProcNumber` + auxiliary
  slots (`NumProcSignalSlots = MaxBackends + NUM_AUXILIARY_PROCS`).

Each `ProcSignalSlot`:
- `pss_pid` — atomic uint32; 0 = unused.
- `pss_signalFlags[NUM_PROCSIGNALS]` — `volatile sig_atomic_t` flags,
  one per reason. The target sets these in its signal handler.
- `pss_mutex` — spinlock protecting the above.
- `pss_cancel_key`, `pss_cancel_key_len` — for cancel protocol
  (queries match on the key to authorize a SIGINT).
- `pss_barrierGeneration` (atomic uint64) — highest generation this
  process has *absorbed*. Starts at `UINT64_MAX` (means "I've absorbed
  everything") until process registers, then reset.
- `pss_barrierCheckMask` (atomic uint32) — which barrier types we
  still need to process.
- `pss_barrierCV` — condition variable for `WaitForProcSignalBarrier`.

## ProcSignalReason values (procsignal.h)

`PROCSIG_CATCHUP_INTERRUPT`, `PROCSIG_NOTIFY_INTERRUPT`,
`PROCSIG_PARALLEL_MESSAGE`, `PROCSIG_WALSND_INIT_STOPPING`,
`PROCSIG_BARRIER` (used internally), `PROCSIG_LOG_MEMORY_CONTEXT`,
`PROCSIG_PARALLEL_APPLY_MESSAGE`, `PROCSIG_LOG_BACKTRACE`, plus
several recovery-conflict reasons.

## SendProcSignal (`:295`)

1. If `procNumber != INVALID_PROC_NUMBER`, take that slot's
   spinlock, check `pss_pid == pid`, set `pss_signalFlags[reason]`,
   release spinlock, `kill(pid, SIGUSR1)`. Returns 0 / -1.
2. If procNumber unknown, **search the slot array back-to-front**
   (most aux processes live near the end). For each slot whose
   `pss_pid == pid` (unlocked quick check), repeat the locked path.
3. The PID match is rechecked under the spinlock to avoid TOCTOU.

## The barrier mechanism (`EmitProcSignalBarrier` `:368`)

Used for *global* state changes that need confirmation from every
backend (e.g. dropping a logical slot, changing checksum mode).

1. For every slot, `pg_atomic_fetch_or_u32(&slot->pss_barrierCheckMask,
   1<<type)`. This is a full barrier per atomic op.
2. `pg_atomic_add_fetch_u64(&ProcSignal->psh_barrierGeneration, 1)`
   to mint a new generation. Return value.
3. For every active slot, set `pss_signalFlags[PROCSIG_BARRIER]` and
   `kill(pid, SIGUSR1)`.

Backends absorb via `ProcessProcSignalBarrier`:
1. Read shared `psh_barrierGeneration`; compare with our
   `pss_barrierGeneration`. If equal, nothing to do.
2. Atomically swap `pss_barrierCheckMask → 0` and process each set
   bit by calling the right `Process*Barrier` function
   (`ProcessBarrierSmgrRelease`, etc).
3. Bump `pss_barrierGeneration` to the shared value.
4. `ConditionVariableBroadcast(&slot->pss_barrierCV)` so
   `WaitForProcSignalBarrier` callers can wake.

**Critical ordering** at `:451-455`: `WaitForProcSignalBarrier` checks
only `pss_barrierGeneration`, NOT `pss_barrierCheckMask`. The mask is
cleared *before* absorbing, but the generation is updated *after*. So
if a waiter reads generation == target, the absorbing process has
definitely run all the bit-handlers.

## ProcSignalInit (`:170`)

Per-backend setup at startup:
1. Acquire spinlock on `ProcSignal->psh_slot[MyProcNumber]`.
2. Clear `pss_signalFlags`.
3. `pg_atomic_write_membarrier_u32(&slot->pss_pid, MyProcPid)` —
   the membarrier variant ensures any pre-startup state setup is
   visible before the pid is published. `[from-comment] :192-197`.
4. Read the current `psh_barrierGeneration`, write to ours →
   we declare ourselves "fully absorbed" relative to current state,
   since a fresh process has no cached state to invalidate.
5. Register `on_shmem_exit(CleanupProcSignalState)`.

`CleanupProcSignalState` (`:241`) clears the slot and sets
`pss_barrierGeneration = UINT64_MAX` (so any `WaitForProcSignalBarrier`
checks for our generation see "infinity" and don't block on us).
Broadcasts on the CV to wake any waiters.

## SendCancelRequest (`:739`)

Authentication for query cancellation: client sends `BackendKeyData`
(includes a secret cancel key); server walks slots, compares key under
the spinlock, sends `SIGINT` on match.

## SIGUSR1 handler

Lives in `tcop/postgres.c::procsignal_sigusr1_handler` — walks
`pss_signalFlags` and calls the per-reason `Handle*Interrupt`
functions (each just sets a flag + sets MyLatch).

## Cross-references

- `tcop/postgres.c::procsignal_sigusr1_handler` — the SIGUSR1 dispatcher.
- `sinval.c::HandleCatchupInterrupt` — one specific reason handler.
- `replication/walsender.c` — `PROCSIG_WALSND_INIT_STOPPING`.
- `access/parallel.c` — `PROCSIG_PARALLEL_MESSAGE`.

## Open questions

1. The race between `SendProcSignal` reading `pss_pid` and the target
   exiting/reusing the slot is handled by the spinlock + double-check.
   If pid is reused by an unrelated backend in the tiny window, we'd
   send SIGUSR1 to the wrong PG backend; backends tolerate spurious
   SIGUSR1 because the flag-walk will find no flag set. `[from-comment]
   latch.c:323-331` — analogous logic.
2. **Whether `kill(pid, SIGUSR1)` can race with the target's
   `CleanupProcSignalState`** — the spinlock prevents
   *concurrent* `SendProcSignal` + cleanup, but if SendProcSignal
   releases the lock and *then* calls `kill`, and target dies first,
   we'd `kill` a dead pid (harmless `ESRCH`). `[verified-by-code]
   :305-313`.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
- [subsystems/storage-ipc.md](../../../../../subsystems/storage-ipc.md)
