# TIDBitmap — build, union/intersect, and iterate

This is the **dynamic** half of TIDBitmap.  For the static
shape — `PagetableEntry`, the three lifecycle states, the
chunk-arithmetic constants, the recheck flag — see
[[tidbitmap-structure-and-lossy]].  This doc covers the
build-time operations the index AMs and `BitmapAnd`/`BitmapOr`
use, plus the iteration protocol that `BitmapHeapScan`
consumes.

**Anchors** (all cites against `source/` at commit `e18b0cb7344`):
- `source/src/backend/nodes/tidbitmap.c:366-1162` — all build + iterate APIs
- `source/src/include/nodes/tidbitmap.h` — `TBMIterateResult`

## Lifecycle — `tbm_create` → add → iterate → free

The five operations and their constraints:

| Op | When | Modifies | Iterating-allowed? |
|---|---|---|---|
| `tbm_create` | once | new TIDBitmap | n/a |
| `tbm_add_tuples` | many | nentries, words | NO (Asserts) |
| `tbm_add_page` | many | nentries, words | NO |
| `tbm_union` / `tbm_intersect` | combine bitmaps | a in-place | NO |
| `tbm_begin_private_iterate` / `_shared_` | freeze | sorts spages/schunks | once-only transition |
| `tbm_private_iterate` / `_shared_` | drain | iterator cursor | required |
| `tbm_end_*iterate` | drop iterator | iterator only | yes |
| `tbm_free` | done | drop pagetable + free | yes |

The state machine has one **frozen** transition: once any
iterator is created, the bitmap is read-only.  Build sites
`Assert(!tbm->iterating)`; iterate sites `Assert(tbm->iterating
== TBM_ITERATING_*)`.

## Insert — `tbm_add_tuples`

`tidbitmap.c:366-423` [verified-by-code].  This is the per-tuple
insert path used by every index AM's `amgetbitmap`.

```c
void
tbm_add_tuples(TIDBitmap *tbm, const ItemPointerData *tids,
               int ntids, bool recheck)
{
    BlockNumber currblk = InvalidBlockNumber;
    PagetableEntry *page = NULL;

    Assert(tbm->iterating == TBM_NOT_ITERATING);
    for (int i = 0; i < ntids; i++)
    {
        BlockNumber blk = ItemPointerGetBlockNumber(tids + i);
        OffsetNumber off = ItemPointerGetOffsetNumber(tids + i);
        int wordnum, bitnum;

        if (off < 1 || off > TBM_MAX_TUPLES_PER_PAGE)
            elog(ERROR, "tuple offset out of range: %u", off);

        if (blk != currblk)
        {
            if (tbm_page_is_lossy(tbm, blk))
                page = NULL;
            else
                page = tbm_get_pageentry(tbm, blk);
            currblk = blk;
        }

        if (page == NULL)
            continue;  /* whole page is already marked */

        if (page->ischunk)
        {
            /* The page is a lossy chunk header, set bit for itself */
            wordnum = bitnum = 0;
        }
        else
        {
            wordnum = WORDNUM(off - 1);
            bitnum = BITNUM(off - 1);
        }
        page->words[wordnum] |= ((bitmapword) 1 << bitnum);
        page->recheck |= recheck;

        if (tbm->nentries > tbm->maxentries)
        {
            tbm_lossify(tbm);
            currblk = InvalidBlockNumber;  /* force re-lookup */
        }
    }
}
```

Three optimizations the comments call out:

### 1. The `currblk` shortcut

The `if (blk != currblk)` test (line 390) is documented at
`tidbitmap.c:385-389` [from-comment]:

> Look up target page unless we already did.  This saves cycles
> when the input includes consecutive tuples on the same page,
> which is common enough to justify an extra test here.

Index AMs typically deliver TIDs sorted by `(blockno, offset)`,
so most adjacent items share `blk` — the hash lookup runs once
per page-transition instead of once per tuple.

