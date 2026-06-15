# GIN fastupdate — the pending-list buffer between heap insert and entry tree

A naive GIN inserter would, for each indexable heap item, traverse the
entry tree once per key it contains and update the posting list — so
a tsvector with 100 lexemes costs 100 root-to-leaf descents per heap
tuple. The **fastupdate** mechanism amortizes this by collecting
inserts into a **pending list** (a chain of pages linked from the
metapage), then periodically draining them in **bulk** via
`ginInsertCleanup`. Bulk drain wins because:

- Many heap tuples likely share keys, so one tree descent handles
  many TID updates per key.
- The drain phase can use `BuildAccumulator` to sort + group keys
  in memory before touching the tree.

The tradeoff: a scan must consult **both** the pending list and the
entry tree, walking pending-list pages sequentially. That's
acceptable only while the list is small. The
`gin_pending_list_limit` GUC (default 4 MB) caps the size; when
exceeded, an inserter triggers cleanup conditionally (best-effort),
and autovacuum forces a full cleanup at vacuum time.

This doc covers the per-page layout of pending-list pages (with the
`GIN_LIST_FULLROW` semantics for multi-page heap rows), the
`ginHeapTupleFastInsert` enqueue path (with the size-based "make
sublist or append" branch), the `ginInsertCleanup` drain (with the
`LockPage(metapage)`-style cleanup-vs-insert exclusion), the
`gin_clean_pending_list` SQL function, and the autovacuum hook.

Companion docs:
- [[gin-tree-structure]] — the entry tree the pending list eventually drains into.
- [[gin-scan-and-consistent]] — the scan, which consults pending list before entry tree.

## Anchors

- `source/src/backend/access/gin/ginfast.c:1-17` — banner.
- `source/src/backend/access/gin/ginfast.c:41-42` — `GIN_PAGE_FREESIZE`.
- `source/src/backend/access/gin/ginfast.c:59-216` — `writeListPage`, `makeSublist`.
- `source/src/backend/access/gin/ginfast.c:218-472` — `ginHeapTupleFastInsert` (enqueue).
- `source/src/backend/access/gin/ginfast.c:482-552` — `ginHeapTupleFastCollect` (build the collector).
- `source/src/backend/access/gin/ginfast.c:554-778` — `shiftList` (drop drained pages from metapage chain).
- `source/src/backend/access/gin/ginfast.c:779-1000` — `ginInsertCleanup`.
- `source/src/include/access/ginblock.h:46-49` — `GIN_LIST`, `GIN_LIST_FULLROW` flags.
- `source/src/include/access/ginblock.h:55-101` — `GinMetaPageData` (head/tail/tailFreeSize/counts).
- `source/src/backend/access/gin/README` — sections "Pending list" + "Cleaning up the pending list".

## The pending list — a linked chain of `GIN_LIST` pages

```
Metapage:
  head           = block of first list page          (or InvalidBlockNumber if empty)
  tail           = block of last list page
  tailFreeSize   = bytes free on tail page
  nPendingPages
  nPendingHeapTuples

List page (GIN_LIST flag set):
  Standard PageHeader
  Index tuples in normal layout (one per (column, key, TID) combination)
  GinPageOpaque:
    rightlink = block of next list page (or InvalidBlockNumber for tail)
    maxoff    = count of HEAP tuples represented (not item count!)
    flags     = GIN_LIST | (GIN_LIST_FULLROW)
```

[verified-by-code] (`ginblock.h:30-37`, `ginblock.h:55-75`).

The chain is **singly-linked tail-extending** — the metapage points
at head, last page's rightlink is invalid. Drainers walk
head→tail; inserters append to tail.

## `GIN_LIST_FULLROW` — the multi-page-row marker

A pending-list entry is essentially `(column_no, key_datum,
category_byte, heap_tid)` — there's no posting list, just one TID
per entry. A single heap tuple with N keys produces N pending-list
entries; all must appear **consecutively** for a given heap TID
(the cleanup code assumes this).

If those N entries fit on one page, the page has `GIN_LIST_FULLROW`
set: "this page contains all the entries for one or more complete
heap rows."

If a heap tuple has so many keys that its entries spill across
multiple pages, those pages have `GIN_LIST_FULLROW` **clear**:
"this page contains entries for only one heap tuple, and not all
of them." [from-comment] (`README` "Index entries that appear in
pending list pages work a tad differently…").

The consequence: when entries don't all fit on one page, the
"split-row" page may waste a lot of space at the end of the
previous page and on its own last page — but it must have those
pages to itself, otherwise the all-entries-for-this-row invariant
breaks. The `GIN_LIST_FULLROW` flag is what cleanup checks to decide
when to flush its accumulator: "if I see a full-row page, I can
finalize all rows so far."

## The enqueue path — `ginHeapTupleFastInsert`

