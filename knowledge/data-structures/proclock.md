# PROCLOCK — per-(backend, lock) shared-hash entry

`PROCLOCK` is the **per-holder / per-waiter shared-memory
entry**: one for each (backend × LOCK) pair where the backend
either holds a granted lock OR is waiting on the LOCK.
PROCLOCKTAG (a pointer pair) is the lookup key; PROCLOCK is
the row. Linked into both the LOCK's `procLocks` list (for
"who holds this lock?") and the PGPROC's `myProcLocks` list
(for "what does this backend hold?").

Anchors:
- `source/src/include/storage/lock.h:193-198` —
  PROCLOCKTAG struct [verified-by-code]
- `source/src/include/storage/lock.h:200-212` —
  PROCLOCK struct [verified-by-code]
- `source/src/include/storage/lock.h:178-180` —
  "any lock waited on has a PROCLOCK" invariant
  [verified-by-code]
- `knowledge/data-structures/locktag.md` — companion;
  indirectly via PROCLOCK.tag.myLock
- `knowledge/data-structures/lock-struct.md` — companion;
  PROCLOCK lives in LOCK's procLocks list
- `knowledge/data-structures/pgproc-fields.md` — companion;
  PGPROC owns myProcLocks list
- `.claude/skills/locking/SKILL.md` — companion

## The two structs

[verified-by-code `lock.h:193-212`]

```c
typedef struct PROCLOCKTAG
{
    /* NB: this struct contains no padding! */
    LOCK    *myLock;          /* link to per-lockable-object */
    PGPROC  *myProc;          /* link to PGPROC of owner */
} PROCLOCKTAG;

typedef struct PROCLOCK
{
    /* tag */
    PROCLOCKTAG  tag;          /* unique identifier */

    /* data */
    PGPROC      *groupLeader;  /* lock-group leader (or self) */
    LOCKMASK     holdMask;     /* bitmask: modes currently held */
    LOCKMASK     releaseMask;  /* workspace for LockReleaseAll */
    dlist_node   lockLink;     /* LOCK.procLocks list link */
    dlist_node   procLink;     /* PGPROC.myProcLocks list link */
} PROCLOCK;
```

PROCLOCKTAG is two pointers — the (lock, proc) pair. Hashed
byte-wise. The note "no padding" is non-trivial: on some ABIs
two pointers would have alignment padding; PG sizes PGPROC and
LOCK so pointers are word-aligned and packed.

## The dual-list-link pattern

[verified-by-code `lock.h:210-211`]

```c
dlist_node lockLink;       /* in LOCK->procLocks */
dlist_node procLink;       /* in PGPROC->myProcLocks */
```

Every PROCLOCK is linked into TWO lists:
- The owning **LOCK**'s `procLocks` — used to enumerate
  holders/waiters of a specific lock.
- The owning **PGPROC**'s `myProcLocks[partition]` — used to
  enumerate all locks this backend has interest in.

Removing a PROCLOCK requires unlinking from both. The
partitioned per-PGPROC list (`myProcLocks` is an array indexed
by lock-mgr partition) avoids cross-partition contention.

## holdMask — the granted-modes bitmask

```c
LOCKMASK holdMask;
```

Bitmask of lock modes this backend currently holds on this
LOCK. Zero = waiting only, no grant yet.

A PROCLOCK with `holdMask = 0` exists when:
- The backend is waiting on a lock not yet granted.
- The backend just released the lock but the PROCLOCK hasn't
  been recycled yet.

[from-comment `lock.h:181-182`]

> there will be a proclock object, possibly with zero holdMask,
> for any lock that the process is currently waiting on.

## releaseMask — LockReleaseAll workspace

[from-comment `lock.h:185-187`]

> releaseMask is workspace for LockReleaseAll(): it shows the
> locks due to be released during the current call. This must
> only be examined or set by the backend owning the PROCLOCK.

Used during transaction-end / portal-close cleanup:
1. Walk PGPROC's `myProcLocks` lists.
2. For each PROCLOCK, set `releaseMask` = locks to release.
3. Release them.

Single-owner: only the owning backend may set this — no shmem
contention on it.

## groupLeader — parallel-query coordination

[verified-by-code `lock.h:208`]

```c
PGPROC *groupLeader;
```

For parallel-query workers, multiple PROCLOCKs can share a
"lock group" so that:
- A worker's locks don't block siblings or the leader.
- The deadlock detector treats the group as one entity.

