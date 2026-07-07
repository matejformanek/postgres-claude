# SP-GiST — scan traversal and the consistent functions

The scan side of SP-GiST is **opposite-asymmetric** to the
insertion side: insertion holds two exclusive locks and worries
about deadlock; scans hold **one** share lock at a time and worry
about chasing REDIRECTs left behind by concurrent inserts.
Traversal uses a pairing-heap that doubles as a depth-first stack
(plain scan) and a KNN priority queue (ordered scan), and the
opclass's two `consistent` functions — `inner_consistent` for
inner tuples, `leaf_consistent` for leaf tuples — are where qual
matching actually happens.

For the static shape (tuples, page layouts, the four `tupstate`
codes), see [[spgist-tree-and-tuples]].  For the insert side that
*produces* the REDIRECTs this code follows, see
[[spgist-insert-and-picksplit]].

**Anchors** (all cites against `source/` at commit `e18b0cb7344`):
- `source/src/backend/access/spgist/spgscan.c` — the whole scan path
- `source/src/include/access/spgist_private.h:165-243` — `SpGistSearchItem`, `SpGistScanOpaqueData`
- `source/src/include/access/spgist.h` — `spgInnerConsistentIn/Out`, `spgLeafConsistentIn/Out`
- `source/src/backend/access/spgist/README` — concurrency model

## The two entry points — bitmap vs. ordered/non-ordered tuple scans

```c
/* spgscan.c:936-950  */
int64
spggetbitmap(IndexScanDesc scan, TIDBitmap *tbm)
{
    SpGistScanOpaque so = (SpGistScanOpaque) scan->opaque;
    so->want_itup = false;
    so->tbm = tbm;
    so->ntids = 0;
    spgWalk(scan->indexRelation, so, true, storeBitmap);
    return so->ntids;
}

/* spgscan.c:1020-1075 */
bool
spggettuple(IndexScanDesc scan, ScanDirection dir)
```

[verified-by-code]

Both funnel into `spgWalk` (`spgscan.c:811-921`) — the only
difference is the `storeRes` callback (`storeBitmap` vs.
`storeGettuple`) and the `scanWholeIndex` flag.  Bitmap scans
walk the whole tree before returning; gettuple stops at the next
page boundary once it has at least one buffered tuple.

The `dir != ForwardScanDirection` check at line 1025 is a hard
elog [verified-by-code]:

```c
if (dir != ForwardScanDirection)
    elog(ERROR, "SP-GiST only supports forward scan direction");
```

There is no backward-scan support — the partitioning trees
SP-GiST implements (quadtrees, k-d trees, radix tries) have no
natural ordering to walk in reverse.

## The pairing heap doing two jobs

`SpGistScanOpaqueData.scanQueue` (`spgist_private.h:191-192`)
[verified-by-code] is a `pairingheap *` — and depending on what
the comparator does, it behaves as either a depth-first stack or
a closest-first priority queue.

The comparator at `spgscan.c:41-82` [verified-by-code]:

```c
static int
pairingheap_SpGistSearchItem_cmp(const pairingheap_node *a,
                                 const pairingheap_node *b, void *arg)
{
    const SpGistSearchItem *sa = (const SpGistSearchItem *) a;
    const SpGistSearchItem *sb = (const SpGistSearchItem *) b;
    SpGistScanOpaque so = (SpGistScanOpaque) arg;

    if (sa->isNull) { if (!sb->isNull) return -1; }
    else if (sb->isNull) return 1;
    else
    {
        /* Order according to distance comparison */
        for (i = 0; i < so->numberOfNonNullOrderBys; i++)
        {
            if (isnan(sa->distances[i]) && isnan(sb->distances[i]))
                continue;
            if (isnan(sa->distances[i])) return -1;
            if (isnan(sb->distances[i])) return 1;
            if (sa->distances[i] != sb->distances[i])
                return (sa->distances[i] < sb->distances[i]) ? 1 : -1;
        }
    }

    /* Leaf items go before inner pages, to ensure a depth-first search */
    if (sa->isLeaf && !sb->isLeaf) return 1;
    if (!sa->isLeaf && sb->isLeaf) return -1;
    return 0;
}
```

Two rules from this comparator govern traversal order:

1. **For ordered scans** (`numberOfNonNullOrderBys > 0`), items are
   strict-ordered by their `distances[]` array — closest first.
   This is plain KNN.
