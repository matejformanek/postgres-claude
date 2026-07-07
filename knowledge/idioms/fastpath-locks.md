# Fast-path locks — relation-lock optimization

The fast-path lock mechanism accelerates acquisition and release of
**relation locks** that rarely conflict — typical
`AccessShareLock` / `RowShareLock` / `RowExclusiveLock` on user tables.
Skipping the main lock-manager hash table for the common no-conflict
case is the difference between a couple of atomic ops per query and a
LWLock partition acquisition + hashtable lookup.

Anchors:
- `source/src/backend/storage/lmgr/lock.c` — implementation
  [verified-by-code §"The fast-path lock mechanism" comment block]
- `source/src/include/storage/proc.h` — `PGPROC` per-backend state
- `knowledge/data-structures/pgproc-fields.md` — the surrounding
  `PGPROC` fields
- `.claude/skills/locking/SKILL.md` — the heavyweight-lock
  decision tree

## What "fast-path eligible" means

A relation lock is fast-path-eligible iff:

1. The relation is **unshared** (not in `pg_catalog`'s shared
   relations like `pg_database`).
2. The backend is **bound to a database** (not the startup /
   autovacuum-launcher processes that operate cross-DB).
3. The lock mode is one of `AccessShareLock`, `RowShareLock`,
   `RowExclusiveLock` (the three that don't self-conflict and don't
   conflict with each other).
4. The backend currently holds no fast-path slot for this OID at a
   conflicting mode.

`ShareUpdateExclusiveLock` is **excluded** despite being
non-conflicting with the three above — it's self-conflicting, so it
can't use the fast-path. But because it doesn't conflict with the
three modes that do, it can be ignored entirely by fast-path
decisions.

