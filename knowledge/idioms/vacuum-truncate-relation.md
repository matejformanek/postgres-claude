# VACUUM truncate-relation — shrinking the heap file

After VACUUM has freed all the tuples at the tail of a heap
relation, it may **truncate** the on-disk file to release the
empty space back to the filesystem. The truncate is not free:
it requires an exclusive lock briefly, an SSI / replication
guard, a WAL record, and careful ordering against smgr / FSM
state. Knowing the sequence is essential for any work in
VACUUM, smgr, or large-table operations.

Anchors:
- `source/src/backend/catalog/storage.c:282-358` —
  RelationTruncate [verified-by-code]
- `source/src/backend/catalog/storage.c:422` —
  smgrtruncate call [verified-by-code]
- `source/src/backend/access/heap/vacuumlazy.c` —
  lazy_truncate_heap caller
- `knowledge/idioms/relation-extension-lock.md` — companion
  (extension lock conflicts with truncate)
- `knowledge/idioms/checkpoint-coordination.md` — companion
  (truncate vs checkpoint ordering)
- `knowledge/idioms/vacuum-skip-pages.md` — companion
- `.claude/skills/locking/SKILL.md` — companion

## The sequence

[verified-by-code `vacuumlazy.c:lazy_truncate_heap`]

Lazy VACUUM truncates only when:
- Trailing pages are confirmed all-empty (via VM + recheck).
- The relation isn't a "large" table being concurrently
  modified (avoid AccessExclusiveLock contention).
- VACUUM holds the relation lock high enough to upgrade.

The flow:

```
1. Lazy VACUUM detects trailing N empty pages.
2. Try to upgrade RelationLock to AccessExclusiveLock
   (ConditionalLockRelation — gives up if blocked).
3. Re-verify trailing pages still empty under the lock
   (concurrent insertions may have filled them).
4. count_nondeletable_pages — walks tail confirming.
5. RelationTruncate(rel, new_nblocks).
6. Release AccessExclusiveLock.
```

The conditional lock-upgrade is critical: VACUUM gives up the
truncate attempt rather than blocking concurrent DML.

## RelationTruncate — the catalog-storage call

[verified-by-code `storage.c:282-358`]

```c
void RelationTruncate(Relation rel, BlockNumber nblocks);
```

Body (compressed):

```c
1. AtAbort_Pendingsync sentinel ← we may need to roll back.
2. Determine which forks to truncate (main, fsm, vm, init).
3. WAL log: XLOG_SMGR_TRUNCATE with all-forks block counts.
4. For each fork:
     smgrtruncate(rel->rd_smgr, forks, nforks, old_blocks, blocks);
5. Update FSM / VM for the new block count.
6. AtTruncate_RelationBuffers — drop now-orphaned shared buffers.
7. AtEOXact_Pendingsync — queue catalog cleanup for commit.
```

The smgrtruncate call physically calls `ftruncate(fd, ...)` on
each fork; the catalog-side accounting is bookkeeping around it.

## The WAL record + replay

[from-comment `storage.c:336-358`]

> Make sure that a concurrent checkpoint can't complete while
> truncation is in progress.
>
> The truncation operation might drop buffers that the checkpoint
> otherwise would have flushed. If it does, then it's essential
> that the files actually get truncated on disk before the
> checkpoint record is written. ...

The truncate WAL record is written BEFORE the smgrtruncate
calls. Why: if a crash happens between WAL write and physical
truncate, recovery replays the truncate and the on-disk state
becomes consistent.

Recovery handler: `smgr_redo` → `XLOG_SMGR_TRUNCATE` → calls
`smgrtruncate` with the WAL-record's block counts.

## Concurrency with the extension lock

[per `relation-extension-lock` companion]

`RelationTruncate` does NOT take the extension lock — it relies
on holding `AccessExclusiveLock` on the relation, which blocks
any backend that would want the extension lock. The exclusive
lock is the discipline.

This is why the **conditional upgrade** in `lazy_truncate_heap`
matters: a concurrent INSERT holding the extension lock
prevents the upgrade, and VACUUM gives up.

