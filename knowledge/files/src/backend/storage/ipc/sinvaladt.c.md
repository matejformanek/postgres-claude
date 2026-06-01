# `storage/ipc/sinvaladt.c`

- **Source:** `source/src/backend/storage/ipc/sinvaladt.c` (714 lines)
- **Header:** `source/src/include/storage/sinvaladt.h`
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** deep-read

## Purpose

The **sinval queue** implementation: a single shared circular buffer
of `SharedInvalidationMessage` plus per-backend `nextMsgNum` cursors.
The conceptual model is an infinite array with `[minMsgNum, maxMsgNum)`
holding live entries; physically it's `MAXNUMMESSAGES = 4096`
slots indexed by `MsgNum % MAXNUMMESSAGES`. `[from-comment] :30-50`.

Used by `sinval.c` for cache invalidation; clients send via
`SendSharedInvalidMessages` and receive via
`ReceiveSharedInvalidMessages`.

## Tunables (file-static)

- `MAXNUMMESSAGES = 4096` — circular buffer size; must be power of 2.
- `MSGNUMWRAPAROUND = MAXNUMMESSAGES * 262144` — rebases counters
  before signed int overflow. Must be a multiple of MAXNUMMESSAGES.
- `CLEANUP_MIN = MAXNUMMESSAGES / 2 = 2048` — minimum messages before
  trying to clean up.
- `CLEANUP_QUANTUM = MAXNUMMESSAGES / 16 = 256` — how often to
  reattempt cleanup.
- `SIG_THRESHOLD = MAXNUMMESSAGES / 2 = 2048` — at how-far-behind we
  send PROCSIG_CATCHUP_INTERRUPT.
- `WRITE_QUANTUM = 64` — max messages inserted per write-lock acquisition.

`:128-135`.

## Shared structures

### `ProcState[NumProcStateSlots]` (`:137-163`)

Per backend, indexed by `pgprocno` (`MyProcNumber`):
- `procPid` — 0 means inactive entry.
- `nextMsgNum` — backend's read cursor.
- `resetState` — true ⇒ backend missed messages, must throw away all
  caches on next receive.
- `signaled` — true ⇒ a PROCSIG_CATCHUP_INTERRUPT is already in flight
  to this backend; don't send another.
- `hasMessages` — fast-path flag, true ⇒ at least one message has
  arrived since last drain.
- `sendOnly` — true only for the Startup process: it sends invals
  during recovery for the benefit of hot-standby readers, but has no
  catalog cache itself so never receives. `[from-comment] :148-154`.
- `nextLXID` — the next LocalTransactionId for the *next* occupant of
  this slot. Carried across to avoid VXID reuse within a short window.

### `SISeg` (`:165-197`)

- `minMsgNum`, `maxMsgNum` — bounds. `minMsgNum` is *lower bound on
  any backend's `nextMsgNum`* — only refreshed in `SICleanupQueue`,
  so it can lag. `[from-comment] :40-43`.
- `nextThreshold` — when `maxMsgNum - minMsgNum` exceeds this, call
  cleanup again.
- `msgnumLock` — spinlock just for `maxMsgNum`, used by readers without
  the write LWLock. **The spinlock is needed for memory-barrier
  semantics, not for atomicity** — writes to the buffer must be visible
  before the new `maxMsgNum` is. `[from-comment] :96-102`.
- `buffer[MAXNUMMESSAGES]` — the ring.
- `numProcs`, `pgprocnos[*]` — a *dense* list of active slot indexes,
  separate from `ProcArrayStruct->pgprocnos` to avoid ProcArrayLock
  contention. `[from-comment] :188-193`.
- `procState[FLEXIBLE_ARRAY_MEMBER]` — sparse array indexed by
  `pgprocno`.

## Locking — the unusual reader/writer pattern

Two LWLocks + one spinlock:

- **`SInvalReadLock`** SHARED by readers (`SIGetDataEntries`). But
  **readers modify their own `ProcState`** — the shared lock here is
  not "read-only"; rather it expresses that each reader only touches
  its own slot. `[from-comment] :459-465`.
- **`SInvalReadLock` EXCLUSIVE** is taken by `SICleanupQueue` to do
  array-wide updates, locking out all readers. `:592`.
- **`SInvalWriteLock`** EXCLUSIVE only — serializes writers
  (`SIInsertDataEntries`), and used by `SharedInvalBackendInit` /
  `CleanupInvalidationState` for slot acquisition.
- **`msgnumLock`** spinlock — needed because writers can run in
  parallel with readers; the spinlock is the memory barrier between
  buffer-content writes and `maxMsgNum` advance.

  > "The reason it is needed is to provide a memory barrier: we need
  > to be sure that messages written to the array are actually there
  > before maxMsgNum is increased." `[from-comment] :97-102`.

  **The exact rule:** you need the spinlock to read `maxMsgNum`
  unless you hold `SInvalWriteLock`, and to write `maxMsgNum` unless
  you hold *both* locks. `:91-94`.

## SIInsertDataEntries (`:371`)

1. Process in batches of ≤ `WRITE_QUANTUM = 64`.
2. Take `SInvalWriteLock` EX.
3. Loop: if buffer would overflow or threshold crossed →
   `SICleanupQueue(callerHasWriteLock=true, …)`.
