# hash/README — summary

- **Source path:** `source/src/backend/access/hash/README` (651 lines)
- **Last verified commit:** `ef6a95c7c64`

## Purpose

Canonical narrative for **hash indexing** — Seltzer/Yigit "New Hashing Package" linear-hashing scheme with overflow pages. Stores **only hash codes** (not original values) since v8.4, allowing sorted-within-page entries for binary search. Per-bucket linked list with cleanup-lock-based concurrency. [from-README, README:1-43]

## The ideas you must hold

1. **Linear hashing with phased splitpoints.** Buckets are allocated in **power-of-2 splitpoint groups**, then split into 4 phases (for groups ≥ 10) to avoid huge one-shot allocations. Bucket→block address is computed from `hashm_spares[]` + bucket number; bucket pages never move once created. [from-README, README:45-99]
2. **Four page kinds.** Metapage (block 0), primary bucket pages, overflow pages, bitmap pages (which track free overflow pages). Bitmap pages are themselves a subset of overflow pages. [from-README, README:48-52]
3. **No bucket merge; no shrink.** Only REINDEX reduces size. Overflow pages can be recycled within an index but never returned to OS. [from-README, README:31-34]
4. **Index entries store only hash code.** Smaller entries, sortable within a page → binary search per page. Cross-page ordering is NOT maintained within a bucket. [from-README, README:36-42]
5. **Concurrency = buffer content locks + pins + cleanup locks.** A *cleanup lock* (exclusive lock + we hold the only pin) on the primary bucket page = right to reorganize the entire bucket. Scans **retain a pin on the primary bucket page** throughout the scan; VACUUM and split both need cleanup locks on it. [from-README, README:142-160]
6. **Bucket-lock order: lower-numbered bucket first; metapage last.** Deadlock avoidance. [from-README, README:162-165]
7. **Metapage caching in relcache.** Avoid per-op metapage lock. Cache may be stale; primary bucket pages store the bucket count "as of when this bucket was last split" in the `hasho_prevblkno` slot (since the prev-block of a primary bucket is always Invalid). If cached `hashm_maxbucket < hasho_prevblkno` → bucket was split → re-cache via metapage lock and retry. [from-README, README:168-209]
8. **Split flags (bucket-being-split, bucket-being-populated, split-cleanup, moved-by-split).** Mark in-progress and post-split state. Scans during a split scan *both* old and new buckets but skip `moved-by-split` tuples in the old one. Splits are completed at the next insert/split that touches the old bucket. [from-README, README:213-234]
9. **Reader algorithm.** Lock primary bucket, walk pages reading all matching items into local memory, release locks (but keep primary-bucket pin). If bucket-being-populated → scan old bucket too, skipping moved-by-split. [from-README, README:248-285]
10. **Insert / overflow chain.** Pages sorted by hash code within a page → insertion picks the right offset. When a bucket fills, insert obtains overflow page via bitmap allocator, chains it, WAL-logs. May trigger split if load factor exceeded. [from-README, README:287-336]
11. **Split is best-effort.** Inserter tries cleanup lock on old bucket; **if it fails, abandon** (don't wait while holding metapage lock). Next inserter retries. If a split fails mid-way, it'll be retried on next insert to the old bucket. [from-README, README:338-383]
12. **VACUUM walks buckets in number order with cleanup lock.** Page-chain lock-chaining (lock next before releasing current) prevents the scan-overtaking-VACUUM hazard described in §"Interlocking Between Scans and VACUUM". After cleaning, attempts a cleanup lock on primary bucket to "squeeze" (compact). [from-README, README:385-453]
13. **Free-space management is bitmap-based.** A bit per overflow page (0=free, 1=in use). `hashm_firstfree` is a *lower bound* on first free bit (not exact) — safe to underestimate, fatal to overestimate. Freeing requires moving tuples atomically with bitmap update to avoid "double-read" on standby. [from-README, README:454-560]

## WAL records

| Record | Coverage |
|---|---|
| `XLOG_HASH_INIT_META_PAGE` | metapage init |
| `XLOG_HASH_INIT_BITMAP_PAGE` | bitmap page init |
| `XLOG_HASH_INSERT` | single-page tuple insert + metapage tuple-count update |
| `XLOG_HASH_ADD_OVFL_PAGE` | allocate + link overflow page (+ bitmap update) |
| `XLOG_HASH_SPLIT_ALLOCATE_PAGE` | new bucket page during split |
| `XLOG_HASH_SPLIT_PAGE` | move N tuples to new bucket page |
| `XLOG_HASH_SPLIT_COMPLETE` | clear bucket-being-split + bucket-being-populated |
| `XLOG_HASH_MOVE_PAGE_CONTENTS` | squeeze move |
| `XLOG_HASH_SQUEEZE_PAGE` | bucket squeeze cleanup |
| `XLOG_HASH_DELETE` | per-page tuple delete during VACUUM |
| `XLOG_HASH_SPLIT_CLEANUP` | clear split-cleanup flag |
| `XLOG_HASH_UPDATE_META_PAGE` | metapage tuple-count update post-VACUUM |
| `XLOG_HASH_VACUUM_ONE_PAGE` | opportunistic LP_DEAD cleanup (with snapshot conflict) |

[from-README, README:563-642]

## Where each section is implemented

| README section | Implementing files |
|---|---|
| Page addressing + bucket math | `hashpage.c` (`_hash_spareindex`, `_hash_getbuf`) |
| Insert + split | `hashinsert.c`, `hashpage.c` (`_hash_splitbucket`) |
| Reader algorithm | `hashsearch.c` |
| Overflow / bitmap free-space | `hashovfl.c` |
| Bulk sorted build | `hashsort.c` (build-time tuplesort) |
| VACUUM | `hash.c` (`hashbulkdelete`/`hashvacuumcleanup`) |
| WAL replay | `hash_xlog.c` |
| Validation | `hashvalidate.c` |
| Utilities (page-special, mask, hash funcs) | `hashutil.c`, `hashfunc.c` |

## Highest-risk claims to spot-check

1. **"Cleanup lock on primary bucket = right to reorganize"** — verified everywhere by `LockBufferForCleanup` calls in `hashpage.c::_hash_splitbucket`, `hash.c::hashbulkdelete`. [verified-by-code]
2. **"Bucket lock order: lower first, metapage last"** — followed by every two-bucket path (split). [from-README, README:162-165; verified-by-code]
3. **"hashm_firstfree may underestimate, never overestimate"** — see `hashovfl.c::_hash_freeovflpage` careful sequencing. [from-README, README:550-556]
