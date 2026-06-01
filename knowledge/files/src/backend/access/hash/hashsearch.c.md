# hashsearch.c

- **Source path:** `source/src/backend/access/hash/hashsearch.c` (718 lines)
- **Last verified commit:** `ef6a95c7c64`

## Purpose

Scan engine: `_hash_first` (entry point for first call), `_hash_next` (subsequent), `_hash_readpage` (load matching items from one page into local memory), `_hash_load_qualified_items`. [from-comment, hashsearch.c:1-13]

## Algorithm (per README)

1. `_hash_first`:
   - Resolve hashkey from scan key.
   - Lock primary bucket via `_hash_getbucketbuf_from_hashkey` (handles cache invalidation).
   - **If bucket is being populated by a split** (`H_BUCKET_BEING_POPULATED`): switch into "scan two buckets" mode — set scan state to scan new bucket first (skipping `MOVED_BY_SPLIT` tuples), then old bucket. [from-README, README:281-285]
   - Call `_hash_readpage` to load matching items.
2. `_hash_next`:
   - If current item array exhausted, advance to next page in bucket chain (`hasho_nextblkno`).
   - At end of new bucket, switch to old bucket if in split-mode.
3. `_hash_readpage`:
   - Take content lock, binary-search by hash code, walk forward collecting matching items into `HashScanOpaque.currPos.items[]`.
   - Release content lock.
   - **Keep pin on primary bucket page** throughout the entire scan to prevent VACUUM/split. [from-README, README:269-279]

## Locking

- Pin on primary bucket: **held entire scan**.
- Per-page: content lock during load, released immediately after.
- Lock-chaining is *not* used here (in contrast to VACUUM); the bucket pin is sufficient to prevent the page from being recycled.

## LP_DEAD optimization

Scan may set `LP_DEAD` on items it determined are dead (heap row gone). These bits are dirty-hint only; cleanup happens at insert time via `_hash_vacuum_one_page`.

## SSI

`PredicateLockPage` on primary bucket page at scan start.

Tags: [from-README, README:248-285]; [verified-by-code at function structure].

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
