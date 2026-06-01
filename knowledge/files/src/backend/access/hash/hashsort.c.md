# hashsort.c

- **Source path:** `source/src/backend/access/hash/hashsort.c` (157 lines)
- **Last verified commit:** `ef6a95c7c64`

## Purpose

Build-time tuplesort by `(bucket, hashcode, heap_tid)` for locality. Tuples are then bulk-inserted in bucket-order so consecutive inserts hit consecutive pages. [from-comment, hashsort.c:1-15]

## Key entry points

- `_h_spoolinit` — start a tuplesort with the bucket-comparator (uses `hashm_maxbucket`, `hashm_highmask`, `hashm_lowmask` snapshot at start).
- `_h_spool` — push one (hashkey, heap_tid).
- `_h_indexbuild` — drain sorted tuples, calling `_hash_doinsert` for each.

## Note on bucket splits during build

If row estimate was too low, splits may occur during the build. The bucket-comparator is based on the *initial* mask values, so split tuples may be slightly out-of-order with respect to the current bucket layout. Not a correctness issue — `_hash_doinsert` always re-hashes — just a locality hit. [from-comment, hashsort.c:9-15]

Tags: [from-comment].
