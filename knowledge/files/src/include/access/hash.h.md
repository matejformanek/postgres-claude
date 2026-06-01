# hash.h

- **Source path:** `source/src/include/access/hash.h` (490 lines)
- **Last verified commit:** `ef6a95c7c64`

## Purpose

Everything-header for the hash AM: page-special struct, metapage layout, bucket flags, scan opaque, procnum constants, prototype declarations. No separate gist-style private/public split. [from-comment, hash.h:1-15]

## Key types

- `HashPageOpaqueData` — page-special: `hasho_prevblkno`, `hasho_nextblkno`, `hasho_bucket` (bucket #), `hasho_flag` (page-type and split flags), `hasho_page_id` (magic).
- `HashMetaPageData` — metapage: `hashm_magic`, `hashm_version`, `hashm_ntuples`, `hashm_ffactor` (fill factor target), `hashm_bsize` (page size), `hashm_bmsize` (bitmap size in bits), `hashm_bmshift`, `hashm_maxbucket`, `hashm_highmask`, `hashm_lowmask`, `hashm_ovflpoint` (current splitpoint), `hashm_firstfree`, `hashm_nmaps` (bitmap page count), `hashm_procid`, `hashm_spares[HASH_MAX_SPLITPOINTS]`, `hashm_mapp[HASH_MAX_BITMAPS]`.
- `HashScanOpaqueData` — per-scan state.

## Page flag bits

- `LH_UNUSED_PAGE`, `LH_OVERFLOW_PAGE`, `LH_BUCKET_PAGE`, `LH_BITMAP_PAGE`, `LH_META_PAGE` — page types (mutually exclusive).
- `H_NEEDS_SPLIT_CLEANUP` — old bucket post-split; tuples copied to new still live here.
- `H_BUCKET_BEING_SPLIT` — split in progress, this is the source bucket.
- `H_BUCKET_BEING_POPULATED` — split in progress, this is the destination bucket.
- `H_PAGE_HAS_DEAD_TUPLES` — LP_DEAD-marked items present.

## Tuple flag

- `LH_PAGE_HAS_DEAD_TUPLES`, also `MOVED_BY_SPLIT` flag on individual items.

## Procnum constants

```c
HASHSTANDARD_PROC      1   /* 32-bit hash */
HASHEXTENDED_PROC      2   /* 64-bit hash with seed */
HASHOPTIONS_PROC       3   /* reloption parser */
HASHNProcs             3
```

## Splitpoint constants

- `HASH_MAX_SPLITPOINTS = 32` — limits index size to ~2^32 buckets.
- `HASH_MAX_BITMAPS = 1024`.
