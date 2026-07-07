# Relation extension lock — exclusive grow-table guard

The **relation extension lock** is a heavyweight lock acquired
to safely add new blocks to a relation. Without it, two backends
simultaneously running `heap_insert` could both call
`smgrextend` on the same block number and corrupt the relation.
Heavyweight (taken via the lock manager), short-held (typically
microseconds per extension), and one of the few non-tuple
heavyweight locks held during normal DML.

Anchors:
- `source/src/backend/storage/lmgr/lmgr.c:414-455` —
  LockRelationForExtension + Conditional* +
  RelationExtensionLockWaiterCount [verified-by-code]
- `source/src/backend/storage/lmgr/lmgr.c:471-490` —
  UnlockRelationForExtension [verified-by-code]
- `source/src/include/storage/lmgr.h` — public API
- `knowledge/idioms/checkpoint-coordination.md` — companion
  (smgr discipline)
- `knowledge/idioms/fastpath-locks.md` — companion (most
  relation locks fastpath; extension lock does NOT)
- `.claude/skills/locking/SKILL.md` — companion

## When it's taken

[from-code `lmgr.c:414-432`]

```c
void LockRelationForExtension(Relation relation, LOCKMODE lockmode);
bool ConditionalLockRelationForExtension(Relation relation, LOCKMODE lockmode);
int  RelationExtensionLockWaiterCount(Relation relation);
void UnlockRelationForExtension(Relation relation, LOCKMODE lockmode);
```

`LockRelationForExtension` uses lockmode `ExclusiveLock` (mode
7) on a `LOCKTAG_RELATION_EXTEND` tag. Callers:

- `RelationGetBufferForTuple` — when inserting and the FSM
  doesn't already have a non-full target page.
- `index_build` / bulk-load paths — when extending an index.
- `RelationCopyStorage` / CLUSTER / VACUUM FULL.

It is **NOT** taken for every INSERT; only when the backend
must actually extend the file. Most inserts find a non-full
page via FSM and never touch the extension lock.

## Why it's not in the relation's tuple-lock space

The extension lock has its own LOCKTAG (`LOCKTAG_RELATION_EXTEND`
distinct from `LOCKTAG_RELATION`) so that:

- It doesn't conflict with normal DML on the relation (which
  takes `RowExclusiveLock` on `LOCKTAG_RELATION`).
- Multiple readers / writers can proceed while one backend
  extends.

A backend holding the extension lock blocks ONLY other
backends trying to extend the same relation.

## Conditional acquisition + waiter count

[verified-by-code `lmgr.c:436-468`]

```c
bool ConditionalLockRelationForExtension(...)
int  RelationExtensionLockWaiterCount(Relation relation)
```

The conditional variant returns false immediately if the lock
isn't available (skipping the wait). Used in batch-extend
heuristics: if multiple waiters are queued, the lock-holder
extends N blocks at once to amortize.

`RelationExtensionLockWaiterCount` is the heuristic input —
"how many backends are waiting to extend?" — driving the
multi-block extension policy in `RelationAddBlocks`.

## The multi-block extension pattern

[from `relation-extension` operational lore]

When `RelationExtensionLockWaiterCount > 0`, the holder
extends *multiple* blocks (typically 8–512 depending on
config + load) so each waiter can pick up one without taking
the lock again. Reduces lock contention on write-heavy loads
with many concurrent INSERTs.

The block-count is bounded by `effective_io_concurrency` and
relation-extension heuristics in
`RelationGetBufferForTuple` / `RelationExtendBufferedBy`.

## Coordinator-free batch extend

Modern PG (16+) implements `RelationExtendBufferedBy`, which
allocates **B blocks atomically** in one extension-lock
acquisition. This is the workhorse for INSERT/COPY hot
paths.

[verified-by-code `bufmgr.c` `ExtendBufferedRel*` family]

## What the lock protects

[from-comment `lmgr.h`]

- The file's **block count** as known to FileNode.
- The smgr-level "next block number" used by `smgrnblocks`.
- Concurrent shared-buffer reservations for the new blocks.

After `smgrextend` returns and the extension lock is released,
the new blocks are visible to all backends (via FSM or sequential
scan).