### 2. The lossy-page no-op

Line 392-394 + line 399-400 [verified-by-code]:

```c
if (tbm_page_is_lossy(tbm, blk))
    page = NULL;        /* remember page is lossy */
...
if (page == NULL)
    continue;            /* whole page is already marked */
```

If the page is covered by an existing lossy chunk, the new tuple
is *already* implicitly included — the chunk bit is set for that
page, the whole page will be re-scanned at iterate time, and
recording individual offsets is wasted work.  This is what
makes consecutive `tbm_add_tuples` calls *cheaper* as the bitmap
fills up, not more expensive.

### 3. The `currblk = InvalidBlockNumber` invalidation after lossify

Line 419-420 [verified-by-code]:

```c
if (tbm->nentries > tbm->maxentries)
{
    tbm_lossify(tbm);
    /* Page could have been converted to lossy, so force new lookup */
    currblk = InvalidBlockNumber;
}
```

`tbm_lossify` may have just converted `currblk`'s entry into a
chunk.  The cached `page` pointer still points at it, but
`page->ischunk` is now true and the `words[]` layout has
flipped.  Invalidating `currblk` forces a re-lookup on the next
iteration that calls `tbm_page_is_lossy(blk)` correctly.

## Page-level insert — `tbm_add_page`

`tidbitmap.c:431-439` [verified-by-code].  Used when the index
AM only knows "some tuple on this page matches" — typically
BRIN summarize-and-scan or fallback paths for lossy GIN bitmaps.

```c
void
tbm_add_page(TIDBitmap *tbm, BlockNumber pageno)
{
    /* Enter the page in the bitmap, or mark it lossy if already present */
    tbm_mark_page_lossy(tbm, pageno);
    /* If we went over the memory limit, lossify some more pages */
    if (tbm->nentries > tbm->maxentries)
        tbm_lossify(tbm);
}
```

Two-line wrapper: `tbm_mark_page_lossy` forces this page into
the chunk-bit representation (deleting any prior exact entry
for it), then the standard lossify trigger.  **Every
`tbm_add_page` is implicitly recheck-required** because the
whole-page representation has no per-tuple resolution.

## Union — `tbm_union`

`tidbitmap.c:446-466` [verified-by-code] dispatches to
`tbm_union_page` (lines 469-520) per entry of `b`.  `a` is
modified in-place; `b` is unchanged.

`tbm_union_page` has three branches:

### Branch 1 — bpage is a lossy chunk

Lines 474-494 [verified-by-code].  For each set bit in the
chunk, call `tbm_mark_page_lossy(a, pg)`.  This expands the
chunk into per-page lossy marks in `a`; if any of those pages
had exact entries in `a`, they get clobbered.

### Branch 2 — bpage is exact, but a's page is already lossy

Lines 496-500 [verified-by-code]:

```c
else if (tbm_page_is_lossy(a, bpage->blockno))
{
    /* page is already lossy in a, nothing to do */
    return;
}
```

A's lossy chunk subsumes whatever exact bits b has.

### Branch 3 — both exact

Lines 502-516 [verified-by-code]:

```c
apage = tbm_get_pageentry(a, bpage->blockno);
if (apage->ischunk)
{
    apage->words[0] |= ((bitmapword) 1 << 0);
}
else
{
    /* Both pages are exact, merge at the bit level */
    for (int wordnum = 0; wordnum < WORDS_PER_PAGE; wordnum++)
        apage->words[wordnum] |= bpage->words[wordnum];
    apage->recheck |= bpage->recheck;
}
```

The `apage->ischunk` arm catches the case where
`tbm_get_pageentry(a, blockno)` returned an existing chunk
header (the blockno is itself a chunk boundary).  Setting bit 0
in the chunk's `words[0]` records "blockno+0 has tuples", which
is what we want.

The exact-exact case is the obvious OR-over-words.  Recheck
flags also OR.

## Intersect — `tbm_intersect`

