# TIDBitmap — structure and the lossy/exact trick

`TIDBitmap` is the in-memory data structure that bitmap-index scans
build up and that bitmap-heap scans consume.  It's a hash table of
**`PagetableEntry`** records keyed by `BlockNumber`, where each
entry can be in one of two modes:

- **exact**: a per-tuple bitmap of size `TBM_MAX_TUPLES_PER_PAGE`
  bits — every set bit is "yes there's a matching tuple at offset
  `bit+1`".
- **lossy chunk**: a *batch* of pages.  One `PagetableEntry`
  covers `PAGES_PER_CHUNK` consecutive pages, with one bit per
  page indicating "this page contains *some* matching tuple,
  but we don't remember which".

The lossy mode is what makes TIDBitmap work for queries that
would otherwise blow out `work_mem` — and the "recheck after
lossification" property is what lets the executor still produce
correct results.

This doc covers the **shape** — the structs, the three lifecycle
states, the chunk arithmetic, the recheck flag.  The dynamic
half (`tbm_add_tuples`, iterators, lossify trigger,
`tbm_union`/`tbm_intersect`) is [[tidbitmap-build-and-iterate]].
The executor side that builds and consumes it is
[[bitmap-and-or-heap-executor]].

**Anchors** (all cites against `source/` at commit `e18b0cb7344`):
- `source/src/backend/nodes/tidbitmap.c` — entire implementation
- `source/src/include/nodes/tidbitmap.h` — public API + `TBMIterateResult`

## The two-mode `PagetableEntry`

`tidbitmap.c:92-99` [verified-by-code]:

```c
typedef struct PagetableEntry
{
    BlockNumber blockno;        /* page number (hashtable key) */
    char        status;         /* hash entry status */
    bool        ischunk;        /* T = lossy storage, F = exact */
    bool        recheck;        /* should the tuples be rechecked? */
    bitmapword  words[Max(WORDS_PER_PAGE, WORDS_PER_CHUNK)];
} PagetableEntry;
```

The `words[]` array is dimensioned for the **larger** of the two
modes:

```c
/* tidbitmap.c:73-76 */
#define WORDS_PER_PAGE   ((TBM_MAX_TUPLES_PER_PAGE - 1) / BITS_PER_BITMAPWORD + 1)
#define WORDS_PER_CHUNK  ((PAGES_PER_CHUNK - 1) / BITS_PER_BITMAPWORD + 1)
```

`TBM_MAX_TUPLES_PER_PAGE` is `MaxHeapTuplesPerPage` from
`htup_details.h` — the hard upper bound on heap tuples per
page (291 at the default 8K BLCKSZ).  So per-tuple exact storage
takes `ceil(291 / 64) = 5` `bitmapword`s.

`PAGES_PER_CHUNK` is `BLCKSZ / 32 = 256` at the default block
size — chosen by the comment at `tidbitmap.c:51-65`
[from-comment]:

> Therefore it's best if PAGES_PER_CHUNK is the same as
> TBM_MAX_TUPLES_PER_PAGE, or at least not too different.  But
> we also want PAGES_PER_CHUNK to be a power of 2 to avoid
> expensive integer remainder operations.

A `1` bit in chunk word `k` covers `chunk_blockno + k`.  The
chunk header lives at `(blockno / PAGES_PER_CHUNK) *
PAGES_PER_CHUNK` — see the bit arithmetic in
`tbm_page_is_lossy` (lines 1261-1262) [verified-by-code]:

```c
bitno = pageno % PAGES_PER_CHUNK;
chunk_pageno = pageno - bitno;
```

### Why one struct for both modes

The comment at `tidbitmap.c:58-62` [from-comment]:

> We actually store both exact pages and lossy chunks in the
> same hash table, using identical data structures.  (This is
> because the memory management for hashtables doesn't
> easily/efficiently allow space to be transferred easily from
> one hashtable to another.)

Trade-off: every entry pays for the larger of `WORDS_PER_PAGE` and
`WORDS_PER_CHUNK`, even when it's the smaller mode.  At default
BLCKSZ this is ~5 words either way (since both are roughly 256
bits), so the waste is tiny.  The win is "no rebalancing
between two hash tables when a page transitions from exact to
lossy".

### The "no exact at chunk-header offset" rule

From `tidbitmap.c:83-86` [from-comment]:

> Note that it is not possible to have exact storage for the
> first page of a chunk if we are using lossy storage for any
> page in the chunk's range, since the same hashtable entry has
> to serve both purposes.

This is why `tbm_mark_page_lossy` (lines 1283-1350) reuses an
existing exact entry at the chunk-header `blockno` rather than
inserting a second entry — there can only be one entry per
`blockno` in the hash table.  The `ischunk` field flips and the
previously per-tuple `words[]` are clobbered with the per-page
chunk bits.

The `tbm_lossify` skip at lines 1383-1384 [verified-by-code]:

```c
if ((page->blockno % PAGES_PER_CHUNK) == 0)
    continue;
```

— says **"don't lossify a page whose blockno *is* its own chunk
header"** because converting it would save zero space (the
chunk-header would still occupy one entry).

### The `recheck` flag

`recheck` is set when the index AM tells us "this tuple matches
the index quals, but the table tuple might still need the qual
re-evaluated" (e.g. lossy GIN compression).  When iterators
report a `TBMIterateResult` (see
[[tidbitmap-build-and-iterate]]), the recheck flag propagates
up so `BitmapHeapScan` knows to re-run the qual against the
heap tuple.

Two key invariants from the comment at `tidbitmap.c:88-90`
[from-comment]:

> recheck is used only on exact pages --- it indicates that
> although only the stated tuples need be checked, the full
> index qual condition must be checked for each (ie, these are
> candidate matches).

Lossy entries are **always** recheck-required — the executor
re-checks the qual for every tuple on the page when it sees
`lossy = true`.  This is enforced at iterate time in
`tbm_private_iterate` (lines 1098-1108) [verified-by-code]:

```c
tbmres->blockno = chunk_blockno;
tbmres->lossy = true;
tbmres->recheck = true;
```

— `recheck = true` is hard-coded for lossy pages.

## The three lifecycle states — `TBM_EMPTY` / `TBM_ONE_PAGE` / `TBM_HASH`

`tidbitmap.c:121-126` [verified-by-code]:

```c
typedef enum
{
    TBM_EMPTY,      /* no hashtable, nentries == 0 */
    TBM_ONE_PAGE,   /* entry1 contains the single entry */
    TBM_HASH,       /* pagetable is valid, entry1 is not */
} TBMStatus;
```

The motivation, from the comment at `tidbitmap.c:110-119`
[from-comment]:

> We want to avoid the overhead of creating the hashtable,
> which is comparatively large, when not necessary.
> Particularly when we are using a bitmap scan on the inside
> of a nestloop join: a bitmap may well live only long enough
> to accumulate one entry in such cases.  We therefore avoid
> creating an actual hashtable until we need two pagetable
> entries.

So:

| Status | Storage | Used for |
|---|---|---|
| `TBM_EMPTY` | nothing | freshly `tbm_create`d, no inserts yet |
| `TBM_ONE_PAGE` | `tbm->entry1` (inline field) | exactly one page, common in nestloop |
| `TBM_HASH` | `tbm->pagetable` (simplehash) | the general case |

The transitions happen in `tbm_get_pageentry`
(`tidbitmap.c:1202-1244`) [verified-by-code]:

```c
if (tbm->status == TBM_EMPTY)
{
    /* Use the fixed slot */
    page = &tbm->entry1;
    tbm->status = TBM_ONE_PAGE;
}
else
{
    if (tbm->status == TBM_ONE_PAGE)
    {
        page = &tbm->entry1;
        if (page->blockno == pageno)
            return page;
        /* Time to switch from one page to a hashtable */
        tbm_create_pagetable(tbm);
    }
    page = pagetable_insert(tbm->pagetable, pageno, &found);
}
```

`tbm_create_pagetable` at `tidbitmap.c:281-306` [verified-by-code]
allocates the simplehash and migrates the existing single entry:

```c
tbm->pagetable = pagetable_create(tbm->mcxt, 128, tbm);

if (tbm->status == TBM_ONE_PAGE)
{
    PagetableEntry *page;
    bool found;
    char oldstatus;

    page = pagetable_insert(tbm->pagetable,
                            tbm->entry1.blockno,
                            &found);
    Assert(!found);
    oldstatus = page->status;
    memcpy(page, &tbm->entry1, sizeof(PagetableEntry));
    page->status = oldstatus;
}

tbm->status = TBM_HASH;
```

The `oldstatus` save/restore is necessary because simplehash uses
the `status` field for its own bookkeeping (slot occupancy
tracking) — the copy from `entry1` would clobber it, so we
preserve and re-write.

