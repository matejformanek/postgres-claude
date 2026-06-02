# `storage/lmgr/lwlock.c`

- **Source:** `source/src/backend/storage/lmgr/lwlock.c` (1 939 lines)
- **Header:** `source/src/include/storage/lwlock.h`
- **Last verified commit:** `ef6a95c` (2026-06-01)

## 1. Purpose

Lightweight lock manager. LWLocks "are intended primarily to provide mutual exclusion of access to shared-memory data structures. Therefore, they offer both exclusive and shared lock modes (to support read/write and read-only access to a shared object). There are few other frammishes." `[from-comment]` (`lwlock.c:6-12`).

Three modes: `LW_EXCLUSIVE`, `LW_SHARED`, and an internal `LW_WAIT_UNTIL_FREE` used only by `LWLockAcquireOrWait` for WAL-insert-lock semantics `[verified-by-code]` (`lwlock.h:102-109`). LWLocks are *not* deadlock-detected, but are auto-released on `elog(ERROR)` via `LWLockReleaseAll`.

Top-of-file comment also documents the **atomic-CAS-on-lockcount** design that replaced the older spinlock-protected reader-writer counter (`lwlock.c:29-75`), and the four-phase race-mitigation protocol (`lwlock.c:60-75`).

## 2. Public surface

Acquisition: `LWLockAcquire(lock, mode) → bool`, `LWLockConditionalAcquire(lock, mode) → bool`, `LWLockAcquireOrWait(lock, mode) → bool` (`lwlock.c:1150, 1321, 1378`). Return values: `LWLockAcquire` returns `true` if acquired without sleeping; `LWLockConditionalAcquire` returns `false` immediately if would block; `LWLockAcquireOrWait` returns `false` if it had to wait *and* the lock is now free (caller need not do work). `[verified-by-code]`.

Release: `LWLockRelease`, `LWLockReleaseClearVar`, `LWLockReleaseAll` (`lwlock.c:1767, 1840, 1866`).

Variable-wait (used by WAL): `LWLockWaitForVar`, `LWLockUpdateVar`, `LWLockConflictsWithVar` (`lwlock.c:1566, 1702, 1505`).

Tranche/init: `LWLockNewTrancheId`, `RequestNamedLWLockTranche`, `GetNamedLWLockTranche`, `LWLockInitialize`, `InitLWLockAccess` (`lwlock.c:562, 620, 522, 670, 506`).

Introspection (debug-only): `LWLockHeldByMe`, `LWLockAnyHeldByMe`, `LWLockHeldByMeInMode`, `GetLWLockIdentifier` (`lwlock.c:1885, 1903, 1929, 747`). Note: `LWLockHeldByMe*` are documented as "meant as debug support only" in their comments `[from-comment]` (`lwlock.c:1879-1928`).

Shmem callbacks: `LWLockShmemRequest`, `LWLockShmemInit` (`lwlock.c:416, 445`).

## 3. Key types

- `LWLock` (defined in `lwlock.h`): `{tranche : uint16; state : pg_atomic_uint32; waiters : proclist_head}` plus debug-only `nwaiters` and `owner`. The single `state` word packs:
  - bits 0..(MAX_BACKENDS-1): share count
  - bit log2(MAX_BACKENDS): `LW_VAL_EXCLUSIVE` sentinel
  - bit 29: `LW_FLAG_LOCKED` (wait-list spinlock substitute)
  - bit 30: `LW_FLAG_WAKE_IN_PROGRESS`
  - bit 31: `LW_FLAG_HAS_WAITERS`
  - `[verified-by-code]` (`lwlock.c:96-108`).
- `LWLockHandle` — `{LWLock *lock; LWLockMode mode}` array entry. `held_lwlocks[MAX_SIMUL_LWLOCKS]` with `MAX_SIMUL_LWLOCKS = 200` `[verified-by-code]` (`lwlock.c:157-167`). Overflow is `elog(ERROR, "too many LWLocks taken")` at `lwlock.c:1182`.
- `LWLockTrancheShmemData` — `{user_defined[256] : {name, main_array_idx}; num_user_defined; slock_t lock}`. Extension tranches; the embedded spinlock protects `num_user_defined` `[verified-by-code]` (`lwlock.c:175-193`).
- Three tranche kinds (`lwlock.c:120-135`): (1) individually-named, (2) built-in tranche for grouped locks, (3) extension-defined. All three feed into `BuiltinTrancheNames[]` from `lwlocklist.h`.

## 4. Key invariants and locking

### Interrupt handling

