# Spinlock discipline — when to use SpinLock + when not

Spinlocks are PG's **shortest-held** synchronization primitive
— a single byte (`slock_t`) protecting a critical section
typically a few dozen instructions long. Held by busy-waiting,
NOT by sleeping. The discipline around them is extreme: no
function calls, no allocations, no system calls, no ereport
inside a held spinlock. Used for buffer-header state words,
proclist nodes, and a few other "must be brief" cases.

Anchors:
- `source/src/include/storage/spin.h` — public API
- `source/src/include/storage/s_lock.h:1-150` — design
  comments + implementation contract [verified-by-code]
- `knowledge/idioms/lwlock-rank-discipline.md` — the heavier
  alternative
- `.claude/skills/locking/SKILL.md` — picking among
  atomics / spinlocks / LWLocks / heavyweight

## The 3 API calls

```c
SpinLockInit(slock_t *lock);
SpinLockAcquire(slock_t *lock);
SpinLockRelease(slock_t *lock);
```

`slock_t` is typically 1 byte (architecture-dependent). Init
sets it to "unlocked." Acquire spins on test-and-set until
acquired. Release stores "unlocked."

The implementation under the hood uses `S_LOCK`, `TAS`, and
`TAS_SPIN` macros which dispatch to architecture-specific
atomic primitives [verified-by-code `s_lock.h:12-65`].

## The "kept short" contract

[from-comment `s_lock.h`]

A spinlock is held for **micro-seconds**, NOT milli-seconds.
The contract says (paraphrased):

> Spinlocks are intended for very short critical sections. If
> you need to do anything that might block, allocate memory,
> call into other subsystems, raise an error, or otherwise
> take more than a few microseconds, use an LWLock instead.

Concrete rules for code inside a held spinlock:

- **No function calls** (except trivial inlines).
- **No allocations** (palloc, malloc).
- **No system calls** (read, write, kernel ops).
- **No `ereport(ERROR, ...)`** — would longjmp without
  release.
- **No LWLock or heavyweight-lock acquisition.**
- **No buffer pin / unpin.**
- **No catalog access.**

Violations lead to: backend hang (waiting on something
blocked), backend crash (assertion), or backend deadlock
(some other path needs THIS spinlock).

## Why busy-wait?

Spinlocks are chosen because:

1. **The critical section is so short** that the cost of
   sleeping + waking exceeds the cost of spinning.
2. **The lock contention is naturally low** (most accesses
   are uncontended; spinning is rare).
3. **Backend latency matters** for the operation (e.g. buffer
   header reads — every page read goes through one).

If any of these doesn't apply, the right choice is an
LWLock (sleeps on contention) or an atomic operation.

## When to use a spinlock

Real examples in the codebase:

- **`BufferDesc.spinlock`** — protects the dual state +
  ref count + lock bits. Held only for the brief moment of
  reading or updating the packed state field.
- **`proclist` modifications inside LWLock state** — the
  `LW_FLAG_LOCKED` bit acts as a spinlock for proclist
  edits.
- **`PGPROC` field updates** that are read by other backends
  but the writer doesn't need to sleep.

The common pattern: a struct with a small "packed state"
field readers consult, with a spinlock for the rare
multi-step updates.

## When NOT to use a spinlock

Don't use a spinlock when:

- The protected operation includes any function call other
  than trivial inlines.
- You need to wait for something external (use latch +
  LWLock).
- The struct fits a single 32-bit atomic — use the atomic
  directly.
- The lock is held across more than ~50 instructions.

If you're tempted by performance, **measure first**. Modern
LWLocks on the uncontended path are extremely fast (~10ns);
the spinlock advantage is small.

## The TAS / TAS_SPIN distinction

[from-comment `s_lock.h:31-44`]

```c
int TAS(slock_t *lock);       /* test-and-set */
int TAS_SPIN(slock_t *lock);  /* test-and-set in spin loop */
```

These are implementation details, NOT public API. The
distinction:

- **TAS** — used for the initial acquisition try.
- **TAS_SPIN** — used inside the spin loop. On some
  architectures, the spin variant uses a non-coherent read
  to reduce cache-line ping-pong; only when the read sees
  "unlocked" does the full TAS fire.

Don't call these directly. Use `SpinLockAcquire`.

## The "interrupted" retry case

[from-comment `s_lock.h:49-58`]

> on Alpha TAS() will "fail" if interrupted.

On some architectures, an interrupt mid-TAS can result in a
spurious failure. The implementation handles this with a
retry loop. Pure userspace code doesn't have to think about
this; it's an implementation contract.

## Memory ordering

[from-comment `s_lock.h:60-68`]

> On platforms with weak memory ordering, the TAS(), TAS_SPIN(),
> and S_UNLOCK() macros must include memory barriers.

x86 has strong ordering; ARM / Alpha need explicit memory
barriers. The macros include them transparently. Code outside
the macros may need its own barriers.

## Common review-time concerns

- **Don't introduce new spinlocks lightly.** If you can use
  an atomic op (`pg_atomic_*`), use it. If LWLock would
  work, use it.
- **Document the held-time bound** in the comment on the
  field. A spinlock without "held for at most N ns" gets
  abused over time.
- **Audit added code paths inside a held spinlock** for
  forbidden operations. Pre-commit asserts catch some but
  not all.
- **Always pair `SpinLockAcquire` with `SpinLockRelease`** in
  the same function. Don't split across helpers.

## Invariants

- **[INV-1]** Held for microseconds, NOT milli-seconds.
- **[INV-2]** No function calls / ereport / palloc / syscall
  inside.
- **[INV-3]** No nested lock acquisition (LWLock, spinlock,
  heavyweight) inside.
- **[INV-4]** Acquire / Release paired in same function;
  no escape across boundaries.
- **[INV-5]** Architecture-specific memory barriers handled
  by the macros.

## Useful greps

- All SpinLock callers:
  `grep -RIn 'SpinLockAcquire\|SpinLockRelease' source/src/backend | wc -l`
- The s_lock implementations:
  `grep -n '#elif def\|TAS_SPIN' source/src/include/storage/s_lock.h | head -10`
- BufferDesc spinlock pattern:
  `grep -RIn 'LockBufHdr\|UnlockBufHdr' source/src/backend/storage/buffer | head -10`



## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/include/storage/s_lock.h`](../files/src/include/storage/s_lock.h.md) | 1 | design comments + implementation contract |
| [`src/include/storage/s_lock.h`](../files/src/include/storage/s_lock.h.md) | — | implementation contract + architecture dispatch |
| [`src/include/storage/spin.h`](../files/src/include/storage/spin.h.md) | — | public API |

<!-- /callsites:auto -->

## Cross-references

- `knowledge/idioms/lwlock-rank-discipline.md` — the heavier
  alternative; use when spinlock contract would be broken.
- `knowledge/data-structures/bufferdesc-state.md` — canonical
  spinlock user (state-word updates).
- `knowledge/data-structures/lwlock-struct.md` — proclist
  uses LW_FLAG_LOCKED as an internal spinlock.
- `.claude/skills/locking/SKILL.md` — full atomic /
  spinlock / LWLock / heavyweight decision tree.
- `source/src/include/storage/spin.h` — public API.
- `source/src/include/storage/s_lock.h` — implementation
  contract + architecture dispatch.
