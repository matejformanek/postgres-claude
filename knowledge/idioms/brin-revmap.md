# BRIN revmap — the heap-block-range → summary-tuple translation page

BRIN's revmap is the index's **only first-class lookup structure**: a
flat array (spread across the first N blocks after the metapage) where
the i-th slot holds the ItemPointer of the summary tuple for the i-th
page range. Heap block X → range = `X / pagesPerRange` → revmap entry
gives `(blk, off)` of the BrinTuple summarizing that range.

There is **no B-tree** in a BRIN index. The revmap is a fixed-stride
array; lookup is two arithmetic divisions and one buffer fetch. The
tradeoff: every range probe touches the same revmap blocks (hot in
buffer cache), and the index size is `~(heap_pages / pagesPerRange) ×
sizeof(ItemPointer)` regardless of distinct-key cardinality. A 1 TB
table with `pages_per_range=128` (default) has 8 GB / 1 MB = 8192
ranges → 8192 × 6 bytes = ~48 KB of revmap. The summary tuples
themselves are typically ~50-200 bytes each, totaling another ~400 KB.

This doc walks the metapage + revmap layout, the
`brinGetTupleForHeapBlock` lookup with concurrent-update retry, the
`revmap_physical_extend` pageops dance (evacuate regular tuples to
grow), and the desummarize path that re-opens a range to incremental
rebuild.

Companion docs:
- [[brin-tuple-format]] — what the revmap points at.
- [[brin-summarize-and-scan]] — the summarize-range builder + bringetbitmap scan.

## Anchors

- `source/src/backend/access/brin/README` — design overview (~150 lines, complete read).
- `source/src/backend/access/brin/brin_revmap.c:1-19` — banner.
- `source/src/backend/access/brin/brin_revmap.c:40-43` — HEAPBLK→revmap arithmetic macros.
- `source/src/backend/access/brin/brin_revmap.c:46-53` — `BrinRevmap` struct.
- `source/src/backend/access/brin/brin_revmap.c:69-94` — `brinRevmapInitialize`.
- `source/src/backend/access/brin/brin_revmap.c:154-192` — `brinSetHeapBlockItemptr` (writer).
- `source/src/backend/access/brin/brin_revmap.c:194-313` — `brinGetTupleForHeapBlock` (reader; the hot path).
- `source/src/backend/access/brin/brin_revmap.c:322-440` — `brinRevmapDesummarizeRange`.
- `source/src/backend/access/brin/brin_revmap.c:500-640` — `revmap_physical_extend`.
- `source/src/include/access/brin_page.h:51-94` — page-type constants, `BrinMetaPageData`, `RevmapContents`, `REVMAP_PAGE_MAXITEMS`.

## Index physical layout

```
Block 0     │ BrinMetaPageData (magic, version, pagesPerRange, lastRevmapPage)
Block 1     │ RevmapContents { ItemPointerData rm_tids[REVMAP_PAGE_MAXITEMS] }
Block 2     │ RevmapContents { ItemPointerData rm_tids[REVMAP_PAGE_MAXITEMS] }
...
Block K     │ RevmapContents { ... }                                    ← lastRevmapPage
Block K+1   │ Regular BRIN page: BrinTuple data
Block K+2   │ Regular BRIN page: BrinTuple data
...
```

`REVMAP_PAGE_MAXITEMS = REVMAP_CONTENT_SIZE / sizeof(ItemPointerData)`
≈ `(8192 − headers) / 6 ≈ 1350` entries per revmap page. So each
revmap page covers `1350 × pagesPerRange` heap pages. With default
`pagesPerRange = 128` and `BLCKSZ = 8 KiB`, one revmap page covers
`128 × 1350 = 172 800` heap pages = ~1.35 GiB of heap. A 1 TB table
needs only ~750 revmap pages. [verified-by-code]
(`brin_page.h:78-94`).

## The metapage — BrinMetaPageData

```c
/* brin_page.h:64-70 */
typedef struct BrinMetaPageData {
    uint32       brinMagic;          /* 0xA8109CFA */
    uint32       brinVersion;        /* BRIN_CURRENT_VERSION = 1 */
    BlockNumber  pagesPerRange;      /* fixed at index creation */
    BlockNumber  lastRevmapPage;     /* highest-numbered revmap block */
} BrinMetaPageData;
```

`pagesPerRange` is **immutable** after CREATE INDEX. Changing it
requires REINDEX. `lastRevmapPage` grows as the heap grows; new
revmap pages get allocated by `revmap_physical_extend` (covered
below). [verified-by-code] (`brin_page.h:64-72`).

