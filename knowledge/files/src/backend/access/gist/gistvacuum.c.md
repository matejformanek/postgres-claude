# gistvacuum.c

- **Source path:** `source/src/backend/access/gist/gistvacuum.c` (717 lines)
- **Last verified commit:** `ef6a95c7c64`

## Purpose

`ambulkdelete` (`gistbulkdelete`) + `amvacuumcleanup` (`gistvacuumcleanup`). Two-stage algorithm per README §"Bulk delete algorithm". [from-comment, gistvacuum.c:1-13]

## Stage 1 — index scan

- Physical-order scan via `read_stream.c`.
- For each leaf, call user's `callback` (heap-tuple-is-dead test) on each tuple; remove dead tuples via `PageIndexMultiDelete`, emit `XLOG_GIST_DELETE` with `snapshotConflictHorizon` (the AM-vacuum case).
- For internal pages: just record block number in an `IntegerSet` for stage 2.
- **Detect concurrent split** via `F_FOLLOW_RIGHT` and NSN: if the page split while we were scanning and one half moved before our cursor, "jump back" to re-scan. Same mechanism as nbtree but without nbtree's `cycleid` (NSN is enough). [from-README, README:443-454]
- Track empty leaves for stage 2.

## Stage 2 — leaf-page unlinking

- For each internal page recorded in stage 1, scan its downlinks looking for entries pointing at empty leaves.
- Acquire locks: **parent first, then leaf** (this is the only case where parent-before-child applies; per README §"Concurrency", normal lock order is child-before-parent. Vacuum uses the opposite order because it already holds index-relation-level vacuum lock and won't deadlock with insert).
- Re-check leaf is still empty (concurrent inserts could have populated it).
- Remove downlink, stamp leaf with `GistPageSetDeleted(deleteXid)`, emit `XLOG_GIST_PAGE_DELETE`.
- **Never delete the last child of an internal page** — insertion algorithm assumes internal pages are non-empty. [from-README, README:468-470]

## Best-effort caveat

Stage 2 can fail to find a downlink if a concurrent split moved it after stage 1's pass; in that case the empty page is leaked until next VACUUM. [from-README, README:472-476]

## Deleted-page recycling

Recycled only after `deleteXid` is globally invisible. When recycled, the allocator emits `XLOG_GIST_PAGE_REUSE` carrying `deleteXid` as `snapshotConflictHorizon` so standbys can drain conflicts. [from-README, README:478-485; cross-ref gistxlog.c:378-391]

## Cross-references

- **Called by:** `commands/vacuum.c` via AM slots.
- **Calls into:** `read_stream.c` (sequential scan), `xloginsert.c`, `lib/integerset.c` (internal-page-block list).

Tags: [from-README, README:443-486]; behavior [verified-by-code].

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
- [idioms/memory-context-slab-generation-bump.md](../../../../../idioms/memory-context-slab-generation-bump.md)