- `LWLockAcquire` calls `HOLD_INTERRUPTS()` at `lwlock.c:1189`; `LWLockRelease` calls `RESUME_INTERRUPTS()` at `lwlock.c:1833`. Query-cancel/die signals are deferred while an LWLock is held. `[verified-by-code]`.
- `LWLockConditionalAcquire` `HOLD`s and only `RESUME`s on failure (`lwlock.c:1338, 1346`) — successful acquisition leaves interrupts disabled.
- `LWLockReleaseAll` is **deliberately interrupt-balance-neutral** — it does `HOLD_INTERRUPTS()` once per held lock to match the upcoming `RESUME_INTERRUPTS()` from `LWLockRelease`, so the holdoff count is not double-decremented during error recovery. `[from-comment]` (`lwlock.c:1855-1863`).

### State word atomicity

- All state changes use `pg_atomic_compare_exchange_u32` or `pg_atomic_fetch_*`. The CAS in `LWLockAttemptLock` "doubles as a memory barrier" — that's the source of the README's claim that "LWLock acquisition acts as a memory sequence point" (cited in `lock.c` fast-path comment at `lock.c:993-997`). `[from-comment]` (`lwlock.c:797-803`).
- `LW_FLAG_LOCKED` is a one-bit spinlock-style mutex *on the wait list*; not the lock itself. `LWLockWaitListLock`/`Unlock` use `pg_atomic_fetch_or_u32` / `pg_atomic_fetch_and_u32` (`lwlock.c:852, 895`).

### MAX_SIMUL_LWLOCKS = 200

A backend cannot hold more than 200 LWLocks simultaneously. This is checked at `lwlock.c:1181-1183` on every acquire. `[verified-by-code]`.

### Granted in arrival order

- README:28-30 promises "Waiting processes will be granted the lock in arrival order." Implementation: `LWLockQueueSelf` appends to `lock->waiters` proclist (`lwlock.c:1018`); `LWLockWakeup` walks the list head-to-tail (`lwlock.c:916-979`). `[verified-by-code]`.
- Caveat in `LWLockWakeup`: once an exclusive waiter has been woken, no further waiters of *any* mode are woken until that one runs — this prevents shared-waiter starvation of exclusive waiters (`lwlock.c:920-921`).

### Wait-for-var protocol (WAL insert locks)

- `LWLockWaitForVar(lock, valptr, oldval, newval)`: wait until either `lock` is free or `*valptr != oldval`. Never actually acquires the lock; returns when condition is met. `[from-comment]` (`lwlock.c:13-21, 1495-1565`).
- `LWLockUpdateVar(lock, valptr, val)` updates the var *while holding the lock exclusive* and wakes any `WAIT_UNTIL_FREE` waiters with a matching value. `[verified-by-code]` (`lwlock.c:1702-1766`).
- Sole caller is `WaitXLogInsertionsToFinish` `[from-comment]` (`lwlock.c:1514`).

### Tranche IDs

- Individual locks: tranche ID 0..(NUM_INDIVIDUAL_LWLOCKS-1).
- Built-in tranches: `LWTRANCHE_*` enum, after individuals.
- Extension tranches: ≥ `LWTRANCHE_FIRST_USER_DEFINED`, registered via `LWLockNewTrancheId` (allocs from `ProcGlobal->LWLockCounter`) or `RequestNamedLWLockTranche` (carves a slice of `MainLWLockArray`).
- **Wait-event name == tranche name.** "All these names are user-visible as wait event names, so choose with care ... and do not forget to update the documentation's list of wait events." `[from-comment]` (`lwlock.c:134-136`).

## 5. Functions of note

### 5.1 `LWLockAttemptLock` (`lwlock.c:764-824`)

The CAS loop that is the heart of the implementation. For exclusive: requires `(state & LW_LOCK_MASK) == 0`, then adds `LW_VAL_EXCLUSIVE`. For shared: requires `(state & LW_VAL_EXCLUSIVE) == 0`, then adds `LW_VAL_SHARED`. Always swaps (even when not free) "because this doubles as a memory barrier" — explicit comment `[from-comment]` (`lwlock.c:797-803`). Returns `true` if must wait.

### 5.2 `LWLockAcquire` (`lwlock.c:1150-1311`)

Four-phase outer loop matching the comment at `lwlock.c:66-72`: try CAS, queue, retry CAS, sleep. The "queue then retry" handles the race where the lock-holder releases between our first failed CAS and our enqueue. After sleeping on `PGSemaphoreLock(proc->sem)`, clears `LW_FLAG_WAKE_IN_PROGRESS` and loops back to phase 1 — the lock is *not* handed to us directly by the releaser (see comment `lwlock.c:1195-1206` for the rationale: avoids forced process swap per acquisition).