One subtlety, also documented in the lifecycle comment
[from-comment]:

> NOTE: we don't get rid of the hashtable if the bitmap later
> shrinks down to zero or one page again.  So, status can be
> TBM_HASH even when nentries is zero or one.

Once you've allocated the simplehash, you keep it for the
TIDBitmap's lifetime.  This avoids re-allocation if the bitmap
shrinks-then-grows.

## The `pagetable` simplehash — generated, not handwritten

`tidbitmap.c:232-243` [verified-by-code]:

```c
#define SH_USE_NONDEFAULT_ALLOCATOR
#define SH_PREFIX pagetable
#define SH_ELEMENT_TYPE PagetableEntry
#define SH_KEY_TYPE BlockNumber
#define SH_KEY blockno
#define SH_HASH_KEY(tb, key) murmurhash32(key)
#define SH_EQUAL(tb, a, b) a == b
#define SH_SCOPE static inline
#define SH_DEFINE
#define SH_DECLARE
#include "lib/simplehash.h"
```

Open-addressing simplehash with `murmurhash32` over the
`BlockNumber` — fast, in-place, no per-entry pointer chasing.
The `SH_USE_NONDEFAULT_ALLOCATOR` is what lets `tbm_create`
specify a per-bitmap memory context (`tbm->mcxt`) so frees
happen on `MemoryContextDelete` automatically.

The `status` field on `PagetableEntry` (line 95) is what
simplehash uses to track slot occupancy — `SH_STATUS_EMPTY`,
`SH_STATUS_IN_USE`, etc.  This is why most of the code goes to
care about `oldstatus = page->status` before
`MemSet(page, 0, ...)` resets the entry's user-visible fields:

```c
/* tidbitmap.c:1232-1241 */
if (!found)
{
    char oldstatus = page->status;
    MemSet(page, 0, sizeof(PagetableEntry));
    page->status = oldstatus;
    page->blockno = pageno;
    /* must count it too */
    tbm->nentries++;
    tbm->npages++;
}
```

Saving `oldstatus`, MemSet-ing the whole struct, then restoring
`oldstatus` is the canonical "reset user fields without disturbing
simplehash bookkeeping" pattern.

## The full `TIDBitmap` struct

`tidbitmap.c:141-162` [verified-by-code]:

```c
struct TIDBitmap
{
    NodeTag       type;             /* to make it a valid Node */
    MemoryContext mcxt;             /* memory context containing me */
    TBMStatus     status;
    struct pagetable_hash *pagetable;
    int           nentries;         /* number of entries in pagetable */
    int           maxentries;       /* limit on same to meet maxbytes */
    int           npages;           /* exact entries */
    int           nchunks;          /* lossy chunk entries */
    TBMIteratingState iterating;
    uint32        lossify_start;    /* lossify rotation cursor */
    PagetableEntry entry1;          /* used when status == TBM_ONE_PAGE */
    /* iteration state, valid after tbm_begin_iterate */
    PagetableEntry **spages;        /* sorted exact-page list */
    PagetableEntry **schunks;       /* sorted lossy-chunk list */
    /* DSA pointers, parallel-bitmap-scan only */
    dsa_pointer    dsapagetable;
    dsa_pointer    dsapagetableold;
    dsa_pointer    ptpages;
    dsa_pointer    ptchunks;
    dsa_area      *dsa;
};
```

Field-by-field crib sheet:

- **`nentries = npages + nchunks`** — total pagetable entries.
  Maintained as the sum throughout add/delete operations.
- **`maxentries`** — calculated by `tbm_calculate_entries(maxbytes)`
  from `work_mem`.  Once `nentries > maxentries`, `tbm_lossify`
  kicks in.
- **`iterating`** — `TBM_NOT_ITERATING` / `TBM_ITERATING_PRIVATE`
  / `TBM_ITERATING_SHARED`.  Once any iterator begins,
  modifications are forbidden — many of the build functions
  `Assert(!tbm->iterating)` at entry.
- **`lossify_start`** — round-robin cursor so consecutive
  `tbm_lossify` passes don't keep targeting the same range of
  the hashtable (see `tidbitmap.c:1389-1396`)
  [verified-by-code].
- **`entry1`** — the inline single-entry slot for `TBM_ONE_PAGE`.
- **`spages` / `schunks`** — sorted arrays of pointers built at
  `tbm_begin_private_iterate` time (or DSA pointers
  `ptpages` / `ptchunks` for shared iterators).
