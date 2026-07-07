# LOCALLOCK — per-backend heavyweight-lock cache

`LOCALLOCK` is the backend-local mirror of every heavyweight
lock this backend has acquired. The shared lock-manager
hashtable lives in shared memory and is partition-locked; the
LOCALLOCK hashtable lives in process memory and tracks
"what locks am I currently holding, on whose behalf?"
Together they implement the heavyweight-lock subsystem's
recursive-acquire counting, ResourceOwner integration, and
fast-path bypass detection.

Anchors:
- `source/src/include/storage/lock.h:239-272` — struct
  definitions [verified-by-code]
- `source/src/backend/storage/lmgr/lock.c` — implementation
- `knowledge/idioms/fastpath-locks.md` — the fast-path
  bypass this struct interacts with
- `knowledge/subsystems/storage-lmgr.md` — lmgr context

## The three nested structs

```c
typedef struct LOCALLOCKTAG
{
    LOCKTAG   lock;     /* identifies the lockable object */
    LOCKMODE  mode;     /* lock mode for this entry */
} LOCALLOCKTAG;

typedef struct LOCALLOCKOWNER
{
    struct ResourceOwnerData *owner;
    int64     nLocks;   /* # of times held by this owner */
} LOCALLOCKOWNER;

typedef struct LOCALLOCK
{
    LOCALLOCKTAG  tag;          /* unique identifier */
    uint32        hashcode;     /* copy of LOCKTAG's hash */
    LOCK         *lock;         /* shared LOCK object, or NULL */
    PROCLOCK     *proclock;     /* shared PROCLOCK object, or NULL */
    int64         nLocks;       /* total times lock is held */
    int           numLockOwners;
    int           maxLockOwners;
    LOCALLOCKOWNER *lockOwners; /* dynamic array */
    bool          holdsStrongLockCount;
    bool          lockCleared;
} LOCALLOCK;
```

[verified-by-code `lock.h:239-272`]

## What the tag identifies

The `LOCALLOCKTAG` keys the local-hashtable. Two locks on the
same object at different modes are SEPARATE LOCALLOCK entries
— same backend can hold `AccessShareLock` AND `RowShareLock`
on the same relation simultaneously, each with its own
per-owner accounting.

## The nLocks counter — recursive acquire

`LOCALLOCK.nLocks` counts how many times this backend has
acquired this lock-on-this-object-at-this-mode. Heavyweight
locks support **recursive acquisition** — the same backend
calling `LockRelation(X, AccessShareLock)` twice does not
deadlock; the second call increments `nLocks` to 2, the
first `UnlockRelation` decrements to 1, the second
decrements to 0 and releases.

The shared `LOCK` object does NOT track recursion. Per-backend
recursion lives entirely in LOCALLOCK.

## Per-ResourceOwner accounting

`lockOwners[]` is a dynamic array of `LOCALLOCKOWNER` records
— one per `ResourceOwner` that has claimed a share of this
lock. The split exists because a single transaction with
nested subtransactions may have multiple ResourceOwners that
all want to "own" the same lock; on subtransaction
abort/commit, the per-owner counts roll up or release
independently.

`numLockOwners` is the count; `maxLockOwners` is the array's
allocation. The array grows as needed.

## The NULL shared-object case

[from-comment `lock.h:225-231`]

> if we acquired the lock via the fast-path mechanism, the
> lock and proclock fields are set to NULL, since there
> probably aren't any such objects in shared memory.

A LOCALLOCK with `lock == NULL` is **fast-path-tracked**.
The fast-path subsystem (see `knowledge/idioms/fastpath-locks.md`)
keeps the lock in `PGPROC.fpRelId[]` instead of the shared
hashtable. The LOCALLOCK still exists for nLocks accounting,
but the shared `LOCK` and `PROCLOCK` are absent.

If contention later forces fast-path-to-main-table transfer,
the LOCALLOCK's `lock`/`proclock` pointers get populated.

## holdsStrongLockCount

[verified-by-code `lock.h:270`]

A flag indicating this backend has incremented
`FastPathStrongRelationLocks` for this lock. Strong locks
(modes that conflict with the fast-path eligible modes)
require an atomic counter bump so fast-path-holding backends
can see "someone is trying to take an incompatible mode."