`tidbitmap.c:527-569` [verified-by-code] is symmetric:
`tbm_intersect_page` per entry of `a`, deleting entries that
become empty.

`tbm_intersect_page` (lines 576-651) has the same three-way
branch but more bookkeeping because it can produce **empty
pages** that need deletion:

### Branch 1 — apage is a chunk, walk b for each page

Lines 581-619 [verified-by-code].  For each set chunk bit, check
b: if b doesn't have an entry for that page (exact or lossy),
clear the chunk bit.  If after the walk all chunk bits are
clear, return `true` (delete).

### Branch 2 — apage is exact, but b's page is lossy

Lines 620-629 [verified-by-code]:

```c
else if (tbm_page_is_lossy(b, apage->blockno))
{
    /*
     * Some of the tuples in 'a' might not satisfy the quals for 'b',
     * but because the page 'b' is lossy, we don't know which ones.
     * Therefore we mark 'a' as requiring rechecks, to indicate that
     * at most those tuples set in 'a' are matches.
     */
    apage->recheck = true;
    return false;
}
```

The result is the tuples in a's exact representation, but
flagged for recheck because we lost precision on b's side.
This is the formalization of "lossy ∩ exact = recheck-required
exact".

### Branch 3 — both exact, bit-level AND

Lines 631-650 [verified-by-code]:

```c
bpage = tbm_find_pageentry(b, apage->blockno);
if (bpage != NULL)
{
    for (int wordnum = 0; wordnum < WORDS_PER_PAGE; wordnum++)
    {
        apage->words[wordnum] &= bpage->words[wordnum];
        if (apage->words[wordnum] != 0)
            candelete = false;
    }
    apage->recheck |= bpage->recheck;
}
/* If there is no matching b page, we can just delete the a page */
return candelete;
```

`apage->words &= bpage->words` is the work; `candelete` becomes
true if every word is now zero.  If b has no entry for this
blockno at all, b implicitly contributes a zero bitmap and we
delete.

The outer loop at `tidbitmap.c:553-567` [verified-by-code]
handles the deletion:

```c
if (tbm_intersect_page(a, apage, b))
{
    if (apage->ischunk)
        a->nchunks--;
    else
        a->npages--;
    a->nentries--;
    if (!pagetable_delete(a->pagetable, apage->blockno))
        elog(ERROR, "hash table corrupted");
}
```

`pagetable_delete` returns false if the entry wasn't there — the
elog catches inconsistencies.

## Lossify — `tbm_lossify`

`tidbitmap.c:1355-1419` [verified-by-code], called when
`nentries > maxentries`.  It iterates the hash table looking for
exact entries to convert to lossy chunks.  Three things to know:

### The half-the-budget target

Lines 1366-1369 [from-comment]:

> Since we are called as soon as nentries exceeds maxentries,
> we should push nentries down to significantly less than
> maxentries, or else we'll just end up doing this again very
> soon.  We shoot for maxentries/2.

The break-out check at line 1389:

```c
if (tbm->nentries <= tbm->maxentries / 2)
{
    tbm->lossify_start = i.cur;
    break;
}
```

Saving `lossify_start = i.cur` ensures the next lossify pass
starts from a different point in the hashtable, distributing
lossy regions roughly uniformly over time.

### The "skip already-a-chunk-boundary" skip

Lines 1382-1384 [verified-by-code]:

```c
if ((page->blockno % PAGES_PER_CHUNK) == 0)
    continue;
```

Why?  Converting a page that *is* its own chunk header saves
zero entries — the entry stays, just with `ischunk` flipped.
Skipping it focuses lossify on pages that *will* be subsumed
into a chunk header at a different blockno.

### The "I cannot fit" escape

Lines 1417-1418 [verified-by-code]:

```c
if (tbm->nentries > tbm->maxentries / 2)
    tbm->maxentries = Min(tbm->nentries, (INT_MAX - 1) / 2) * 2;
```

