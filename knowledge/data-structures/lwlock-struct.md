# LWLock — the atomic-state struct

`LWLock` is the actual struct stored in shared memory for each
lightweight lock. Distinct from the **discipline** of using
LWLocks (companion: `lwlock-rank-discipline.md`) — this doc
covers the in-memory layout: a single 32-bit atomic state word
plus a proclist of waiters. The clever bit-packing in the state
word is what makes the uncontended path nearly free.

Anchors:
- `source/src/include/storage/lwlock.h:75-90` — struct
  definition [verified-by-code]
- `source/src/backend/storage/lmgr/lwlock.c:96-118` — state
  bit layout [verified-by-code]
- `knowledge/idioms/lwlock-rank-discipline.md` — companion;
  rules for using LWLocks

## The struct

```c
typedef struct LWLock
{
    uint16            tranche;     /* tranche ID for observability */
    pg_atomic_uint32  state;       /* packed lock state */
    proclist_head     waiters;     /* list of waiting PGPROCs */
#ifdef LOCK_DEBUG
    pg_atomic_uint32  nwaiters;    /* debug-only waiter count */
    struct PGPROC    *owner;       /* debug-only last exclusive owner */
#endif
} LWLock;
```

[verified-by-code `lwlock.h:75-84`]

Three fields in the release-build layout:

- **`tranche`** — observability metadata (which lock family
  this belongs to). Used by `pg_stat_activity.wait_event_name`.
- **`state`** — the actual lock state, packed into 32 bits via
  atomics.
- **`waiters`** — a `proclist_head` of waiting PGPROCs.

## The state word — bit packing

[verified-by-code `lwlock.c:96-118`]

```c
#define LW_FLAG_HAS_WAITERS    ((uint32) 1 << 31)
#define LW_FLAG_RELEASE_OK     ((uint32) 1 << 30)
#define LW_FLAG_LOCKED         ((uint32) 1 << 29)
#define LW_VAL_EXCLUSIVE       (MAX_BACKENDS + 1)
#define LW_VAL_SHARED          1
#define LW_LOCK_MASK           (MAX_BACKENDS | LW_VAL_EXCLUSIVE)
#define LW_FLAG_MASK           (LW_FLAG_HAS_WAITERS | LW_FLAG_RELEASE_OK | LW_FLAG_LOCKED)
```

Three high-bit flags + a lower-bits "lock value":

| Bits | Meaning |
|---|---|
| Bit 31 | `LW_FLAG_HAS_WAITERS` — at least one waiter on proclist |
| Bit 30 | `LW_FLAG_RELEASE_OK` — release is allowed (debugging gate) |
| Bit 29 | `LW_FLAG_LOCKED` — proclist is being modified |
| Bits 0..28 | Lock value: 0 = unlocked, 1..MAX_BACKENDS = shared count, MAX_BACKENDS+1 = exclusive |

`LW_VAL_EXCLUSIVE` is `MAX_BACKENDS+1` — chosen so that
"shared count + 1" overflows into the exclusive bit. Any
attempt to acquire shared while exclusive is held would set
the state above the shared-count range, which is detected.

The `StaticAssertDecl` [verified-by-code `lwlock.c:117-118`]
ensures the value-region and flag-region don't overlap.

## The acquisition fast path

[verified-by-code `lwlock.c:780-820`]

Conceptually:

```c
do {
    old_state = pg_atomic_read_u32(&lock->state);
    if (mode == LW_EXCLUSIVE) {
        if (old_state & LW_LOCK_MASK)
            goto slow_path;            /* something held */
        desired_state = old_state + LW_VAL_EXCLUSIVE;
    } else {  /* LW_SHARED */
        if (old_state & LW_VAL_EXCLUSIVE)
            goto slow_path;            /* exclusive held */
        desired_state = old_state + LW_VAL_SHARED;
    }
} while (!pg_atomic_compare_exchange_u32(&lock->state, &old_state, desired_state));
```

The fast path is ONE atomic compare-and-swap. Uncontended
case: 10-20ns. No syscall, no proclist touch.

## The slow path

If the fast-path CAS fails (contention) or the lock is
clearly held in an incompatible mode:

1. Set `LW_FLAG_HAS_WAITERS` if not set.
2. Lock the proclist via `LW_FLAG_LOCKED` (a 2nd CAS).
3. Append this PGPROC to `waiters`.
4. Unlock the proclist.
5. **Wait on the PGPROC's latch** (released by the holder
   on `LWLockRelease`).

The proclist-locked flag (`LW_FLAG_LOCKED`) provides a brief
spinlock-like protection — only the proclist mutation itself
needs serialization; readers don't need to lock.

## Release

[verified-by-code `lwlock.c:946-970`]

```c
old_state = pg_atomic_fetch_sub_u32(&lock->state, LW_VAL_*);
if (old_state has waiters)
    wake_some_waiters();
```

Atomic decrement, then check waiters. Waking is selective —
either the next exclusive or all next-shareds.