`gininsert` callers collect tuples into a `GinTupleCollector`:

```c
typedef struct GinTupleCollector {
    IndexTuple *tuples;     /* IndexTuples to be added to pending list */
    int32       lentuples;  /* allocated size */
    int32       ntuples;    /* current count */
    int32       sumsize;    /* total bytes */
} GinTupleCollector;
```

Then `ginHeapTupleFastInsert(ginstate, collector)` writes them to
the pending list:

```c
/* ginfast.c:218-472 (skeleton) */
void ginHeapTupleFastInsert(GinState *ginstate, GinTupleCollector *collector)
{
    if (collector->ntuples == 0) return;
    needWal = RelationNeedsWAL(index);

    metabuffer = ReadBuffer(index, GIN_METAPAGE_BLKNO);

    /* Decision: append to tail page, or make a separate sublist? */
    if (collector->sumsize + ntuples * sizeof(ItemIdData) > GinListPageSize) {
        /* Total > one page → make sublist; no need to lock metapage yet */
        separateList = true;
    } else {
        LockBuffer(metabuffer, GIN_EXCLUSIVE);
        if (metadata->head == InvalidBlockNumber
            || size > metadata->tailFreeSize) {
            /* Empty list or won't fit in tail → make sublist; unlock metapage */
            separateList = true;
            LockBuffer(metabuffer, GIN_UNLOCK);
        }
    }

    if (separateList) {
        makeSublist(index, collector->tuples, collector->ntuples, &sublist);

        /* Now re-lock metapage and link sublist into chain */
        LockBuffer(metabuffer, GIN_EXCLUSIVE);
        if (metadata->head == InvalidBlockNumber) {
            /* Adopt the sublist wholesale */
            metadata->head = sublist.head;
            metadata->tail = sublist.tail;
        } else {
            /* Merge: extend old tail's rightlink to point at new sublist head */
            buffer = ReadBuffer(index, metadata->tail);
            LockBuffer(buffer, EXCLUSIVE);
            GinPageGetOpaque(page)->rightlink = sublist.head;
            metadata->tail = sublist.tail;
        }
        metadata->nPendingPages += sublist.nPendingPages;
        metadata->nPendingHeapTuples += sublist.nPendingHeapTuples;
    } else {
        /* Append directly to tail (metapage already locked) */
        buffer = ReadBuffer(index, metadata->tail);
        LockBuffer(buffer, EXCLUSIVE);
        GinPageGetOpaque(page)->maxoff++;     /* heap-tuple count */
        metadata->nPendingHeapTuples++;
        for (i = 0; i < collector->ntuples; i++)
            PageAddItem(page, collector->tuples[i], ...);
        metadata->tailFreeSize = PageGetExactFreeSpace(page);
    }

    /* Update metapage pd_lower (xlog compression requires it) */
    PageHeader(metapage)->pd_lower = ...sizeof(GinMetaPageData)...;
    MarkBufferDirty(metabuffer);

    /* Force pending-list cleanup if size exceeded */
    cleanupSize = GinGetPendingListCleanupSize(index);
    if (metadata->nPendingPages * GIN_PAGE_FREESIZE > cleanupSize * 1024)
        needCleanup = true;

    UnlockReleaseBuffer(metabuffer);

    /* Non-forcibly: ConditionalLock; if cleanup running already, skip */
    if (needCleanup)
        ginInsertCleanup(ginstate, false /*full_clean*/, true /*fill_fsm*/,
                         false /*forceCleanup*/, NULL);
}
```

[verified-by-code] (`ginfast.c:218-472`).

### Sublist vs append

The "separate sublist" path is chosen in two cases:

1. **The collector's total size exceeds one page** — we'll have to
   write multiple pages anyway, might as well do it without
   holding the metapage lock during the I/O.
2. **The list is empty, OR the new tuples won't fit in the current
   tail's free space**.

Otherwise we **append directly to the tail page** under the
metapage's exclusive lock. The metapage lock provides
single-writer serialization on the pending list.

The "make sublist with metapage unlocked" optimization is the
concurrency win: writing N pages of pending entries doesn't block
other inserters. They can still append to the *current* tail; we'll
re-acquire the metapage exclusive when we finalize.

### `CheckForSerializableConflictIn`

Before any mutation, the inserter calls
`CheckForSerializableConflictIn(index, NULL, GIN_METAPAGE_BLKNO)`.
Predicate locks on the metapage represent "this transaction modified
the index" because pending-list entries logically belong anywhere
in the entry tree. A serializable conflicting reader who took a
predicate lock on the metapage will see a write conflict.
[from-comment] (`ginfast.c:245-251`).

## The drain path — `ginInsertCleanup`