- **`dsa*` fields** — only populated when `tbm_create` is
  called with a non-NULL DSA area, i.e. for parallel bitmap
  scans.  See [[parallel-bitmap-heap]] for that flow.

## Public iterate-result — `TBMIterateResult`

The result struct `tidbitmap.h` (not fully shown) exposes:

```c
typedef struct TBMIterateResult
{
    BlockNumber blockno;
    bool        lossy;
    bool        recheck;
    void       *internal_page;     /* opaque PagetableEntry */
} TBMIterateResult;
```

Three things to notice:

1. **No `offsets[]` array.**  The caller doesn't receive the
   list of offsets directly — instead, it gets the opaque
   `internal_page` pointer and uses
   `tbm_extract_page_tuple(iteritem, offsets, max_offsets)`
   to fill an array.
2. **`lossy` is the page-level signal.**  When set, the caller
   re-reads the whole heap page and re-checks the qual on
   every tuple.
3. **`recheck` carries the per-tuple "candidate" semantics.**
   Set when the index AM said "matching but not certain"; set
   automatically for lossy pages.

The `tbm_extract_page_tuple` helper at `tidbitmap.c:898-933`
[verified-by-code] walks the `words[]` array decoding set bits
back to 1-based `OffsetNumber`s.  See
[[tidbitmap-build-and-iterate]] for the full iteration flow.

## Memory budget — `tbm_calculate_entries`

The `maxbytes` argument to `tbm_create` is the **work_mem**
budget for this bitmap; `tbm_calculate_entries` converts it to a
target entry count using `sizeof(PagetableEntry)` plus simplehash
overhead.  When `nentries > maxentries` after an insert,
`tbm_lossify` runs — collapsing some exact entries into chunks
to fit.

The "we admit we can't fit" escape at `tidbitmap.c:1408-1419`
[verified-by-code]:

```c
/*
 * With a big bitmap and small work_mem, it's possible that we
 * cannot get under maxentries.  Again, if that happens, we'd
 * end up uselessly calling tbm_lossify over and over.  To
 * prevent this from becoming a performance sink, force
 * maxentries up to at least double the current number of
 * entries.  (In essence, we're admitting inability to fit
 * within work_mem when we do this.)
 */
if (tbm->nentries > tbm->maxentries / 2)
    tbm->maxentries = Min(tbm->nentries, (INT_MAX - 1) / 2) * 2;
```

Crucial behavioral detail: **TIDBitmap doesn't fail when it
overflows work_mem**.  It expands silently and you'll see
elevated memory usage in EXPLAIN ANALYZE.  This is by design —
returning wrong results would be worse than over-spending
memory.

## `entry1` vs. hashtable lookups — `tbm_find_pageentry`

`tidbitmap.c:1169-1192` [verified-by-code]:

```c
static const PagetableEntry *
tbm_find_pageentry(const TIDBitmap *tbm, BlockNumber pageno)
{
    const PagetableEntry *page;

    if (tbm->nentries == 0)
        return NULL;

    if (tbm->status == TBM_ONE_PAGE)
    {
        page = &tbm->entry1;
        if (page->blockno != pageno)
            return NULL;
        Assert(!page->ischunk);
        return page;
    }

    page = pagetable_lookup(tbm->pagetable, pageno);
    if (page == NULL)
        return NULL;
    if (page->ischunk)
        return NULL;        /* don't want a lossy chunk header */
    return page;
}
```

Three lookups in sequence — return early if `nentries == 0`,
return either-`entry1` or null if `TBM_ONE_PAGE`, otherwise hash
lookup.  The final `if (page->ischunk) return NULL` is the
**critical** semantic: lookups asking for an "exact entry at
pageno" must get NULL if that pageno is covered by a lossy
chunk — they can't fetch the chunk header masquerading as an
exact page.

The complementary `tbm_get_pageentry` (lines 1202-1244)
[verified-by-code] is the **insert-or-get** variant — it
creates a new exact entry if missing, but the caller is
responsible for checking `tbm_page_is_lossy(blkno)` first.  See
the dance at `tbm_add_tuples` lines 390-400 [verified-by-code]:

```c
if (blk != currblk)
{
    if (tbm_page_is_lossy(tbm, blk))
        page = NULL;        /* remember page is lossy */
    else
        page = tbm_get_pageentry(tbm, blk);
    currblk = blk;
}

if (page == NULL)
    continue;        /* whole page is already marked */
```