4. Write into `buffer[max % MAXNUMMESSAGES]` for each message.
5. Under `msgnumLock` spinlock, advance `maxMsgNum`.
6. For each *active* backend (iterating dense `pgprocnos[]`), set
   `stateP->hasMessages = true` (unlocked — the LWLock release will
   provide the barrier).
7. Release `SInvalWriteLock` (memory barrier).

## SIGetDataEntries (`:474`)

1. Quick unlocked check `if (!stateP->hasMessages) return 0`. Comment
   `:485-495` notes the read could migrate backwards before function
   entry; we accept that small race because the next round will catch it.
2. Take `SInvalReadLock` SHARED.
3. **Reset `hasMessages = false` *before* reading `maxMsgNum`** —
   otherwise messages arriving between the maxMsgNum read and the
   hasMessages reset would set `hasMessages=true` and then we'd clobber
   it. `[from-comment] :501-509`.
4. Read `maxMsgNum` under `msgnumLock`.
5. If our `resetState` is set → return `-1` after clearing flags.
6. Pull messages into caller's buffer; advance `stateP->nextMsgNum`.
7. If we caught up (`nextMsgNum >= max`), clear `signaled` — we're
   eligible for another catchup interrupt later. Else set
   `hasMessages = true` so the next call retries.
8. Release lock.

## SICleanupQueue (`:578`)

The garbage collector + catchup-signaler. Called from writers when the
queue gets full and from receivers after they catch up
(daisy-chain via `sinval.c`).

1. Take `SInvalWriteLock` (if not already) + `SInvalReadLock` EX —
   total exclusion.
2. Walk active backends:
   - Skip `resetState || sendOnly`.
   - If a backend is *too* far behind (`nextMsgNum < lowbound`):
     force `resetState = true`; ignore from minMsgNum calc.
   - Track global minimum `n` → new `minMsgNum`.
   - Track furthest-back *unsignaled* backend → `needSig`.
3. If `minMsgNum >= MSGNUMWRAPAROUND`: rebase all counters by
   subtracting `MSGNUMWRAPAROUND`.
4. Recompute `nextThreshold`.
5. **Drop both locks before signaling.** `SendProcSignal(...,
   PROCSIG_CATCHUP_INTERRUPT, ...)` can be slow, so release first.
   `[from-comment] :662-666`. Mark `needSig->signaled = true` *before*
   releasing.
6. If caller had write lock, reacquire before returning.

**Caution noted at `:572-576`**: "because we transiently release write
lock when we have to signal some other backend, it is NOT guaranteed
that there are still minFree free message slots at exit." Caller
must recheck. `SIInsertDataEntries` does this in its inner `for(;;)`
loop at `:403-411`.

## SharedInvalBackendInit / CleanupInvalidationState

Slot lifecycle, both under `SInvalWriteLock` EX. The
init function adds the new `MyProcNumber` to the dense `pgprocnos[]`
list. `CleanupInvalidationState` removes it with the standard
"swap with last, decrement count" trick. `:351-359`.

Note: an attempt to claim a slot whose `procPid != 0` is an `ERROR`
("sinval slot for backend %d is already in use by process %d") — this
**guards against forgotten-cleanup bugs**. `:295-300`.

## GetNextLocalTransactionId (`:702`)

Splits VXID generation: each backend owns its own
`nextLocalTransactionId` so VXID allocation is lock-free. The high
part is `ProcNumber` (slot index), low part is the LXID. The
`nextLXID` field in `ProcState` preserves the counter across slot
reuse so a freshly-occupied slot doesn't restart from 0 (which would
risk vxid reuse). `[from-comment] :689-700`.

## Cross-references

- `sinval.c` — the API facing the rest of the system.
- `utils/cache/inval.c` — message types + dispatch.
- `procsignal.c` — `PROCSIG_CATCHUP_INTERRUPT`.

## Open questions / unverified

1. **`SInvalReadLock` SHARED while writers run** is unusual.
   Comment `:459-465` warns: "Note that this is not exactly the normal
   (read-only) interpretation of a shared lock! Look closely at the
   interactions before allowing SInvalReadLock to be grabbed in
   shared mode for any other reason!" — any extension that re-uses
   this lock for an unrelated purpose would silently violate
   isolation.
2. **Memory-barrier reasoning at `:419-433`**: writer sets
   `buffer[max%N] = msg`, then bumps `maxMsgNum` under spinlock
   (full barrier on x86 + an acquire/release on weak archs). Then
   sets `hasMessages` on every backend without explicit barrier —
   the comment says `LWLockRelease(SInvalWriteLock)` is the barrier.
   `[verified-by-code]`, but verifying that `LWLockRelease` actually
   contains a `pg_write_barrier` would require a peek at `lwlock.c`.
   `[unverified-here]`.
3. **`nextThreshold` heuristic** `:656-660` — the formula rounds up
   to next `CLEANUP_QUANTUM` multiple. Reasonable but not commented
   beyond "should be a power of 2 for speed".

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/storage-ipc.md](../../../../../subsystems/storage-ipc.md)
