# LOCK — shared lock-mgr hash entry

`LOCK` is the **shared-memory hash entry** for a lockable
object. One entry per LOCKTAG that has at least one outstanding
lock-mgr request (granted or waiting). Holds the per-mode
grant + wait masks, the list of PROCLOCKs (one per holder /
waiter), and the count arrays driving the conflict-detection
state machine.

Anchors:
- `source/src/include/storage/lock.h:139-155` —
  LOCK struct [verified-by-code]
- `source/src/include/storage/lock.h:142` —
  tag field (the LOCKTAG hash key) [verified-by-code]
- `source/src/include/storage/lock.h:147` —
  procLocks list [verified-by-code]
- `source/src/include/storage/lock.h:148` —
  waitProcs queue [verified-by-code]
- `knowledge/data-structures/locktag.md` — companion;
  the hash key
- `knowledge/data-structures/proclock.md` — companion;
  per-holder per-lock state
- `knowledge/data-structures/locallock.md` — companion
  (already on main); backend-local per-lock state
- `.claude/skills/locking/SKILL.md` — companion

## The struct

[verified-by-code `lock.h:139-155`]

```c
typedef struct LOCK
{
    /* hash key */
    LOCKTAG     tag;          /* unique identifier of lockable object */

    /* data */
    LOCKMASK    grantMask;    /* bitmask: types already granted */
    LOCKMASK    waitMask;     /* bitmask: types being waited for */
    dlist_head  procLocks;    /* list of PROCLOCKs for this LOCK */
    dclist_head waitProcs;    /* PGPROCs waiting on this lock */
    int         requested[MAX_LOCKMODES];   /* per-mode request counts */
    int         nRequested;   /* sum of requested[] */
    int         granted[MAX_LOCKMODES];     /* per-mode grant counts */
    int         nGranted;     /* sum of granted[] */
} LOCK;
```

The hash table is keyed on `tag` (a LOCKTAG); the rest is data.

## grantMask + waitMask — the bitmasks

```c
LOCKMASK grantMask;
LOCKMASK waitMask;
```

`LOCKMASK` is `uint32`. Each bit represents a lock mode (1 =
AccessShareLock, 2 = RowShareLock, ..., 7 = ExclusiveLock,
8 = AccessExclusiveLock). The masks:
- `grantMask` — OR of all modes currently granted on this
  LOCK by anyone.
- `waitMask` — OR of all modes that have at least one waiter.

Conflict detection: a new request for mode M conflicts if
`conflictTab[M] & grantMask` is non-zero. That tells the
lock-mgr "wait or grant?".

## procLocks list — per-holder state

[verified-by-code `lock.h:147`]

```c
dlist_head procLocks;
```

A doubly-linked list of PROCLOCK structs. **One PROCLOCK per
(backend × lock) pair**, holding:
- Which modes the backend holds (`PROCLOCK.holdMask`).
- The backend's PGPROC pointer (`PROCLOCKTAG.myProc`).

To list all holders of a lock: walk `procLocks`. To check if
backend B holds the lock: search `procLocks` for one with
`tag.myProc == B`.

## waitProcs queue — FIFO wait list

[verified-by-code `lock.h:148`]

```c
dclist_head waitProcs;
```

A `dclist` (doubly-linked circular list) of PGPROCs waiting on
this lock. FIFO ordering for non-recursive waits; the deadlock
detector may re-order to break cycles.

When a lock-holder releases, `ProcLockWakeup` walks this list
and grants whichever waiters' modes are now compatible.

## requested[] / granted[] — per-mode counts

```c
int requested[MAX_LOCKMODES];     /* [0..MAX_LOCKMODES-1] */
int nRequested;                    /* sum */
int granted[MAX_LOCKMODES];
int nGranted;
```

`requested[mode]` = number of distinct requests (grants +
waits) for that mode. `granted[mode]` = number actually held.

The `nGranted == 0` test is the "any holders left?" check that
decides whether to free the LOCK entry on release.

