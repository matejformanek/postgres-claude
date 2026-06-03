# `storage/lmgr/s_lock.c`

- **Source:** `source/src/backend/storage/lmgr/s_lock.c` (300 lines)
- **Header:** `source/src/include/storage/s_lock.h` (the hardware-TAS macros), `source/src/include/storage/spin.h` (the public API)
- **Last verified commit:** `ef6a95c` (2026-06-01)

NB: the task brief listed both `s_lock.c` and `spin.c`, but **there is no `spin.c`** in this tree. The spinlock front-end is entirely macros in `spin.h` and `s_lock.h`; `s_lock.c` contains only the *contended-path* slowdown loop.

## 1. Purpose

Platform-independent portion of waiting for a contended spinlock. Per the top-of-file comment `[from-comment]` (`s_lock.c:5-37`):

> When waiting for a contended spinlock we loop tightly for awhile, then delay using `pg_usleep()` and try again. … We time out and declare error after NUM_DELAYS delays (thus, exactly that many tries). With the given settings, this will usually take 2 or so minutes. It seems better to fix the total number of tries (and thus the probability of unintended failure) than to fix the total time spent.

The inline TAS itself is in `s_lock.h`; only when TAS fails does control reach this file via `s_lock` (`s_lock.c:97`), the function called by the `SpinLockAcquire` macro on contention.

## 2. Public surface

- `s_lock(volatile slock_t *lock, file, line, func) → int` — wait-on-contended-spinlock body. Returns number of delays performed (for debug stats) `[verified-by-code]` (`s_lock.c:97-115`).
- `s_unlock(volatile slock_t *lock)` — only used where the TAS macro doesn't inline an unlock; on most platforms this is a no-op shim `[verified-by-code]` (`s_lock.c:116-119`).
- `perform_spin_delay(SpinDelayStatus *status)`, `finish_spin_delay(SpinDelayStatus *status)` — the reusable spin-loop building blocks used **also** by `LWLockWaitListLock` (`lwlock.c:858-871`) `[verified-by-code]` (`s_lock.c:126-199`).
- `set_spins_per_delay(int)`, `update_spins_per_delay(int) → int` — exchange of the locally-adaptive `spins_per_delay` between backends and postmaster `[verified-by-code]` (`s_lock.c:207-247`).

## 3. Key types and constants

- `slock_t` — platform-specific; usually a `char` or `int` (defined in `s_lock.h` per arch).
- `SpinDelayStatus` (declared in `s_lock.h`) — `{spins, delays, cur_delay, file, line, func}`. Initialised by `init_local_spin_delay()` (a macro using `__FILE__`/`__LINE__`).
- `MIN_SPINS_PER_DELAY = 10`, `MAX_SPINS_PER_DELAY = 1000`, `NUM_DELAYS = 1000`, `MIN_DELAY_USEC = 1000` (1 ms), `MAX_DELAY_USEC = 1000000` (1 s) `[verified-by-code]` (`s_lock.c:57-61`).
- `spins_per_delay` — process-local, adaptive. Decremented on each contention encountered, incremented on each fast-acquire — converges toward `MIN` on a uniprocessor (where spinning is pointless) and toward `MAX` on a true multi-CPU machine `[from-comment]` (`s_lock.c:170-184`).
- `DEFAULT_SPINS_PER_DELAY` — defined in `s_lock.h`; used at backend startup before `set_spins_per_delay` runs.

## 4. Key invariants and locking

### Stuck-spinlock contract

After `NUM_DELAYS = 1000` delay cycles (~2 minutes on typical hardware) without acquiring the lock, `s_lock_stuck` runs and **panics** the backend with `elog(PANIC, "stuck spinlock detected at %s, %s:%d", func, file, line)` `[verified-by-code]` (`s_lock.c:78-92`). Since spinlocks are not expected to be held more than a few dozen instructions, this is treated as an error in the holder.

### No interrupts, no errors, no kernel calls

Stated in `spin.h:26-29` and `README:8-11` `[from-README]`:
- A `CHECK_FOR_INTERRUPTS` cannot occur inside a spinlock-held region.
- `ereport(ERROR)` cannot escape — there's no automatic release.
- Kernel calls / subroutine calls are disallowed in the spinlock-held region.

`s_lock.c` itself **does** call `pg_usleep` and `pgstat_report_wait_start/end` from inside `perform_spin_delay`, but only after the spinlock attempt has *failed* — these run while waiting, not while holding.

### Compiler barrier built into the macros

