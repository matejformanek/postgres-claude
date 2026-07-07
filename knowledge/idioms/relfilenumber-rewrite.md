# RelFileNumber rewrite — when relations get new on-disk identities

PostgreSQL's `pg_class.oid` is the **logical** identity of a
relation; `pg_class.relfilenode` (a `RelFileNumber`) is its
**physical** on-disk identity. The two normally match, but
several operations (REINDEX, CLUSTER, VACUUM FULL,
ALTER TABLE rewrites) assign a NEW relfilenumber while keeping
the logical OID. The old file is left for cleanup; the
relation now points at fresh storage.

Anchors:
- `source/src/backend/utils/cache/relcache.c:3761-3775
  RelationSetNewRelfilenumber` [verified-by-code]
- `source/src/include/storage/relfilelocator.h` —
  RelFileNumber type
- `knowledge/data-structures/relfilelocator.md` — companion
  data-structure doc

## What triggers a rewrite

| Operation | Reason |
|---|---|
| `REINDEX` | Rebuild index from scratch; new file |
| `CLUSTER` | Re-order heap by index; new file |
| `VACUUM FULL` | Compact heap; new file |
| `ALTER TABLE ... TYPE` (some) | Column-type change requires re-scan; new file |
| `TRUNCATE` | Drop and recreate; new file (under MVCC) |
| `ALTER COLUMN ... SET DEFAULT` (some forms) | Some forms force rewrite |

The unifying property: the rewrite path **drops the old
contents and writes new ones** — it would be unsafe to write
into the existing file because concurrent readers might be
mid-scan.

## RelationSetNewRelfilenumber

[verified-by-code `relcache.c:3775`]

```c
void
RelationSetNewRelfilenumber(Relation relation, char persistence);
```

The function:
1. Allocate a fresh `RelFileNumber` from the global
   counter.
2. Create the new file on disk (or mark for creation).
3. Update `pg_class.relfilenode` for this relation.
4. The OLD relfilenumber's file is left for VACUUM /
   recovery cleanup.

The `persistence` parameter ('p' permanent, 'u' unlogged,
't' temp) determines the WAL semantics — permanent rewrites
emit WAL; unlogged don't.

## Why not overwrite the existing file?

Two reasons:

1. **Concurrent readers.** A backend running a slow query
   may still be mid-scan of the old file. Overwriting would
   corrupt their result.
2. **Rollback.** A failed REINDEX should leave the original
   intact. A fresh file lets rollback drop the new and
   keep the old.

The two-file approach: new file is built atop-rolled,
catalogs are updated atomically at commit, then the old
file is unlinked.

## The OID vs relfilenumber distinction

Most code uses `pg_class.oid` (logical id) for catalog
lookups and `Relation` objects in memory. Storage-layer
code uses `RelFileNumber` for file paths and WAL records.

Mapping:
- `relation->rd_id` — logical OID.
- `relation->rd_locator.relNumber` — current relfilenumber.

After a rewrite, the same `rd_id` may have a new
`rd_locator.relNumber`. Code that caches relfilenumbers
across catalog-visibility-changing operations gets stale.

## Mapped relations (the exception)

[from companion `relfilelocator.md`]

`pg_class`, `pg_attribute`, and a few other "bootstrap"
catalogs are **mapped relations** — their
`pg_class.relfilenode` is zero, and the actual relfilenumber
lives in `relmap` files. Mapped relations are still subject
to rewrites (e.g., VACUUM FULL pg_class), but the rewrite
updates the relmap atomically.

## The cleanup process

Old files left by a rewrite are cleaned up:

1. **At commit** — the old relfilenumber is added to a
   pending-deletion list.
2. **At checkpoint** — the deletion list is processed; files
   are `unlink`ed from disk.
3. **At recovery** — orphan files (relfilenumbers not in
   pg_class) are removed during startup.

The deferred cleanup is the reason for VACUUM FULL's "took
the disk space to 2× before freeing it" — the new file
exists alongside the old until commit + checkpoint.

## WAL semantics during rewrite