## LOCK_LOCKMETHOD + LOCK_LOCKTAG macros

[verified-by-code `lock.h:156-157`]

```c
#define LOCK_LOCKMETHOD(lock) ((LOCKMETHODID) (lock).tag.locktag_lockmethodid)
#define LOCK_LOCKTAG(lock) ((LockTagType) (lock).tag.locktag_type)
```

Convenience accessors for the lockmethod (default vs user) and
the tag type (RELATION, TUPLE, etc.) without manual struct
navigation.

## Lifecycle in the shared hash

```
LockAcquire:
  hash_search(LockMethodLockHash, &tag, HASH_ENTER, &found)
  if (!found): zero-init the LOCK entry
  ...
LockRelease:
  hash_search(..., HASH_FIND)
  decrement nGranted etc.
  if (nGranted == 0 && nRequested == 0):
    hash_search(..., HASH_REMOVE)  -- free the entry
```

LOCK entries are created on first request, destroyed when no
more holders / waiters. The hash uses `dynahash`.

## Hash partitioning

[per `lwlock-rank-discipline`]

The lock-mgr hash is partitioned into 16 segments (controlled
by `NUM_LOCK_PARTITIONS`). Each partition has its own LWLock
(LockMgrLock partition lock). LOCKTAG hashes to a partition
via the low bits of the hash value; the corresponding LWLock
must be held to read or modify entries in that partition.

This is why locking takes an `LWLockAcquire` on the lock-mgr
partition LWLock as a prelude to hash search.

## Common review-time concerns

- **LOCK lives in shared memory** — only the per-partition
  LWLock protects mutations.
- **grantMask + counts must be kept in sync** — when adjusting
  granted[mode], also adjust grantMask and nGranted.
- **waitProcs ordering is FIFO** by default; deadlock detector
  re-orders.
- **Don't free a LOCK with nonzero nRequested** — check both
  granted AND requested.
- **The struct size is tuned** for shared-mem allocation;
  avoid adding fields.
- **MAX_LOCKMODES is 10** — keep code agnostic to specific
  value where possible.

## Invariants

- **[INV-1]** LOCK keyed on LOCKTAG in shared hash; one per
  lockable object with active interest.
- **[INV-2]** `grantMask` = OR of granted modes; kept in sync
  with `granted[]`.
- **[INV-3]** `procLocks` lists every backend with an interest
  (granted OR waiting).
- **[INV-4]** `waitProcs` is FIFO unless deadlock detector
  rearranges.
- **[INV-5]** LOCK entry freed when nGranted + nRequested ==
  0.

## Useful greps

- Hash entry users:
  `grep -RIn 'LockMethodLockHash\|hash_search.*LOCK' source/src/backend/storage/lmgr/lock.c | head -10`
- Grant + wait machinery:
  `grep -n 'LockAcquire\|LockRelease\|ProcLockWakeup' source/src/backend/storage/lmgr/lock.c | head -10`

## Cross-references

- `knowledge/data-structures/locktag.md` — the LOCKTAG hash
  key.
- `knowledge/data-structures/proclock.md` — per-(lock, proc)
  entry.
- `knowledge/data-structures/locallock.md` — backend-local
  copy (already on main).
- `knowledge/data-structures/pgproc-fields.md` — PGPROC holds
  waitProcs node + procLocks list link.
- `knowledge/idioms/fastpath-locks.md` — fastpath bypasses
  the shared LOCK entry entirely.
- `knowledge/idioms/deadlock-detection.md` — uses
  procLocks + waitProcs to walk dependency graph.
- `knowledge/idioms/lwlock-rank-discipline.md` — lock-mgr
  partition LWLocks.
- `knowledge/subsystems/storage-lmgr.md` — lock manager.
- `.claude/skills/locking/SKILL.md` — companion.
- `source/src/include/storage/lock.h:139` — full struct.
- `source/src/backend/storage/lmgr/lock.c` — LockAcquire +
  LockRelease + ProcLockWakeup.