2. **For non-ordered scans** the distance loop runs zero times, so
   items only differ in the `isLeaf` tiebreaker, where leaf items
   sort *before* inner items.  The comment is explicit: *"Leaf
   items go before inner pages, to ensure a depth-first search."*
   [from-comment]  Practical effect: when the queue has a mix of
   "an inner page to visit later" and "a leaf I just landed on",
   the leaf wins — so the walker fully drains a leaf chain before
   descending elsewhere.

This is the elegant bit: one queue type handles three scan modes
(KNN, plain depth-first, bitmap) without per-mode branching in
the walker.

## `SpGistSearchItem` — the unit of work

`spgist_private.h:165-184` [verified-by-code]:

```c
typedef struct SpGistSearchItem
{
    pairingheap_node phNode;
    Datum            value;          /* reconstructed parent value, or leafValue */
    SpGistLeafTuple  leafTuple;      /* whole leaf tuple, if needed */
    void            *traversalValue; /* opclass-specific traverse value */
    int              level;
    ItemPointerData  heapPtr;        /* inner tuple TID, or heap TID if isLeaf */
    bool             isNull;
    bool             isLeaf;
    bool             recheck;
    bool             recheckDistances;
    double           distances[FLEXIBLE_ARRAY_MEMBER];
} SpGistSearchItem;
```

Two kinds of items live in the queue:

| `isLeaf` | `heapPtr` meaning | Action when popped |
|---|---|---|
| false (default) | (block, offset) of an **inner tuple** to visit | call `inner_consistent`, push children |
| true (ordered only) | heap TID of a leaf candidate awaiting KNN ordering | emit via `storeRes`, the only place leaf items appear |

For a plain (non-ordered) scan, leaf items never enter the queue
— `spgLeafTest` reports them directly via `storeRes`.  For an
ordered scan, the leaf becomes a queue entry so it can be ranked
against still-pending inner-tuple subtrees.

The `traversalValue` field is the **most subtle part** of the
opclass contract.  It carries opclass-private state from one
inner-consistent call to the next descent — for example, a
quadtree opclass uses it to thread the current bounding box from
parent to child.  The `inner_consistent` callback must allocate
the traversal value in `in->traversalMemoryContext` (which is
`so->traversalCxt`, long-lived for the whole scan) so it
survives until the child item is popped.  See `spgMakeInnerItem`
at `spgscan.c:651-652` [verified-by-code]:

```c
item->traversalValue =
    out->traversalValues ? out->traversalValues[i] : NULL;
```

## The walker — `spgWalk`

`spgscan.c:811-921` [verified-by-code].  Pseudocode:

```
while (scanWholeIndex || !reportedSome):
    item := pop highest-priority from scanQueue
    if item is None: break

  redirect:
    if item.isLeaf:
        storeRes(item)   # ordered-scan leaf - emit it
        continue
    else:
        ensure buffer for item.heapPtr.blkno is locked SHARE
        if page is leaf:
            if blkno is root:
                scan every offset 1..max
            else:
                walk chain from item.heapPtr.offnum until InvalidOffsetNumber
                    if leaf is REDIRECT: chase via 'goto redirect'
        else:  # inner page
            tuple := PageGetItem(page, item.heapPtr.offnum)
            if tuple is REDIRECT: chase via 'goto redirect'
            elif tuple is LIVE: spgInnerTest(...)
            else: elog(ERROR, "unexpected SPGiST tuple state")
    free item
    MemoryContextReset(tempCxt)
```

The buffer-lock discipline at `spgscan.c:845-855`
[verified-by-code] is the simplest possible: keep a single
buffer across iterations if the next item is on the same page,
otherwise drop and re-lock.  Locks are share-mode.  This is the
*only* lock the scan holds, and it's the asymmetry to insertion:

> Search traversal algorithm is rather traditional.  At each
> non-leaf level, it share-locks the page, identifies which
> node(s) in the current inner tuple need to be visited, and
> puts those addresses on a stack of pages to examine later.
> It then releases lock on the current buffer before visiting
> the next stack item.  So only one page is locked at a time,
> and no deadlock is possible.

(README §CONCURRENCY, lines 252-256) [from-README]

### The REDIRECT chase

Two `goto redirect` sites in `spgWalk` handle the race against
concurrent insertions:

- **Leaf-chain REDIRECT** (`spgscan.c:886`): when walking a
  leaf chain, if `spgTestLeafTuple` returns
  `SpGistRedirectOffsetNumber`, the item's `heapPtr` has been
  rewritten to the redirect target, and we jump back to the
  top to re-lock the new page.

  ```c
  while (offset != InvalidOffsetNumber)
  {
      offset = spgTestLeafTuple(so, item, page, offset,
                                isnull, false,
                                &reportedSome, storeRes);
      if (offset == SpGistRedirectOffsetNumber)
          goto redirect;
  }
  ```

