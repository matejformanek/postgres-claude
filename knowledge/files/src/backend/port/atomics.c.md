---
path: src/backend/port/atomics.c
anchor_sha: e18b0cb7344
loc: 73
depth: read
---

# src/backend/port/atomics.c

## Purpose

Non-inline fallback implementations of 64-bit atomic operations for platforms
that lack native 8-byte atomic primitives. The bulk of `port/atomics.h` is
inlined, with each platform/compiler header (`atomics/generic-gcc.h`,
`atomics/arch-x86.h`, etc.) providing the real intrinsic. This file only
compiles when the platform forces the simulated path via
`PG_HAVE_ATOMIC_U64_SIMULATION` (`atomics.c:21`) — typically 32-bit or older
architectures where the compiler can't guarantee an 8-byte atomic CAS without
a lock. In that case `pg_atomic_uint64` is emulated using an embedded spinlock
(`slock_t` overlapped onto `ptr->sema`) plus a plain `uint64 value` field.
`[verified-by-code]`

This is part of the lowest layer of PG's locking hierarchy: above bare CPU
ops, below `SpinLockAcquire`, far below `LWLockAcquire`. The simulation makes
`pg_atomic_*_u64` correct (strong CAS) on every supported platform regardless
of whether the CPU has a native 8-byte CAS. `[from-comment]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `void pg_atomic_init_u64_impl(pg_atomic_uint64 *, uint64)` | `atomics.c:23` | Initializes the embedded spinlock + stored value |
| `bool pg_atomic_compare_exchange_u64_impl(pg_atomic_uint64 *, uint64 *expected, uint64 newval)` | `atomics.c:33` | Strong CAS — never spurious-fails |
| `uint64 pg_atomic_fetch_add_u64_impl(pg_atomic_uint64 *, int64 add_)` | `atomics.c:61` | Returns old value |

All three are only compiled inside `#ifdef PG_HAVE_ATOMIC_U64_SIMULATION`
(`atomics.c:21,73`). The matching `.h` declarations live in
`src/include/port/atomics/fallback.h`. `[verified-by-code]`

## Internal landmarks

- **`StaticAssertDecl` at `atomics.c:26`** — compile-time guard that the
  `sema` field inside `pg_atomic_uint64` is at least as large as `slock_t`.
  This is the contract that lets the spinlock be overlaid on the same struct
  the caller passes in.
- **"Strong" CAS comment at `atomics.c:39-46`** — explicit design note: it
  would look profitable to skip the cmpxchg when the spinlock is contended
  (i.e. emulate a weak CAS that may spuriously fail), but several algorithms
  rely on strong-CAS semantics, so the implementation always takes the lock
  and does the full compare. `[from-comment]`

## Invariants & gotchas

- **Field overlap.** The `slock_t` is stored in the same `ptr->sema` field
  that holds the spinlock state of the simulated atomic. Callers MUST go
  through `pg_atomic_*` APIs; touching `ptr->value` or `ptr->sema` directly
  is undefined.
- **No interrupts under spinlock.** This file inherits the universal
  spinlock rule from `storage/spin.h`: no `CHECK_FOR_INTERRUPTS`, no
  `ereport`, no syscalls while the lock is held. The bodies here are
  trivially short (3-5 instructions between `SpinLockAcquire` and
  `SpinLockRelease`) precisely so they obey that rule.
- **Strong vs weak CAS.** Algorithms in `src/backend/access/...` and
  `src/backend/storage/lmgr/lwlock.c` assume strong-CAS semantics. The
  spinlocked path here matches; native paths in
  `include/port/atomics/arch-x86.h` etc. must match too. If you ever add a
  new platform header, this is a property to preserve.
- **Not compiled on modern x86_64 / arm64.** On any host where the GCC
  built-in atomics work on 8-byte values, `PG_HAVE_ATOMIC_U64_SIMULATION` is
  undefined and this whole file is empty. Don't be surprised when
  `objdump -d backend | grep pg_atomic_fetch_add_u64_impl` shows nothing.
- **64-bit only.** There is NO equivalent `PG_HAVE_ATOMIC_U32_SIMULATION`
  block here — 32-bit atomics are universally available on all PG-supported
  platforms, so they're always inlined via `atomics/fallback.h`.
  `[verified-by-code]`

## Cross-refs

- `knowledge/idioms/locking.md` — the six-layer PG lock taxonomy (atomic /
  spinlock / LWLock / heavyweight / predicate / buffer-pin). This file is
  layer 1 (atomics) implemented using layer 2 (spinlocks) as a fallback.
- `knowledge/files/src/include/port/atomics.h.md` — the public header that
  routes between native and simulated implementations.
- `knowledge/files/src/include/storage/spin.h.md` — the `SpinLockAcquire` /
  `SpinLockRelease` contract these fallbacks rely on.