```c
/* ginfast.c:779-1000 (skeleton) */
void ginInsertCleanup(GinState *ginstate, bool full_clean,
                      bool fill_fsm, bool forceCleanup, IndexBulkDeleteResult *stats)
{
    /* Step 1: take the cleanup lock */
    if (forceCleanup) {
        LockPage(index, GIN_METAPAGE_BLKNO, ExclusiveLock);     /* WAIT */
        workMemory = AmAutoVacuum() ? autovacuum_work_mem : maintenance_work_mem;
    } else {
        if (!ConditionalLockPage(index, GIN_METAPAGE_BLKNO, ExclusiveLock))
            return;                                              /* skip */
        workMemory = work_mem;
    }

    metabuffer = ReadBuffer(index, GIN_METAPAGE_BLKNO);
    LockBuffer(metabuffer, GIN_SHARE);
    metadata = GinPageGetMeta(metapage);
    if (metadata->head == InvalidBlockNumber) {
        UnlockReleaseBuffer(metabuffer);
        UnlockPage(index, GIN_METAPAGE_BLKNO, ExclusiveLock);
        return;                                                  /* empty */
    }

    /* Step 2: snapshot current tail to bound the work (concurrent inserters
     * may extend the chain, but we won't chase that) */
    blknoFinish = metadata->tail;
    blkno = metadata->head;
    buffer = ReadBuffer(index, blkno);
    LockBuffer(buffer, GIN_SHARE);
    LockBuffer(metabuffer, GIN_UNLOCK);

    opCtx = AllocSetContextCreate(...);
    initKeyArray(&datums, 128);
    ginInitBA(&accum);                                          /* BuildAccumulator */

    /* Step 3: walk the chain, collect into accumulator */
    for (;;) {
        if (blkno == blknoFinish && !full_clean)
            cleanupFinish = true;

        processPendingPage(&accum, &datums, page, FirstOffsetNumber);
        vacuum_delay_point(false);

        /* Flush if: at end of chain, OR full-row page + memory exhausted */
        if (rightlink == InvalidBlockNumber
            || (GinPageHasFullRow(page) && accum.allocatedMemory >= workMemory * 1024)) {

            /* Step 3a: drop locks, flush accumulator into entry tree */
            LockBuffer(buffer, GIN_UNLOCK);
            ginBeginBAScan(&accum);
            while ((list = ginGetBAEntry(&accum, &attnum, &key, &category, &nlist))) {
                ginEntryInsert(ginstate, attnum, key, category, list, nlist, NULL);
            }

            /* Step 3b: re-lock metapage + buffer; drop drained pages from chain */
            LockBuffer(metabuffer, GIN_EXCLUSIVE);
            LockBuffer(buffer, GIN_SHARE);
            /* (handle any tuples concurrent inserters added to the same page) */
            shiftList(index, metabuffer, ..., stats);            /* updates metadata->head */
        }

        if (rightlink == InvalidBlockNumber || cleanupFinish) break;
        /* Advance */
    }
}
```

[verified-by-code] (`ginfast.c:779-1000`).

### The cleanup lock — `LockPage(GIN_METAPAGE_BLKNO, ExclusiveLock)`

A heavyweight relation-level lock on the **metapage's block number**
(not the relation itself) serializes cleanup processes. Concurrent
inserters take only the buffer lock on the metapage, not this
relation lock, so they don't contend with cleanup.

- **Forced cleanup** (vacuum, `gin_clean_pending_list`,
  `forceCleanup = true`) → `LockPage` (blocking). Waits for any
  concurrent cleanup to finish.
- **Opportunistic cleanup** (an inserter that observed the pending
  list crossed `gin_pending_list_limit`) → `ConditionalLockPage`
  (non-blocking). If a cleanup is already running, just return —
  the other process will handle it.

[from-comment] (`ginfast.c:800-805`).

### The `BuildAccumulator` — bulk-insertion engine

`BuildAccumulator` is the same data structure CREATE INDEX uses to
batch up entries by `(column, key, category)` before writing the
entry tree. The drain code:

1. **Read each pending-list page** with `processPendingPage`,
   accumulating `(key, TID)` pairs.
2. **Periodically flush** the accumulator. Two triggers:
   - End of chain → flush remaining.
   - "Full-row page" + accumulator over `work_mem` → safe to flush
     because we know every preceding page contains complete rows
     (no half-finished heap tuples in the accumulator).
3. **For each (key, TIDs) tuple in accumulator**: call
   `ginEntryInsert` which traverses the entry tree and either
   updates an existing posting list or creates a new entry. This
   is the **single descent per key** that fastupdate amortizes.

### Concurrent extension handling

Concurrent inserters can append to the chain while we're draining.
The `blknoFinish` snapshot caps our work — if the chain extends past
that, we don't chase it (a subsequent cleanup will pick it up).

If a concurrent inserter appended to a page we just drained, the
`shiftList` step re-checks the page's `maxoff` after re-locking.
"While we left the page unlocked, more stuff might have gotten
added to it. If so, process those entries immediately." [from-comment]
(`ginfast.c:944-948`).