- **Inner-tuple REDIRECT** (`spgscan.c:897-903`): same idea —
  the inner tuple we expected to call `inner_consistent` on
  has been replaced with a REDIRECT; rewrite `item->heapPtr`
  and restart.

The "should never happen" cases are the dead-tuple states that
don't carry forwarding info:

```c
/* spgscan.c:792-794 */
elog(ERROR, "unexpected SPGiST tuple state: %d", leafTuple->tupstate);
```

A scan arriving at a PLACEHOLDER means an invariant was
violated; same for DEAD reached from a non-root context (DEAD
should be at the head of a chain that other inner tuples still
point at, but no live entries follow).

## `inner_consistent` — the per-inner-tuple opclass call

`spgInnerTest` at `spgscan.c:661-737` [verified-by-code] is the
adapter that calls the opclass.  The setup (lines 600-621):

```c
in->scankeys = so->keyData;
in->orderbys = so->orderByData;
in->nkeys = so->numberOfKeys;
in->norderbys = so->numberOfNonNullOrderBys;
Assert(!item->isLeaf);
in->reconstructedValue = item->value;
in->traversalMemoryContext = so->traversalCxt;
in->traversalValue = item->traversalValue;
in->level = item->level;
in->returnData = so->want_itup;
in->allTheSame = innerTuple->allTheSame;
in->hasPrefix = (innerTuple->prefixSize > 0);
in->prefixDatum = SGITDATUM(innerTuple, &so->state);
in->nNodes = innerTuple->nNodes;
in->nodeLabels = spgExtractNodeLabels(&so->state, innerTuple);
```

The opclass returns:

- `out.nNodes` — how many child nodes to visit
- `out.nodeNumbers[]` — which node indices to visit (subset of
  `0..nNodes-1`)
- `out.levelAdds[]` (optional) — how much to increment `level`
  for each descent (a radix-tree opclass consumes a node label's
  worth)
- `out.reconstructedValues[]` (optional) — propagate parent
  context to children
- `out.traversalValues[]` (optional) — opclass-private context
- `out.distances[]` (KNN only) — distance per child

**The `allTheSame` invariant** (line 693-695) [verified-by-code]:
the consistent function must return *all* of the children, *or
none of them*, when `allTheSame` is set — otherwise the assertion
fires:

```c
if (innerTuple->allTheSame && out.nNodes != 0 && out.nNodes != nNodes)
    elog(ERROR, "inconsistent inner_consistent results for allTheSame inner tuple");
```

This mirrors the insert-side invariant (see
[[spgist-insert-and-picksplit]] §Branch B): `allTheSame` is the
opclass's "I couldn't partition" escape hatch and the rest of
the system has to honor that there's no useful per-node
information to compare against.

### The nulls-tree short-circuit

When the item is from the nulls tree (`isnull == true`), the
opclass is **not called** — see lines 685-691 [verified-by-code]:

```c
else
{
    /* force all children to be visited */
    out.nNodes = nNodes;
    out.nodeNumbers = palloc_array(int, nNodes);
    for (i = 0; i < nNodes; i++)
        out.nodeNumbers[i] = i;
}
```

The nulls tree exists purely so the opclass author never has to
think about NULLs.  Every IS NULL scan key flips `searchNulls = true`
in `spgPrepareScanKeys`; the nulls-tree start item is added in
`resetSpGistScanOpaque` (line 166-168) [verified-by-code].

## `leaf_consistent` — the per-leaf-tuple opclass call

`spgLeafTest` at `spgscan.c:510-597` [verified-by-code].  This
is where qual matching produces output.  Setup at lines
536-548:

```c
MemoryContext oldCxt = MemoryContextSwitchTo(so->tempCxt);
in.scankeys = so->keyData;
in.nkeys = so->numberOfKeys;
in.orderbys = so->orderByData;
in.norderbys = so->numberOfNonNullOrderBys;
Assert(!item->isLeaf);
in.reconstructedValue = item->value;
in.traversalValue = item->traversalValue;
in.level = item->level;
in.returnData = so->want_itup;
in.leafDatum = SGLTDATUM(leafTuple, &so->state);
```

The opclass returns `bool` (does this leaf match?) plus
optionally:

- `out.leafValue` — the original indexed value, reconstructed
  if we needed it for an index-only scan
