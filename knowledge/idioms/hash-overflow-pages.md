# Hash overflow pages — bitmap-tracked recyclable pages with hashm_firstfree hint

When a bucket's primary page fills, the hash AM allocates an
**overflow page** and chains it via `hasho_nextblkno`. Overflow pages
are stored in the same index file as bucket pages, interspersed
between splitpoint phases. To track which overflow pages are free vs
in-use, the AM keeps **bitmap pages** (`LH_BITMAP_PAGE`) — one bit
per overflow page, 0 = free, 1 = in-use.

The metapage's `hashm_firstfree` is the **lowest bit number known
to be free**, used as a starting hint for allocation searches.
Newly-allocated overflow pages flip their bit to 1; deletions
during vacuum flip back to 0 and update `hashm_firstfree` if
needed.

This doc covers the bit-number-to-block-number conversion via the
`hashm_spares[]` array, the `_hash_addovflpage` allocation flow
(first-free search → recycle existing free page OR extend file +
maybe add new bitmap page), `_hash_freeovflpage`'s **two-phase chain
splice + bit clear** during vacuum cleanup, the locking order to
avoid deadlock with inserters, and the `HASH_MAX_BITMAPS` ceiling.

Companion docs:
- [[hash-page-layout]] — `hashm_spares[]` array and splitpoint addressing.
- [[hash-bucket-split]] — splits use overflow allocation when target bucket fills.

## Anchors

- `source/src/backend/access/hash/README` — sections "Free Space Management" + "Bitmaps".
- `source/src/backend/access/hash/hashovfl.c:1-30` — banner.
- `source/src/backend/access/hash/hashovfl.c:35-54` — `bitno_to_blkno`.
- `source/src/backend/access/hash/hashovfl.c:62-90` — `_hash_ovflblkno_to_bitno`.
- `source/src/backend/access/hash/hashovfl.c:112-490` — `_hash_addovflpage`.
- `source/src/backend/access/hash/hashovfl.c:492-770` — `_hash_freeovflpage`.
- `source/src/backend/access/hash/hashovfl.c:777-840` — `_hash_initbitmapbuffer`.
- `source/src/include/access/hash.h:230` — `HASH_MAX_BITMAPS = min(BLCKSZ/8, 1024)`.
- `source/src/include/access/hash.h:301-340` — `BMPG_SHIFT`, `BMPG_MASK`, `BITS_PER_MAP`, `HashPageGetBitmap`.

## The bit-number → block-number mapping

Every overflow page has a unique **bit number** (zero-based count
across all overflow pages in the index). To convert bit number to
physical block:

```c
/* hashovfl.c:35-54 */
static BlockNumber bitno_to_blkno(HashMetaPage metap, uint32 ovflbitnum)
{
    uint32 splitnum = metap->hashm_ovflpoint;
    uint32 i;

    ovflbitnum += 1;                                  /* 0-based → 1-based */

    /* Find the splitpoint this overflow page belongs to */
    for (i = 1; i < splitnum && ovflbitnum > metap->hashm_spares[i]; i++)
        ;

    /* Block = bucket pages before this splitpoint + this overflow's position */
    return (BlockNumber)(_hash_get_totalbuckets(i) + ovflbitnum);
}
```

[verified-by-code] (`hashovfl.c:35-54`).

The algorithm: walk `hashm_spares[]` until we find the splitpoint
whose overflow-page range includes this bit number, then add the
position. `_hash_get_totalbuckets(i)` returns the total buckets
allocated through splitpoint phase i.

The inverse (`_hash_ovflblkno_to_bitno`, `hashovfl.c:62`) does the
same thing in reverse — given a physical block number, find its
bit number for the bitmap.

## Bitmap page layout

Each bitmap page has:

```
PageHeader (standard)
[BITS_PER_PAGE bits of free/in-use markers]   ← uint32 array
HashPageOpaqueData                            ← in special area
```

`HashPageGetBitmap(page)` returns a `uint32 *` pointer to the bit
array. The page's `hasho_flag = LH_BITMAP_PAGE`.

