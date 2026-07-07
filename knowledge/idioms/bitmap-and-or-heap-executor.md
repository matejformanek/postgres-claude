# BitmapAnd / BitmapOr / BitmapHeapScan — executor composition

The executor's bitmap-scan family is **three node types** that
work together:

- `BitmapIndexScan` — runs an `amgetbitmap` call on one index
  and returns a fresh `TIDBitmap`.
- `BitmapAnd` / `BitmapOr` — combine N child bitmaps via
  `tbm_intersect` / `tbm_union` and return the result.
- `BitmapHeapScan` — iterates the bitmap, fetches matching
  heap pages, re-checks the qual when the bitmap was lossy, and
  emits matching tuples.

This doc walks the executor side; the bitmap structure +
operations are [[tidbitmap-structure-and-lossy]] +
[[tidbitmap-build-and-iterate]].  The parallel-scan flow is
[[parallel-bitmap-heap]] (this doc covers the non-parallel
backbone).

**Anchors** (all cites against `source/` at commit `e18b0cb7344`):
- `source/src/backend/executor/nodeBitmapAnd.c` — N-way intersect
- `source/src/backend/executor/nodeBitmapOr.c` — N-way union
- `source/src/backend/executor/nodeBitmapHeapscan.c` — fetch + recheck
- `source/src/backend/executor/nodeBitmapIndexscan.c` — the AM-call entry
- `source/src/backend/optimizer/path/indxpath.c` — selectivity ordering

## The plan shape and the MultiExec convention

`BitmapAnd`, `BitmapOr`, `BitmapHeapScan`, and `BitmapIndexScan`
do **not** participate in the regular `ExecProcNode` /
per-tuple pull protocol.  Each has a stub:

```c
/* nodeBitmapAnd.c:44-49 */
static TupleTableSlot *
ExecBitmapAnd(PlanState *pstate)
{
    elog(ERROR, "BitmapAnd node does not support ExecProcNode call convention");
    return NULL;
}
```

[verified-by-code].  Instead they use `MultiExecProcNode`, which
returns a whole **`TIDBitmap *`** at once.  The convention from
`nodeBitmapAnd.c:22-27` [from-comment]:

> BitmapAnd nodes don't make use of their left and right
> subtrees, rather they maintain a list of subplans, much like
> Append nodes.

So `BitmapAndState.bitmapplans` is an array of child
`PlanState *`, each of which is either another `BitmapAnd` /
`BitmapOr`, or a leaf `BitmapIndexScan`.  Recursion bottoms out
at index-scan leaves; the bitmap propagates up.

## `BitmapAnd` — N-way intersect with early termination

`nodeBitmapAnd.c:112-170` [verified-by-code]:

```c
Node *
MultiExecBitmapAnd(BitmapAndState *node)
{
    PlanState **bitmapplans = node->bitmapplans;
    int nplans = node->nplans;
    TIDBitmap *result = NULL;

    for (i = 0; i < nplans; i++)
    {
        PlanState *subnode = bitmapplans[i];
        TIDBitmap *subresult;

        subresult = (TIDBitmap *) MultiExecProcNode(subnode);
        if (!subresult || !IsA(subresult, TIDBitmap))
            elog(ERROR, "unrecognized result from subplan");

        if (result == NULL)
            result = subresult;          /* first subplan */
        else
        {
            tbm_intersect(result, subresult);
            tbm_free(subresult);
        }

        if (tbm_is_empty(result))
            break;                       /* short-circuit */
    }

    if (result == NULL)
        elog(ERROR, "BitmapAnd doesn't support zero inputs");

    return (Node *) result;
}
```

Three properties worth noticing:

### 1. The first subplan's bitmap *is* the result, in-place

`result = subresult` keeps the first subplan's bitmap; subsequent
subplans get `tbm_intersect`'d in.  This avoids allocating a
fresh bitmap for the result — the first child's bitmap mutates
into the AND of all children.  Subsequent subplan bitmaps are
freed with `tbm_free` immediately after intersection.

### 2. Empty-bitmap short-circuit

Lines 151-159 [from-comment]:

> If at any stage we have a completely empty bitmap, we can
> fall out without evaluating the remaining subplans, since
> ANDing them can no longer change the result.  (Note: the
> fact that indxpath.c orders the subplans by selectivity
> should make this case more likely to occur.)

The planner's `indxpath.c` puts the **most selective** child
first.  If that child returns an empty (or near-empty) bitmap,
later children are skipped — they can't reduce the bitmap
further.  This is the executor-side justification for the
planner's per-clause selectivity sort.

### 3. The zero-input error path

`elog(ERROR, "BitmapAnd doesn't support zero inputs")` at
line 162-163 should never fire — the planner constructs
`BitmapAnd` only when ≥ 2 index scans are anded.  It's a
defensive backstop for plan-construction bugs.

## `BitmapOr` — N-way union with a streaming optimization

`nodeBitmapOr.c:113-188` [verified-by-code] has the same shape
as `BitmapAnd` but with a critical performance optimization for
`BitmapIndexScan` children.

### The streaming path — child writes directly into result

Lines 138-160 [verified-by-code]:

```c
if (IsA(subnode, BitmapIndexScanState))
{
    if (result == NULL) /* first subplan */
    {
        result = tbm_create(work_mem * (Size) 1024,
                            ((BitmapOr *) node->ps.plan)->isshared ?
                            node->ps.state->es_query_dsa : NULL);
    }

    ((BitmapIndexScanState *) subnode)->biss_result = result;

    subresult = (TIDBitmap *) MultiExecProcNode(subnode);

    if (subresult != result)
        elog(ERROR, "unrecognized result from subplan");
}
```

The comment at lines 139-143 [from-comment]:

> We can special-case BitmapIndexScan children to avoid an
> explicit tbm_union step for each child: just pass down the
> current result bitmap and let the child OR directly into it.

So instead of "each child builds its own bitmap and we union
them at the end", the OR node pre-creates one shared `result`
bitmap and **passes it down** via `biss_result`.  The
`BitmapIndexScan` AM call then `tbm_add_tuples` directly into
the shared bitmap.

Win: zero intermediate allocations, zero `tbm_union` overhead,
and (importantly) **lossify can fire earlier** because all
children share the same memory budget.  Without this, you could
have 5 children each building a near-full bitmap before the
union explodes work_mem.

### The fallback path — non-leaf children

Lines 161-176 [verified-by-code] handle non-`BitmapIndexScan`
children (nested `BitmapAnd` / `BitmapOr`):

```c
else
{
    /* standard implementation */
    subresult = (TIDBitmap *) MultiExecProcNode(subnode);

    if (!subresult || !IsA(subresult, TIDBitmap))
        elog(ERROR, "unrecognized result from subplan");

    if (result == NULL)
        result = subresult;
    else
    {
        tbm_union(result, subresult);
        tbm_free(subresult);
    }
}
```

— same shape as `BitmapAnd`'s loop but with `tbm_union` instead
of `tbm_intersect`, and no short-circuit (the bitmap only
grows).

### Why not the same streaming for `BitmapAnd`?

Intersection isn't compatible with the "let child write into
shared bitmap" trick.  An intersection requires having both
operands' full sets to compute their overlap; streaming
intersect into a half-built target would be incorrect.

So `BitmapOr` streams; `BitmapAnd` doesn't.

## `BitmapHeapScan` — fetch + recheck + emit

`nodeBitmapHeapscan.c:101-220` [verified-by-code].  The
function is split into two phases — setup (`BitmapTableScanSetup`)
and per-tuple work (`BitmapHeapNext`).

### Setup — kick off the index scan, prepare the iterator

`nodeBitmapHeapscan.c:101-165` [verified-by-code]:

```c
static void
BitmapTableScanSetup(BitmapHeapScanState *node)
{
    TBMIterator tbmiterator = {0};
    ParallelBitmapHeapState *pstate = node->pstate;
    dsa_area *dsa = node->ss.ps.state->es_query_dsa;

    if (!pstate)
    {
        node->tbm = (TIDBitmap *) MultiExecProcNode(outerPlanState(node));
        if (!node->tbm || !IsA(node->tbm, TIDBitmap))
            elog(ERROR, "unrecognized result from subplan");
    }
    else if (BitmapShouldInitializeSharedState(pstate))
    {
        /* leader builds bitmap; workers will wake when done */
        node->tbm = (TIDBitmap *) MultiExecProcNode(outerPlanState(node));
        pstate->tbmiterator = tbm_prepare_shared_iterate(node->tbm);
        BitmapDoneInitializingSharedState(pstate);
    }

    tbmiterator = tbm_begin_iterate(node->tbm, dsa,
                                    pstate ? pstate->tbmiterator : InvalidDsaPointer);

    if (!node->ss.ss_currentScanDesc)
    {
        uint32 flags = SO_NONE;
        if (ScanRelIsReadOnly(&node->ss))
            flags |= SO_HINT_REL_READ_ONLY;
        node->ss.ss_currentScanDesc =
            table_beginscan_bm(node->ss.ss_currentRelation,
                               node->ss.ps.state->es_snapshot,
                               0, NULL, flags);
    }

    node->ss.ss_currentScanDesc->st.rs_tbmiterator = tbmiterator;
    node->initialized = true;
}
```

Three phases hidden in here:

1. **Build the bitmap.**  `MultiExecProcNode(outerPlanState)`
   runs the child tree — the index scans, BitmapAnds,
   BitmapOrs.  The whole bitmap arrives in one shot.
2. **Prepare iteration.**  `tbm_begin_iterate` produces either
   a private or shared iterator depending on whether `dsa` and
   `pstate->tbmiterator` are non-null.
3. **Start the table scan.**  `table_beginscan_bm` produces a
   `TableScanDesc` configured for bitmap-style scanning — the
   `SO_HINT_REL_READ_ONLY` flag triggers prefetch optimizations
   in the underlying read stream.

The parallel-coordination branch
(`BitmapShouldInitializeSharedState`, lines 115-134) is the
"first worker to arrive builds the bitmap; everyone else
waits" pattern.  Details in [[parallel-bitmap-heap]].

### Per-tuple loop — fetch and recheck

`nodeBitmapHeapscan.c:173-220` [verified-by-code]:

```c
static TupleTableSlot *
BitmapHeapNext(BitmapHeapScanState *node)
{
    ExprContext *econtext = node->ss.ps.ps_ExprContext;
    TupleTableSlot *slot = node->ss.ss_ScanTupleSlot;

    if (!node->initialized)
        BitmapTableScanSetup(node);

    while (table_scan_bitmap_next_tuple(node->ss.ss_currentScanDesc,
                                        slot, &node->recheck,
                                        &node->stats.lossy_pages,
                                        &node->stats.exact_pages))
    {
        CHECK_FOR_INTERRUPTS();

        if (node->recheck)
        {
            econtext->ecxt_scantuple = slot;
            if (!ExecQualAndReset(node->bitmapqualorig, econtext))
            {
                InstrCountFiltered2(node, 1);
                ExecClearTuple(slot);
                continue;
            }
        }

        return slot;
    }

    return ExecClearTuple(slot);
}
```

Key behaviors:

#### `table_scan_bitmap_next_tuple` is the table-AM hook

This is in the table-AM interface (`tableam.h`) — the heap
implementation lives in `heapam_handler.c`'s
`heap_scan_bitmap_next_tuple`.  It returns true and fills `slot`
plus `*recheck` per tuple, or false at end-of-scan.

The two output counters `lossy_pages` and `exact_pages` are
incremented by the heap-AM as it consumes the iterator:

- `exact_pages` ← pages where the bitmap held per-tuple bits
- `lossy_pages` ← pages where the bitmap was a chunk

These feed `EXPLAIN ANALYZE` so DBAs can see when work_mem
forced lossification.

#### The recheck handshake

Lines 200-209 [verified-by-code]:

```c
if (node->recheck)
{
    econtext->ecxt_scantuple = slot;
    if (!ExecQualAndReset(node->bitmapqualorig, econtext))
    {
        InstrCountFiltered2(node, 1);
        ExecClearTuple(slot);
        continue;
    }
}
```