- `out.recheck` — bool, set if the opclass match is lossy
- `out.distances[]` — KNN distance per ordering operator
- `out.recheckDistances` — bool, set if distances are lossy

**Memory hygiene** is non-trivial here: the opclass runs in
`tempCxt`, which the walker resets after every item.  Anything
the opclass produces that needs to outlive this iteration —
specifically, the items pushed back into the queue — must be
copied out of `tempCxt`.  `spgNewHeapItem` at `spgscan.c:457-502`
[verified-by-code] does this `datumCopy` deliberately:

```c
if (so->want_itup)
{
    item->value = isnull ? (Datum) 0 :
        datumCopy(leafValue, so->state.attType.attbyval,
                  so->state.attType.attlen);
    ...
}
```

### Plain scan vs. ordered scan diverge here

`spgLeafTest`'s success path branches on whether the scan is
ordered (`spgscan.c:567-594`) [verified-by-code]:

- **Plain (non-ordered) scan**: emit the heap TID via `storeRes`
  *immediately*.  `reportedSome = true`.
- **Ordered scan**: wrap the leaf in a new `SpGistSearchItem`
  with `isLeaf = true` and push it back into the queue.  The
  comparator will rank it against other pending inner-tuple
  subtrees; the item will be popped (and emitted via
  `storeRes`) only when no still-pending inner tuple could
  possibly be closer.

This is what makes KNN with SP-GiST cheap: the index is walked
in distance order until the executor stops asking for more
rows.  We never have to materialize all matches up front.

The KNN-NULL-handling rule from the comparator's header comment
[from-comment]:

> KNN-searches currently only support NULLS LAST.  So, preserve
> this logic here.

— and that's what the comparator's "if `sa->isNull` and not
`sb->isNull` return -1" line enforces (pairing-heaps in PG are
**max-heaps** in the cmp sense, so returning -1 means "sa comes
later").

## storeRes — the two output sinks

The walker calls `storeRes` to deliver a tuple.  Two
implementations:

### `storeBitmap` (lines 925-934)

`storeBitmap` is straight-line — just
`tbm_add_tuples(so->tbm, heapPtr, 1, recheck)` and
`so->ntids++`.  Bitmap scans don't care about ordering, distances,
or reconstruction.

### `storeGettuple` (lines 953-1018)

For `spggettuple`, buffer up to `MaxIndexTuplesPerPage` results
in `so->heapPtrs[]`, `so->recheck[]`, and (for ordered scans)
`so->distances[]`.  If the scan wants the indexed value back
(`want_itup`, set when this is an index-only scan), reconstruct
the tuple via `heap_form_tuple` from the deformed leaf datums:

```c
/* spgscan.c:1004-1015 */
if (so->state.leafTupDesc->natts > 1)
    spgDeformLeafTuple(leafTuple, so->state.leafTupDesc,
                       leafDatums, leafIsnulls, isnull);

leafDatums[spgKeyColumn] = leafValue;
leafIsnulls[spgKeyColumn] = isnull;

so->reconTups[so->nPtrs] = heap_form_tuple(so->reconTupDesc,
                                           leafDatums,
                                           leafIsnulls);
```

After `spgWalk` returns, `spggettuple` drains the buffered
results one at a time, setting `scan->xs_heaptid` and (for
ordered scans) calling `index_store_float8_orderby_distances`.
When the buffer empties, it calls `spgWalk` again — with
`scanWholeIndex = false` so the walker stops at the next page
boundary.

## Initialization — what `resetSpGistScanOpaque` does

`spgscan.c:154-195` [verified-by-code] is called every time
`spgrescan` runs (which `spgbeginscan` arranges via the API
contract).  Steps:

1. Reset `traversalCxt` (drops all live items, traversal values,
   reconstructed values).
2. Allocate a fresh pairing heap in `traversalCxt`.
3. If `searchNulls`, add a start item pointing at
   `SPGIST_NULL_BLKNO` (block 2).
4. If `searchNonNulls`, add a start item pointing at
   `SPGIST_ROOT_BLKNO` (block 1).
5. Free any leftover distances / reconstructed tuples from the
   previous scan batch.

`spgPrepareScanKeys` at `spgscan.c:208-374` [verified-by-code]
is what computes `searchNulls` / `searchNonNulls` — it walks the
scan keys, pulls out IS NULL / IS NOT NULL specially, and the
remaining keys go into `so->keyData` for the opclass.  Notable:
*"all SPGiST-indexable operators are strict, so any null RHS
value makes the scan condition unsatisfiable"*  [from-comment,
line 203-205].

## What happens on `xs_want_itup` (index-only scans)