## SSI predicate-lock interaction

Active SSI (Serializable Snapshot Isolation) backends may hold
predicate locks on the relation. `RelationTruncate` ignores
SSI locks for VACUUM's case (the freed pages have no live
tuples), but for DDL TRUNCATE (`TRUNCATE TABLE` SQL), the
predicate locks are dropped explicitly.

## Replication considerations

[per `walsender-state-machine`]

The truncate WAL record is decoded by logical replication output
plugins, but it's typically filtered out (logical reps don't see
physical truncate; the logical level sees DELETE for each row).

Physical replication: replays the truncate as part of normal WAL
apply, releasing standby disk space.

## What's NOT truncated

[from-code]

- The catalog row stays (rel still exists; just smaller).
- The `pg_class.relpages` is updated separately by
  `vac_update_relstats`.
- `relfilenumber` doesn't change — it's the same file, just
  shorter.

Compare with VACUUM FULL / CLUSTER which create a NEW
relfilenumber.

## Common review-time concerns

- **AccessExclusiveLock conditional upgrade** — VACUUM never
  forces this; auto/manual VACUUM gives up if blocked.
- **WAL record precedes physical truncate** — durability +
  recovery invariant.
- **Buffer drop after truncate** — orphaned buffers from
  freed blocks get evicted by `AtTruncate_RelationBuffers`.
- **All-fork truncate is atomic** in one WAL record — partial
  truncate is undefined.
- **Don't truncate during a checkpoint** — explicit synch.
- **Recovery replays truncate** — crash-safe via WAL.

## Invariants

- **[INV-1]** Conditional lock upgrade; lazy VACUUM never
  blocks on it.
- **[INV-2]** Truncate WAL record precedes smgrtruncate.
- **[INV-3]** AtTruncate_RelationBuffers evicts now-orphaned
  buffers.
- **[INV-4]** All forks truncated under one WAL record.
- **[INV-5]** relfilenumber unchanged; only block count
  shrinks.

## Useful greps

- The main call:
  `grep -n 'RelationTruncate\|lazy_truncate_heap' source/src/backend/catalog/storage.c source/src/backend/access/heap/vacuumlazy.c | head -10`
- Recovery side:
  `grep -n 'XLOG_SMGR_TRUNCATE\|smgr_redo' source/src/backend/catalog/storage.c | head -5`
- Buffer drop:
  `grep -n 'AtTruncate_RelationBuffers' source/src/backend/storage/buffer/bufmgr.c | head -5`

## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/access/heap/vacuumlazy.c`](../files/src/backend/access/heap/vacuumlazy.c.md) | — | lazy_truncate_heap caller |
| [`src/backend/catalog/storage.c`](../files/src/backend/catalog/storage.c.md) | 282 | RelationTruncate entry |
| [`src/backend/catalog/storage.c`](../files/src/backend/catalog/storage.c.md) | 422 | smgrtruncate call |

<!-- /callsites:auto -->

## Scenarios that use me
<!-- scenarios:auto -->

*Auto-derived from direct references + transitive file-overlap.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

- [`add-new-system-catalog-column`](../scenarios/add-new-system-catalog-column.md)

<!-- /scenarios:auto -->
## Cross-references

- `knowledge/idioms/relation-extension-lock.md` — extension
  lock conflicts with AccessExclusiveLock truncate.
- `knowledge/idioms/checkpoint-coordination.md` — truncate
  ordering vs checkpoint.
- `knowledge/idioms/vacuum-skip-pages.md` — VM-driven scan
  skipping during lazy VACUUM.
- `knowledge/idioms/wal-record-construction.md` —
  XLOG_SMGR_TRUNCATE format.
- `knowledge/data-structures/relfilelocator.md` —
  relfilenumber identity preserved.
- `knowledge/subsystems/storage-buffer.md` — buffer eviction
  during truncate.
- `knowledge/subsystems/access-heap.md` — vacuumlazy.c.
- `.claude/skills/locking/SKILL.md` — companion (lock
  upgrade discipline).
- `source/src/backend/catalog/storage.c:282` —
  RelationTruncate entry.