### `shiftList` — dropping drained pages

After flushing the accumulator, drained pages are decommissioned:

- `metadata->head` is advanced to point past them.
- Each old page is marked `GIN_DELETED`.
- `pd_prune_xid` on each gets set to current xid (for recycling
  bookkeeping).
- Pages are added to the index FSM if `fill_fsm = true`.

The pages can't be recycled immediately — they're flagged deleted
but kept until any transaction that could still see them via the
old metapage state has finished. [verified-by-code] (`ginfast.c:554+`).

## Cleanup triggers

Three ways `ginInsertCleanup` is invoked:

1. **Inline from inserter** (`forceCleanup = false`). When
   `nPendingPages * GIN_PAGE_FREESIZE > gin_pending_list_limit *
   1024`, the just-completed inserter calls cleanup conditionally.
   If another cleanup is running, skip.
2. **VACUUM / autovacuum** (`forceCleanup = true`). `ginbulkdelete`
   calls cleanup first thing, so pending entries are flushed
   before vacuum scans the entry tree.
3. **`gin_clean_pending_list(index)`** SQL function. Calls cleanup
   with `forceCleanup = true, full_clean = true` — drains the
   whole list, not just the snapshot up to the initial tail.

[verified-by-code] (`ginfast.c:448-471` for #1; `ginbulkdelete` for #2;
`gin_clean_pending_list` in `ginutil.c` for #3).

## The `fastupdate` opclass option

The GUC `gin_fastupdate` (default on) controls whether to use the
pending list at all. With `fastupdate = off`, every insert goes
straight to the entry tree — slower per insert, but no pending list
to drain and no scan-must-consult-pending overhead. Useful for
read-heavy workloads where insert throughput isn't the bottleneck.

The option is per-index, set with `CREATE INDEX ... WITH
(fastupdate = off)` or `ALTER INDEX ... SET (fastupdate = off)`.
[verified-by-code] (grep `fastupdate` in `ginutil.c`).

## Invariants and races

1. **Entries for one heap tuple are consecutive** in the pending
   list. The cleanup code relies on this to determine when the
   accumulator can be safely flushed. [from-comment]
   (`README` "code that searches the pending list assumes that
   all entries for a given heap tuple appear consecutively").
2. **`GIN_LIST_FULLROW`** identifies a page that contains complete
   row(s). A heap row whose entries spill across multiple pages
   uses pages without that flag, and those pages contain entries
   for *only* that one heap tuple.
3. **`LockPage(metapage, ExclusiveLock)` serializes cleanup**, but
   doesn't block inserters (they use buffer lock only).
4. **Forced cleanup waits** (`LockPage` blocking); opportunistic
   cleanup skips (`ConditionalLockPage`). [from-comment]
   (`ginfast.c:807-828`).
5. **Concurrent inserts during drain** are handled by
   re-checking page contents after re-locking. The accumulator-flush
   point is the linearization point: any inserts that happen during
   the flush are folded in by the post-flush re-check.
6. **`shiftList` advances `metadata->head`** but doesn't immediately
   recycle drained pages — they need to wait until no concurrent
   reader could still see them via the old metadata.
7. **Predicate locks on the metapage** represent "any GIN write"
   for serializable isolation. [from-comment]
   (`ginfast.c:245-251`).
8. **`gin_pending_list_limit`** is in **KB**; the comparison is
   `nPendingPages * GIN_PAGE_FREESIZE > limit_kb * 1024`.
9. **Pre-v11 `pg_upgrade`d indexes** have incorrect `pd_lower` on
   the metapage; every write fixes this. [from-comment]
   (`ginfast.c:412-417`).

## Useful greps

```bash
# Top-level fastupdate path:
grep -nE "ginHeapTupleFastInsert|ginHeapTupleFastCollect|ginInsertCleanup|shiftList" \
       source/src/backend/access/gin/ginfast.c

# Page-flag flag macros:
grep -nE "GIN_LIST\b|GIN_LIST_FULLROW|GinPageHasFullRow|GinPageIsList" \
       source/src/include/access/ginblock.h

# Where scan reads the pending list:
grep -rn "scanPendingInsert\|GinScanOpaque.*pendingList" \
       source/src/backend/access/gin/

# SQL functions:
grep -rn "gin_clean_pending_list\|gin_pending_list_limit" source/src/
```

## Cross-references

- [[gin-tree-structure]] — what the cleanup eventually inserts into.
- [[gin-scan-and-consistent]] — scan must consult pending list first.
- `source/src/backend/access/gin/README` — sections "Pending list", "Cleaning up the pending list".
- `knowledge/idioms/predicate-locks.md` — SSI predicate-lock semantics underlying the metapage lock.
