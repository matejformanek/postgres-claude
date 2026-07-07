# GIN tree structure — entry B-tree of keys + posting trees / inline posting lists

GIN (Generalized INverted index) is built around the idea that one
indexable item (e.g. a tsvector document) contains **many keys** (e.g.
the lexemes), and a query for one key must return **many heap rows**.
The data structure is the classic inverted-index shape:

```
Entry tree (B-tree of keys)
  ├── key "alpha" → posting list of heap TIDs (small)         [inline]
  ├── key "beta"  → posting list of heap TIDs (small)         [inline]
  ├── key "the"   → ROOT of posting tree (big)                [external B-tree]
  │                 ├── leaf 1: compressed segments of TIDs
  │                 ├── leaf 2: compressed segments of TIDs
  │                 └── ...
  └── ...
```

The **entry tree** is a Lehman-Yao B-tree over the keys themselves —
no left-links, never deletes (the README justifies this: "the set of
distinct words in a large corpus changes very slowly"). Each leaf
entry stores either:

- **Inline posting list** — a sorted-then-varbyte-compressed array of
  ItemPointers embedded in the index tuple, used when the list is
  small enough.
- **Posting tree pointer** — a `(blkno, GIN_TREE_POSTING=0xFFFF)`
  sentinel ItemPointer pointing at the root of a separate B-tree
  whose keys are heap TIDs.

The choice between inline and external is dynamic: as a key
accumulates more heap rows, its inline list grows until it would
exceed the per-tuple size budget, then a posting tree is created and
the inline list is moved into it.

This doc covers the entry-tree shape, the **abuse of `t_tid`** in
entry-tuple headers (encoding posting offset vs posting-tree blkno
in the same field), the posting-tree page layout, the **varbyte
posting-list compression**, and the special "null category" entries
that let GIN handle NULL, empty arrays, and zero-length values.

Companion docs:
- [[gin-fastupdate-pending]] — the pending-list buffer that delays insertions.
- [[gin-scan-and-consistent]] — the query side: extractQueryFn + consistentFn.

## Anchors

- `source/src/backend/access/gin/README` — full design (~500 lines; read sections "Gin for PostgreSQL", "Concurrency", "Posting tree", "Posting List Compression").
- `source/src/include/access/ginblock.h:30-110` — `GinPageOpaqueData`, page-type flags (`GIN_DATA`, `GIN_LEAF`, `GIN_META`, `GIN_LIST`, `GIN_COMPRESSED`).
- `source/src/include/access/ginblock.h:55-101` — `GinMetaPageData` (head/tail of pending list + version + page counts).
- `source/src/include/access/ginblock.h:228-260` — entry-tuple `t_tid` abuse macros (`GinGetPostingOffset`, `GinIsPostingTree`, `GinSetPostingTree`).
- `source/src/include/access/ginblock.h:262-323` — data-page (posting tree) layout.
- `source/src/include/access/ginblock.h:336-344` — `GinPostingList` compressed-segment struct.
- `source/src/backend/access/gin/ginpostinglist.c` — varbyte codec.
- `source/src/backend/access/gin/ginbtree.c` — generic B-tree primitives (used by both entry tree and posting tree).
- `source/src/backend/access/gin/ginentrypage.c` — entry-tree-specific page ops.
- `source/src/backend/access/gin/gindatapage.c` — posting-tree-specific page ops.
- `source/src/backend/access/gin/ginutil.c` — `GinFormTuple` builder.

## Physical layout

```
Block 0 — Metapage (GinMetaPageData)
Block 1 — Entry tree ROOT
Block N — Pending list head/tail (linked via metapage)
Block M — Entry tree internal/leaf nodes
Block K — Posting tree pages (data pages, GIN_DATA flag)
```

[verified-by-code] (`ginblock.h:51-53`).

The metapage points at the pending list (`head`, `tail`,
`tailFreeSize`, counts). The entry tree root is at fixed block 1
(`GIN_ROOT_BLKNO`). Beyond that, blocks are typed by their
`GinPageOpaque` flags:

| Bit  | Flag                  | Meaning                                   |
|------|-----------------------|-------------------------------------------|
| 0    | `GIN_DATA`            | posting tree page (vs entry tree)         |
| 1    | `GIN_LEAF`            | leaf page                                 |
| 2    | `GIN_DELETED`         | empty + recyclable                        |
| 3    | `GIN_META`            | the metapage                              |
| 4    | `GIN_LIST`            | pending-list page                         |
| 5    | `GIN_LIST_FULLROW`    | pending-list page contains complete rows  |
| 6    | `GIN_INCOMPLETE_SPLIT`| post-split, parent downlink pending       |
| 7    | `GIN_COMPRESSED`      | data leaf page uses compressed format     |

The four orthogonal axes — entry vs data, leaf vs internal,
compressed vs uncompressed (pre-9.4 only), pending vs not — combine
into ~7 effective page types. [verified-by-code] (`ginblock.h:41-49`).

## Metapage — GinMetaPageData

```c
/* ginblock.h:55-101 */
typedef struct GinMetaPageData {
    BlockNumber head;                 /* pending list head */
    BlockNumber tail;                 /* pending list tail */
    uint32      tailFreeSize;
    BlockNumber nPendingPages;
    int64       nPendingHeapTuples;

    /* Planner stats (refreshed by VACUUM) */
    BlockNumber nTotalPages;
    BlockNumber nEntryPages;
    BlockNumber nDataPages;
    int64       nEntries;

    int32       ginVersion;           /* 0, 1, or 2 */
} GinMetaPageData;
```

`ginVersion = 2` (current) means: compressed posting lists in
posting trees + null/placeholder entries. v1 used uncompressed
posting trees (auto-upgraded on modify). v0 lacks null entries
entirely and rejects full-index scans. [from-comment]
(`ginblock.h:86-101`).

## Entry-tuple `t_tid` abuse — two cases

A GIN entry-tuple uses the index-tuple format from `index_form_tuple`
(column number + key datum + null bitmap), but **repurposes the
trailing `t_tid` field** to encode either an inline posting list or a
posting-tree root. The macros at `ginblock.h:228-240`:

### Case 1: Inline posting list

```c
GinGetPostingOffset(itup) = GinItemPointerGetBlockNumber(&itup->t_tid) & ~GIN_ITUP_COMPRESSED
                            /* byte offset from itup start to the posting list */
GinGetNPosting(itup)      = GinItemPointerGetOffsetNumber(&itup->t_tid)
                            /* count of heap TIDs in the inline list */
GinItupIsCompressed(itup) = high bit of the BlockNumber slot
GinGetPosting(itup)       = (char *)itup + GinGetPostingOffset(itup)
```

So `t_tid.ip_blkid` = (compressed-flag bit) | (byte offset within
tuple), and `t_tid.ip_posid` = number of heap TIDs in the list. The
list itself lives at the byte offset, after the index-tuple header
and (if present) null bitmap and category byte. [from-comment]
(`README` "Index tuple header fields of a leaf key entry are abused
as follows").

### Case 2: Posting tree

```c
GinIsPostingTree(itup)    = (GinGetNPosting(itup) == GIN_TREE_POSTING)   /* 0xFFFF */
GinGetPostingTree(itup)   = GinItemPointerGetBlockNumber(&itup->t_tid)
                            /* block number of the posting tree root */
GinSetPostingTree(itup, blkno):
    set OffsetNumber to GIN_TREE_POSTING
    set BlockNumber  to blkno
```

The sentinel `GIN_TREE_POSTING = 0xFFFF` is "large enough that that
many heap itempointers couldn't possibly fit on an index page"
(`README`). So if `GinGetNPosting(itup) == 0xFFFF`, treat the tuple
as a posting-tree pointer; otherwise it's an inline list of that
many TIDs. [verified-by-code] (`ginblock.h:231-234`).

The dual encoding lets every entry-tuple be exactly the same size
regardless of which case applies. The choice is made at insert/merge
time based on `GinMaxItemSize` (3 items must fit per page).

## Entry tree concurrency

The entry tree is a **Lehman-Yao B-tree** (right-link, no left-link),
similar to nbtree but with crucial differences:

1. **No deletions** in the entry tree. New keys can be added; existing
   keys can have their posting lists updated, but the key itself
   never goes away. This dramatically simplifies vacuum and
   concurrency.
2. **No dedicated high-key**. The rightmost tuple on a page serves as
   the high key. This works only because there are no deletions —
   if a leaf could shrink, the high key could decrease, and the
   parent's downlink would become stale.
3. **Lehman-Yao downlink layout is reversed from nbtree**:
   ```
   nbtree:  (K_{n+1}, None), (-Inf, P_0), (K_1, P_1), ..., (K_n, P_n)
   GIN:                      (P_0, K_1), (P_1, K_2), ..., (P_n, K_{n+1})
   ```
   GIN groups `P_i` with `K_{i+1}` — no -Inf placeholder needed.
   [from-comment] (`README` Lehman-Yao layout discussion).

Search: descend from root holding pin+share on one page at a time;
release previous on advance. Step right on key-not-found (page may
have been split right). [from-comment] (`README` "Locating the leaf page").

Insert: descend pinning every page (so we can split-and-update-parent
without re-traversing); re-lock the leaf exclusive. On split, lock
parent exclusive **before** unlocking the child. [from-comment]
(`README` "Insert").

## Posting tree — internal layout

If a key's posting list exceeds the budget for inline storage, the
posting tree is created. It's a **separate B-tree** with `GIN_DATA`
flag set, whose keys are ItemPointers (heap TIDs) and whose leaves
hold compressed posting lists.

```c
/* ginblock.h:262-323 (paraphrased) */
/* Internal posting-tree page layout: */
/*   PageHeader                                       */
/*   ItemPointerData rightBound       (just after header) */
/*   PostingItem[] = (childBlock, itemPointer-right-bound) ... */
/*   ...                                              */
/*   special: GinPageOpaqueData                       */

#define GinDataPageGetRightBound(page)  ((ItemPointer) PageGetContents(page))
#define GinDataPageGetData(page)        (PageGetContents(page) + MAXALIGN(sizeof(ItemPointerData)))
#define GinDataPageGetPostingItem(page, i) \
    ((PostingItem *) (GinDataPageGetData(page) + ((i)-1) * sizeof(PostingItem)))
```

`PostingItem` is a `(BlockNumber childBlk, ItemPointer rightBound)`
pair. The child page contains TIDs ≤ rightBound; rightmost descent
goes to the page whose rightBound is "infinity" (sentinel).

Leaf pages have `GIN_LEAF | GIN_DATA | GIN_COMPRESSED` flags and a
sequence of `GinPostingList` segments between `pd_lower` and
`pd_upper`. Each segment is independently decodable.

```c
/* ginblock.h:336-344 */
typedef struct {
    ItemPointerData first;                     /* first item, uncompressed */
    uint16          nbytes;                    /* size of bytes[] */
    unsigned char   bytes[FLEXIBLE_ARRAY_MEMBER];  /* varbyte-encoded deltas */
} GinPostingList;

#define SizeOfGinPostingList(plist) \
    (offsetof(GinPostingList, bytes) + SHORTALIGN((plist)->nbytes))
```

The segments-not-one-big-list design is for **fast random access**:
to find an item, you don't have to decode from the start of the
list, just to the start of its segment. Also, an update only
re-encodes the affected segment. [from-comment]
(`README` "Posting tree").

## Posting list compression — varbyte deltas

The compression idea (`ginpostinglist.c`):

1. **Combine block+offset into a single 43-bit integer**. The offset
   gets the low 11 bits (`MaxHeapTuplesPerPageBits = 11`, enough for
   `MaxHeapTuplesPerPage` per a normal 8 KiB page); block gets the
   high 32 bits. So one item = 43 bits = at most 6 bytes.
2. **Delta-encode**: store the difference from the previous item.
   Since TIDs are sorted in the posting list, deltas are small.
3. **Varbyte encode**: each byte uses 7 bits of payload + 1 high bit
   = "more bytes follow." A delta of 1 fits in 1 byte; large deltas
   take up to 6.

[from-comment] (`README` "Posting List Compression", `ginpostinglist.c:81`).

In the best case (sequential heap inserts, all TIDs on the same
page), an item costs ~1 byte. Worst case (random heap insert
pattern), ~6 bytes per item. The first item per segment is **always
uncompressed** (the `first ItemPointerData` in the GinPostingList
struct) so segment-level random access works.

The 11-bit offset field is the reason GIN can't index relations
with `MaxHeapTuplesPerPage > 2048`. With default 8 KiB blocks and
minimum-size tuples, you'd hit ~300 tuples per page — well under
the limit.

## Null categories — the placeholder problem

A naive inverted index can't represent NULL keys or empty indexable
items (e.g. an empty array, a null tsvector). GIN adds **null
category bytes** to handle these:

```
Category 1 = ordinary null key value extracted from an item
Category 2 = placeholder for zero-key indexable item (e.g. empty array)
Category 3 = placeholder for null indexable item (the item itself is NULL)
```

[from-comment] (`README` "If the key datum is null...").

When a tuple's key is NULL (`IndexTupleHasNulls(itup)` is true), the
byte right after the nominal index data is the category. Different
categories are distinct keys at the B-tree level (so a scan
filtering "category 1" doesn't return category 2/3 entries), but
multiple heap TIDs sharing the same category coalesce into one entry
just like ordinary keys.

The placeholder categories (2 and 3) exist so that full-index scans
return the right number of distinct items — without them, an empty
array would have **no** entry in the index, and `tsvector @@ tsquery
'~'` style scans would miss it.

## Multi-column GIN

In a multi-column GIN index, every key tuple has a leading `int2`
column number stored as the first attribute, before the key datum:

```
Single-column index:  (key_datum, t_tid={posting})
Multi-column index:   (column_no_int2, key_datum, t_tid={posting})
```

The column number is never null, but the key datum still can be (in
which case the null bitmap is present + a category byte follows).
This is how GIN handles "index multiple text columns separately" —
they share one entry tree but their entries are partitioned by the
column-number prefix. [from-comment] (`README` "In a multi-column
index, a key tuple contains the pair (column number, key datum)").

## GinFormTuple — the builder

```c
/* ginutil.c (paraphrased) */
IndexTuple GinFormTuple(GinState *ginstate, OffsetNumber attnum, Datum key,
                        GinNullCategory category, Pointer data, Size dataSize,
                        int nipd, bool errorTooBig)
{
    /* Step 1: use index_form_tuple to build a "normal" tuple */
    itup = index_form_tuple(...);
    /* Step 2: if category byte needed, ensure space; insert it */
    /* Step 3: append the posting list bytes after the (header + null + cat) */
    /* Step 4: set t_tid:
     *   GinSetPostingOffset(itup, byte_offset_of_posting_list)
     *   GinSetNPosting(itup, nipd)
     *   (high bit of BlockNumber set if compressed)
     */
    /* Step 5: check size against GinMaxItemSize; ereport if too big */
    return itup;
}
```

[verified-by-code] (calls in `gininsert.c`, `gindatapage.c`).

The "build a normal tuple then modify" idiom is what lets GIN reuse
`index_form_tuple`'s null-bitmap and datum-packing logic without
forking a new builder.

## Invariants and races

1. **Entry tree never deletes** — major simplification for vacuum +
   concurrency. Adding a key is the only modification.
   [from-comment] (`README` "Note: There is no delete operation in
   the key (entry) tree").
2. **Entry-tuple's `t_tid` is overloaded**: low 31 bits of
   BlockNumber = byte offset to inline list; high bit =
   compressed flag; OffsetNumber = count, or `0xFFFF` if
   posting-tree pointer (in which case BlockNumber is the actual
   block).
3. **`GinMaxItemSize` requires 3 items per entry-tree page.** Higher
   than nbtree's because GIN doesn't store a separate high key.
   [verified-by-code] (`ginblock.h:249-253`).
4. **Posting lists are sorted by TID.** This is what enables
   delta-encoding and segment-based random access.
5. **Segments in a posting tree leaf are independent**: each can be
   decoded without reading earlier ones. Updates re-encode only the
   affected segment. [from-comment] (`README`).
6. **Lehman-Yao right-links** in both entry and posting trees,
   protect against page splits during reader descent. No
   left-links — GIN never scans backward.
7. **`GIN_INCOMPLETE_SPLIT`** flag handles the "page split but
   parent not yet updated" state. Search may have to follow
   right-link to find the new sibling.
8. **Posting-tree page deletion** (vacuum) requires a full cleanup
   lock on the **tree root**, blocking concurrent inserts.
   [from-comment] (`README` "Page deletion").
9. **`pd_lower` on data leaf pages** is meaningful for **compressed**
   pages (delimits the posting-list area). On uncompressed (pre-9.4)
   pages it can't be trusted. [from-comment] (`ginblock.h:301-308`).
10. **Null category byte location** is at `IndexInfoFindDataOffset` (or
    `+ sizeof(int2)` in multi-col), only when `IndexTupleHasNulls`.

## Useful greps

```bash
# Page-type predicates:
grep -nE "GinPageIs|GinPageSet|GinPageGetOpaque" source/src/include/access/ginblock.h

# Entry-tuple t_tid macros:
grep -nE "GinGetPostingOffset|GinGetNPosting|GinIsPostingTree|GinSetPostingTree|GIN_TREE_POSTING" \
       source/src/include/access/ginblock.h

# Posting list codec entry points:
grep -nE "ginCompressPostingList|ginPostingListDecode" \
       source/src/backend/access/gin/ginpostinglist.c

# Where the entry tree is operated:
grep -n "ginbtree\|ginEntry" source/src/backend/access/gin/ginentrypage.c | head

# Where the posting tree is operated:
grep -n "ginbtree\|ginData" source/src/backend/access/gin/gindatapage.c | head
```

## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/access/gin/ginbtree.c`](../files/src/backend/access/gin/ginbtree.c.md) | — | generic B-tree primitives (used by both entry tree and posting tree) |
| [`src/backend/access/gin/gindatapage.c`](../files/src/backend/access/gin/gindatapage.c.md) | — | posting-tree-specific page ops |
| [`src/backend/access/gin/ginentrypage.c`](../files/src/backend/access/gin/ginentrypage.c.md) | — | entry-tree-specific page ops |
| [`src/backend/access/gin/ginpostinglist.c`](../files/src/backend/access/gin/ginpostinglist.c.md) | — | varbyte codec |
| [`src/backend/access/gin/ginutil.c`](../files/src/backend/access/gin/ginutil.c.md) | — | GinFormTuple builder |
| [`src/include/access/ginblock.h`](../files/src/include/access/ginblock.h.md) | 30 | GinPageOpaqueData, page-type flags (GIN_DATA, GIN_LEAF, GIN_META, GIN_LIST, GIN_COMPRESSED) |
| [`src/include/access/ginblock.h`](../files/src/include/access/ginblock.h.md) | 55 | GinMetaPageData (head/tail of pending list + version + page counts) |
| [`src/include/access/ginblock.h`](../files/src/include/access/ginblock.h.md) | 228 | entry-tuple t_tid abuse macros (GinGetPostingOffset, GinIsPostingTree, GinSetPostingTree) |
| [`src/include/access/ginblock.h`](../files/src/include/access/ginblock.h.md) | 262 | data-page (posting tree) layout |
| [`src/include/access/ginblock.h`](../files/src/include/access/ginblock.h.md) | 336 | GinPostingList compressed-segment struct |

<!-- /callsites:auto -->

## Scenarios that use me
<!-- scenarios:auto -->

*Auto-derived from direct references + transitive file-overlap.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

_(none detected — this idiom is either cross-cutting infrastructure or an internal helper pattern)_

<!-- /scenarios:auto -->
## Cross-references

- [[gin-fastupdate-pending]] — the pending-list buffer between inserter and entry tree.
- [[gin-scan-and-consistent]] — the query side that walks these structures.
- `knowledge/subsystems/access-nbtree.md` — the reference Lehman-Yao implementation GIN's entry tree mirrors.
- `source/src/backend/access/gin/README` — design overview (essential read).
