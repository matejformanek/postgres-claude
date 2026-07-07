# LWLock rank discipline — deadlock-free ordering

LWLocks (Lightweight Locks) are the workhorse synchronization
primitive inside the backend. Unlike heavyweight locks, they
have **no deadlock detector** — instead, the codebase
enforces a strict acquisition order. A patch that acquires a
"lower-ranked" LWLock while holding a "higher-ranked" one
will hang under contention. The discipline is partly
documented, partly tribal knowledge, and is the most common
cause of "I added a one-line change and the regression tests
hang" bugs.

Anchors:
- `source/src/include/storage/lwlock.h` — LWLock API
  [verified-by-code]
- `source/src/include/storage/lwlocklist.h` — built-in lock
  + tranche IDs
- `source/src/backend/storage/lmgr/lwlock.c` — implementation
- `knowledge/subsystems/storage-lmgr.md` — lmgr context
- `.claude/skills/locking/SKILL.md` — companion skill

## The LWLock model

```c
typedef enum LWLockMode
{
    LW_EXCLUSIVE,
    LW_SHARED,
    ...
} LWLockMode;

LWLockAcquire(lock, mode);
LWLockRelease(lock);
LWLockHeldByMe(lock);            /* assertion helper */
LWLockHeldByMeInMode(lock, mode);
```

[verified-by-code `lwlock.h:102-124`]

Three acquisition variants:

- **`LWLockAcquire(lock, mode)`** — block until acquired.
- **`LWLockConditionalAcquire(lock, mode)`** — try once,
  return false if not immediately available. Used when the
  alternative is "give up and try later" rather than wait.
- **`LWLockAcquireOrWait(lock, mode)`** — race-detection
  variant; lock acquired iff no concurrent acquirer. Used for
  the optimistic-fast-path pattern in WAL emission.

## The no-deadlock-detector contract

Heavyweight locks have a deadlock detector — a separate process
periodically inspects the lock-wait graph and aborts a victim
transaction to break cycles. **LWLocks have no such mechanism.**
A backend blocking on an LWLock blocks indefinitely; nothing
arbitrates.

The contract: **all callers must acquire LWLocks in a
consistent global order.** Two cycles in the order graph =
guaranteed deadlock under contention.

## Rank groups (the documented hierarchy)

[from comment blocks in `lwlocklist.h`]

Approximate rank order, lowest-numbered first:

1. **Postmaster-level** — `XidGenLock`, `ProcArrayLock`,
   `ShmemIndexLock`. Held briefly; rarely conflict.
2. **WAL / xlog** — `WALInsertLocks`, `WALWriteLock`,
   `ControlFileLock`. Acquired during WAL emission /
   checkpoint.
3. **Buffer-mapping partitions** — `BufMappingLock` (one per
   partition). Acquired to look up a page in the buffer table.
4. **Lock-manager partitions** — `LockMgrLock` (one per
   partition). Acquired during heavyweight-lock acquisition.
5. **Per-buffer content locks** — embedded in BufferDesc.
   Acquired AFTER buffer mapping; holding a partition lock
   while acquiring a content lock is **rank-correct**.
6. **Per-buffer header spinlocks** — held briefly, never
   waited on.

(The numbering is conceptual; the actual codebase doesn't
expose a single ordered list.)

The general rule: **never acquire a higher-numbered LWLock
while holding a lower-numbered one**.

## Tranche IDs

[verified-by-code `lwlock.h:158-173`]

```c
typedef enum BuiltinTrancheIds
{
    LWTRANCHE_INVALID = NUM_INDIVIDUAL_LWLOCKS - 1,
#define PG_LWLOCKTRANCHE(id, name) LWTRANCHE_##id,
#include "storage/lwlocklist.h"
#undef PG_LWLOCKTRANCHE
    LWTRANCHE_FIRST_USER_DEFINED,
} BuiltinTrancheIds;
```

Each LWLock belongs to a **tranche** — a logical group used
for `pg_stat_activity.wait_event_name` reporting. Tranches
don't enforce rank; they're observability metadata.

User-defined tranches (from extensions) start at
`LWTRANCHE_FIRST_USER_DEFINED` via
`LWLockRegisterTranche()`.

## The "two locks at once" pattern (when allowed)

It's **OK** to hold two LWLocks at once provided:

1. The two locks have a well-defined rank order.
2. The order is the same at EVERY site that acquires both.
3. The code path is short — held LWLocks should not bracket
   any blocking operation (I/O, palloc that may grow context).

Canonical example: acquiring a buffer pin requires
`BufMappingLock` (partition lock for the lookup), then the
buffer's `content_lock` (for read/write). Always
mapping-then-content; never content-then-mapping.

