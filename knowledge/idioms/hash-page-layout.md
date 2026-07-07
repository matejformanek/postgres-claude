# Hash AM page layout — metapage + spareindex addressing + four-phase splitpoint allocation

PostgreSQL's hash AM implements Seltzer & Yigit's linear-hashing variant:
the index grows by **splitting one bucket at a time** (not doubling the
whole table), and the bucket-number-to-physical-block mapping is
computed arithmetically from the metapage's `hashm_spares[]` array and
the splitpoint group structure. The result is a hash index that grows
incrementally without rewriting existing pages — bucket N never moves
once allocated.

The addressing trick is the **four-phase splitpoint allocation**: for
splitpoint groups ≥ 10, the `(2^x)` buckets at that group are allocated
in **four equal phases of `2^(x-2)` buckets each**, with each phase's
worth of bucket pages laid out consecutively in the index file. This
caps the growth rate so a 1M-tuple insert doesn't suddenly allocate
512K bucket pages.

This doc covers the metapage struct, the `BUCKET_TO_BLKNO` macro and
`_hash_spareindex` decoding, the four page types (`LH_META`,
`LH_BUCKET`, `LH_OVERFLOW`, `LH_BITMAP`) with their per-page flag bits,
the metapage caching strategy (per-backend relcache copy) and how
splits propagate via `hasho_prevblkno` cross-checks.

Companion docs:
- [[hash-bucket-split]] — the bucket-split mechanism that grows the table.
- [[hash-overflow-pages]] — overflow allocation via bitmap pages.

## Anchors

- `source/src/backend/access/hash/README` — full design overview (~620 lines).
- `source/src/include/access/hash.h:30-50` — `Bucket` type, `BUCKET_TO_BLKNO`.
- `source/src/include/access/hash.h:53-93` — `LH_*` page-type flags, `HashPageOpaqueData`.
- `source/src/include/access/hash.h:198-265` — `HASH_METAPAGE = 0`, `HASH_MAGIC`, `HASH_VERSION`, `HashMetaPageData`.
- `source/src/include/access/hash.h:232-242` — `HASH_SPLITPOINT_*` constants.
- `source/src/backend/access/hash/hashutil.c` — `_hash_spareindex` decoding.
- `source/src/backend/access/hash/hashpage.c` — `_hash_getbucketbuf_from_hashkey`, `_hash_init_metabuffer`.

## Five page types

```c
/* hash.h:53-64 */
#define LH_UNUSED_PAGE                     (0)
#define LH_OVERFLOW_PAGE                   (1 << 0)   /* in a bucket chain, after primary */
#define LH_BUCKET_PAGE                     (1 << 1)   /* primary bucket page */
#define LH_BITMAP_PAGE                     (1 << 2)   /* tracks free overflow pages */
#define LH_META_PAGE                       (1 << 3)   /* the metapage at block 0 */
#define LH_BUCKET_BEING_POPULATED          (1 << 4)   /* split target, mid-population */
#define LH_BUCKET_BEING_SPLIT              (1 << 5)   /* split source, mid-redistribution */
#define LH_BUCKET_NEEDS_SPLIT_CLEANUP      (1 << 6)   /* deferred cleanup pending */
#define LH_PAGE_HAS_DEAD_TUPLES            (1 << 7)
```

`LH_PAGE_TYPE = LH_OVERFLOW | LH_BUCKET | LH_BITMAP | LH_META` — mask
for the four mutually-exclusive type bits. The transient flags (bits
4-7) layer on top. [verified-by-code] (`hash.h:63-64`).

The page-special struct:

```c
/* hash.h:77-86 */
typedef struct HashPageOpaqueData {
    BlockNumber  hasho_prevblkno;        /* prev page in chain (or maxbucket-at-split) */
    BlockNumber  hasho_nextblkno;        /* next page in chain */
    Bucket       hasho_bucket;           /* bucket number this page belongs to */
    uint16       hasho_flag;             /* LH_* type + transient bits */
    uint16       hasho_page_id;          /* HASHO_PAGE_ID = 0xFF80 sentinel */
} HashPageOpaqueData;
```