### 5.3 `LWLockAcquireOrWait` (`lwlock.c:1378-1493`)

WAL-insert variant: if we have to wait, we wait *until the lock is free* but don't take it. Returns `false` if waited (caller knows the protected condition is now true and doesn't need to do work). Used by `XLogFlush` to let the first finisher do the syscall while others wait.

### 5.4 `LWLockRelease` (`lwlock.c:1767-1834`)

Atomic subtract of `LW_VAL_EXCLUSIVE` or `LW_VAL_SHARED`. **The released oldstate is inspected** to decide whether to wake waiters: only if `HAS_WAITERS && !WAKE_IN_PROGRESS && lock count went to 0`. Removes from `held_lwlocks[]` by linear scan from the end (latest-acquired most likely match). `RESUME_INTERRUPTS()` is the **last** action.

### 5.5 `LWLockWakeup` (`lwlock.c:904-1017`)

Holds wait-list lock (`LW_FLAG_LOCKED`); collects a contiguous prefix of waiters into a local proclist; sets `LW_FLAG_WAKE_IN_PROGRESS` if any exclusive-mode waiter is among them; clears their `lwWaiting` and unlocks the wait list; then unlocks the waiters' semaphores. Splitting collection from wake-up minimises time under the wait-list spinlock.

### 5.6 `LWLockReleaseAll` (`lwlock.c:1866-1876`)

Called by `AbortTransaction` and from elog cleanup. Releases all held LWLocks back-to-front; each release matches its own `RESUME_INTERRUPTS` with an extra `HOLD_INTERRUPTS` to keep the holdoff count balanced.

### 5.7 `LWLockInitialize` (`lwlock.c:670-690`)

Initialises a fresh `LWLock`: `state = LW_FLAG_RELEASE_OK` (no — actually just 0), `tranche = tranche_id`, init proclist for waiters, debug `nwaiters = 0`. Callable on caller-allocated shmem (the third tranche kind).

## 6. Cross-references

- `lock.c` — primary client of LWLocks: partition LWLocks for the heavyweight lock table + `fpInfoLock` per PGPROC.
- `predicate.c` — uses predicate-lock partition LWLocks + named ones (`SerializableFinishedListLock`, `SerializablePredicateListLock`, `SerializableXactHashLock`, `SerialControlLock`).
- `bufmgr.c` (storage/buffer) — buffer-mapping partition LWLocks + per-buffer content lock.
- `xlog.c` — `LWLockAcquireOrWait`, `LWLockWaitForVar`, `LWLockUpdateVar` (WAL insert locks).
- `lwlocklist.h` (`source/src/include/storage/lwlocklist.h`) — declarative list of all individually-named locks and tranches.
- `lwlocknames.h` — generated by `generate-lwlocknames.pl` from `lwlocklist.h`.

## 7. Open questions

1. **Memory-ordering across non-CAS atomics.** `LWLockRelease` uses `pg_atomic_sub_fetch_u32` which is documented as full barrier; `LWLockWakeup` uses `pg_atomic_compare_exchange_u32` to clear `HAS_WAITERS`. I did not exhaustively verify that every state-word update is full-barrier where readers expect it. `[unverified]`.
2. **`LW_FLAG_RELEASE_OK` mentioned in `LWLockWakeup` comments** — was renamed/removed; I see only `WAKE_IN_PROGRESS`, `HAS_WAITERS`, `LOCKED`. `[unverified]`.
3. **Group locking interaction.** Does `LWLockAcquire` know anything about lock groups? No: LWLocks are mode-only and don't consult `lockGroupLeader`. Group locking is purely a heavyweight-lock concept.
4. **`LWLockHeldByMe*`** functions can produce false negatives in multi-stride array scans (`LWLockAnyHeldByMe`) if extensions allocate LWLocks at non-uniform strides — they're explicitly debug-only.

## 8. Tag tally

- `[verified-by-code]`: 14
- `[from-comment]`: 9
- `[from-README]`: 2
- `[unverified]`: 4

## files-examined rows

| path | depth | date | commit | doc |
|---|---|---|---|---|
| source/src/backend/storage/lmgr/lwlock.c | deep (selected functions + state-word layout) | 2026-06-01 | ef6a95c | knowledge/files/src/backend/storage/lmgr/lwlock.c.md |
| source/src/include/storage/lwlock.h | full-read | 2026-06-01 | ef6a95c | (this doc) |

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
- [subsystems/storage-lmgr.md](../../../../../subsystems/storage-lmgr.md)
- [subsystems/utils-mmgr.md](../../../../../subsystems/utils-mmgr.md)