For non-parallel locks: `groupLeader == myProc` (self).
For parallel workers: `groupLeader == leader's PGPROC`.

This is what makes parallel workers able to hold relation locks
without conflicting with the leader's locks.

## Lifecycle in the shared hash

```
LockAcquire:
  1. Find or create LOCK entry (hash on LOCKTAG).
  2. Find or create PROCLOCK entry (hash on PROCLOCKTAG).
  3. Link new PROCLOCK into LOCK.procLocks + PGPROC.myProcLocks.
  4. If granted: set holdMask bit; bump LOCK.granted[mode].
     If waiting: bump LOCK.requested[mode], enqueue PGPROC on
                 LOCK.waitProcs.
LockRelease:
  1. Find PROCLOCK.
  2. Clear holdMask bit; decrement LOCK.granted[mode].
  3. If PROCLOCK now has holdMask=0 AND not waiting: free
     PROCLOCK entry; unlink from both lists.
  4. If LOCK now has nGranted=0 AND nRequested=0: free LOCK.
```

The "PROCLOCK with holdMask=0 may stick around" comment refers
to the recycle window — the next acquire may re-use it.

## Hash partitioning

[per `lock-struct` companion]

The proclock hash is partitioned the same way as the lock
hash — `NUM_LOCK_PARTITIONS = 16`, each with its own LWLock.
The partition for a PROCLOCK is determined by the LOCK's
partition (so a given lock and its PROCLOCKs are all in the
same partition; releases don't cross partitions).

## Common review-time concerns

- **PROCLOCK exists during waits** — holdMask = 0 is normal.
- **Both list links must be maintained** — forgetting one
  corrupts the lists.
- **groupLeader vs myProc** — confusion causes parallel
  workers to deadlock.
- **releaseMask is single-owner** — don't touch from outside.
- **PROCLOCKTAG has no padding** — adding fields to PGPROC or
  LOCK could change padding; verify.
- **Recycle window for holdMask=0 PROCLOCKs** — don't assume
  freshly-found PROCLOCK is the one this acquire created.

## Invariants

- **[INV-1]** One PROCLOCK per (PGPROC, LOCK) pair with any
  interest.
- **[INV-2]** Linked into both LOCK.procLocks and
  PGPROC.myProcLocks lists.
- **[INV-3]** holdMask = 0 acceptable; means waiting or
  pending recycle.
- **[INV-4]** releaseMask is single-owner workspace.
- **[INV-5]** groupLeader = self for non-parallel; = leader
  for parallel workers.

## Useful greps

- Hash entry users:
  `grep -RIn 'LockMethodProcLockHash\|hash_search.*PROCLOCK' source/src/backend/storage/lmgr/lock.c | head -10`
- groupLeader logic:
  `grep -RIn 'groupLeader' source/src/backend/storage/lmgr | head -10`
- LockReleaseAll:
  `grep -n 'LockReleaseAll' source/src/backend/storage/lmgr/lock.c | head -5`


## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/storage/lmgr/lock.c`](../files/src/backend/storage/lmgr/lock.c.md) | — | lifecycle |
| [`src/include/storage/lock.h`](../files/src/include/storage/lock.h.md) | 178 | "any lock waited on has a PROCLOCK" invariant |
| [`src/include/storage/lock.h`](../files/src/include/storage/lock.h.md) | 193 | PROCLOCKTAG struct |
| [`src/include/storage/lock.h`](../files/src/include/storage/lock.h.md) | 200 | PROCLOCK struct |

<!-- /callsites:auto -->

## Cross-references

- `knowledge/data-structures/locktag.md` — accessed via
  PROCLOCK.tag.myLock->tag.
- `knowledge/data-structures/lock-struct.md` — PROCLOCK in
  LOCK.procLocks.
- `knowledge/data-structures/pgproc-fields.md` — myProcLocks
  array.
- `knowledge/data-structures/locallock.md` — backend-local
  state pointing here.
- `knowledge/idioms/deadlock-detection.md` — walks PROCLOCKs
  + waitProcs.
- `knowledge/idioms/parallel-worker-coordination.md` —
  groupLeader semantics.
- `knowledge/idioms/fastpath-locks.md` — fastpath skips
  PROCLOCK creation.
- `knowledge/subsystems/storage-lmgr.md` — lock manager.
- `.claude/skills/locking/SKILL.md` — companion.
- `source/src/include/storage/lock.h:193-212` — full
  structs.
- `source/src/backend/storage/lmgr/lock.c` — lifecycle.
