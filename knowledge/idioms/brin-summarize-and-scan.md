# BRIN summarize + bringetbitmap — placeholder-protected range build, opclass consistent fan-out

BRIN has two write paths and one read path that exercise the
revmap+tuple machinery:

- **Insert path** (`brininsert`): heap tuple arrives, find the
  covering range's summary, ask opclass to extend it with the new
  value; in-place rewrite if it fits, otherwise allocate a new BRIN
  tuple and re-point the revmap.
- **Summarize path** (`summarize_range`, `brinsummarize`): scan a
  range of heap pages, build a fresh summary, replace the
  placeholder. Used by `CREATE INDEX`, `brin_summarize_new_values`,
  `brin_summarize_range`, and VACUUM.
- **Scan path** (`bringetbitmap`): walk the revmap, deserialize
  each summary, call the opclass `consistent` function with the
  scan keys, add the range's heap pages to the output TIDBitmap if
  the function says yes (or the range is unsummarized / placeholder
  / empty).

This doc focuses on **summarize + scan** — the insert path
(`brininsert` → `brin_doupdate` / `brin_doinsert`) shares the same
locking primitives but is straightforward once you know the
read+write APIs. The crucial subtlety is the **placeholder race
protection**: `summarize_range` writes a placeholder BrinTuple first,
then scans the heap, then atomically replaces the placeholder with
the real summary — with a retry loop that catches concurrent
inserters who updated the placeholder mid-scan.

Companion docs:
- [[brin-revmap]] — the lookup index summarize/scan traverse.
- [[brin-tuple-format]] — the BrinTuple form/deform.
- [[parallel-bitmap-heap]] — `BitmapHeapScan` consumes the TIDBitmap output.
- [[heap-tuple-visibility-mvcc]] — the BitmapHeapScan re-checks each tuple's MVCC visibility (BRIN is lossy by design).

## Anchors

- `source/src/backend/access/brin/README` — design overview (esp. the "Summarization" + "Access Method Design" sections).
- `source/src/backend/access/brin/brin.c:348-515` — `brininsert`.
- `source/src/backend/access/brin/brin.c:572-958` — `bringetbitmap` (the scan).
- `source/src/backend/access/brin/brin.c:982-1278` — `brinbuildempty` + `brinbuild` + `brinbuildCallback`.
- `source/src/backend/access/brin/brin.c:1371-1500` — `brin_summarize_new_values` / `brin_summarize_range` (SQL functions).
- `source/src/backend/access/brin/brin.c:1652-1875` — `brinsummarize` + `summarize_range`.
- `source/src/backend/access/brin/brin_pageops.c` — `brin_doinsert` + `brin_doupdate` + `brin_can_do_samepage_update`.
- `source/src/backend/access/brin/brin_minmax.c` — minmax opclass (read this for an opclass example).

## The big picture

BRIN's amgetbitmap returns a **lossy TIDBitmap** of all heap pages
in matching ranges. BitmapHeapScan handles the recheck:

```
SeqScan ──no fast filter──→ table scan, slow
NBtreeScan ─exact pointers─→ random I/O, but tuples filtered by index
BRIN BitmapScan ─range hint─→ skip whole ranges; readahead-friendly sequential I/O on remaining ranges
                                ↓
                       BitmapHeapScan re-checks each tuple against quals
```

The scan never returns specific heap TIDs. It returns "this 1 MB
range of heap pages *might* contain matching tuples; check them."
The crucial economy: a properly-correlated query that touches 10
ranges out of 8000 in a 1 TB table reads ~10 MB of heap instead of
1 TB. The crucial pessimum: a poorly-correlated query touches every
range and reads the whole table (plus the BRIN scan overhead).

## bringetbitmap — the scan path