## The HEAPBLK arithmetic

```c
/* brin_revmap.c:40-43 */
#define HEAPBLK_TO_REVMAP_BLK(pagesPerRange, heapBlk) \
    ((heapBlk / pagesPerRange) / REVMAP_PAGE_MAXITEMS)
#define HEAPBLK_TO_REVMAP_INDEX(pagesPerRange, heapBlk) \
    ((heapBlk / pagesPerRange) % REVMAP_PAGE_MAXITEMS)
```

Two divisions to translate a heap block number to `(revmap page,
index within page)`:

1. `heapBlk / pagesPerRange` = range number (0, 1, 2, ...).
2. range number / `REVMAP_PAGE_MAXITEMS` = which revmap *page*.
3. range number % `REVMAP_PAGE_MAXITEMS` = position within that page.
4. Add 1 to the revmap-page result because block 0 is the metapage.

So heap block 1000, `pagesPerRange = 128`, `REVMAP_PAGE_MAXITEMS = 1350`:
- range = 1000 / 128 = 7
- revmap page = 7 / 1350 = 0 → physical block = 0 + 1 = 1
- index within page = 7 % 1350 = 7

[verified-by-code] (`brin_revmap.c:447`, `brin_revmap.c:505`).

## The revmap access object — BrinRevmap

```c
/* brin_revmap.c:46-53 */
struct BrinRevmap {
    Relation     rm_irel;
    BlockNumber  rm_pagesPerRange;
    BlockNumber  rm_lastRevmapPage;  /* cached from metapage */
    Buffer       rm_metaBuf;          /* pinned for the lifetime of revmap */
    Buffer       rm_currBuf;          /* most recently touched revmap page */
};
```

`brinRevmapInitialize` (`brin_revmap.c:69`) reads the metapage,
caches `pagesPerRange` and `lastRevmapPage`, and pins the metapage
buffer for the lifetime of the access object. `rm_currBuf` is a
working buffer used by callers to avoid re-pinning the same revmap
page across multiple lookups in the same scan. [verified-by-code]
(`brin_revmap.c:77-93`).

The metapage is pinned but **not locked** outside `revmap_physical_extend` —
that's the only operation that needs to mutate `lastRevmapPage`.

## The reader — brinGetTupleForHeapBlock

This is the hot path called by both `bringetbitmap` (scan) and the
inserter (check if a page range needs re-summarization).

```c
/* brin_revmap.c:194-313 (skeleton) */
BrinTuple *brinGetTupleForHeapBlock(BrinRevmap *revmap, BlockNumber heapBlk,
                                    Buffer *buf, OffsetNumber *off, Size *size,
                                    int mode)
{
    /* Normalize heapBlk to the first page in its range */
    heapBlk = (heapBlk / revmap->rm_pagesPerRange) * revmap->rm_pagesPerRange;

    mapBlk = revmap_get_blkno(revmap, heapBlk);
    if (mapBlk == InvalidBlockNumber) {                  /* not yet summarized */
        *off = InvalidOffsetNumber;
        return NULL;
    }

    ItemPointerSetInvalid(&previptr);
    for (;;) {                                           /* retry on stale TID */
        CHECK_FOR_INTERRUPTS();

        if (rm_currBuf is wrong page) ReleaseBuffer(rm_currBuf), ReadBuffer(mapBlk);
        LockBuffer(rm_currBuf, BUFFER_LOCK_SHARE);

        contents = (RevmapContents *) PageGetContents(BufferGetPage(rm_currBuf));
        iptr = &contents->rm_tids[HEAPBLK_TO_REVMAP_INDEX(pagesPerRange, heapBlk)];

        if (!ItemPointerIsValid(iptr)) {                 /* range not summarized */
            LockBuffer(rm_currBuf, UNLOCK);
            return NULL;
        }

        /* Anti-loop guard: same TID twice = revmap corruption */
        if (ItemPointerIsValid(&previptr) && ItemPointerEquals(&previptr, iptr))
            ereport(ERROR, ... "corrupted BRIN index: inconsistent range map");
        previptr = *iptr;

        blk = ItemPointerGetBlockNumber(iptr);
        *off = ItemPointerGetOffsetNumber(iptr);
        LockBuffer(rm_currBuf, UNLOCK);

        /* Follow the pointer to the regular BRIN page */
        if (!BufferIsValid(*buf) || BufferGetBlockNumber(*buf) != blk) {
            if (BufferIsValid(*buf)) ReleaseBuffer(*buf);
            *buf = ReadBuffer(idxRel, blk);
        }
        LockBuffer(*buf, mode);
        page = BufferGetPage(*buf);

        /* Defensive: if we landed on a revmap page, restart (very rare) */
        if (BRIN_IS_REGULAR_PAGE(page)) {
            if (*off > PageGetMaxOffsetNumber(page))     /* desummarized race */
                return NULL;
            lp = PageGetItemId(page, *off);
            if (ItemIdIsUsed(lp)) {
                tup = (BrinTuple *) PageGetItem(page, lp);
                if (tup->bt_blkno == heapBlk) {
                    if (size) *size = ItemIdGetLength(lp);
                    return tup;                          /* FOUND */
                }
            }
        }

        /* No luck — concurrent update; retry */
        LockBuffer(*buf, BUFFER_LOCK_UNLOCK);
    }
}
```