Key constants:

- `BITS_PER_MAP = 32` (bits per uint32 word).
- `BMPG_SHIFT(metap) = hashm_bmshift` — log2 of bits per bitmap page.
- `BMPG_MASK(metap) = (1 << BMPG_SHIFT) - 1` — to mod a bit number.
- `BMPGSZ_BIT(metap) = 1 << BMPG_SHIFT` — total bits per page.

So `bitmappage = bitno >> BMPG_SHIFT` and `bitmapbit = bitno &
BMPG_MASK`. [verified-by-code] (use of `BMPG_SHIFT` in
`hashovfl.c:564`).

## `_hash_addovflpage` — allocation

Called from `_hash_doinsert` when a bucket fills, and from
`_hash_splitbucket` when redistribution needs a new overflow page in
the target bucket. Five stages:

```c
/* hashovfl.c:112-490 (skeleton) */
Buffer _hash_addovflpage(Relation rel, Buffer metabuf, Buffer buf, bool retain_pin)
{
    /* Stage 1: walk to the bucket's tail page */
    LockBuffer(buf, EXCLUSIVE);
    for (;;) {
        if (!hasho_nextblkno_valid) break;
        /* Release current page, advance to next */
        retain_pin = false;  buf = _hash_getbuf(next);
    }

    /* Stage 2: take metapage lock to search bitmap */
    LockBuffer(metabuf, EXCLUSIVE);

    orig_firstfree = metap->hashm_firstfree;
    first_page = orig_firstfree >> BMPG_SHIFT;
    bit = orig_firstfree & BMPG_MASK;
    i = first_page; j = bit / BITS_PER_MAP; bit &= ~(BITS_PER_MAP - 1);

    /* Stage 3: outer loop over bitmap pages, inner loop over words */
    for (;;) {
        splitnum = metap->hashm_ovflpoint;
        max_ovflpg = metap->hashm_spares[splitnum] - 1;
        last_page = max_ovflpg >> BMPG_SHIFT;
        last_bit  = max_ovflpg & BMPG_MASK;
        if (i > last_page) break;                       /* no free page found */

        mapblkno = metap->hashm_mapp[i];
        last_inpage = (i == last_page) ? last_bit : BMPGSZ_BIT - 1;

        LockBuffer(metabuf, UNLOCK);                    /* release metapage */
        mapbuf = _hash_getbuf(rel, mapblkno, HASH_WRITE, LH_BITMAP_PAGE);
        freep = HashPageGetBitmap(mappage);

        for (; bit <= last_inpage; j++, bit += BITS_PER_MAP) {
            if (freep[j] != ALL_SET) {                  /* a free bit somewhere */
                LockBuffer(metabuf, EXCLUSIVE);
                bit += _hash_firstfreebit(freep[j]);    /* find which bit */
                bitmap_page_bit = bit;
                bit += (i << BMPG_SHIFT);               /* → absolute bit number */
                blkno = bitno_to_blkno(metap, bit);
                ovflbuf = _hash_getinitbuf(rel, blkno); /* fetch + init the recycled page */
                page_found = true;
                goto found;
            }
        }
        _hash_relbuf(rel, mapbuf);                       /* this bitmap full; next */
        i++; j = 0; bit = 0;
        LockBuffer(metabuf, EXCLUSIVE);
    }

    /* Stage 4: no recyclable page — extend the file */
    if (last_bit == BMPGSZ_BIT - 1) {
        /* Current bitmap is full → need new bitmap page too */
        if (metap->hashm_nmaps >= HASH_MAX_BITMAPS)
            ereport(ERROR, ..., "out of overflow pages");
        newmapbuf = _hash_getnewbuf(rel, bitno_to_blkno(metap, metap->hashm_spares[splitnum]), ...);
    }

    /* Allocate the actual overflow page (one or two new blocks) */
    bit = newmapbuf ? metap->hashm_spares[splitnum] + 1 : metap->hashm_spares[splitnum];
    blkno = bitno_to_blkno(metap, bit);
    ovflbuf = _hash_getnewbuf(rel, blkno, MAIN_FORKNUM);

found:
    /* Stage 5: update under critical section */
    START_CRIT_SECTION();
    if (page_found) {
        SETBIT(freep, bitmap_page_bit);
        MarkBufferDirty(mapbuf);
    } else {
        metap->hashm_spares[splitnum]++;
        if (newmapbuf) {
            _hash_initbitmapbuffer(newmapbuf, metap->hashm_bmsize, false);
            metap->hashm_mapp[metap->hashm_nmaps++] = BufferGetBlockNumber(newmapbuf);
            metap->hashm_spares[splitnum]++;            /* for the bitmap itself */
        }
    }

    /* Link new overflow page into bucket chain */
    pageopaque->hasho_nextblkno = BufferGetBlockNumber(ovflbuf);    /* tail.next = new */
    ovflopaque->hasho_prevblkno = BufferGetBlockNumber(buf);        /* new.prev = tail */
    ovflopaque->hasho_nextblkno = InvalidBlockNumber;
    ovflopaque->hasho_bucket    = pageopaque->hasho_bucket;
    ovflopaque->hasho_flag      = LH_OVERFLOW_PAGE;

    /* Update hashm_firstfree if we used it */
    if (bit > orig_firstfree)
        metap->hashm_firstfree = bit + 1;
    else
        metap->hashm_firstfree = orig_firstfree;        /* keep hint */

    /* WAL */
    if (RelationNeedsWAL(rel)) ...;
    END_CRIT_SECTION();
    return ovflbuf;
}
```