The `hasho_prevblkno` field is overloaded on bucket pages: instead of
storing the previous page in a chain (there is none — bucket pages are
the start of the chain), it stores the **`hashm_maxbucket` value at
the time this bucket was split (or created)**. This is the cache-
invalidation mechanism (covered below). [from-comment] (`hash.h:67-72`).

`hasho_page_id = 0xFF80` is the magic-byte sentinel; pg_filedump uses
it to distinguish hash index pages from other index types. The
comment notes "It should be the last 2 bytes on the page. This is more
or less 'free' due to alignment considerations." [from-comment]
(`hash.h:95-101`).

## The metapage

```c
/* hash.h:244-265 */
typedef struct HashMetaPageData {
    uint32       hashm_magic;            /* 0x6440640 = "Hd@@" backwards */
    uint32       hashm_version;          /* HASH_VERSION = 4 */
    double       hashm_ntuples;
    uint16       hashm_ffactor;          /* target fill (tuples/bucket) */
    uint16       hashm_bsize;            /* index page size */
    uint16       hashm_bmsize;           /* bitmap-array size (bytes) — power of 2 */
    uint16       hashm_bmshift;          /* log2(bitmap-array size in BITS) */
    uint32       hashm_maxbucket;        /* current highest-numbered bucket in use */
    uint32       hashm_highmask;         /* mask to modulo into entire table */
    uint32       hashm_lowmask;          /* mask to modulo into LOWER half */
    uint32       hashm_ovflpoint;        /* splitpoint from which we're allocating ovfl */
    uint32       hashm_firstfree;        /* lowest-numbered free ovfl bit */
    uint32       hashm_nmaps;            /* # of bitmap pages */
    RegProcedure hashm_procid;           /* hash function OID */
    uint32       hashm_spares[HASH_MAX_SPLITPOINTS]; /* # of ovfl pages before each splitpoint phase */
    BlockNumber  hashm_mapp[HASH_MAX_BITMAPS];       /* bitmap-page block numbers */
} HashMetaPageData;
```

`HASH_METAPAGE = 0` — always block 0. [verified-by-code] (`hash.h:198`).

Key fields:

- **`hashm_maxbucket`**: the largest bucket number currently in use.
  Together with `highmask` and `lowmask`, these define the linear-
  hashing parameters.
- **`hashm_highmask` / `hashm_lowmask`**: linear hashing's twin masks.
  A hash value `h`:
  - `bucket = h & lowmask`
  - If that's `> maxbucket`: `bucket = h & highmask`
  
  (Linear-hashing trick — buckets below the "split pointer" use
  highmask, others use lowmask. Same `hashm_lowmask = 2*N - 1` and
  `hashm_highmask = 4*N - 1` for the simple doubling case.)
- **`hashm_spares[S]`**: number of overflow pages allocated before
  splitpoint phase S. Used by `BUCKET_TO_BLKNO` to compute physical
  block addresses arithmetically. Always
  `hashm_spares[N] <= hashm_spares[N+1]`. [from-comment]
  (`README` "Primary bucket pages are allocated in power-of-2 groups").
- **`hashm_ovflpoint`**: current splitpoint phase from which new
  overflow pages are being allocated.
- **`hashm_firstfree`**: lowest-numbered free overflow page's bit
  number (across all bitmap pages). New overflow allocation starts
  searching here.
- **`hashm_mapp[]`**: array of block numbers of bitmap pages.
  `HASH_MAX_BITMAPS = min(BLCKSZ/8, 1024)` — 1024 with 8 KiB pages,
  giving 256 GB of overflow page tracking. [verified-by-code]
  (`hash.h:230`).

## Splitpoint groups — the addressing scheme

