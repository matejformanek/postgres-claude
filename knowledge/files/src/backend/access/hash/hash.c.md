# hash.c

- **Source path:** `source/src/backend/access/hash/hash.c` (1027 lines)
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `hashinsert.c`, `hashpage.c`, `hashsearch.c`, `hashovfl.c`, `hashsort.c`, `hash_xlog.c`, `hashutil.c`, `hashvalidate.c`.

## Purpose

The public interface module: `hashhandler` (`IndexAmRoutine`), build paths (`hashbuild`, `hashbuildempty`), insert wrapper (`hashinsert`), scan slots (`hashbeginscan`/`hashrescan`/`hashendscan`/`hashgettuple`/`hashgetbitmap`), VACUUM (`hashbulkdelete`/`hashvacuumcleanup`). Mostly thin wrappers over the per-module logic. [from-comment, hash.c:1-15]

## Capability vtable (`hashhandler`)

- `amgettuple` + `amgetbitmap` both supported.
- `amcanorder=false`, `amcanmulticol=false` (single-column only!), `amcanunique=false`, `amparallelscan=false`, `amsearchnulls=false` (nulls are not indexable in hash), `amclusterable=false`.

## Build path (`hashbuild`)

1. Estimate target number of buckets from `RelOptInfo` row estimate + `hash_metapage_init`'s `_h_spoolinit` for sort-based bulk load.
2. Walk heap, hash each row, feed to a hash-spool (`hashsort.c`) which tuplesorts by `(bucket, hashcode, tid)`.
3. Bulk-insert sorted tuples bucket-by-bucket.
4. If row estimate was too low, bucket splits may occur during build (acceptable; locality still good). [from-comment, hashsort.c:9-15]

## VACUUM path

- `hashbulkdelete` walks buckets 0..maxbucket, takes cleanup lock on each primary bucket page, walks the page chain via lock-chaining (lock next before releasing current) to prevent scan-overtaking. Emits `XLOG_HASH_DELETE` per page touched, then attempts a final squeeze via `_hash_squeezebucket` (in `hashovfl.c`).
- `hashvacuumcleanup` updates the metapage tuple count (`XLOG_HASH_UPDATE_META_PAGE`) and reports stats. Carefully handles concurrent splits/inserts by re-checking bucket count.

Tags: [from-comment]; [from-README, README:385-453].

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