`SpinLockAcquire`/`Release` macros include a compiler barrier so loads/stores cannot be reordered across them by the compiler (this is a documented property in `spin.h:21-24`). The hardware barriers are implicit in the TAS instruction itself.

### Sleep + exponential backoff details

`perform_spin_delay` (`s_lock.c:126-166`):
1. `SPIN_DELAY()` macro — a CPU-relax / pause instruction (defined per-arch in `s_lock.h`).
2. After `spins_per_delay` busy iterations, `pg_usleep(cur_delay)`. First sleep is 1 ms; multiplied by a random factor in `[1.0, 2.0]` each iteration; wraps back to 1 ms after exceeding 1 s `[verified-by-code]` (`s_lock.c:155-162`).
3. `pgstat_report_wait_start(WAIT_EVENT_SPIN_DELAY)` reports the wait — but only once we're actually sleeping, because busy spinning would dominate any profiling overhead `[from-comment]` (`s_lock.c:140-146`).

`finish_spin_delay` adjusts `spins_per_delay` after acquisition: +100 (capped at MAX) if no delay was needed; -1 (floored at MIN) if delays did happen.

## 5. Functions of note

### 5.1 `s_lock` (`s_lock.c:97-115`)

```c
init_local_spin_delay(&delayStatus);
while (TAS_SPIN(lock))
    perform_spin_delay(&delayStatus);
finish_spin_delay(&delayStatus);
return delayStatus.delays;
```

`TAS_SPIN` is a macro that may be a tight cmp-then-TAS loop (avoiding cache-line bouncing); `TAS` is the actual atomic TAS. Both are per-arch in `s_lock.h`.

### 5.2 `perform_spin_delay` (`s_lock.c:126-166`)

Building block reused by LWLock's wait-list spinlock substitute (`LWLockWaitListLock` calls it after a contended `pg_atomic_fetch_or_u32`). The unified backoff/timeout policy is the reason this lives here and not in `lwlock.c`.

### 5.3 `update_spins_per_delay` (`s_lock.c:218-247`)

Postmaster periodically averages backends' `spins_per_delay` and stores it back so new backends start with a sensible default — converges across the cluster faster than each backend reconverging from `DEFAULT_SPINS_PER_DELAY`.

### 5.4 `main` (`s_lock.c:251`, only when `S_LOCK_TEST` defined)

Standalone test harness — not compiled into the backend. Builds a test binary that exercises s_lock against itself.

## 6. Cross-references

- `spin.h` — public macro front-end (`SpinLockInit`, `SpinLockAcquire`, `SpinLockRelease`).
- `s_lock.h` — per-architecture TAS macros and `slock_t` definition.
- `lwlock.c` — uses `perform_spin_delay` / `finish_spin_delay` for its wait-list spin substitute.
- Any caller of `SpinLockAcquire` (e.g. `FastPathStrongRelationLocks->mutex` in `lock.c:495`).

## 7. Open questions

1. **Whether the ~2-minute timeout interacts badly with debugging.** Attaching gdb to a backend currently spinning on a lock held by another (debugged-paused) backend will trigger the PANIC. Workaround is to set NUM_DELAYS very high in a debug build. `[inferred]`.
2. **Quality of `pg_prng_double` distribution at scale.** The backoff jitter uses the global PRNG which is seeded once per backend; not obviously safe for spinlock-contention storms across many backends (they'd all jitter similarly if seeded from short-period entropy). `[unverified]`.
3. **Behavior of `SPIN_DELAY()` on architectures without a pause instruction.** Falls back to an empty macro? A no-op slows down convergence. `[unverified]` without reading per-arch `s_lock.h`.

## 8. Tag tally

- `[verified-by-code]`: 7
- `[from-comment]`: 4
- `[from-README]`: 1
- `[inferred]`: 1
- `[unverified]`: 2

## files-examined rows

| path | depth | date | commit | doc |
|---|---|---|---|---|
| source/src/backend/storage/lmgr/s_lock.c | full-read | 2026-06-01 | ef6a95c | knowledge/files/src/backend/storage/lmgr/s_lock.c.md |
| source/src/include/storage/spin.h | quick-skim (citing comments only) | 2026-06-01 | ef6a95c | (this doc) |
| source/src/include/storage/s_lock.h | not opened (per-arch macros) | 2026-06-01 | ef6a95c | (this doc) |

## Synthesized by
<!-- backlinks:auto -->
- [idioms/locking-overview.md](../../../../../idioms/locking-overview.md)
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
- [subsystems/storage-lmgr.md](../../../../../subsystems/storage-lmgr.md)