If the page is lossy, the new tuple insert is a no-op — the
chunk's bit for that page is already set, the whole page will
be re-scanned later, and recording individual tuples is wasted
work.

## Invariants worth remembering

1. **`PagetableEntry.blockno` is the simplehash key.**  No two
   entries can have the same blockno; lossy chunks and exact
   entries live in disjoint blockno ranges.
2. **A chunk-header `blockno` is always
   `(orig_blockno / PAGES_PER_CHUNK) * PAGES_PER_CHUNK`.**
3. **An entry's `ischunk` bit is monotone — once flipped to
   true, never goes back.**  `tbm_lossify` is one-way.
4. **`recheck = true` on every lossy result; `recheck =
   page->recheck` on every exact result.**
5. **`status = oldstatus` save/restore is mandatory before any
   `MemSet(page, 0, ...)`.**  Simplehash bookkeeping lives in
   that byte.
6. **`TBM_HASH` is sticky.**  Once `tbm_create_pagetable`
   runs, the bitmap stays in `TBM_HASH` even if it shrinks.
7. **Iteration is read-only.**  Any `tbm_add_*` / `tbm_union`
   / `tbm_intersect` call after `tbm_begin_*iterate` is
   forbidden and Asserts.
8. **`nentries = npages + nchunks` is a hard invariant
   maintained by every add/delete site.**
9. **`maxentries` is advisory — the bitmap silently doubles
   it rather than fail.**  Plan for memory growth beyond
   `work_mem`.
10. **Lookups for exact entries return NULL when the page is
    covered by a lossy chunk** (`tbm_find_pageentry` final
    check).

## Useful greps

```bash
# All four PagetableEntry creation/mutation sites
grep -n "PagetableEntry\|pagetable_insert\|pagetable_lookup\|pagetable_delete" \
    source/src/backend/nodes/tidbitmap.c

# Lossy/exact transition arithmetic
grep -n "PAGES_PER_CHUNK\|ischunk\|chunk_pageno" \
    source/src/backend/nodes/tidbitmap.c

# Status machine
grep -n "TBM_EMPTY\|TBM_ONE_PAGE\|TBM_HASH\|tbm_create_pagetable" \
    source/src/backend/nodes/tidbitmap.c

# Simplehash hookup
grep -n "SH_PREFIX pagetable\|SH_HASH_KEY\|SH_EQUAL\|murmurhash32" \
    source/src/backend/nodes/tidbitmap.c

# Recheck flag propagation
grep -n "recheck\|tbmres->recheck\|tbmres->lossy" \
    source/src/backend/nodes/tidbitmap.c
```

## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/nodes/tidbitmap.c`](../files/src/backend/nodes/tidbitmap.c.md) | — | entire implementation |
| [`src/include/nodes/tidbitmap.h`](../files/src/include/nodes/tidbitmap.h.md) | — | public API + TBMIterateResult |

<!-- /callsites:auto -->

## Scenarios that use me
<!-- scenarios:auto -->

*Auto-derived from direct references + transitive file-overlap.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

_(none detected — this idiom is either cross-cutting infrastructure or an internal helper pattern)_

<!-- /scenarios:auto -->
## Cross-references

- [[tidbitmap-build-and-iterate]] — the dynamic half: insert,
  union, intersect, iterate (private + shared), lossify trigger.
- [[bitmap-and-or-heap-executor]] — `BitmapHeapScan`,
  `BitmapAnd`, `BitmapOr` — how the executor produces and
  consumes a TIDBitmap.
- [[parallel-bitmap-heap]] — DSA-backed shared TIDBitmaps for
  parallel bitmap-heap scans.
- [[brin-summarize-and-scan]] — BRIN's `bringetbitmap` calls
  `tbm_add_tuples`/`tbm_add_page` per range.
- [[gin-scan-and-consistent]] — GIN's posting-tree scan adds to
  the same bitmap.
- [[spgist-scan-and-consistent]] — SP-GiST's `spggetbitmap`
  funnels into `tbm_add_tuples` via `storeBitmap`.
- [[memory-contexts]] — `tbm->mcxt` is the per-bitmap context;
  `MemoryContextDelete` is the cleanup path.
- [[simplehash-pattern]] — the generic `simplehash.h` open-
  addressing template used here.