[verified-by-code] (`brin_revmap.c:194-313`).

Six properties:

1. **HeapBlk normalization** — the input may be any page in the range;
   we normalize to the range's first page for the revmap index.
   [verified-by-code] (`brin_revmap.c:208`).
2. **Shared lock on revmap page**, exclusive lock on the regular
   page (or share, depending on `mode`). Two-step locking: read the
   pointer, drop the revmap lock, then fetch the target. Concurrent
   `brinSetHeapBlockItemptr` can update the pointer between these
   steps; the retry loop catches the resulting `tup->bt_blkno !=
   heapBlk` mismatch.
3. **`bt_blkno` cross-check** is the durability guarantee against
   stale revmap reads. If the revmap pointed at TID T at the time we
   read it, but T was concurrently reused by an evacuation, the
   tuple at T will have a different `bt_blkno` — we retry.
4. **Anti-loop guard via `previptr`** — if the revmap returns the
   same TID twice in a row but we never landed on the right tuple,
   the index is corrupt; raise `ERRCODE_INDEX_CORRUPTED`.
   [from-comment] (`brin_revmap.c:250-260`).
5. **Land-on-revmap-page test** (`BRIN_IS_REGULAR_PAGE(page)` check)
   handles a rare race where a concurrent extension evacuates the
   target page into a revmap page. The loop retries.
   [verified-by-code] (`brin_revmap.c:277-278`).
6. **Concurrent desummarize** — if the page range was concurrently
   desummarized (offset out of range), return NULL. The caller treats
   this the same as "not yet summarized." [verified-by-code]
   (`brin_revmap.c:285-289`).

## The writer — brinSetHeapBlockItemptr

```c
/* brin_revmap.c:154-192 */
void brinSetHeapBlockItemptr(Buffer buf, BlockNumber pagesPerRange,
                              BlockNumber heapBlk, ItemPointerData tid)
{
    /* Caller has the revmap page locked exclusive */
    contents = (RevmapContents *) PageGetContents(BufferGetPage(buf));
    iptr = contents->rm_tids;
    iptr += HEAPBLK_TO_REVMAP_INDEX(pagesPerRange, heapBlk);
    *iptr = tid;
}
```

Simple — just compute the index slot and write the new ItemPointer.
The caller must have locked the page exclusive (acquired via
`brinLockRevmapPageForUpdate`) and is responsible for writing WAL +
setting LSN afterward.

The "used during WAL replay" comment is the key: the same function
runs during XLOG_BRIN_INSERT/UPDATE/etc. redo, where the WAL record
provides `(heapBlk, tid)` and replay applies the bit-identical
change. [from-comment] (`brin_revmap.c:147-152`).

## Extending the revmap — revmap_physical_extend

When `revmap_get_blkno(heapBlk)` would return a block past
`lastRevmapPage`, we must allocate a new revmap page. The complication:
the index file may have grown with **regular BRIN pages** past the
current `lastRevmapPage` — those pages need to be **evacuated** out of
the way before the slot at `lastRevmapPage + 1` can be claimed for the
revmap.