## The proclist

`proclist_head waiters` is a linked list of PGPROCs, threaded
through each PGPROC's `lwWaitLink` field. Not a `dlist_node`
(which would be too large for the PGPROC's tight budget);
custom proclist primitives ([from `proclist.h`]) are used.

The list is ordered FIFO with priority for exclusive waiters
that arrived first.

## Tranches — observability, not enforcement

The `tranche` field is the observability tag, NOT a rank
enforcement. `pg_stat_activity` reports the wait_event_name
based on the tranche ID + a string registered at startup.

| Tranche family | Examples |
|---|---|
| Built-in individual locks | `WALWriteLock`, `ProcArrayLock` |
| Built-in tranches | `BufferContent`, `BufferIO`, `PredicateLockManager` |
| User-defined tranches | Extension-allocated via `LWLockNewTrancheId` |

Tranches matter for **diagnosis**, not for **correctness**.
The rank discipline (see companion idiom) is what prevents
deadlocks; tranches are how you find out WHICH LWLock a
backend is stuck on.

## Cache-line alignment

[from-comment `lwlock.h:88-95`]

The main LWLock array is laid out with each LWLock on its own
cache line, sometimes with extra padding to avoid false
sharing on heavily-contended locks. The struct itself is
small (~20-24 bytes); the padding pushes individual locks
apart.

The `LWLockPadded` typedef wraps `LWLock` with the alignment
padding. The buffer manager uses `BufferDescPadded` for the
same reason.

## The LOCK_DEBUG fields

`#ifdef LOCK_DEBUG` adds `nwaiters` (atomic counter) and
`owner` (last exclusive holder PGPROC). Used by:

- Assertion checks (e.g. "we're not releasing a lock we don't
  hold").
- TRACE_POSTGRESQL_LWLOCK_* DTrace probes.
- `pg_stat_activity` enhancements in debug builds.

In release builds, the struct is smaller (no debug fields)
and there's no per-LWLock overhead for tracking.

## Common review-time concerns

- **Don't introspect the state word directly.** Use
  `LWLockHeldByMe(lock)`, `LWLockHeldByMeInMode(lock, mode)`.
- **The proclist is private** — only LWLock release modifies
  it (under `LW_FLAG_LOCKED`).
- **Adding a new tranche** — register at `_PG_init` via
  `LWLockNewTrancheId` + `LWLockRegisterTranche`.
- **Cache-line alignment matters** for hot locks. New LWLock
  arrays in shared memory should pad.
- **`LW_FLAG_RELEASE_OK`** is a defensive debug flag; gates
  certain release paths in assertion builds.

## Invariants

- **[INV-1]** State word packs flags (high 3 bits) + lock
  value (low bits).
- **[INV-2]** Exclusive value = `MAX_BACKENDS + 1`; shared
  values 1..MAX_BACKENDS.
- **[INV-3]** Uncontended acquire = one CAS.
- **[INV-4]** Tranches are observability, not rank
  enforcement.
- **[INV-5]** Cache-line alignment via `LWLockPadded` for
  hot locks.

## Useful greps

- The state-word manipulation:
  `grep -n 'LW_VAL_EXCLUSIVE\|LW_VAL_SHARED\|LW_FLAG_' source/src/backend/storage/lmgr/lwlock.c | head -25`
- All LWLockPadded uses:
  `grep -RIn 'LWLockPadded' source/src/backend | head -10`
- Tranche registration:
  `grep -RIn 'LWLockNewTrancheId\|LWLockRegisterTranche' source/src/backend`


## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/storage/lmgr/lwlock.c`](../files/src/backend/storage/lmgr/lwlock.c.md) | 96 | state bit layout |
| [`src/backend/storage/lmgr/lwlock.c`](../files/src/backend/storage/lmgr/lwlock.c.md) | — | atomic state manipulation |
| [`src/include/storage/lwlock.h`](../files/src/include/storage/lwlock.h.md) | 75 | struct definition |
| [`src/include/storage/lwlock.h`](../files/src/include/storage/lwlock.h.md) | — | struct definition |
| [`src/include/storage/proclist.h`](../files/src/include/storage/proclist.h.md) | — | proclist primitive used for waiters |

<!-- /callsites:auto -->

## Cross-references

- `knowledge/idioms/lwlock-rank-discipline.md` — companion;
  rules for using LWLocks.
- `knowledge/data-structures/pgproc-fields.md` — PGPROC has
  the wait-link field threaded into the proclist.
- `knowledge/data-structures/bufferdesc-state.md` — the
  buffer-content LWLock embedded in BufferDesc uses this
  struct.
- `.claude/skills/locking/SKILL.md` — heavyweight vs LWLock
  decision tree.
- `source/src/include/storage/lwlock.h` — struct definition.
- `source/src/backend/storage/lmgr/lwlock.c` — atomic state
  manipulation.
- `source/src/include/storage/proclist.h` — the proclist
  primitive used for waiters.