## The "don't hold while doing X" rules

[from comment blocks in `lwlock.c`]

- **Don't hold an LWLock while calling `palloc`** that may
  trigger context expansion → could call into the OS for
  more memory → could block.
- **Don't hold an LWLock while calling `ereport(ERROR, ...)`**
  → the longjmp unwinds without releasing held LWLocks. The
  `LWLockReleaseAll()` function exists for AbortTransaction to
  clean up, but the cleanup is a safety net, not a feature.
- **Don't hold an LWLock across a SystemV/IPC call.**
- **Don't take a heavyweight lock while holding an LWLock.**
  The heavyweight lock subsystem may take LWLocks of its own
  (notably `LockMgrLock` partitions); the recursion can
  deadlock.

## ProcArrayLock — the most contended lock

`ProcArrayLock` protects the array of in-flight transaction
XIDs. Every snapshot acquisition takes it in shared mode;
every transaction commit takes it in exclusive mode. It is
**the** scalability bottleneck on snapshot-heavy workloads.

The LSN-based snapshot path (`GetSnapshotData()` lock-free
fast-path) was added specifically to reduce
`ProcArrayLock`-shared acquisitions in v14+.

Code that adds new ProcArrayLock acquisitions deserves
benchmarking on a high-concurrency workload.

## Common review-time concerns

- **New LWLock?** Pick a rank slot deliberately and add
  comments. The next reader needs to know where in the global
  order it fits.
- **New acquisition site of an existing lock?** Verify the
  rank order isn't violated. `git grep` the other acquirers.
- **Per-tuple LWLock acquisition?** Almost always a
  performance bug — LWLocks have nontrivial uncontended
  cost. Use atomic ops or fast-path tricks.
- **`LWLockConditionalAcquire`?** Make sure the failure path
  doesn't busy-loop. `pg_usleep` or yield.
- **`LWLockReleaseAll()` only at AbortTransaction.** Don't
  call it manually.

## Invariants

- **[INV-1]** LWLocks have no deadlock detector; ordering is
  the only safety mechanism.
- **[INV-2]** All sites acquiring two LWLocks must use the
  same order.
- **[INV-3]** Don't bracket palloc-may-grow / ereport / IPC
  / heavyweight-lock with held LWLocks.
- **[INV-4]** Tranches are for observability, not rank
  enforcement.
- **[INV-5]** `LWLockReleaseAll()` is AbortTransaction's
  safety net, not API.

## Useful greps

- All built-in LWLock + tranche definitions:
  `grep -n 'PG_LWLOCK\|PG_LWLOCKTRANCHE' source/src/include/storage/lwlocklist.h`
- Acquire sites of a specific lock:
  `grep -RIn 'LWLockAcquire(ProcArrayLock' source/src/backend`
- Conditional-acquire patterns:
  `grep -RIn 'LWLockConditionalAcquire' source/src/backend | head -20`



## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/storage/lmgr/lwlock.c`](../files/src/backend/storage/lmgr/lwlock.c.md) | — | implementation |
| [`src/include/storage/lwlock.h`](../files/src/include/storage/lwlock.h.md) | — | LWLock API |
| [`src/include/storage/lwlocklist.h`](../files/src/include/storage/lwlocklist.h.md) | — | built-in lock + tranche registry |

<!-- /callsites:auto -->



## Scenarios that use me
<!-- scenarios:auto -->

*Auto-derived from direct references + transitive file-overlap.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

- [`add-new-lwlock-tranche`](../scenarios/add-new-lwlock-tranche.md)
- [`add-new-shared-memory-region`](../scenarios/add-new-shared-memory-region.md)

<!-- /scenarios:auto -->

## Cross-references

- `.claude/skills/locking/SKILL.md` — the skill covering
  heavyweight + LWLock + spinlock decision tree.
- `knowledge/subsystems/storage-lmgr.md` — lmgr where
  heavyweight locks live; LWLocks underlie heavyweight too.
- `knowledge/idioms/predicate-locks.md` — SSI locks; live in
  the same subsystem dir but distinct mechanism.
- `knowledge/idioms/fastpath-locks.md` — relation-lock
  optimization that bypasses LWLock partition acquisition.
- `knowledge/data-structures/bufferdesc-state.md` — the
  content-lock + header-spinlock embedded in BufferDesc.
- `source/src/include/storage/lwlock.h` — public API.
- `source/src/include/storage/lwlocklist.h` — built-in lock
  + tranche registry.
- `source/src/backend/storage/lmgr/lwlock.c` — implementation.