```c
/* brin_revmap.c:521-640 (skeleton) */
static void revmap_physical_extend(BrinRevmap *revmap)
{
    /* Step 1: lock the metapage exclusive */
    LockBuffer(rm_metaBuf, EXCLUSIVE);
    metadata = PageGetContents(rm_metaBuf);

    /* Step 2: recheck cached lastRevmapPage */
    if (metadata->lastRevmapPage != revmap->rm_lastRevmapPage) {
        revmap->rm_lastRevmapPage = metadata->lastRevmapPage;
        LockBuffer(rm_metaBuf, UNLOCK);
        return;                                          /* caller retries */
    }
    mapBlk = metadata->lastRevmapPage + 1;

    /* Step 3: get the buffer — read or extend */
    nblocks = RelationGetNumberOfBlocks(irel);
    if (mapBlk < nblocks) {
        buf = ReadBuffer(irel, mapBlk);
        LockBuffer(buf, EXCLUSIVE);
    } else {
        buf = ExtendBufferedRel(BMR_REL(irel), MAIN_FORKNUM, NULL, EB_LOCK_FIRST);
        if (BufferGetBlockNumber(buf) != mapBlk) {
            /* extreme race: someone else extended; retry */
            LockBuffer(rm_metaBuf, UNLOCK);
            UnlockReleaseBuffer(buf);
            return;
        }
    }

    /* Step 4: corruption check on page type */
    if (!PageIsNew(page) && !BRIN_IS_REGULAR_PAGE(page))
        ereport(ERROR, ... "unexpected page type 0x%04X");

    /* Step 5: EVACUATE if in use */
    if (brin_start_evacuating_page(irel, buf)) {
        LockBuffer(rm_metaBuf, UNLOCK);
        brin_evacuate_page(irel, pagesPerRange, revmap, buf);
        return;                                          /* caller retries */
    }

    /* Step 6: convert to revmap page */
    START_CRIT_SECTION();
    brin_page_init(page, BRIN_PAGETYPE_REVMAP);
    MarkBufferDirty(buf);
    metadata->lastRevmapPage = mapBlk;
    /* Fix pd_lower (for xlog compression) */
    ((PageHeader) metapage)->pd_lower = (char *)metadata + sizeof(BrinMetaPageData) - (char *)metapage;
    MarkBufferDirty(rm_metaBuf);

    if (RelationNeedsWAL(irel)) {
        xl_brin_revmap_extend xlrec = { .targetBlk = mapBlk };
        XLogRegisterBuffer(0, rm_metaBuf, REGBUF_STANDARD);
        XLogRegisterBuffer(1, buf, REGBUF_WILL_INIT);
        recptr = XLogInsert(RM_BRIN_ID, XLOG_BRIN_REVMAP_EXTEND);
        ...
    }
    END_CRIT_SECTION();
}
```

[verified-by-code] (`brin_revmap.c:521-640`).

Three retry-able failure cases (caller loops):

1. **Cached lastRevmapPage stale** — another extender raced ahead;
   refresh and retry.
2. **`ExtendBufferedRel` returned a different block** — someone
   extended the relation in parallel. Drop the locks and retry.
3. **Page is in use by regular BRIN tuples** — `brin_evacuate_page`
   migrates those tuples to other regular blocks; then the caller
   retries the extension.

The "evacuation" mechanism is what lets the revmap grow into space
that's already been written. The `BRIN_EVACUATE_PAGE` flag in
`BrinSpecialSpace` signals that the page is mid-evacuation;
`brin_start_evacuating_page` sets it under the buffer lock.
[verified-by-code] (`brin_page.h:60`).

## Desummarize — brinRevmapDesummarizeRange

User-invoked via `brin_desummarize_range(idx, blkno)`. Drops the
summary tuple for a range and clears the revmap entry, returning the
range to "unsummarized" state. Useful when summaries have become
loose due to many deletes (e.g. min/max no longer reflect actual
content).

```c
/* brin_revmap.c:322-440 (skeleton, key invariants) */
bool brinRevmapDesummarizeRange(Relation idxrel, BlockNumber heapBlk)
{
    /* Caller holds ShareUpdateExclusiveLock on the index */

    revmap = brinRevmapInitialize(idxrel, &pagesPerRange);
    heapBlk = (heapBlk / pagesPerRange) * pagesPerRange;

    /* Step 1: read the revmap entry */
    LockBuffer(revmapBuf, BUFFER_LOCK_SHARE);
    iptr = &contents->rm_tids[HEAPBLK_TO_REVMAP_INDEX(...)];
    if (!ItemPointerIsValid(iptr)) {                      /* already unsummarized */
        return true;
    }
    tid = *iptr;
    LockBuffer(revmapBuf, UNLOCK);

    /* Step 2: lock the regular page exclusive */
    LockBuffer(regBuf, EXCLUSIVE);

    /* Step 3: verify the tuple is still what we think (anti-race) */
    tup = PageGetItem(...);
    if (tup->bt_blkno != heapBlk) {
        UnlockBuffer; return false;                       /* caller retries */
    }

    /* Step 4: lock revmap exclusive, set tid invalid, delete tuple, WAL log */
    LockBuffer(revmapBuf, EXCLUSIVE);
    START_CRIT_SECTION();
    ItemPointerSetInvalid(iptr);
    PageIndexTupleDelete(regPage, off);
    /* WAL XLOG_BRIN_DESUMMARIZE */
    END_CRIT_SECTION();
    ...
}
```