```c
/* brin.c:572-958 (skeleton) */
bringetbitmap(IndexScanDesc scan, TIDBitmap *tbm)
{
    /* Step 1: setup */
    nblocks = number-of-blocks-in-heap;
    consistentFn = palloc0_array(FmgrInfo, natts);    /* lazy-loaded per attribute */

    /* Step 2: split scan keys by attribute (regular vs IS [NOT] NULL) */
    for (keyno in scan->keyData) {
        if (key->sk_flags & SK_ISNULL)
            nullkeys[attno - 1][nnullkeys[attno - 1]++] = key;
        else
            keys[attno - 1][nkeys[attno - 1]++] = key;
        if (consistentFn[attno - 1].fn_oid == InvalidOid)
            fmgr_info_copy(&consistentFn[attno - 1],
                           index_getprocinfo(idxRel, attno, BRIN_PROCNUM_CONSISTENT),
                           ...);
    }

    dtup = brin_new_memtuple(bdesc);

    /* Step 3: per-range memory context (reset every iteration) */
    perRangeCxt = AllocSetContextCreate(...);
    MemoryContextSwitchTo(perRangeCxt);

    /* Step 4: walk the revmap */
    for (uint64 heapBlk = 0; heapBlk < nblocks; heapBlk += opaque->bo_pagesPerRange)
    {
        CHECK_FOR_INTERRUPTS();
        MemoryContextReset(perRangeCxt);

        tup = brinGetTupleForHeapBlock(rmAccess, heapBlk, &buf, &off, &size, SHARE);
        if (tup) {
            btup = brin_copy_tuple(tup, size, btup, &btupsz);
            LockBuffer(buf, UNLOCK);
        }

        if (!gottuple) {                                    /* unsummarized → include */
            addrange = true;
        } else {
            dtup = brin_deform_tuple(bdesc, btup, dtup);
            if (dtup->bt_placeholder) {                      /* placeholder → include */
                addrange = true;
            } else {
                addrange = true;
                for (attno = 1; attno <= natts; attno++) {
                    if (no scan keys for this attno) continue;
                    bval = &dtup->bt_columns[attno - 1];

                    /* Empty range → no tuples possible */
                    if (dtup->bt_empty_range) { addrange = false; break; }

                    /* IS [NOT] NULL keys */
                    if (oi_regular_nulls && !check_null_keys(bval, nullkeys, nnullkeys))
                    { addrange = false; break; }

                    if (no regular keys) continue;
                    if (bval->bv_allnulls) { addrange = false; break; }   /* allnull + strict op */

                    collation = keys[attno - 1][0]->sk_collation;

                    /* Call opclass consistent function */
                    if (consistentFn[attno - 1].fn_nargs >= 4) {
                        add = FunctionCall4Coll(&consistentFn, collation,
                                                bdesc, bval, keys, nkeys);
                        addrange = DatumGetBool(add);
                    } else {
                        for (keyno = 0; keyno < nkeys; keyno++) {
                            add = FunctionCall3Coll(&consistentFn, ..., bdesc, bval, keys[keyno]);
                            addrange = DatumGetBool(add);
                            if (!addrange) break;
                        }
                    }
                    if (!addrange) break;
                }
            }
        }

        if (addrange) {
            for (pageno = heapBlk; pageno < min(nblocks, heapBlk + pagesPerRange); pageno++) {
                MemoryContextSwitchTo(oldcxt);
                tbm_add_page(tbm, pageno);
                totalpages++;
                MemoryContextSwitchTo(perRangeCxt);
            }
        }
    }
    return totalpages * 10;                                 /* approximate row count */
}
```

### Five inclusion conditions

A range is added to the output bitmap if **any** of:

1. **No summary tuple** (unsummarized range) — must include because
   we don't know what's there.
2. **Placeholder summary** — concurrent summarize in progress;
   include conservatively.
3. **Empty-range flag** AND a key exists → **exclude** (the only
   case where empty-range causes exclusion).
4. **`bv_allnulls` + strict regular key** → exclude (can't match
   NULL with a non-null operator).
5. **Opclass `consistent` says yes** for some key combination.

The default (no keys present at all) is "include." [verified-by-code]
(`brin.c:770-927`).

### Opclass consistent — two arities

Each opclass declares a `BRIN_PROCNUM_CONSISTENT` support procedure.
Two calling conventions:

- **3-arg** (legacy): `consistent(bdesc, bval, ScanKey)` — one key
  per call. BRIN loops over keys, AND'ing results, short-circuits
  on first false.