The README's central insight (`README` lines 60-100): bucket numbers
are partitioned by **splitpoint group**, and bucket pages of a single
**phase within a group** are laid out **consecutively** in the index
file:

```
Bucket 0       → splitpoint group 0, phase 0 (just bucket 0)
Bucket 1       → splitpoint group 1, phase 0 (just bucket 1)
Buckets 2-3    → splitpoint group 2, phase 0 (2 buckets)
Buckets 4-7    → splitpoint group 3, phase 0 (4 buckets)
Buckets 8-15   → splitpoint group 4, phase 0 (8 buckets)
...
Buckets 512-639 → splitpoint group 10, phase 0 (128 buckets)
Buckets 640-767 → splitpoint group 10, phase 1 (128 more)
Buckets 768-895 → splitpoint group 10, phase 2 (128 more)
Buckets 896-1023 → splitpoint group 10, phase 3 (128 more)
Buckets 1024-1151 → splitpoint group 11, phase 0 (256 buckets)
```

Groups 0-9 use **a single phase** (one allocation chunk per group);
groups 10+ split into 4 equal phases of `2^(x-2)` buckets each, where
`2^x` is the total bucket count for that group. The four-phase
allocation prevents huge bursts of file growth on big indexes.
[from-comment] (`README` "splitpoint group 10... 2 ^ 9 buckets in 4
different phases").

The encoding in `hash.h`:

```c
/* hash.h:232-242 */
#define HASH_SPLITPOINT_PHASE_BITS              2
#define HASH_SPLITPOINT_PHASES_PER_GRP          (1 << 2)        /* = 4 */
#define HASH_SPLITPOINT_PHASE_MASK              3
#define HASH_SPLITPOINT_GROUPS_WITH_ONE_PHASE   10
#define HASH_MAX_SPLITPOINT_GROUP               32
#define HASH_MAX_SPLITPOINTS \
    (((32 - 10) * 4) + 10)                                       /* = 98 */
```

[verified-by-code] (`hash.h:232-242`).

So `hashm_spares[]` has 98 entries. The maximum bucket count is bounded
by `2^32 / 1 = 4 billion` (limit of `uint32 Bucket`).

## `BUCKET_TO_BLKNO` — physical address computation

```c
/* hash.h:39-40 */
#define BUCKET_TO_BLKNO(metap, B) \
    ((BlockNumber)((B) + ((B) ? (metap)->hashm_spares[_hash_spareindex((B)+1)-1] : 0)) + 1)
```

The decoding: for bucket B,
1. Compute `S = _hash_spareindex(B + 1) - 1` — the global splitpoint
   phase number containing bucket B.
2. Physical block = `B + hashm_spares[S] + 1`.

The `+ 1` at the end skips the metapage at block 0. The `(B ? ... : 0)`
handles bucket 0 specially (it's always at block 1).
[verified-by-code] (`hash.h:39-40`).

`_hash_spareindex(B + 1)` returns the **splitpoint phase number** the
given bucket-count-plus-one belongs to. For small buckets (groups 0-9),
each group has one phase. For groups ≥ 10, the four sub-phases get
distinct indices.

The arithmetic: `hashm_spares[S]` counts every overflow page
allocated **before** splitpoint phase S's bucket pages. Adding it to
bucket-number-within-the-phase gives the physical block of the
bucket page.

## Linear hashing — the `lowmask` / `highmask` pair

Standard linear hashing has a "split pointer" P that scans through the
table. Buckets ≥ P use the old (smaller) mask; buckets < P have been
split and use a larger mask. PostgreSQL's hash AM stores this as two
masks:

```
hashm_lowmask  = mask for buckets >= P  (covers half the keyspace)
hashm_highmask = mask for buckets < P   (covers full keyspace)
maxbucket      = the count of buckets currently in existence
```

Hash function `_hash_hashkey2bucket` computes:

```c
bucket = hashvalue & highmask;
if (bucket > maxbucket)
    bucket = hashvalue & lowmask;
```

After a split, `maxbucket` increments. If the split rolls over a power
of 2, `lowmask` becomes the old `highmask` and `highmask` shifts up
one bit.

The mask pair lets the next lookup go directly to the right bucket
without consulting any split-pointer global state.

## Metapage caching

Every index lookup needs `maxbucket`/`highmask`/`lowmask` to compute
the target bucket. Locking the metapage for every operation would be
a hotspot. The hash AM caches a copy of the metapage in each
backend's relcache entry (`hashm_cached`-style state in `rd_amcache`).

The cache may go stale if a concurrent split has happened. The
detection mechanism uses `HashPageOpaqueData.hasho_prevblkno`:

> In a bucket page, hasho_prevblkno stores the hashm_maxbucket value
> as of the last time the bucket was last split, or else as of the
> time the bucket was created. … this is used to determine whether a
> cached copy of the metapage is too stale to be used without needing
> to lock or pin the metapage.

[from-comment] (`hash.h:67-72`).

When we land on bucket page B and our cached `maxbucket` is less than
the page's `hasho_prevblkno`, the bucket has been split since our
cache was refreshed. We must refresh the metapage and retry.

This is a clever inversion: we never check the cache against the
truth; we check against the **page we're currently looking at**, which
encodes "I was last touched at maxbucket = X." If our cache says
maxbucket = Y < X, we're stale.

## Lock order — the deadlock-avoidance rule

> To avoid deadlocks, we must be consistent about the lock order in
> which we lock the buckets for operations that requires locks on
> two different buckets. We choose to always lock the lower-numbered
> bucket first. The metapage is only ever locked after all bucket
> locks have been taken.

[from-comment] (`README` "Lock Definitions").

This rule applies to bucket splits (which need locks on the source
bucket + the new target bucket) and to scans crossing bucket
boundaries via the `hashso_split_bucket_buf`.

## Bitmap pages — overflow page tracking

Bitmap pages (`LH_BITMAP_PAGE` flag) track which overflow pages are
free vs in-use. The metapage's `hashm_mapp[]` array gives the block
numbers of these bitmap pages; `hashm_nmaps` is the count.

Each bit in a bitmap page corresponds to one overflow page (0 =
available, 1 = in-use). `hashm_firstfree` is the lowest bit number
known to be free — overflow allocation starts there.

> It turns out in fact that each bitmap page's first bit represents
> itself --- this is not an essential property, but falls out of the
> fact that we only allocate another bitmap page when we really need
> one.

[from-comment] (`README` "the entries in the bitmap are indexed by
bit number").

See [[hash-overflow-pages]] for the allocation algorithm.

## VACUUM and the EOF discrepancy

> The last page nominally used by the index is always determinable
> from hashm_spares[S]. To avoid complaints from smgr, the logical
> EOF as seen by the filesystem and smgr must always be greater than
> or equal to this page. We have to allow the case "greater than"
> because it's possible that during an index extension we crash
> after allocating filesystem space and before updating the metapage.

[from-comment] (`README` "The last page nominally used").

Crash safety: if we crash mid-extend, the file is longer than
`hashm_spares[S]` says. On filesystems with holes, the intervening
pages may be unallocated. The hash AM tolerates this by reading
"more than enough" — the actual EOF and the metapage's view diverge
benignly.

## Limits

- **Max buckets**: `2^32 - 1` (uint32 Bucket type).
- **Max splitpoint phases**: 98 (`HASH_MAX_SPLITPOINTS`).
- **Max bitmaps**: 1024 with 8 KiB pages → ~256 GB of overflow space.
  Smaller `BLCKSZ` gives fewer bitmap pages.
- **Max item size**: `HashMaxItemSize(page)` = page contents minus
  page-header minus one ItemId minus opaque. About 8160 bytes at
  8 KiB. A hash item that doesn't fit on a page is rejected at
  insert time — there's no TOAST for hash index entries.
- **Hash function**: stored as `hashm_procid` in the metapage; the
  opclass's support function 1 (must match operator class
  registration).

## Invariants and races

1. **Bucket N never moves once allocated**. The `BUCKET_TO_BLKNO`
   arithmetic depends on this. Splits redistribute *tuples* between
   bucket pages but don't relocate bucket pages.
2. **`hashm_spares[N] <= hashm_spares[N+1]`**, always. Once
   splitpoint N+1 exists, spares[N] is frozen. [from-comment]
   (`README`).
3. **Metapage is block 0**, always.
4. **`HASHO_PAGE_ID = 0xFF80`** is at the last 2 bytes of every
   hash index page, for filetype detection. [verified-by-code]
   (`hash.h:101`).
5. **Bucket page's `hasho_prevblkno` stores `maxbucket-at-last-split`**,
   not a previous-page pointer. Used for stale-cache detection.
   [from-comment] (`hash.h:67-72`).
6. **Lock order: low-numbered bucket first, metapage last**.
   [from-comment] (`README`).
7. **Buckets 0 and 1 are always at blocks 1 and 2** (because
   `hashm_spares[0] = 0`). [from-comment]
   (`README` "hashm_spares[0] is always 0").
8. **EOF may exceed `hashm_spares[S]`-derived last page** if a crash
   interrupted an extend. The hash AM tolerates this.
9. **Each bitmap page's first bit represents itself** — falls out of
   allocation order. [from-comment] (`README`).

## Useful greps

```bash
# Page-type predicates:
grep -nE "LH_(BUCKET|META|OVERFLOW|BITMAP)_PAGE|LH_PAGE_TYPE|H_BUCKET" \
       source/src/include/access/hash.h

# Metapage struct fields:
grep -n "hashm_" source/src/include/access/hash.h | head -20

# Bucket-to-block mapping:
grep -rn "BUCKET_TO_BLKNO\|_hash_spareindex" \
       source/src/include/access/hash.h \
       source/src/backend/access/hash/

# Splitpoint constants:
grep -nE "HASH_SPLITPOINT_|HASH_MAX_SPLITPOINTS" \
       source/src/include/access/hash.h

# Bitmap page layout:
grep -rn "hashm_mapp\|hashm_nmaps\|hashm_bmsize\|hashm_bmshift" source/src/backend/access/hash/

# Lock order (search for low-numbered-first):
grep -rn "low.*number.*bucket.*first\|lock.*lower" source/src/backend/access/hash/
```



## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/access/hash/hashpage.c`](../files/src/backend/access/hash/hashpage.c.md) | — | _hash_getbucketbuf_from_hashkey, _hash_init_metabuffer |
| [`src/backend/access/hash/hashutil.c`](../files/src/backend/access/hash/hashutil.c.md) | — | _hash_spareindex decoding |
| [`src/include/access/hash.h`](../files/src/include/access/hash.h.md) | 30 | Bucket type, BUCKET_TO_BLKNO |
| [`src/include/access/hash.h`](../files/src/include/access/hash.h.md) | 53 | LH_ page-type flags, HashPageOpaqueData |
| [`src/include/access/hash.h`](../files/src/include/access/hash.h.md) | 198 | HASH_METAPAGE = 0, HASH_MAGIC, HASH_VERSION, HashMetaPageData |
| [`src/include/access/hash.h`](../files/src/include/access/hash.h.md) | 232 | HASH_SPLITPOINT_ constants |

<!-- /callsites:auto -->

## Cross-references

- [[hash-bucket-split]] — the split mechanism that grows the table.
- [[hash-overflow-pages]] — bitmap-page-driven overflow allocation/recycling.
- `source/src/backend/access/hash/README` — full design.
- `knowledge/subsystems/access-nbtree.md` — sibling B-tree implementation for comparison.
