# hashinsert.c

- **Source path:** `source/src/backend/access/hash/hashinsert.c` (465 lines)
- **Last verified commit:** `ef6a95c7c64`

## Purpose

Top-level `_hash_doinsert` (the AM's per-row insert path) + the opportunistic LP_DEAD cleanup `_hash_vacuum_one_page`. [from-comment, hashinsert.c:1-13]

## Insert path (`_hash_doinsert`)

1. Compute `hashkey` via opclass `hash` proc.
2. Locate target bucket: use cached metapage values (`hashm_maxbucket`, `hashm_highmask`, `hashm_lowmask`) → bucket number → block via `_hash_getbucketbuf_from_hashkey` (in `hashpage.c`).
3. Lock primary bucket page exclusively.
4. **Stale-cache check**: read `hasho_prevblkno` (which stores `maxbucket` at last split for this bucket). If `prev_maxbucket > cached_maxbucket` → bucket was split → release, re-cache metapage, retry. [from-README, README:179-209]
5. **Finish-split check**: if primary bucket page has `H_BUCKET_BEING_SPLIT` and we hold the only pin → try to finish the previous split. (Conditional; never block.) [from-README, README:292-300]
6. Walk bucket chain looking for room. If a page is full, **first try `_hash_vacuum_one_page`** to remove LP_DEAD items, then re-check fit. [verified-by-code, hashinsert.c body]
7. If no room anywhere → allocate overflow page via `_hash_addovflpage` (in `hashovfl.c`).
8. Acquire metapage exclusive lock, `PageAddItem` at the correct sorted offset, increment metapage tuple count, decide if split needed.
9. Emit `XLOG_HASH_INSERT` (target page + metapage).
10. If split needed → call `_hash_expandtable` (in `hashpage.c`); release locks.

## `_hash_vacuum_one_page`

The opportunistic LP_DEAD cleanup analog. Removes items marked `LP_DEAD` by previous scans. Emits `XLOG_HASH_VACUUM_ONE_PAGE` with `snapshotConflictHorizon` — this is the only hash AM record that carries a per-record recovery conflict (the regular VACUUM-emitted `XLOG_HASH_DELETE` does not, because heap pruning already published the cutoff). [verified-by-code, comments around hash_xlog.h:45]

## Locking

- Order: primary bucket → metapage (per README §"Lock Definitions"; metapage always last). [from-README, README:162-165]
- LP_DEAD scans set bits without a content lock (hint), but `_hash_vacuum_one_page` requires exclusive lock to actually clear them.

Tags: [from-README]; [verified-by-code at function structure].