`spgcanreturn` at `spgscan.c:1077-1090` [verified-by-code]:

```c
bool
spgcanreturn(Relation index, int attno)
{
    SpGistCache *cache;

    /* INCLUDE attributes can always be fetched for index-only scans */
    if (attno > 1)
        return true;

    /* We can do it if the opclass config function says so */
    cache = spgGetCache(index);
    return cache->config.canReturnData;
}
```

So an index-only scan over an SP-GiST index needs the opclass to
declare `canReturnData = true` for the indexed column — meaning
the opclass can reconstruct the original value from the leaf
datum + the parent's reconstructed value.  Most opclasses can
(quadtree/k-d trees store the point directly; radix tries
concatenate the path).  INCLUDE columns are always returnable
because they're stored verbatim in the leaf.

The reconstruction itself happens **either** inside
`leaf_consistent` (which sets `out.leafValue`), or — when
INCLUDE columns are present — via `spgDeformLeafTuple` reading
straight off the leaf tuple bytes.

## Invariants

1. **One share-locked buffer at a time.**  No deadlock against
   inserts (which hold exclusive locks) — at worst, one waits
   for the other.  No deadlock among scanners.
2. **The pairing-heap is both stack and priority queue.**  The
   comparator's "leaf items before inner items" tiebreaker is
   what makes plain scans depth-first.
3. **Nulls tree never calls opclass functions.**  Hardwired
   logic: visit every node.
4. **`allTheSame` ⇒ inner_consistent returns all or none.**
   Asserted at `spgscan.c:694-695`.
5. **`traversalValue` lives in `traversalCxt`, not `tempCxt`.**
   It must survive across queue pops.
6. **Plain-scan leaf matches emit immediately; ordered-scan
   leaf matches enqueue and emit only when popped.**  This is
   what makes KNN incremental.
7. **REDIRECT chase is done via `goto redirect`** — restart of
   the same iteration, not a new pop.  Until-success retry.
8. **`spggettuple` is forward-only.**  The Postgres planner
   knows this via `amcanorderbyop` + the lack of `amcanbackward`.

## Useful greps

```bash
# Comparator that drives the pairing-heap order
grep -n "pairingheap_SpGistSearchItem_cmp" \
    source/src/backend/access/spgist/spgscan.c

# Every opclass-callback dispatch site
grep -n "FunctionCall.*innerConsistentFn\|FunctionCall.*leafConsistentFn" \
    source/src/backend/access/spgist/spgscan.c

# REDIRECT chase landmarks
grep -n "SpGistRedirectOffsetNumber\|goto redirect" \
    source/src/backend/access/spgist/spgscan.c

# The two storeRes implementations
grep -n "storeBitmap\|storeGettuple" \
    source/src/backend/access/spgist/spgscan.c

# Where nulls tree skips opclass call
grep -n "force all children to be visited\|/\* force \"match\"" \
    source/src/backend/access/spgist/spg*.c
```



## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/access/spgist/spgscan.c`](../files/src/backend/access/spgist/spgscan.c.md) | — | whole scan path |
| [`src/include/access/spgist.h`](../files/src/include/access/spgist.h.md) | — | spgInnerConsistentIn/Out, spgLeafConsistentIn/Out |
| [`src/include/access/spgist_private.h`](../files/src/include/access/spgist_private.h.md) | 165 | SpGistSearchItem, SpGistScanOpaqueData |

<!-- /callsites:auto -->

## Cross-references

- [[spgist-tree-and-tuples]] — the structs this scan walks; the
  REDIRECT/PLACEHOLDER/DEAD semantics drive the `goto redirect`
  logic here.
- [[spgist-insert-and-picksplit]] — produces the REDIRECTs;
  understand `state->redirectXid` and why VACUUM waits before
  converting them to PLACEHOLDERs.
- [[bitmap-heap-scan-flow]] — TIDBitmap-backed scan composition;
  `spggetbitmap`'s output is one input among many.
- [[gin-scan-and-consistent]] — GIN's analog: also has
  `extractQueryFn` and a tri-valued `consistentFn`, but the
  posting-tree walk is breadth-first and not closest-first.
- [[brin-summarize-and-scan]] — for the opposite end of the AM
  spectrum, where the scan is a single linear pass over the
  revmap.
- [[memory-contexts]] — `tempCxt` reset-per-item and
  `traversalCxt` scan-lifetime are the canonical pattern.
- [[buffer-manager]] — `LockBuffer(... BUFFER_LOCK_SHARE)` and
  the consequences of holding only one share lock at a time.