When the entire bitmap is already lossy (every entry is a
chunk), no further lossification reduces `nentries`.  Rather
than spin in an infinite lossify loop, we **silently expand
`maxentries`** to double the current count.  The
"In essence, we're admitting inability to fit within work_mem"
note at lines 1411-1414 [from-comment] is honest about it.

Operational consequence: queries that exceed `work_mem` via
bitmap scans don't fail, they just consume extra memory.
Monitor process RSS, not just `work_mem` settings.

## Private iteration — `tbm_begin_private_iterate` + `tbm_private_iterate`

`tidbitmap.c:675-740` [verified-by-code] is the freeze
operation.  Two arrays are built once and shared by all
iterators on this bitmap:

```c
if (tbm->status == TBM_HASH && tbm->iterating == TBM_NOT_ITERATING)
{
    ...
    if (!tbm->spages && tbm->npages > 0)
        tbm->spages = palloc(tbm->npages * sizeof(PagetableEntry *));
    if (!tbm->schunks && tbm->nchunks > 0)
        tbm->schunks = palloc(tbm->nchunks * sizeof(PagetableEntry *));

    pagetable_start_iterate(tbm->pagetable, &i);
    while ((page = pagetable_iterate(tbm->pagetable, &i)) != NULL)
    {
        if (page->ischunk)
            tbm->schunks[nchunks++] = page;
        else
            tbm->spages[npages++] = page;
    }
    if (npages > 1)
        qsort(tbm->spages, npages, sizeof(PagetableEntry *), tbm_comparator);
    if (nchunks > 1)
        qsort(tbm->schunks, nchunks, sizeof(PagetableEntry *), tbm_comparator);
}

tbm->iterating = TBM_ITERATING_PRIVATE;
```

Two arrays, each sorted by `blockno`.  The comparator at
`tidbitmap.c:1424-1431` [verified-by-code] is just
`pg_cmp_u32` on `blockno`.

The motivation for two arrays (not one) is the **merge** that
iterate does next: walking sorted lossy chunks and sorted exact
pages in lockstep, emitting the smaller blockno at each step.

### `tbm_private_iterate` — the merge

`tidbitmap.c:973-1044` [verified-by-code].  The shape:

```
1. Advance schunkptr/schunkbit forward to next set chunk bit
   (skip over zero bits inside the chunk via tbm_advance_schunkbit).

2. If we have a lossy chunk bit AND
   (no more exact pages OR
    chunk_blockno < exact_pages[spageptr]->blockno):
       emit chunk_blockno as lossy, advance schunkbit
       return true

3. If we have an exact page:
       emit it
       advance spageptr
       return true

4. Otherwise: tbmres->blockno = InvalidBlockNumber
              return false (done)
```

The merge guarantee from the API doc at `tidbitmap.c:957`
[from-comment]:

> Pages are guaranteed to be delivered in numerical order.

This is what makes `BitmapHeapScan` able to use a read-stream
prefetch: it can issue async reads for the next few pages
without worrying about random-order arrivals.

### `tbm_advance_schunkbit`

`tidbitmap.c:934-950` [verified-by-code].  Walks a chunk's
words[] looking for the next set bit:

```c
while (schunkbit < PAGES_PER_CHUNK)
{
    int wordnum = WORDNUM(schunkbit);
    int bitnum = BITNUM(schunkbit);

    if ((chunk->words[wordnum] & ((bitmapword) 1 << bitnum)) != 0)
        break;
    schunkbit++;
}
*schunkbitp = schunkbit;
```

Naïve linear walk — a popcnt-based bitscan would be faster but
the loop is hit so rarely (only once per emitted lossy page)
that the simplicity wins.

## Shared iteration — `tbm_prepare_shared_iterate`

`tidbitmap.c:752-889` [verified-by-code].  Used by
parallel bitmap-heap scans.  Three things differ from the
private version:

### 1. All state lives in DSA, not local memory

The sorted arrays go into `PTIterationArray` structs allocated
via `dsa_allocate`; the bitmap itself is also DSA-backed.  The
`PTEntryArray` and `PTIterationArray` structs both carry an
atomic `refcount` field so multiple iterators can share — last
one to release calls `dsa_free`.

```c
/* tidbitmap.c:787-799 */
if (tbm->npages)
{
    tbm->ptpages = dsa_allocate(tbm->dsa, sizeof(PTIterationArray) +
                                tbm->npages * sizeof(int));
    ptpages = dsa_get_address(tbm->dsa, tbm->ptpages);
    pg_atomic_init_u32(&ptpages->refcount, 0);
}
```

### 2. Index arrays, not pointer arrays

Pointers don't work across processes because addresses differ
per process.  Instead, `PTIterationArray.index[]` holds
**integer indexes** into `PTEntryArray.ptentry[]`.  Each
worker dereferences via `&ptbase[idxpages[spageptr]]`.

```c
/* tidbitmap.c:815-820 */
idx = page - ptbase->ptentry;
if (page->ischunk)
    ptchunks->index[nchunks++] = idx;
else
    ptpages->index[npages++] = idx;
```

### 3. LWLock-protected iteration cursor

`TBMSharedIteratorState` has `spageptr`, `schunkptr`,
`schunkbit` plus an `LWLock`.  Each `tbm_shared_iterate` call
acquires the lock, advances the cursor, releases.  This
serializes the *cursor advance* — the actual heap fetch and
qual eval happen later in parallel.

```c
/* tidbitmap.c:1068-1069 */
/* Acquire the LWLock before accessing the shared members */
LWLockAcquire(&istate->lock, LW_EXCLUSIVE);
```

The lock is held only for the cursor advance + the
`PagetableEntry` copy into `tbmres`; the lock is released
before returning, so workers can do their per-page work in
parallel.

### Comparator for shared iteration

`tbm_shared_comparator` at `tidbitmap.c:1438-1446`
[verified-by-code] dereferences index into the base array
before comparing blockno — the qsort_arg context is the array
base pointer:

```c
static int
tbm_shared_comparator(const void *left, const void *right, void *arg)
{
    PagetableEntry *base = (PagetableEntry *) arg;
    PagetableEntry *l = &base[*(const int *) left];
    PagetableEntry *r = &base[*(const int *) right];
    return pg_cmp_u32(l->blockno, r->blockno);
}
```

## Per-page tuple extraction — `tbm_extract_page_tuple`

`tidbitmap.c:898-929` [verified-by-code].  After iterate yields
a non-lossy page, the caller fills an `OffsetNumber` array by
walking the bitmap words:

```c
for (int wordnum = 0; wordnum < WORDS_PER_PAGE; wordnum++)
{
    bitmapword w = page->words[wordnum];

    if (w != 0)
    {
        int off = wordnum * BITS_PER_BITMAPWORD + 1;

        while (w != 0)
        {
            if (w & 1)
            {
                if (ntuples < max_offsets)
                    offsets[ntuples] = (OffsetNumber) off;
                ntuples++;
            }
            off++;
            w >>= 1;
        }
    }
}
return ntuples;
```

Three things to notice:

1. **`+1` offset transform**: bit `k` in `words[]` represents
   offset `k+1` (because OffsetNumber is 1-based, but the
   bitmap is 0-indexed).
2. **`max_offsets` is advisory**: if the page has more matches
   than fit, the function returns the total count without
   writing past `max_offsets`.  The caller can decide whether
   to error or alloc more.
3. **Naive bit-twiddle, no popcnt**: same simplicity-first
   choice as `tbm_advance_schunkbit`.

The typical caller is `BitmapHeapScan` — see
[[bitmap-and-or-heap-executor]] for how this fits into the
larger executor loop.

## Invariants worth remembering

