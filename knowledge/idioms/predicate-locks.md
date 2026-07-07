# Predicate locks — Serializable Snapshot Isolation (SSI)

Predicate locks track "what did this serializable transaction
*observe*?" without actually blocking writers. When a later
transaction *would* invalidate one of those observations, SSI
detects the dangerous rw-anti-dependency cycle and aborts one of
the conflicting transactions with `ERROR: could not serialize
access due to read/write dependencies`. Used **only** under
`SERIALIZABLE` isolation; ignored under `REPEATABLE READ` and
`READ COMMITTED`.

Anchors:
- `source/src/backend/storage/lmgr/predicate.c` — implementation
  [verified-by-code]
- `source/src/backend/storage/lmgr/README-SSI` — long-form design
  doc (the canonical reference)
- `source/src/include/storage/predicate.h` — public API
- `knowledge/subsystems/storage-lmgr.md` — lmgr context

## What a predicate lock represents

**Not a lock in the conflict-blocking sense.** A predicate lock is
an annotation on the lock manager that says "transaction T read
(or scanned) this relation / page / TID at time `xmin`." Multiple
transactions can hold predicate locks on the same object — they
never block each other.

The conflict check happens at write time and at commit time:

- **At write**: `CheckForSerializableConflictIn(rel, tid, blkno)`
  scans existing predicate locks on the target. Any conflicting
  reader transaction's SSI state gets an `inConflict` edge added.
- **At commit / read**: `CheckForSerializableConflictOut(rel, xid,
  snapshot)` checks the writer's outbound edges.
- **At a third transaction's commit**: if the two edges form a
  `rw-rw` cycle, one transaction must abort.

[verified-by-code `predicate.c:163-185` summary block]

## Granularity hierarchy

Predicate locks come at three granularities:

| Level | Function | When set |
|---|---|---|
| Tuple (TID) | `PredicateLockTID()` | Index-tuple fetch |
| Page | `PredicateLockPage()` | Sequential scan of one block |
| Relation | `PredicateLockRelation()` | Whole-table scan |

The system **auto-coarsens** when a backend accumulates too many
fine-grained locks — e.g. 100 page locks on the same relation
collapse to one relation lock. This is the "lock escalation"
behavior; tunable via `max_pred_locks_per_relation`,
`max_pred_locks_per_page`,
`max_pred_locks_per_transaction`.

## Page-split / page-combine coupling

When an index AM splits a page, every predicate lock on the old
page must extend to the new sibling — a reader who observed key K
on the old page would still observe K after the split.
`PredicateLockPageSplit(oldblkno, newblkno)`
[verified-by-code `predicate.c:3073`] makes that transfer. The
inverse, `PredicateLockPageCombine`
[verified-by-code `predicate.c:3158`], merges locks when pages
merge.

Forgetting to call these on a custom AM = serializable failures
that no one can reproduce locally. Standard index AMs (btree,
hash, gist, gin, brin) wire these correctly.

## The relation-transfer dance

When a relation transitions from "small" (cheap to track at fine
granularity) to "large" (escalation hot), the SSI machinery may
need to **transfer predicate locks to a relation-level lock**. The
`TransferPredicateLocksToHeapRelation()` function
[verified-by-code `predicate.c:165-179`] performs that
consolidation atomically.

## Two-phase commit support

Predicate locks are durable across `PREPARE TRANSACTION`. The
`AtPrepare_PredicateLocks` / `PostPrepare_PredicateLocks` pair
serializes the lock state into a 2PC record;
`predicatelock_twophase_recover` rebuilds it after crash.

## When are predicate locks *not* taken?

- **In `READ COMMITTED` / `REPEATABLE READ`**: SSI is off; no
  predicate locks.
- **In parallel workers** for non-serializable transactions:
  again off.
- **Inside `pg_class` / `pg_attribute` catalog reads**: SSI
  bypasses predicate locks on system catalogs by convention; DDL
  is serialized separately.
- **During VACUUM / autovacuum**: maintenance does not participate
  in SSI's rw-edge graph.

## Implementation hot-spots