## Why extension lock isn't fastpath

[per `fastpath-locks` idiom]

Fastpath locks bypass the lock manager hash table for
relation locks held by `RowExclusiveLock` and below. The
extension lock is `ExclusiveLock` (mode 7), which exceeds
the fastpath ceiling — so it always goes through the
heavyweight LWLock-protected lock-manager hash.

This is intentional: the extension lock is rare per-tuple
but critical for correctness, so the extra cost is acceptable.

## Cleanup at abort

On error / abort during DML, if the backend held the extension
lock and had already called `smgrextend`, the new block may be
"orphaned" — allocated in the file but not in any catalog. On
next VACUUM or restart, the file is truncated back if the
catalog says fewer blocks exist.

The lock itself is released by the standard `LockReleaseAll`
in `AbortTransaction`.

## Performance characteristics

- Held for microseconds typically (one smgrextend call + buffer
  reservation).
- Batch-extend amortizes when contention is detected.
- A "stuck" extension lock points to:
  - A truly stalled smgrextend (slow disk, full FS).
  - A backend holding it across an unrelated wait (bug).
  - Misconfiguration (e.g., low `wal_buffers` causing WAL
    contention DURING extension).

## Common review-time concerns

- **Don't hold the extension lock across user code** — held
  only across smgr / buffer-pool calls.
- **Conditional + retry** for low-priority extension paths.
- **Batch-extend respects waiter count** — single-block
  extension under contention is a perf regression.
- **AbortTransaction releases it** as part of LockReleaseAll;
  no manual cleanup.
- **Don't bypass for "perf" reasons** — concurrent smgrextend
  on same block = corruption.
- **One per relation**, not per fork — index/heap/fsm/vm
  extensions of the same relation contend.

## Invariants

- **[INV-1]** Extension lock = `LOCKTAG_RELATION_EXTEND` +
  `ExclusiveLock`; distinct from relation tuple-lock space.
- **[INV-2]** Held only across smgr-extend + buffer-reserve;
  never across user code.
- **[INV-3]** Batch-extend triggered by waiter count > 0.
- **[INV-4]** Always heavyweight (above fastpath ceiling).
- **[INV-5]** Released via standard LockReleaseAll at abort.

## Useful greps

- Lock entrypoints:
  `grep -n 'LockRelationForExtension\|UnlockRelationForExtension' source/src/backend/storage/lmgr/lmgr.c | head -10`
- Callers:
  `grep -RIn 'LockRelationForExtension' source/src/backend | head -15`
- Batch extend:
  `grep -RIn 'ExtendBufferedRel\|RelationExtendBufferedBy' source/src/backend | head -10`



## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/access/heap/hio.c`](../files/src/backend/access/heap/hio.c.md) | — | RelationGetBufferForTuple uses the lock |
| [`src/backend/storage/lmgr/lmgr.c`](../files/src/backend/storage/lmgr/lmgr.c.md) | 414 | LockRelationForExtension + Conditional + RelationExtensionLockWaiterCount |
| [`src/backend/storage/lmgr/lmgr.c`](../files/src/backend/storage/lmgr/lmgr.c.md) | 471 | UnlockRelationForExtension |
| [`src/include/storage/lmgr.h`](../files/src/include/storage/lmgr.h.md) | — | public API |

<!-- /callsites:auto -->

## Cross-references

- `knowledge/idioms/checkpoint-coordination.md` — extension
  via smgr; checkpoint ordering matters.
- `knowledge/idioms/fastpath-locks.md` — explains why
  extension lock isn't fastpath.
- `knowledge/idioms/visibility-map-update.md` — VM extension
  takes its own version of the lock.
- `knowledge/data-structures/locallock.md` — generic
  heavyweight-lock state.
- `knowledge/subsystems/storage-lmgr.md` — lock manager
  overview.
- `.claude/skills/locking/SKILL.md` — companion.
- `source/src/backend/storage/lmgr/lmgr.c:414-490` — entry
  points.
- `source/src/backend/access/heap/hio.c` —
  RelationGetBufferForTuple uses the lock.