1. **Once any iterator is created, modifications are
   forbidden.**  All build sites Assert; the bitmap is
   effectively frozen.
2. **Lossify can fire on every `tbm_add_tuples` /
   `tbm_add_page` call.**  Maintain `currblk = InvalidBlockNumber`
   after lossify because cached page pointers may have flipped
   to chunk-mode.
3. **Pages are delivered in increasing blockno order.**  This
   is the merge invariant that lets `BitmapHeapScan` prefetch.
4. **Lossy chunks are merged in chunk-bit order, not chunk
   blockno order** — `tbm_advance_schunkbit` walks bits within
   a chunk before moving to the next chunk.
5. **Intersection of an exact `a` page with a lossy `b` page
   ⇒ a stays exact but recheck = true.**  This is how recheck
   propagates through `BitmapAnd`.
6. **Union of an exact `a` page with a lossy `b` chunk ⇒ a's
   page becomes lossy.**  Lossy is a "ratchet" — once introduced
   into a page's representation, never goes back.
7. **DSA iteration uses `int` indexes, not pointers.**  Cross-
   process pointer values are not portable.
8. **Shared iterators serialize cursor advance via an LWLock.**
   Per-page heap work happens in parallel after the cursor
   advance returns.
9. **`tbm_extract_page_tuple` writes 1-based OffsetNumbers
   from 0-based bits.**  Don't forget the `+1`.
10. **`tbm_free_shared_area` honors refcounts.**  Last
    iterator out frees the DSA allocations.

## Useful greps

```bash
# Build entry points
grep -n "^tbm_add_tuples\|^tbm_add_page\|^tbm_union\|^tbm_intersect" \
    source/src/backend/nodes/tidbitmap.c

# Iterate entry points
grep -n "tbm_begin_private_iterate\|tbm_prepare_shared_iterate\|tbm_private_iterate\|tbm_shared_iterate\|tbm_extract_page_tuple" \
    source/src/backend/nodes/tidbitmap.c

# Lossify trigger sites
grep -n "tbm_lossify\|tbm->nentries > tbm->maxentries" \
    source/src/backend/nodes/tidbitmap.c

# DSA atomics + refcounting
grep -n "pg_atomic_init_u32\|pg_atomic_add_fetch_u32\|pg_atomic_sub_fetch_u32" \
    source/src/backend/nodes/tidbitmap.c

# Index AM callers
grep -rn "tbm_add_tuples\|tbm_add_page" source/src/backend/access/ | head
```



## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/nodes/tidbitmap.c`](../files/src/backend/nodes/tidbitmap.c.md) | 366 | all build + iterate APIs |
| [`src/include/nodes/tidbitmap.h`](../files/src/include/nodes/tidbitmap.h.md) | — | TBMIterateResult |

<!-- /callsites:auto -->

## Cross-references

- [[tidbitmap-structure-and-lossy]] — `PagetableEntry`, the
  three-state lifecycle, lossy/exact arithmetic.
- [[bitmap-and-or-heap-executor]] — the executor side
  (`BitmapHeapScan` + `BitmapAnd` + `BitmapOr`).
- [[parallel-bitmap-heap]] — full parallel bitmap-heap scan
  flow using the shared iteration here.
- [[brin-summarize-and-scan]] — `bringetbitmap` is a major
  caller of `tbm_add_tuples`/`tbm_add_page`.
- [[gin-scan-and-consistent]] — `gingetbitmap` calls
  `tbm_add_tuples` per matched posting-tree entry.
- [[spgist-scan-and-consistent]] — `spggetbitmap` funnels into
  `tbm_add_tuples` via the `storeBitmap` callback.
- [[buffer-manager]] — `LWLockAcquire(LW_EXCLUSIVE)` on
  `LWTRANCHE_SHARED_TIDBITMAP` is the cursor lock.
- [[memory-contexts]] — `tbm->mcxt` lifecycle; spages/schunks
  are allocated in this context, not the iterator.