The two-step "look + verify" is the same anti-race pattern as the
read path; the revmap pointer can move under us during the gap
between read and lock-for-write.

## Invariants and races

1. **`pagesPerRange` is immutable.** Change requires REINDEX.
2. **The revmap is contiguous from block 1 to `lastRevmapPage`.**
   Any block in that range is a revmap page; any block past it is
   a regular BRIN page.
3. **Revmap entries are 6-byte ItemPointers** — fixed-size array
   indexed by range number. No collisions, no chains.
4. **Concurrent inserters retry the revmap read** if the underlying
   BrinTuple has moved. The `bt_blkno` cross-check is what catches
   it. [verified-by-code] (`brin_revmap.c:294-302`).
5. **Anti-loop guard** raises `ERRCODE_INDEX_CORRUPTED` if the same
   TID is returned twice in a row without landing on the right
   tuple. [from-comment] (`brin_revmap.c:250-260`).
6. **Revmap extension may evacuate** regular tuples. The
   `BRIN_EVACUATE_PAGE` flag in `BrinSpecialSpace` is the marker.
7. **`brinSetHeapBlockItemptr` is reused by WAL replay.** Don't add
   per-call state that doesn't survive a redo.
   [from-comment] (`brin_revmap.c:147-152`).
8. **Metapage's `pd_lower` is fixed at extend-time** because pre-v11
   `pg_upgrade`d indexes have wrong `pd_lower` values, and xlog
   page-compression depends on it. [from-comment]
   (`brin_revmap.c:611-616`).

## Useful greps

```bash
# Every revmap call site:
grep -rn "brinRevmapInitialize\|brinGetTupleForHeapBlock\|brinSetHeapBlockItemptr\|brinRevmapExtend" \
       source/src/backend/access/brin/

# Page-type constants:
grep -n "BRIN_PAGETYPE\|BRIN_IS_" source/src/include/access/brin_page.h

# WAL record types:
grep -n "XLOG_BRIN_" source/src/include/access/brin_xlog.h

# Layout constants:
grep -nE "REVMAP_PAGE_MAXITEMS|HEAPBLK_TO_REVMAP|BRIN_META" \
       source/src/include/access/brin_page.h \
       source/src/backend/access/brin/brin_revmap.c
```



## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/access/brin/brin_revmap.c`](../files/src/backend/access/brin/brin_revmap.c.md) | 1 | banner |
| [`src/backend/access/brin/brin_revmap.c`](../files/src/backend/access/brin/brin_revmap.c.md) | 40 | HEAPBLK→revmap arithmetic macros |
| [`src/backend/access/brin/brin_revmap.c`](../files/src/backend/access/brin/brin_revmap.c.md) | 46 | BrinRevmap struct |
| [`src/backend/access/brin/brin_revmap.c`](../files/src/backend/access/brin/brin_revmap.c.md) | 69 | brinRevmapInitialize |
| [`src/backend/access/brin/brin_revmap.c`](../files/src/backend/access/brin/brin_revmap.c.md) | 154 | brinSetHeapBlockItemptr (writer) |
| [`src/backend/access/brin/brin_revmap.c`](../files/src/backend/access/brin/brin_revmap.c.md) | 194 | brinGetTupleForHeapBlock (reader; the hot path) |
| [`src/backend/access/brin/brin_revmap.c`](../files/src/backend/access/brin/brin_revmap.c.md) | 322 | brinRevmapDesummarizeRange |
| [`src/backend/access/brin/brin_revmap.c`](../files/src/backend/access/brin/brin_revmap.c.md) | 500 | revmap_physical_extend |
| [`src/include/access/brin_page.h`](../files/src/include/access/brin_page.h.md) | 51 | page-type constants, BrinMetaPageData, RevmapContents, REVMAP_PAGE_MAXITEMS |

<!-- /callsites:auto -->

## Cross-references

- [[brin-tuple-format]] — the BrinTuple layout the revmap points at.
- [[brin-summarize-and-scan]] — the writer + scanner that drive revmap traffic.
- `source/src/backend/access/brin/README` — design overview.
- `knowledge/subsystems/access-brin.md` (if exists) — subsystem-level view.