- **4-arg** (modern): `consistent(bdesc, bval, ScanKey[], int nkeys)`
  — all keys for the attribute in one call. Opclass can be smarter
  about interactions (e.g. range overlap).

The 4-arg form is preferred for opclasses that benefit from
seeing all keys together (e.g. inclusion's bounding-box test can
short-circuit if no key's box overlaps the summary box). The
opclass decides at registration time which to expose, and BRIN
dispatches via `fn_nargs >= 4`. [verified-by-code]
(`brin.c:883-917`).

### Per-range memory context

The `perRangeCxt` is reset at the top of every loop iteration, so
the consistent-function and `brin_deform_tuple` don't leak across
ranges. The `tbm_add_page` call switches **out** of perRangeCxt
because the TIDBitmap is allocated in the caller's context.
[verified-by-code] (`brin.c:734-737`, `brin.c:938-941`).

### Approximate row count

`return totalpages * 10` is a rough "10 tuples per page" estimate.
The BitmapHeapScan node downstream does the actual recheck and
returns the real count. The planner uses this estimate only for
cost models, not correctness.

## summarize_range — placeholder-protected build

```c
/* brin.c:1763-1875 (skeleton) */
static void summarize_range(IndexInfo *indexInfo, BrinBuildState *state,
                            Relation heapRel, BlockNumber heapBlk, BlockNumber heapNumBlks)
{
    /* Step 1: insert the placeholder tuple */
    phtup = brin_form_placeholder_tuple(state->bs_bdesc, heapBlk, &phsz);
    offset = brin_doinsert(idxRel, pagesPerRange, rmAccess, &phbuf,
                           heapBlk, phtup, phsz);

    /* Step 2: clamp scan end if this is the partial last range */
    scanNumBlks = (heapBlk + pagesPerRange > heapNumBlks)
                  ? min(RelationGetNumberOfBlocks(heapRel) - heapBlk, pagesPerRange)
                  : pagesPerRange;

    /* Step 3: scan the heap range, calling brinbuildCallback for each tuple */
    state->bs_currRangeStart = heapBlk;
    table_index_build_range_scan(heapRel, idxRel, indexInfo,
                                 false /* allow_sync */,
                                 true  /* anyvisible (must see in-progress xacts) */,
                                 false /* progress */,
                                 heapBlk, scanNumBlks,
                                 brinbuildCallback, state, NULL);

    /* Step 4: replace the placeholder with the real summary tuple — retry loop */
    for (;;) {
        CHECK_FOR_INTERRUPTS();
        newtup = brin_form_tuple(state->bs_bdesc, heapBlk, state->bs_dtuple, &newsize);
        samepage = brin_can_do_samepage_update(phbuf, phsz, newsize);
        didupdate = brin_doupdate(idxRel, pagesPerRange, rmAccess,
                                  heapBlk, phbuf, offset,
                                  phtup, phsz, newtup, newsize, samepage);
        brin_free_tuple(phtup);
        brin_free_tuple(newtup);

        if (didupdate) break;

        /* Update lost the race; re-fetch the (now concurrently-modified) placeholder
         * and union it with our scan results, then retry */
        phtup = brinGetTupleForHeapBlock(rmAccess, heapBlk, &phbuf, &offset, &phsz, SHARE);
        if (phtup == NULL) elog(ERROR, "missing placeholder tuple");
        phtup = brin_copy_tuple(phtup, phsz, NULL, NULL);
        LockBuffer(phbuf, UNLOCK);
        union_tuples(state->bs_bdesc, state->bs_dtuple, phtup);
    }
}
```

[verified-by-code] (`brin.c:1763-1875`).

### Why the placeholder

Concurrent inserts into the heap range need a *somewhere* to put
their summary updates. If we just scanned the range and wrote the
result, an insert that landed between our scan and our write would
be lost (its xmin wouldn't be in our scan's snapshot).

The placeholder fixes this:

1. **Place placeholder.** Now any concurrent insert into the range
   will see "there's a summary tuple; let me extend it." It calls
   the opclass `addValue` to broaden the bounds and updates the
   placeholder in place (via `brin_doupdate`).
2. **Scan the heap** (with `anyvisible = true`, so we see in-progress
   tuples too).
3. **Try to atomically swap** the placeholder for the real summary.
   If `brin_doupdate` fails (placeholder content changed — concurrent
   insert beat us), we `union_tuples` our scan results with the
   concurrent insert's, then retry.
4. **Eventually succeed** because the placeholder has finite
   contention (each concurrent insert finishes in O(1) time).

The `anyvisible = true` mode of `table_index_build_range_scan` is
critical: a normal MVCC-snapshot scan would miss tuples inserted
by concurrent transactions whose xmin is still in our snapshot's
in-progress set. With anyvisible, we see them, and our summary will
correctly bound them. [from-comment] (`brin.c:1813-1817`).

### brinbuildCallback

The per-tuple callback during the heap scan:

```c
/* brin.c:1000 (skeleton) */
static void brinbuildCallback(Relation index, ItemPointer tid, Datum *values,
                              bool *isnull, bool tupleIsAlive, void *userstate)
{
    state = (BrinBuildState *) userstate;
    thisblock = ItemPointerGetBlockNumber(tid);

    /* If the tuple is past our current range, advance to next */
    if (thisblock >= state->bs_currRangeStart + state->bs_pagesPerRange) {
        /* form + insert the just-completed range's summary, then reset state */
        form_and_insert_tuple(state);
        state->bs_currRangeStart += state->bs_pagesPerRange;
    }

    /* Feed the value into each opclass's addValue */
    for (keyno = 0; keyno < natts; keyno++) {
        FunctionCall4Coll(addValueFn[keyno], collation,
                          PointerGetDatum(bdesc),
                          PointerGetDatum(&state->bs_dtuple->bt_columns[keyno]),
                          values[keyno], isnull[keyno]);
    }
}
```

For each indexed heap tuple, the opclass `addValue` is called with
the current summary state and the new value. The opclass either:

- Updates the summary in place (e.g. minmax's `if (v < min) min = v`).
- Returns "no change" if the value is already covered.

The callback also handles the **range boundary**: when a heap tuple
lands in a new range, the previous range's summary is finalized and
written before the new range's state is initialized. This is how
the bulk-build path (CREATE INDEX) processes every range in
sequence without holding placeholders.

### brinsummarize — the SQL-callable driver

```c
/* brin.c:1888-1950 (skeleton) */
static void brinsummarize(Relation index, Relation heapRel, BlockNumber pageRange,
                          bool include_partial, double *numSummarized, double *numExisting)
{
    revmap = brinRevmapInitialize(index, &pagesPerRange);
    heapNumBlocks = RelationGetNumberOfBlocks(heapRel);

    /* Either iterate all ranges or just the one containing pageRange */
    startBlk = (pageRange == BRIN_ALL_BLOCKRANGES) ? 0
              : (pageRange / pagesPerRange) * pagesPerRange;

    for (; startBlk < heapNumBlocks; startBlk += pagesPerRange) {
        /* Check if this range is partial; skip if !include_partial */
        if (!include_partial && (startBlk + pagesPerRange) > heapNumBlocks) break;

        /* Look up existing summary */
        tup = brinGetTupleForHeapBlock(revmap, startBlk, &buf, &off, &size, SHARE);
        if (tup != NULL) {
            (*numExisting)++;
            LockBuffer(buf, UNLOCK);
            continue;
        }

        /* Build state on first iteration that needs it */
        if (state == NULL) state = initialize_brin_buildstate(index, revmap, pagesPerRange);

        summarize_range(indexInfo, state, heapRel, startBlk, heapNumBlocks);
        (*numSummarized)++;
    }
}
```

[verified-by-code] (`brin.c:1888-1950`).

Two policies:

1. **`include_partial`** controls whether the final partial range
   (heap blocks past the last full range boundary) is summarized.
   `brin_summarize_new_values` passes `true` (caller has just bulk-loaded
   and wants everything indexed). VACUUM passes `false` (leave the
   partial range for the next insert to fill).
2. **Skip-already-summarized**: `brinGetTupleForHeapBlock != NULL` →
   already done. Caller only summarizes ranges with `InvalidOffsetNumber`
   in the revmap.

`brin_summarize_new_values(index)` is the user-facing SQL function;
`brin_summarize_range(index, blkno)` targets a specific range.
Behind both is `brinsummarize`. [verified-by-code]
(`brin.c:1371-1500`).

## Insert path overview — brininsert + brin_doupdate

```c
/* brin.c:348-515 (skeleton) */
bool brininsert(Relation idxRel, Datum *values, bool *nulls, ItemPointer heap_tid,
                Relation heapRel, IndexUniqueCheck checkUnique, ...)
{
    heapBlk = ItemPointerGetBlockNumber(heap_tid);
    range_first = (heapBlk / pagesPerRange) * pagesPerRange;

    /* Fetch the summary for this range */
    brtup = brinGetTupleForHeapBlock(revmap, range_first, &buf, &off, &size, SHARE);

    /* If the range is not yet summarized, insert does nothing — the next
     * VACUUM or brin_summarize_new_values will pick it up */
    if (brtup == NULL) return false;

    /* Deform and ask opclass: does this value require updating the summary? */
    dtup = brin_deform_tuple(...);
    need_update = false;
    for (keyno = 0; keyno < natts; keyno++) {
        if (opclass->addValue says "expanded")
            need_update = true;
    }
    if (!need_update) return false;

    /* Form the new tuple and atomically replace via brin_doupdate */
    newtup = brin_form_tuple(...);
    brin_doupdate(idxRel, pagesPerRange, rmAccess, range_first,
                  buf, off, brtup, brtupsz, newtup, newtupsz, samepage);
    return false;     /* BRIN never reports uniqueness violations */
}
```

The function returns `false` for both "no update needed" and
"update succeeded" — BRIN doesn't track per-tuple insertions, so
nothing the caller needs to know. The return value of `brininsert`
is semantically "did we report something interesting?" which for
BRIN is always no. [verified-by-code] (`brin.c:516+` for details).

`brin_doupdate` tries an **in-place** rewrite first
(`brin_can_do_samepage_update` checks if the new tuple fits in the
old slot). If not, it falls back to **insert-new + update-revmap +
delete-old**, the three-step atomic swap. The revmap update is the
linearization point — anyone reading the old summary tuple gets the
old data; anyone reading the new revmap pointer gets the new data.
The brief window where the old slot has been freed but the revmap
hasn't been updated is what the `bt_blkno` cross-check in
`brinGetTupleForHeapBlock` defends against. [from BRIN README,
"Access Method Design" section].

## The CREATE INDEX path — brinbuild

```c
/* brin.c:1278+ (skeleton) */
static void brinbuild(Relation heap, Relation index, IndexInfo *indexInfo)
{
    /* Build empty index (write metapage) */
    brin_metapage_init(...);

    /* Allocate the state */
    state = initialize_brin_buildstate(index, revmap, pagesPerRange);

    /* Scan the heap, one range at a time, summarizing as we go */
    table_index_build_scan(heap, index, indexInfo, false, true, brinbuildCallback, state, NULL);

    /* Flush any in-progress range's summary */
    if (state has unfinalized range)
        form_and_insert_tuple(state);
}
```

CREATE INDEX uses `brinbuildCallback` to feed every heap tuple into
the build state's range accumulator. When a tuple crosses a range
boundary, the previous range's summary is finalized and inserted.
This is **simpler than `summarize_range`** because there's no
concurrency: we hold an `AccessShareLock` on the heap (`true` for
allow_sync, but no concurrent writers thanks to ShareLock on the
table from CREATE INDEX).

## Invariants and races

1. **The scan path is read-only** but takes share lock on revmap
   pages and share/exclusive on regular pages (configurable via
   `mode` arg to `brinGetTupleForHeapBlock`).
2. **The placeholder is the linearization point** for concurrent
   summarize + inserts. Concurrent inserts update the placeholder
   in place; summarize replaces it atomically when the heap scan
   completes.
3. **The `anyvisible = true` mode of `table_index_build_range_scan`**
   is critical for summarize correctness — we must see in-progress
   xact tuples or they'd be missed from the summary.
   [from-comment] (`brin.c:1813-1817`).
4. **The retry loop in `summarize_range`** terminates because each
   concurrent inserter's update is O(1); contention is bounded by
   the number of concurrent inserts during the heap scan.
5. **CREATE INDEX is the simple case** — single-threaded build, no
   placeholders needed. `brinbuildCallback` walks the heap and
   emits a fresh summary per range boundary. [verified-by-code]
   (`brin.c:1278+`).
6. **VACUUM calls `brinsummarize` with `include_partial = false`** —
   leaves the trailing partial range to be filled by inserts.
7. **`bringetbitmap` returns lossy results.** The output TIDBitmap
   marks pages, not tuples; BitmapHeapScan re-checks each tuple
   against quals. BRIN doesn't and can't store TIDs.
8. **The 3-arg vs 4-arg consistent function** is opt-in per
   opclass. 4-arg lets the opclass see all keys for the attribute
   together, enabling smarter combination logic.
9. **No uniqueness check** — `brininsert` always returns false; BRIN
   indexes can't enforce uniqueness.

## Useful greps

```bash
# All top-level AM entry points:
grep -nE "^brininsert|^bringetbitmap|^brinbuild|^brinvacuumcleanup|^brinbulkdelete|^brin_handler" \
       source/src/backend/access/brin/brin.c

# Summarize / desummarize SQL functions:
grep -n "brin_summarize\|brin_desummarize" \
       source/src/backend/access/brin/brin.c

# The placeholder protection retry:
grep -n "phtup\|union_tuples\|brin_can_do_samepage_update" \
       source/src/backend/access/brin/brin.c \
       source/src/backend/access/brin/brin_pageops.c

# Consistent function dispatch:
grep -n "consistentFn\|BRIN_PROCNUM_CONSISTENT" \
       source/src/backend/access/brin/brin.c

# Insert + update pageops:
grep -n "brin_doinsert\|brin_doupdate\|brin_evacuate_page" \
       source/src/backend/access/brin/brin_pageops.c | head
```



## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/access/brin/brin.c`](../files/src/backend/access/brin/brin.c.md) | 348 | brininsert |
| [`src/backend/access/brin/brin.c`](../files/src/backend/access/brin/brin.c.md) | 572 | bringetbitmap (the scan) |
| [`src/backend/access/brin/brin.c`](../files/src/backend/access/brin/brin.c.md) | 982 | brinbuildempty + brinbuild + brinbuildCallback |
| [`src/backend/access/brin/brin.c`](../files/src/backend/access/brin/brin.c.md) | 1371 | brin_summarize_new_values / brin_summarize_range (SQL functions) |
| [`src/backend/access/brin/brin.c`](../files/src/backend/access/brin/brin.c.md) | 1652 | brinsummarize + summarize_range |
| [`src/backend/access/brin/brin_minmax.c`](../files/src/backend/access/brin/brin_minmax.c.md) | — | minmax opclass (read this for an opclass example) |
| [`src/backend/access/brin/brin_pageops.c`](../files/src/backend/access/brin/brin_pageops.c.md) | — | brin_doinsert + brin_doupdate + brin_can_do_samepage_update |

<!-- /callsites:auto -->



## Scenarios that use me
<!-- scenarios:auto -->

*Auto-derived from direct references + transitive file-overlap.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

- [`add-new-index-am`](../scenarios/add-new-index-am.md)

<!-- /scenarios:auto -->

## Cross-references

- [[brin-revmap]] — revmap traversal and the bt_blkno cross-check.
- [[brin-tuple-format]] — BrinTuple form/deform + placeholder anatomy.
- [[parallel-bitmap-heap]] — downstream consumer of bringetbitmap's TIDBitmap.
- [[heap-tuple-visibility-mvcc]] — BitmapHeapScan's per-tuple recheck.
- `knowledge/idioms/cost-scan-paths.md` — cost model for BRIN scans.
- `source/src/backend/access/brin/README` — design doc, esp. "Access Method Design" + "Summarization" sections.