[verified-by-code] (`hashovfl.c:112-490`).

### The recycle-first policy

The outer loop starts at `hashm_firstfree` and walks bitmap pages.
The first bit found that's 0 (free) wins — we recycle that page
instead of extending the file. This keeps the index file compact;
extensions only happen when every existing overflow page is in use.

`hashm_firstfree` is a **hint**, not a guarantee. It can lag behind
reality (a page is freed but `firstfree` isn't updated downward) —
but the allocator handles this by continuing to search forward.
The update at the end of allocation only moves `firstfree` forward
to the **next** free bit position.

### Extending the file — and maybe a new bitmap

If no recyclable page exists, we extend the file at the tail of the
current splitpoint phase. The check `last_bit == BMPGSZ_BIT - 1`
detects "this allocation would push us past the current bitmap
page's capacity" and pre-allocates a new bitmap page in the same
WAL record. The new bitmap is initialized with **all bits set to
1** (in-use); the just-allocated overflow page corresponds to one
of those bits.

The "two new blocks at once" trick is what the comment calls "two
pages in the new bitmap's range will exist immediately: the bitmap
page itself, and the following page which is the one we return to
the caller." [from-comment] (`hashovfl.c:272-278`).

### `HASH_MAX_BITMAPS` ceiling

`HASH_MAX_BITMAPS = min(BLCKSZ/8, 1024)`. With 8 KiB pages, this
gives 1024 bitmaps × 64 KiB bits per bitmap = 64M overflow pages
× 8 KiB = **256 GB of overflow space**. Beyond this, the AM refuses
to allocate and raises `out of overflow pages in hash index`.
[verified-by-code] (`hashovfl.c:282-286`, `hash.h:230`).

### Lock order — avoiding deadlock with inserters

> Here, we need to maintain locking order such that, first acquire
> the lock on tail page of bucket, then on meta page to find and
> lock the bitmap page and if it is found, then lock on meta page
> is released, then finally acquire the lock on new overflow buffer.
> We need this locking order to avoid deadlock with backends that
> are doing inserts.

[from-comment] (`hashovfl.c:138-143`).

The order: **tail → meta → bitmap → new-overflow**. Concurrent
inserters take **tail → meta** in the same order. Since the bitmap
+ new-overflow are taken after releasing the metapage, no
overlapping lock holders deadlock.

### Single WAL record for the entire operation

> Note: We could have avoided locking many buffers here if we made
> two WAL records for acquiring an overflow page (one to allocate
> an overflow page and another to add it to overflow bucket chain).
> However, doing so can leak an overflow page, if the system crashes
> after allocation. Needless to say, it is better to have a single
> record from a performance point of view as well.

[from-comment] (`hashovfl.c:144-150`).

The atomic-allocation+link guarantee requires holding several
buffer locks at once during the WAL emit. Tradeoff: more locks held
briefly vs leaked pages on crash.

## `_hash_freeovflpage` — deallocation during vacuum

Called by `hashbucketcleanup` when vacuum has emptied an overflow
page (all its tuples were dead). Steps:

```c
/* hashovfl.c:492-770 (skeleton) */
BlockNumber _hash_freeovflpage(...)
{
    /* Get prev/next pointers from doomed page */
    ovflbitno = _hash_ovflblkno_to_bitno(metap, ovflblkno);
    bitmappage = ovflbitno >> BMPG_SHIFT;
    bitmapbit  = ovflbitno & BMPG_MASK;
    blkno = metap->hashm_mapp[bitmappage];

    LockBuffer(metabuf, UNLOCK);                   /* drop meta read lock */

    mapbuf = _hash_getbuf(rel, blkno, HASH_WRITE, LH_BITMAP_PAGE);
    freep = HashPageGetBitmap(mappage);
    Assert(ISSET(freep, bitmapbit));

    LockBuffer(metabuf, EXCLUSIVE);

    START_CRIT_SECTION();

    /* Insert salvaged tuples on wbuf (the write page = end of bucket chain) */
    if (nitups > 0)
        _hash_pgaddmultitup(rel, wbuf, itups, ...);

    /* Re-init the freed overflow page */
    _hash_pageinit(ovflpage, ...);
    ovflopaque->hasho_prevblkno = InvalidBlockNumber;
    ovflopaque->hasho_nextblkno = InvalidBlockNumber;
    ovflopaque->hasho_bucket = InvalidBucket;
    ovflopaque->hasho_flag = LH_UNUSED_PAGE;

    /* Splice the doomed page out of the bucket chain */
    if (prevbuf) prevopaque->hasho_nextblkno = nextblkno;
    if (nextbuf) nextopaque->hasho_prevblkno = prevblkno;

    /* Clear the bitmap bit */
    CLRBIT(freep, bitmapbit);

    /* Update hashm_firstfree if this is now the lowest free */
    if (ovflbitno < metap->hashm_firstfree) {
        metap->hashm_firstfree = ovflbitno;
        update_metap = true;
    }
    END_CRIT_SECTION();
    return nextblkno;
}
```

[verified-by-code] (`hashovfl.c:492-770`).

### "Move tuples to write page"

The `wbuf` parameter is the current "write page" — vacuum's
squeeze process tries to compact a bucket by moving live tuples
from later overflow pages to earlier ones. `_hash_freeovflpage` is
called only after vacuum has decided the doomed page's tuples can
be moved to `wbuf` and the doomed page can be released. The
`itups[]` array carries those tuples for the actual `PageAddItem`
call.

### Chain splice — doubly-linked list

Overflow pages are doubly-linked via `hasho_prevblkno` and
`hasho_nextblkno`. Removing one requires fixing both the
predecessor's `nextblkno` and the successor's `prevblkno`. The
doomed page itself gets fully re-initialized to `LH_UNUSED_PAGE`
so future allocations can reuse it cleanly.

### `hashm_firstfree` decrement — only forward... wait

Note the asymmetry: `_hash_addovflpage` always moves `firstfree`
forward; `_hash_freeovflpage` moves it **backward** when the
freed bit is lower. This is the only place `firstfree` goes
backward, ensuring the hint stays correct after vacuum.

## The squeeze pass

After vacuuming a bucket's pages individually, the cleanup pass
calls `_hash_squeezebucket` to compact tuples toward the front of
the bucket chain (primary first, then overflow pages in order).
The squeeze:

1. Take cleanup lock on primary bucket page.
2. Walk to last overflow page.
3. Move its tuples to the **write page** (currently the page just
   before, then earlier pages as their slots fill).
4. When an overflow page becomes empty, call `_hash_freeovflpage`
   to remove it from the chain and free its bit.

The squeeze is conservative — it only runs when the cleanup lock
is available (i.e. no scans active). For most workloads, this means
overflow pages accumulate during inserts and get reclaimed at
VACUUM time. [from-comment] (`README` "Bucket Squeeze").

## Cleanup-lock dependency

> VACUUM therefore takes a cleanup lock on every bucket page in
> order to remove tuples. It can also remove tuples copied to a new
> bucket by any previous split operation, because the cleanup lock
> taken on the primary bucket page guarantees that no scans which
> started prior to the most recent split can still be in progress.

[from-comment] (`README` "Lock Definitions").

Two ways the cleanup lock matters for overflow pages:

1. Vacuum needs cleanup lock to delete dead tuples from any page.
2. Squeeze needs cleanup lock to move tuples between pages without
   stomping on concurrent scans.

If cleanup lock can't be acquired, vacuum skips the bucket for
this round (returns to it on retry).

## Invariants and races

1. **`hashm_firstfree` is a hint**, monotonically advanced forward
   by allocation, occasionally backward by free. Search must
   continue past it if no free bit is found at that position.
2. **Bitmap pages are themselves overflow pages** — their bit
   numbers are 0-based and the first bit of each bitmap page
   represents itself (falls out of allocation order, not
   essential). [from-comment] (`README`).
3. **`HASH_MAX_BITMAPS` ceiling** at 1024 bitmaps × 64K bits ×
   8 KiB = 256 GB of overflow space. Beyond this, the index
   refuses new pages.
4. **Single WAL record for allocate+link** prevents page leaks on
   crash, at the cost of holding more locks briefly.
5. **Lock order**: tail-of-bucket → metapage → bitmap → new-overflow.
   [from-comment] (`hashovfl.c:138-143`).
6. **Freed overflow page is re-initialized**, not zero-filled —
   WAL replay expects a valid header. [from-comment]
   (`hashovfl.c:600-606`).
7. **Overflow pages are doubly-linked** via `hasho_prevblkno` +
   `hasho_nextblkno`. Removal splices both ends.
8. **Bitmap bit 0 = free, 1 = in-use** — opposite of some other PG
   bitmap conventions. New bitmap pages are initialized
   **all-ones** then the just-allocated page's bit is left set.
9. **First bit of every bitmap page represents the bitmap itself** —
   the bit is always 1 (in-use). [from-comment] (`README`).

## Useful greps

```bash
# Top-level alloc / free:
grep -nE "_hash_addovflpage|_hash_freeovflpage|_hash_initbitmapbuffer" \
       source/src/backend/access/hash/hashovfl.c

# Bit conversion:
grep -nE "bitno_to_blkno|_hash_ovflblkno_to_bitno|_hash_firstfreebit" \
       source/src/backend/access/hash/hashovfl.c

# Bitmap constants:
grep -rn "BMPG_SHIFT\|BMPG_MASK\|BMPGSZ_BIT\|BITS_PER_MAP\|HASH_MAX_BITMAPS" \
       source/src/include/access/hash.h

# Squeeze + cleanup:
grep -n "_hash_squeezebucket\|hashbucketcleanup" source/src/backend/access/hash/

# WAL records for overflow:
grep -n "XLOG_HASH_ADD_OVFL_PAGE\|XLOG_HASH_DELETE\|XLH_FREE" \
       source/src/include/access/hash_xlog.h
```

## Cross-references

- [[hash-page-layout]] — `hashm_spares[]` array and splitpoint addressing the bit-to-block conversion relies on.
- [[hash-bucket-split]] — bucket splits call `_hash_addovflpage` when target bucket fills.
- `source/src/backend/access/hash/README` — full design.