`bitmapqualorig` is the original index quals stored on
`BitmapHeapScanState` at plan time.  When the table-AM reports
`recheck = true` (either because the bitmap was lossy, or
because the index AM set the per-entry recheck flag — see
[[tidbitmap-structure-and-lossy]]), the executor re-evaluates
the qual against the heap tuple.

If the recheck fails, increment `nfiltered2` (which EXPLAIN
shows as "Rows Removed by Index Recheck") and loop for the
next tuple.

The `CHECK_FOR_INTERRUPTS` inside the loop is necessary because
a full heap re-scan of lossy pages can run for seconds; we want
SIGTERM to land between tuples.

### The MVCC-only restriction

The big block comment at `nodeBitmapHeapscan.c:6-16`
[from-comment] is one of the strongest invariants in the file:

> NOTE: it is critical that this plan type only be used with
> MVCC-compliant snapshots (ie, regular snapshots, not
> SnapshotAny or one of the other special snapshots).  The
> reason is that since index and heap scans are decoupled,
> there can be no assurance that the index tuple prompting a
> visit to a particular heap TID still exists when the visit
> is made.  Therefore the tuple might not exist anymore either
> (which is OK because heap_fetch will cope) --- but worse, the
> tuple slot could have been re-used for a newer tuple.  With
> an MVCC snapshot the newer tuple is certain to fail the time
> qual and so it will not be mistakenly returned, but with
> anything else we might return a tuple that doesn't meet the
> required index qual conditions.

This is why `EXPLAIN` never shows a bitmap-heap scan when the
query uses `SELECT ... FOR UPDATE` SKIP LOCKED with a
non-MVCC snapshot — the planner refuses to generate the plan
shape.  The decoupling between index-build and heap-fetch
phases is fundamental to bitmap scans; making it safe requires
the snapshot to filter out anything inserted in the gap.

### `BitmapHeapRecheck` — used by EvalPlanQual

`nodeBitmapHeapscan.c:240-` (snippet shown):

```c
static bool
BitmapHeapRecheck(BitmapHeapScanState *node, TupleTableSlot *slot)
{
    ExprContext *econtext = node->ss.ps.ps_ExprContext;
    /* Does the tuple meet the original qual conditions? */
    ...
}
```

This is registered with the EvalPlanQual machinery (see
[[evalplanqual-recheck]]).  When a row-locking scan
encounters an updated row, EPQ re-evaluates the plan against
the updated row's version; this callback re-runs the
`bitmapqualorig` against the new tuple.

## Initialization shape — `ExecInitBitmapAnd` / `ExecInitBitmapOr`

Both follow the same pattern (`nodeBitmapAnd.c:57-106`,
`nodeBitmapOr.c:60-107`) [verified-by-code]:

1. `Assert(!(eflags & (EXEC_FLAG_BACKWARD | EXEC_FLAG_MARK)))`
   — these node types don't support backward scans or marks.
2. Allocate state struct with `nplans` array of `PlanState *`.
3. Loop calling `ExecInitNode` on each child plan.
4. **No expression context or tuple slot.**  The comment is
   explicit:

   > BitmapAnd plans don't have expression contexts because
   > they never call ExecQual or ExecProject.  They don't need
   > any tuple slots either.

This makes BitmapAnd/BitmapOr unusually cheap to initialize —
they're pure plumbing.

## Why is the work_mem budget per-bitmap, not per-query?

Each `BitmapHeapScan` calls `tbm_create(work_mem * 1024, ...)`
or the equivalent inside its first `BitmapIndexScan`.  A query
with 3 separate bitmap-heap scans can use 3× work_mem.

For the streaming `BitmapOr` optimization, all child bitmaps
share one budget because they share one `TIDBitmap`.  For
`BitmapAnd`, the children's bitmaps are *consumed* by
`tbm_intersect` and then freed — so the peak memory is
roughly 2× work_mem (the accumulating result + the current
child), not N× work_mem.

This per-bitmap-scan accounting is one of the reasons PG can
underestimate query memory; bitmap-scan-heavy queries with
many children can balloon.

## Invariants worth remembering

1. **BitmapAnd/BitmapOr/BitmapHeapScan/BitmapIndexScan don't
   support `ExecProcNode`.**  They use `MultiExecProcNode` and
   return whole bitmaps.