A rewrite emits:

1. **`XLOG_SMGR_CREATE`** — create the new file.
2. **`XLOG_HEAP_NEWPAGE`** records (or AM-specific) for
   each block written.
3. **`XLOG_RELMAP_UPDATE`** (for mapped relations) — the
   relmap atomic swap.
4. **Catalog tuple updates** — `pg_class.relfilenode` changes.

Crash recovery replays all of these. If the crash happened
mid-rewrite (between steps 2 and 4), the new file exists
on disk but pg_class still points at the old. The orphan
cleanup at startup removes the new file.

## RelFileNumber allocation

A cluster-wide monotonic counter (`pg_xact/`'s relpath
manager) issues fresh relfilenumbers. The counter is
WAL-logged so recovery doesn't reissue an old value.

Wraparound is theoretically possible but practically
unreachable — 32-bit RelFileNumber gives 4 billion
allocations; even a busy cluster takes years to exhaust.

## The catalog-cache invalidation

When `pg_class.relfilenode` changes, the relcache is
invalidated for that relation:

1. The DDL emits a sinval message
   (`SHAREDINVALRELCACHE_ID`).
2. Every backend with the relation cached gets the message.
3. On next access, the cache is refreshed; new
   relfilenumber observed.

[See `knowledge/idioms/sinvaladt-broadcast.md` for the
broadcast mechanism.]

## Common review-time concerns

- **Don't cache RelFileNumbers across catalog updates.**
  After a REINDEX, your cached value is stale.
- **WAL-replayed rewrites need the SMGR_CREATE record.**
  Code that adds a new rewrite path must emit it.
- **Cleanup of orphan files happens at startup AND
  checkpoint.** A new code path that produces orphans must
  ensure both paths handle them.
- **Mapped relation rewrites are subtle** — atomic relmap
  update vs catalog tuple update. Don't reproduce the
  pattern without studying `RelationMapUpdateMap` first.

## Invariants

- **[INV-1]** Rewrites assign a NEW RelFileNumber; OID
  unchanged.
- **[INV-2]** Old file persists until checkpoint after
  commit; not immediately freed.
- **[INV-3]** Rollback drops the new file; old file
  remains usable.
- **[INV-4]** WAL records (SMGR_CREATE + content +
  catalog) replay correctly on crash.
- **[INV-5]** sinval broadcast invalidates relcache on
  every backend.

## Useful greps

- The entry point:
  `grep -n 'RelationSetNewRelfilenumber' source/src/backend/utils/cache/relcache.c | head -5`
- All callers:
  `grep -RIn 'RelationSetNewRelfilenumber' source/src/backend | head -15`
- Orphan-file cleanup:
  `grep -RIn 'RemoveOrphanedFiles\|smgrdounlink' source/src/backend | head -10`



## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/utils/cache/relcache.c`](../files/src/backend/utils/cache/relcache.c.md) | 3761 | 3775 RelationSetNewRelfilenumber |
| [`src/backend/utils/cache/relcache.c`](../files/src/backend/utils/cache/relcache.c.md) | — | RelationSetNewRelfilenumber implementation |
| [`src/include/storage/relfilelocator.h`](../files/src/include/storage/relfilelocator.h.md) | — | RelFileNumber type |

<!-- /callsites:auto -->

## Cross-references

- `knowledge/data-structures/relfilelocator.md` — the
  RelFileLocator type that holds the relfilenumber.
- `knowledge/idioms/sinvaladt-broadcast.md` — sinval
  invalidates relcache after rewrite.
- `knowledge/idioms/checkpoint-coordination.md` — checkpoint
  is where orphan-file deletion happens.
- `knowledge/idioms/crash-recovery-startup.md` — recovery
  cleanup of orphan files.
- `.claude/skills/wal-and-xlog/SKILL.md` — WAL records
  emitted during rewrite.
- `.claude/skills/catalog-conventions/SKILL.md` — pg_class
  updates during rewrite.
- `source/src/backend/utils/cache/relcache.c` —
  RelationSetNewRelfilenumber implementation.
