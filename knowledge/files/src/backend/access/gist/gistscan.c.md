# gistscan.c

- **Source path:** `source/src/backend/access/gist/gistscan.c` (357 lines)
- **Last verified commit:** `ef6a95c7c64`

## Purpose

Scan setup / rescan / endscan. Allocates `GISTScanOpaque`, initializes the pairing-heap queue used by `gistget.c`, manages KNN distance state. [from-comment, gistscan.c:1-13]

## Key entry points

- `gistbeginscan` — alloc `GISTScanOpaque`, init `tempCxt` (per-tuple key reconstruction).
- `gistrescan` — re-initialize scan keys; recompute `consistentFn`/`distanceFn` lookups; clear queue.
- `gistendscan` — free queue, release pinned pages, free temp context.
- `pairingheap_GISTSearchItem_cmp` — distance-then-block-number ordering for the queue (line 28-).

## State

`GISTScanOpaque` carries: pairing heap queue, opclass info per column, `killedItems[]` array for `gistkillitems`, `markPos` for mark/restore (not all paths supported).

Tags: [from-comment].
