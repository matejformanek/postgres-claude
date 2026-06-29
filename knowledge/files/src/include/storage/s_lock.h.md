# `src/include/storage/s_lock.h`

- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
- **Lines:** 753

## Role

**Hardware-level spinlock implementation.** Defines `slock_t`,
the `S_INIT_LOCK` / `S_LOCK` / `S_UNLOCK` / `SPIN_DELAY` macros,
and the per-architecture TAS (test-and-set) primitives.
NEVER include directly — `spin.h` is the public face.

[from-comment] `source/src/include/storage/s_lock.h:5-7`

## Per-arch coverage (selected, by ifdef ladder)

- x86_64 (GCC/Clang inline asm with `lock xchgb` and `pause`)
- ARM64 (LSE atomics or LL/SC pairs)
- PowerPC (lwsync barriers)
- RISC-V
- Solaris/SPARC, AIX
- HP-UX legacy
- Windows MSVC (`_InterlockedCompareExchange`)
- "Generic" fallback via `__sync_lock_test_and_set` (GCC) or
  POSIX `pthread_mutex_t` (very-old-platform safety net)

## Public surface (used only by spin.h)

- `S_INIT_LOCK(lock)` — initialize to unlocked
- `S_LOCK(lock)` → returns "delays" count; **timeout-and-abort()**
  at ~1 minute. [from-comment] lines 15-19. NOT a programmer
  bug if it loops — it's hardware-debug or runaway-process.
- `S_UNLOCK(lock)` — release
- `SPIN_DELAY()` — call inside spin wait loop (e.g. x86 `pause`)
- `TAS(lock)` / `TAS_SPIN(lock)` — low-level atomic, NOT to be
  called directly. `TAS_SPIN` may use unlocked load instead of
  atomic re-test for cache friendliness. [from-comment] lines
  39-44.

## Invariants

- INV-1: **Spinlock must not be held > a few instructions**
  ([from-comment] in `spin.h:26-29`). `CHECK_FOR_INTERRUPTS` is
  explicitly NOT safe while holding.
- INV-2: Memory barriers are inside the macros — caller does NOT
  need volatile pointers (PG ≥ 9.5). [from-comment] lines 54-72.
- INV-3: TAS may report failure even when the lock is free
  (e.g. on Alpha during interrupt). Always use a retry loop.
  [from-comment] lines 48-51.
- INV-4: weak-memory-order arches require explicit fence in
  `TAS`, `TAS_SPIN`, `S_UNLOCK` (lines 65-71).
- INV-5: timeout-and-abort intentionally `abort()`s after ~1
  minute to avoid permanent hangs. This is a **crash signal in
  production logs**; common causes are buggy code holding too
  long, or kernel scheduler starvation.

## Trust boundary (Phase D)

- Hardware/compiler-specific; correctness rests on PG having
  the right asm for each arch. New arch ports must implement
  TAS correctly; getting fences wrong silently corrupts shared
  state.

## Cross-refs

- `knowledge/files/src/include/storage/spin.h.md`
- `knowledge/files/src/backend/storage/lmgr/s_lock.c.md`
  (timeout-and-abort impl)
- `knowledge/idioms/locking.md` (skill) — choosing among
  atomics/spinlock/lwlock/heavyweight

## Issues

None at header level.

## Synthesized by
<!-- backlinks:auto -->
- [idioms/spinlock-discipline.md](../../../../idioms/spinlock-discipline.md)
