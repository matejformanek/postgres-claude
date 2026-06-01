# gistbuild.c

- **Source path:** `source/src/backend/access/gist/gistbuild.c` (1581 lines)
- **Last verified commit:** `ef6a95c7c64`

## Purpose

The `ambuild` implementation. Two strategies, chosen at runtime:
1. **Sorted build** — if all column opclasses provide `sortsupport`. Sorts input via `Tuplesort`, packs leaf pages in order, builds internals bottom-up. B-tree-like.
2. **Insert-based build** — falls back to `gistdoinsert` per row. Switches to **buffering build** after some initial rows (unless disabled), using `gistbuildbuffers.c` machinery to convert random I/O into mostly-sequential.

[from-comment, gistbuild.c:1-25; from-README, README:297-438]

## Strategy selection

`gistGetSortSupport` walks each column's opclass looking for sortsupport (procnum 11). If all present → sorted build. Else → insert/buffering build.

The buffering threshold (`giststate->buffering`) defaults to `GIST_BUFFERING_AUTO`, which switches on once the index size exceeds `effective_cache_size`. Can be forced via `buffering` reloption. [from-README, README:297-310]

## Sorted-build path

1. `Tuplesort_begin` with the per-opclass sort-support comparator.
2. Stream tuples in, sort.
3. Pack leaves into pages until full; emit `log_newpage` per finished page.
4. Maintain a stack of "in-progress" internal pages; when a leaf is finished, push its union-key as a downlink on the parent-in-progress.
5. At end, finalize all in-progress internal pages, write root last.

Multidimensional opclasses can have poor sort linearization; mitigated by tuple-buffering + picksplit on flush. [from-README, README:436-438]

## Buffering build path

Driven by `gistbuildbuffers.c`. See that file's doc.

## WAL during build

`gistbuild` uses `RelationNeedsWAL` checks; in the sorted path each finished page is logged via `log_newpage_buffer`. In the buffering/insert path, normal `XLOG_GIST_PAGE_*` records are emitted by `gistplacetopage`.

Tags: [from-comment, gistbuild.c:1-25]; [from-README, README:297-438].

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