2. **BitmapAnd takes the first child's bitmap in-place; later
   children are intersected and freed.**
3. **BitmapAnd short-circuits on empty.**  The planner sorts
   children by selectivity to maximize this.
4. **BitmapOr streams BitmapIndexScan children into one shared
   bitmap.**  Non-leaf children use the slow `tbm_union` path.
5. **BitmapHeapScan re-checks the qual per tuple when recheck
   is set.**  Source of recheck: lossy pages or per-entry
   index-AM recheck flag.
6. **BitmapHeapScan requires an MVCC snapshot.**  Non-MVCC
   snapshots could return wrong results across the
   index→heap gap.
7. **`exact_pages` and `lossy_pages` are reported in EXPLAIN
   ANALYZE.**  Lossy ≫ exact is the signal to bump work_mem.
8. **`bitmapqualorig` holds the original index qual for
   recheck.**  Stored on the BitmapHeapScanState at plan time.
9. **`BitmapAnd` and `BitmapOr` have no per-tuple work** —
   they're pure setup nodes; all their work happens in
   `MultiExecProcNode`.
10. **`CHECK_FOR_INTERRUPTS` runs inside the per-tuple loop.**
    Long lossy scans can take seconds; interrupts must land
    between tuples, not only at scan boundaries.

## Useful greps

```bash
# The MultiExec wiring
grep -rn "MultiExecBitmapAnd\|MultiExecBitmapOr\|MultiExecBitmapIndexScan" \
    source/src/backend/executor/

# Recheck propagation
grep -rn "bitmapqualorig\|recheck\|table_scan_bitmap_next_tuple" \
    source/src/backend/executor/nodeBitmapHeapscan.c

# The empty-bitmap short-circuit
grep -n "tbm_is_empty" source/src/backend/executor/nodeBitmapAnd.c

# Streaming OR optimization
grep -n "biss_result\|IsA(subnode, BitmapIndexScanState)" \
    source/src/backend/executor/nodeBitmapOr.c

# Planner-side selectivity ordering
grep -n "compare_path_costs\|selectivity" \
    source/src/backend/optimizer/path/indxpath.c | head
```



## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/executor/nodeBitmapAnd.c`](../files/src/backend/executor/nodeBitmapAnd.c.md) | — | N-way intersect |
| [`src/backend/executor/nodeBitmapHeapscan.c`](../files/src/backend/executor/nodeBitmapHeapscan.c.md) | — | fetch + recheck |
| [`src/backend/executor/nodeBitmapIndexscan.c`](../files/src/backend/executor/nodeBitmapIndexscan.c.md) | — | AM-call entry |
| [`src/backend/executor/nodeBitmapOr.c`](../files/src/backend/executor/nodeBitmapOr.c.md) | — | N-way union |
| [`src/backend/optimizer/path/indxpath.c`](../files/src/backend/optimizer/path/indxpath.c.md) | — | selectivity ordering |

<!-- /callsites:auto -->

## Cross-references

- [[tidbitmap-structure-and-lossy]] — `PagetableEntry`,
  lossy/exact, the three-state lifecycle.
- [[tidbitmap-build-and-iterate]] — `tbm_add_tuples`,
  `tbm_union`, `tbm_intersect`, iterators.
- [[parallel-bitmap-heap]] — shared-state coordination via
  `ParallelBitmapHeapState`, the `BM_INITIAL` → `BM_INPROGRESS`
  → `BM_FINISHED` handshake.
- [[bitmap-heap-scan-flow]] — older single-file summary; this
  doc supersedes it.
- [[brin-summarize-and-scan]] — BRIN's `amgetbitmap`
  implementation, a major bitmap-scan source.
- [[gin-scan-and-consistent]] — GIN's `amgetbitmap` path.
- [[spgist-scan-and-consistent]] — SP-GiST's `amgetbitmap`.
- [[evalplanqual-recheck]] — `BitmapHeapRecheck` callback used
  by EPQ.
- [[buffer-manager]] — `table_beginscan_bm` produces a scan
  descriptor configured for the read-stream prefetch model
  bitmap scans use.
