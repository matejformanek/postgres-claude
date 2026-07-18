# `src/include/port/atomics.h`

## Role

Cross-platform atomic-operations API. Provides `pg_atomic_uint32`,
`pg_atomic_uint64`, `pg_atomic_flag`, and the memory-barrier family
(`pg_compiler_barrier`, `pg_read_barrier`, `pg_write_barrier`,
`pg_memory_barrier`, `pg_spin_delay`). Used to build LWLocks, spinlocks,
lock-free counters (e.g. WAL insertion position, procarray xmin caches),
and any shared-memory state that must avoid LWLock overhead.

The header is the public face; the actual implementations live in
`source/src/include/port/atomics/` and are pulled in conditionally based
on `__GNUC__` / `_MSC_VER` and the target arch macros (`__x86_64__`,
`__aarch64__`, `__powerpc64__`, etc.) `[verified-by-code]`
`source/src/include/port/atomics.h:66-93`.

## Public API

Categories `[verified-by-code]` `source/src/include/port/atomics.h:163-617`:

- **Flag (TAS)**: `pg_atomic_init_flag` / `pg_atomic_test_set_flag` /
  `pg_atomic_unlocked_test_flag` / `pg_atomic_clear_flag` — test-and-set
  primitive; `test_set` has acquire, `clear` has release semantics.
- **u32**: `pg_atomic_init_u32`, `pg_atomic_read_u32`,
  `pg_atomic_read_membarrier_u32`, `pg_atomic_write_u32`,
  `pg_atomic_unlocked_write_u32`, `pg_atomic_write_membarrier_u32`,
  `pg_atomic_exchange_u32`, `pg_atomic_compare_exchange_u32`,
  `pg_atomic_fetch_{add,sub,and,or}_u32`,
  `pg_atomic_{add,sub}_fetch_u32`.
- **u64**: same surface as u32 plus `pg_atomic_monotonic_advance_u64`
  (only-increasing counter, used for advance-LSN-style invariants)
  `source/src/include/port/atomics.h:594-617`.
- **Memory barriers**: `pg_compiler_barrier`, `pg_memory_barrier`,
  `pg_read_barrier`, `pg_write_barrier`, `pg_spin_delay`.

The minimum set a new platform must provide is just three CAS/fetch-add/
flag primitives plus the three barrier flavors
`source/src/include/port/atomics.h:10-15`.

## Invariants

1. **Backend-only header.** `#ifdef FRONTEND #error` at line 41-43 —
   frontends must use `<stdatomic.h>` (or no atomics) directly
   `[verified-by-code]` `source/src/include/port/atomics.h:41-43`.
2. **Alignment.** `AssertPointerAlignment(ptr, 4)` for u32 and
   `(ptr, 8)` for u64 are gated on every read/write/RMW call
   `[verified-by-code]` `source/src/include/port/atomics.h:221,239,469-471`.
   The u64 alignment assert is **skipped** when
   `PG_HAVE_ATOMIC_U64_SIMULATION` is in effect — because the simulation
   wraps the value in a struct with an extra `int sema` field and can't
   guarantee 8-byte alignment `[verified-by-code]`
   `source/src/include/port/atomics/fallback.h:21-42`.
3. **Full-barrier RMW.** Every read-modify-write op (`exchange`,
   `compare_exchange`, `fetch_add`, `fetch_sub`, `fetch_and`, `fetch_or`)
   has full-barrier semantics per the comments `[from-comment]`
   `source/src/include/port/atomics.h:327,346,363,378,393`.
4. **Plain read/write are unordered.** `pg_atomic_read_u32` and
   `pg_atomic_write_u32` have "no barrier semantics" — they only
   guarantee atomicity (no torn reads/writes), not ordering with
   surrounding loads/stores `[from-comment]`
   `source/src/include/port/atomics.h:230-234,266-271`. The
   `_membarrier_` variants exist specifically when ordering is wanted
   without the cost of a full RMW.
5. **`pg_atomic_unlocked_write_u32` is fundamentally weaker.** It is
   neither atomic nor ordered — caller must guarantee no concurrent
   readers via external means `[from-comment]`
   `source/src/include/port/atomics.h:282-291`.
6. **`fetch_sub` cannot be passed `INT_MIN`.** Asserted at
   `source/src/include/port/atomics.h:384,442` (and `PG_INT64_MIN` for
   u64). This is because the implementation negates the argument and
   `-INT_MIN` overflows.
7. **`PG_HAVE_8BYTE_SINGLE_COPY_ATOMICITY`** is a separate platform
   declaration (set in the arch headers) about whether a plain aligned
   8-byte load/store is atomic without any RMW dance
   `[from-comment]` `source/src/include/port/atomics.h:15`.

## Notable internals

The 4-layer include chain:

1. `port/atomics/arch-{arm,x86,ppc}.h` — arch-specific assembly or hints
   (e.g. x86 has TSO so read/write barriers are just compiler barriers).
2. `port/atomics/generic-{gcc,msvc}.h` — compiler-intrinsic
   implementations using `__atomic_*` (gcc 4.7+) or `_Interlocked*` (MSVC).
3. `port/atomics/fallback.h` — spinlock-wrapped u64 simulation for any
   platform that didn't define `PG_HAVE_ATOMIC_U64_SUPPORT` after the
   above two steps `[verified-by-code]`
   `source/src/include/port/atomics/fallback.h:21-42`.
