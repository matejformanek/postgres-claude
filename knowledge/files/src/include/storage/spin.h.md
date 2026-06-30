# `src/include/storage/spin.h`

- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
- **Lines:** 67

## Role

**Public spinlock API** — a 3-function inline wrapper above
`s_lock.h`'s hardware macros: `SpinLockInit`, `SpinLockAcquire`,
`SpinLockRelease`. Static inlines exist purely so the call site
gets the same code as the macro but with type-checking.

## Public API

[verified-by-code] `source/src/include/storage/spin.h:44-67`

```c
static inline void SpinLockInit(volatile slock_t *lock);
static inline void SpinLockAcquire(volatile slock_t *lock);
static inline void SpinLockRelease(volatile slock_t *lock);
```

## Invariants (THE spinlock contract)

- INV-1: **Hold for at most a few instructions.** Anything
  longer must use an LWLock.
- INV-2: `CHECK_FOR_INTERRUPTS()` MUST NOT execute while holding
  — interrupts can `siglongjmp` past the release.
  [from-comment] `source/src/include/storage/spin.h:26-29`
- INV-3: Compiler barriers are included; no volatile-qualifier
  contortions needed in calling code (PG ≥ 9.5).
- INV-4: ~1 minute timeout → `abort()`. See s_lock.h INV-5.

## Trust boundary (Phase D)

None directly.

## Cross-refs

- `knowledge/files/src/include/storage/s_lock.h.md` —
  hardware impl
- `knowledge/idioms/locking.md` (skill)

## Issues

None.

## Synthesized by
<!-- backlinks:auto -->
- [idioms/spinlock-discipline.md](../../../../idioms/spinlock-discipline.md)