- `predicate.c:2497-2530` — relation + page-level lock entry
  points. Acquire `SerializableXactHashLock` briefly.
- `predicate.c:3073-3170` — split/combine transfers. Called from
  inside the index AM's `ambuildempty`/`aminsert` paths.
- `predicate.c:3920-3960` — outbound conflict check at read time.

## Memory & lifetime

Per-transaction predicate-lock state lives in `SerializableXact`
slots in shared memory. The pool size is
`max_predicate_locks_per_transaction × max_connections`. If you
exceed that pool, the offending transaction is aborted with
`ERROR: out of shared memory hint`.

The lifetime is **transaction-commit + horizon**: even after a
serializable transaction commits, its predicate locks linger
until no concurrent transaction could still form a cycle with it.
That's why long-running serializable transactions can pin shared
memory beyond their own duration — see
`ReleasePredicateLocks()` semantics.

## Common review-time concerns

- **Adding a new index AM**: must call `PredicateLockPage` on
  every page read, `PredicateLockPageSplit` on every split, and
  `CheckForSerializableConflictIn` on every write. Missing any of
  these silently breaks serializability.
- **Custom relation scan path**: the `tableam` interface provides
  hooks (`scan_set_tidrange`, etc.); the predicate-lock calls
  should land in the same places as the default heap AM does
  them. Grep `heap_get*` for the canonical sites.
- **Whole-table operations**: prefer
  `PredicateLockRelation(rel, snapshot)` over a million per-page
  locks; the lock-pool budget is global.
- **Don't gate predicate-lock calls on `IsolationLevel`** — the
  predicate-lock functions themselves check
  `SerializableXactHashLock` and no-op outside SSI. Branching at
  the call site means code in `READ COMMITTED` differs from
  `SERIALIZABLE`, which is bug-prone.

## Invariants

- **[INV-1]** Predicate locks NEVER block another transaction;
  they only inform conflict detection.
- **[INV-2]** Page-split / page-combine MUST transfer existing
  locks or serializability is violated.
- **[INV-3]** Auto-coarsening can promote N page locks → 1 relation
  lock; consumers must not assume granularity remains stable.
- **[INV-4]** Per-transaction state lives in fixed-size shared
  memory; over-allocation aborts the transaction.
- **[INV-5]** Predicate locks outlive the transaction commit
  while any concurrent transaction could still cycle with it.

## Useful greps

- All API calls into predicate.c:
  `grep -RIn 'PredicateLock\|CheckForSerializableConflict' source/src/backend | wc -l`
- AM-specific call sites for split/combine:
  `grep -RIn 'PredicateLockPageSplit\|PredicateLockPageCombine' source/src/backend/access`
- Pool-budget GUCs:
  `grep -n 'max_pred_locks' source/src/backend/utils/misc/guc_tables.c`

## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/storage/lmgr/predicate.c`](../files/src/backend/storage/lmgr/predicate.c.md) | — | implementation |
| [`src/include/storage/predicate.h`](../files/src/include/storage/predicate.h.md) | — | public API header |

<!-- /callsites:auto -->

## Scenarios that use me
<!-- scenarios:auto -->

*Auto-derived from direct references + transitive file-overlap.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

_(none detected — this idiom is either cross-cutting infrastructure or an internal helper pattern)_

<!-- /scenarios:auto -->
## Cross-references

- `.claude/skills/locking/SKILL.md` — heavyweight locks (the other
  lock subsystem); SSI sits alongside, not inside.
- `knowledge/subsystems/storage-lmgr.md` — the lock manager
  predicate.c lives in.
- `knowledge/subsystems/access-nbtree.md` — the largest predicate-
  lock-aware AM; canonical reference for AM-side wiring.
- `knowledge/idioms/sinvaladt-broadcast.md` — adjacent subsystem;
  catalogs use sinval, transactions use predicate locks.
- `source/src/backend/storage/lmgr/README-SSI` — design rationale
  + theory citation (Cahill/Röhm/Fekete 2008).
- `source/src/backend/storage/lmgr/predicate.c` — implementation.
- `source/src/include/storage/predicate.h` — public API header.
