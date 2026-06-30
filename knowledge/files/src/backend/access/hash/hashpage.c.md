# hashpage.c

- **Source path:** `source/src/backend/access/hash/hashpage.c` (1621 lines)
- **Last verified commit:** `ef6a95c7c64`

## Purpose

Page management: metapage init, bucket-page allocation (`_hash_getnewbuf`), bucket-page lookup with cache validation (`_hash_getbucketbuf_from_hashkey`), the split engine (`_hash_expandtable` + `_hash_splitbucket`), and the metapage cache machinery. [from-comment, hashpage.c:1-26]

## Key functions

| Function | Role |
|---|---|
| `_hash_getbuf` | Get + lock a buffer; sanity-check page type |
| `_hash_getbuf_with_strategy` | Same, with BufferAccessStrategy for VACUUM |
| `_hash_getinitbuf` | Allocate a buffer expected to be uninitialized |
| `_hash_initbuf` | Initialize a freshly-allocated bucket page (set opaque, type, bucket #) |
| `_hash_metapinit` | Initialize a brand-new index's metapage + initial buckets + bitmap |
| `_hash_metainit` | Build the metapage content (`hashm_*` fields) |
| `_hash_getcachedmetap` | Return relcache-cached metapage struct (may be stale) |
| `_hash_getbucketbuf_from_hashkey` | The cache-validating bucket lookup. If `hasho_prevblkno > cached.maxbucket` → bucket was split → relock metapage, refresh cache, retry. [from-README, README:179-209] |
| `_hash_expandtable` | Decide whether to split, pick which bucket, conditional-cleanup-lock dance |
| `_hash_splitbucket` | The actual split: walks old-bucket chain, moves moved-by-split tuples to new bucket. Holds cleanup lock on both old and new throughout. Emits `XLOG_HASH_SPLIT_PAGE` per N-tuple transfer, `XLOG_HASH_SPLIT_ALLOCATE_PAGE` for new pages, `XLOG_HASH_SPLIT_COMPLETE` at end |
| `_hash_finish_split` | Resume a partially-completed split — invoked by inserter that hits `H_BUCKET_BEING_SPLIT` |
| `_hash_dropscanbuf` / `_hash_relbuf` | Release helpers |

## Split locking [HIGH-RISK]

`_hash_expandtable`:
- Lock metapage exclusive.
- Pick bucket to split = `maxbucket - lowmask`.
- `LockBufferForCleanup` (cleanup = exclusive + only pin) on old bucket — **conditional**; if fails, release metapage and abandon. [from-README, README:364-374]
- Pin and exclusive-lock new bucket page (always new, no contenders).
- Walk old bucket chain, hash each tuple, decide old-vs-new, move moved-by-split.

Throughout: **bucket-lock order = lower bucket first**, metapage acquired *before* picking a split-victim (then released and reacquired as needed during the actual move loop).

## `_hash_splitbucket` mechanics

For each old page:
- Scan all tuples; partition into "stays" (re-hash to old) and "moves" (re-hash to new).
- Mark "moves" with `LH_BUCKET_TUPLE_FLAG_MOVED_BY_SPLIT`.
- Copy moves to current new-bucket page (allocate overflow if needed via `_hash_addovflpage`).
- Compact old page (delete moved items).
- Emit one `XLOG_HASH_SPLIT_PAGE` per (old, new) pair.

Final step: clear `H_BUCKET_BEING_SPLIT` on old, `H_BUCKET_BEING_POPULATED` on new, set `H_NEEDS_SPLIT_CLEANUP` on old (tells VACUUM to remove the now-redundant moved-by-split tuples from the old bucket once it's safe).

## Cross-references

- **Called by:** `hashinsert.c`, `hashsearch.c`, `hash.c::hashbulkdelete`.
- **Calls into:** `hashovfl.c` (overflow allocation), `hashutil.c` (`_hash_finish_split`), `hash_xlog.c` (WAL).

Tags: [from-README, README:338-383]; [verified-by-code for `_hash_splitbucket` mechanics].

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
- [idioms/hash-bucket-split.md](../../../../../idioms/hash-bucket-split.md)
- [idioms/hash-page-layout.md](../../../../../idioms/hash-page-layout.md)