4. `port/atomics/generic.h` — builds the higher-level ops (e.g.
   `add_fetch_u32` synthesized from `fetch_add_u32 + add`) for any
   platform that didn't supply them natively.

Required defines that, if missing, halt compilation:
`PG_HAVE_ATOMIC_U32_SUPPORT`, `pg_compiler_barrier_impl`,
`pg_memory_barrier_impl` `[verified-by-code]`
`source/src/include/port/atomics.h:96-104`.

`pg_atomic_monotonic_advance_u64` `source/src/include/port/atomics.h:594-617`
is the only operation defined inline in this header rather than
delegating: it loops `compare_exchange_u64` until `currval >= target`.
It returns the **latest observed** value, not necessarily the target.
This is the API used for LSN-watermark advance.

## Trust-boundary / Phase D surface

- **The u64 fallback (`PG_HAVE_ATOMIC_U64_SIMULATION`).** When this code
  path is taken, every u64 atomic acquires a spinlock — the entire
  premise of "lockless u64 counter" collapses to "u64 counter behind a
  spinlock array". On platforms that hit it (mostly 32-bit and some
  oddball architectures), code that *assumed* cheap u64 atomics (WAL
  insert position, autovacuum counters, parallel scan state) silently
  becomes a contention point. There's no runtime way to detect this
  from C code other than `#ifdef PG_HAVE_ATOMIC_U64_SIMULATION`.
  **Phase-D-doc-issue:** the header should advertise "if you care about
  performance under the fallback, the contention domain is platform's
  spinlock-array size (NUM_SPINLOCK_SEMAPHORES)" — currently it doesn't.
- **`unlocked_write_u32` is footgun-shaped.** Three lines of comment
  warn the reader, but the function lives next to `write_u32` and the
  type signature is identical. A mis-edit that drops the "_unlocked"
  prefix won't compile-fail. Mitigation in practice: only ~3 callers
  in the tree. **Phase-D-review-pattern:** scan PR diffs for new
  `unlocked_write` callers and require justification in the commit msg.
- **Acquire/release vs. seq-cst silence.** The API does *not* expose
  C11-style memory-order arguments. Every RMW is full-barrier (== seq
  cst on x86, `dmb ish` on ARM). For algorithms that only need
  acq/rel, PG performance is leaving cycles on the floor — but only
  on weakly-ordered architectures (ARM, POWER). On x86 there's no
  cost. **Phase-D-doc-issue:** there's no "if you want
  acquire-release, build it from membarrier_read+plain_write" recipe
  in the header.
- **`PG_HAVE_8BYTE_SINGLE_COPY_ATOMICITY`.** Mentioned in the prologue
  but never grep-able as a *use* in this file — it's set in
  arch-headers and consumed by `pg_atomic_read_u64_impl`. A 32-bit
  build without it falls back to the RMW dance for plain reads, which
  is a perf cliff for monitoring tools (`pg_stat_*` views read
  counters).
- **Frontend `#error` is the only seam.** No frontend-safe atomic API
  exists in this header. Frontends needing atomics (e.g. parallel
  pg_dump, pg_basebackup) must roll their own with `<stdatomic.h>` or
  pthreads. Documented gap.

This is the most concurrency-critical header in the tree; nearly every
backend invariant about lock-free state ultimately resolves to one of
its primitives.

## Cross-refs

- `source/src/backend/storage/lmgr/README.barrier` — the canonical
  intro to barriers in PG `[from-comment]`
  `source/src/include/port/atomics.h:28-29`.
- `source/src/include/storage/lwlock.h` — LWLocks are built on top of
  `pg_atomic_uint32` (the lock state word).
- `source/src/include/storage/s_lock.h` — spinlocks; the fallback for
  u64 uses these via `pg_atomic_uint64.sema`.
- `source/src/include/port/atomics/fallback.h` — the slow-path u64
  simulation.
- `source/src/include/port/atomics/generic.h` — derived ops
  (`add_fetch` from `fetch_add`, etc.).
- A16-other: every `pg_atomic_*` user across the backend.

## Issues / unresolved

- **ISSUE-doc**: the header mentions
  `PG_HAVE_8BYTE_SINGLE_COPY_ATOMICITY` in the prologue but the macro
  is not defined here, set elsewhere, with no pointer to *where*. A
  reader has to grep arch-headers. (severity: low)
- **ISSUE-perf**: no acquire/release-only API; everything is either
  unordered (plain `read`/`write`) or full-barrier (RMW + `_membarrier_`
  variants). On ARM/POWER, code that only needs publication semantics
  pays full fence cost. (severity: medium, perf-only)
- **ISSUE-trust**: `pg_atomic_unlocked_write_u32`/`_u64` have no
  compile-time distinction from the safe variants beyond the name; a
  typo silently produces a torn-write hazard. (severity: low)
- **ISSUE-doc**: the u64 fallback is invisible at call sites — a
  developer reading `pg_atomic_fetch_add_u64(...)` has no in-source
  signal that on platform X this is a spinlock. (severity: medium,
  doc-only)

## Synthesized by
<!-- backlinks:auto -->
- [idioms/locking-overview.md](../../../../idioms/locking-overview.md)
- [subsystems/port.md](../../../../subsystems/port.md)