Tracking this per-LOCALLOCK means the matching decrement on
release is correct even if the lock's stronger-locking-state
changed in between.

## lockCleared

[verified-by-code `lock.h:271`]

A flag indicating "we have processed all sinval messages
relevant to this lock." Used so that after acquiring a
relation lock, the backend knows it has seen any catalog
invalidations for that relation, and can safely cache.

## The "garbage after release" rule

[from-comment `lock.h:233-237`]

> a locallock object can be left over from a failed lock
> acquisition attempt. In this case its lock/proclock fields
> are untrustworthy, since the shared lock object is neither
> held nor awaited, and hence is available to be reclaimed.
> If nLocks > 0 then these pointers must either be valid or
> NULL, but when nLocks == 0 they should be considered
> garbage.

`nLocks == 0` means "not currently held"; the entry is
recyclable and the `lock`/`proclock` pointers are stale.
Code that walks the LOCALLOCK hashtable must check `nLocks > 0`
before trusting other fields.

## The hashtable

LOCALLOCKs live in a per-backend hashtable keyed by
`LOCALLOCKTAG`. The hashtable's size is bounded by
`max_locks_per_transaction × (max_connections +
max_prepared_transactions)`. Running out is `ERROR: out of
shared memory hint`.

Most workloads use a tiny fraction of the budget; the default
(64) is usually fine.

## Common review-time concerns

- **Always go through `LockAcquire` / `LockRelease`** — never
  manipulate LOCALLOCK directly.
- **Don't cache LOCALLOCK pointers across `CommandCounterIncrement`**
  — the hashtable may have been compacted; pointers can
  dangle.
- **Recursive acquisition is a feature**, not a bug. Code
  that takes a lock under a lock you might already hold
  doesn't need to check first.
- **`nLocks == 0` means garbage** — check before dereferencing
  the `lock`/`proclock` fields.
- **Fast-path locks have NULL `lock`/`proclock`** — code
  that walks LOCALLOCK for any purpose other than nLocks
  must handle this.

## Invariants

- **[INV-1]** `LOCALLOCKTAG` keys uniquely; different modes
  on the same object are SEPARATE entries.
- **[INV-2]** `nLocks` is the recursive-acquire count for
  THIS backend on THIS lock at THIS mode.
- **[INV-3]** `nLocks == 0` means the entry is garbage;
  `lock`/`proclock` pointers may be stale.
- **[INV-4]** Fast-path-acquired locks have `lock == NULL`;
  the shared hashtable has no entry.
- **[INV-5]** `lockOwners[]` provides per-ResourceOwner
  rollup for subtransaction commit/abort.

## Useful greps

- LOCALLOCK consumers:
  `grep -RIn 'LOCALLOCK\s' source/src/backend/storage/lmgr | head -30`
- The LockAcquire path:
  `grep -n 'LOCALLOCK\|locallock' source/src/backend/storage/lmgr/lock.c | head -30`
- ResourceOwner integration:
  `grep -n 'ResourceOwnerRememberLock' source/src/backend/storage/lmgr/lock.c`

## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/storage/lmgr/lock.c`](../files/src/backend/storage/lmgr/lock.c.md) | — | implementation |
| [`src/include/storage/lock.h`](../files/src/include/storage/lock.h.md) | 239 | struct definitions |
| [`src/include/storage/lock.h`](../files/src/include/storage/lock.h.md) | — | definitions |

<!-- /callsites:auto -->
## Cross-references

- `knowledge/idioms/fastpath-locks.md` — the fast-path subsystem
  whose locks have NULL `lock`/`proclock` in LOCALLOCK.
- `knowledge/idioms/lwlock-rank-discipline.md` — LWLocks
  underlying the shared lock-table partitions.
- `knowledge/data-structures/resourceowner.md` — the
  ResourceOwner that owns subtransaction-scoped lock shares.
- `knowledge/subsystems/storage-lmgr.md` — the lmgr
  subsystem implementation.
- `.claude/skills/locking/SKILL.md` — heavyweight-lock
  decision tree; LockAcquire / LockRelease entry points.
- `source/src/include/storage/lock.h` — definitions.
- `source/src/backend/storage/lmgr/lock.c` — implementation.