[from-comment `lock.c` "The fast-path lock mechanism is concerned only
with relation locks on unshared relations by backends bound to a
database..."]

## Per-backend storage

Each `PGPROC` carries:

```c
uint64 *fpLockBits;   /* lock modes held for each fast-path slot */
Oid    *fpRelId;      /* slots for rel oids */
```

[verified-by-code `proc.h:331-332`]

These arrays are sized `FastPathLockSlotsPerBackend()` = `16 *
FastPathLockGroupsPerBackend`. `FP_LOCK_SLOTS_PER_GROUP = 16` is
fixed [verified-by-code `proc.h:102`]; the number of groups is set
once at postmaster startup based on `max_locks_per_transaction`,
rounded to a power of two.

Each slot is 1 OID + 3 bits of lock modes (mask for AccessShare /
RowShare / RowExclusive). 16 slots per group; multiple groups per
backend to reduce collisions.

## Group selection — the hash

```c
#define FAST_PATH_REL_GROUP(rel) \
    (((uint64) (rel) * 49157) & (FastPathLockGroupsPerBackend - 1))
```

[verified-by-code `lock.c:218-221`]

`49157` is a prime not too close to a power of two — spreads OIDs
even when allocated sequentially.

Given the group, the slot index within the group is searched
linearly. With 16 slots per group, the search is cache-friendly.

## The bit layout per slot

3 bits of lock modes per slot, offset by
`FAST_PATH_LOCKNUMBER_OFFSET = 1` (lock mode 1 = `AccessShareLock`,
mode 2 = `RowShareLock`, mode 3 = `RowExclusiveLock`).

[verified-by-code `lock.c:251-263`]

A slot's 3 bits in the per-group `fpLockBits` word:
- bit 0 (offset 0): AccessShareLock held
- bit 1 (offset 1): RowShareLock held
- bit 2 (offset 2): RowExclusiveLock held

The `FAST_PATH_BIT_POSITION(n, l)` macro computes the bit index in
the 64-bit `fpLockBits[group]` word for slot `n`, lock mode `l`.
3 bits × 16 slots = 48 bits used per word.

## Acquisition

`FastPathGrantRelationLock(relid, lockmode)`:

1. Compute group via `FAST_PATH_REL_GROUP(relid)`.
2. Linear scan the 16 slots in that group looking for either a slot
   already assigned to `relid` (set the bit) or an empty slot
   (assign + set the bit).
3. If neither found → the slot table is full for that group → fall
   through to the slow path (main lock manager hash + LWLock
   partition).

Acquisition is one cache-line read + one atomic write on success.
No LWLock partition acquired.

## Release

`FastPathUnGrantRelationLock(relid, lockmode)`: walk the group's
slots looking for `relid`, clear the matching bit, and zero the OID
slot if all 3 bits cleared.

## When fast-path is forced to transfer to the main lock manager

`FastPathTransferRelationLocks(...)` is called when:

- Another backend wants a lock mode that conflicts with one of the
  three fast-path modes (e.g. `AccessExclusiveLock`, `ShareLock`,
  `ShareRowExclusiveLock`).
- The conflicting backend must KNOW about the fast-path lock to
  block correctly. Fast-path bits are per-backend; they're invisible
  to other backends unless explicitly transferred.

The transfer walks every backend's fast-path slots that match the
target OID, copies them into the main lock-manager hash, and clears
the fast-path bits. From then on, locks on that relation use the
slow path.

This is the **degraded mode** — once a relation transfers to the
main lock manager, it stays there for the rest of the postmaster's
lifetime (or until vacuum removes the entries). Workloads that
hammer `ALTER TABLE` / `ANALYZE` / `DROP` on user tables can
inadvertently push hot relations onto the slow path.

## Per-mode fast-path local counter

`FastPathLocalUseCounts[FP_LOCK_GROUPS_PER_BACKEND_MAX]` — one
counter per group, tracking how full the group is locally. Used to
short-circuit the linear scan when a group has no slots used (skip
the search entirely).

## Performance implication

A typical `SELECT` on a user table acquires `AccessShareLock` via
fast-path: ~10 ns of atomic ops. The slow path costs ~500 ns
(LWLock partition acquire + hashtable lookup + partition release).
At 100K queries per second per backend, fast-path is the
difference between 1 ms and 50 ms per second of CPU spent on
lock acquisition.

## Common review-time concerns

- **Adding a new heavyweight lock mode** to relations would need
  the eligibility predicate re-evaluated. If the new mode doesn't
  conflict with `AccessShareLock` / `RowShareLock` / `RowExclusiveLock`
  it's fine; if it does, it forces fast-path-transfer behavior.
- **Sizing `max_locks_per_transaction`** — too small, groups fill up
  and locks fall through to the slow path. Too large, per-backend
  memory bloats. Default 256 is usually fine.
- **The `IsRelationExtensionLockHeld` static guard** —
  `LOCKTAG_RELATION_EXTEND` excludes fast-path AND excludes any
  other heavyweight-lock acquisition while held. This is a separate
  optimization-and-correctness mechanism documented adjacent to the
  fast-path code; don't conflate the two.

## Invariants

- **[INV-1]** Only `AccessShareLock` / `RowShareLock` /
  `RowExclusiveLock` use fast-path. New lock modes need explicit
  consideration.
- **[INV-2]** `ShareUpdateExclusiveLock` is excluded but
  non-conflicting; safe to ignore.
- **[INV-3]** Shared relations (cross-DB) never use fast-path.
- **[INV-4]** Once a relation is transferred to the main lock
  manager, it doesn't return to fast-path during the postmaster's
  lifetime.
- **[INV-5]** `FastPathLockGroupsPerBackend` is a power of two,
  set at postmaster startup based on `max_locks_per_transaction`.

## Useful greps

- The eligibility predicate:
  `grep -n 'EligibleForRelationFastPath' source/src/backend/storage/lmgr/lock.c`
- Fast-path transfer sites:
  `grep -RIn 'FastPathTransferRelationLocks' source/src/backend`
- PGPROC fields:
  `grep -n 'fpLockBits\|fpRelId' source/src/include/storage/proc.h`



## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/storage/lmgr/lock.c`](../files/src/backend/storage/lmgr/lock.c.md) | — | implementation [verified-by-code §"The fast-path lock mechanism" comment block] |
| [`src/include/storage/proc.h`](../files/src/include/storage/proc.h.md) | — | PGPROC per-backend state |

<!-- /callsites:auto -->

## Cross-references

- `.claude/skills/locking/SKILL.md` — heavyweight-lock decision tree; this fast-path is one of the optimizations applied to relation locks.
- `knowledge/data-structures/pgproc-fields.md` — surrounding `PGPROC` layout including the `fpLockBits` / `fpRelId` arrays.
- `knowledge/subsystems/storage-lmgr.md` — the lock-manager subsystem that fast-path bypasses on the common case.
- `source/src/backend/storage/lmgr/README` — the long-form lock-manager design doc.
