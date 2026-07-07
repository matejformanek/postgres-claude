# SP-GiST — insert path, PickSplit, and the choose dispatch

This is the **dynamic** half of SP-GiST.  The static shape — pages,
inner / leaf / node / dead tuples, the four `tupstate` codes — is
in [[spgist-tree-and-tuples]]; assume that vocabulary here.

The insertion algorithm has one entry point, one outer loop, and
three branches inside the loop driven by the opclass's `choose`
function.  The loop holds *at most two* buffer locks at a time and
uses conditional locking + restart to dodge cross-branch deadlocks.
PickSplit is what runs when a leaf chain is full — it's the
deepest opclass callback and the only one that can re-shape the
tree.

**Anchors** (all cites against `source/` at commit `e18b0cb7344`):
- `source/src/backend/access/spgist/spgdoinsert.c` — the whole insert path
- `source/src/backend/access/spgist/README` — algorithm specification
- `source/src/include/access/spgist_private.h` — `spgChooseIn` / `spgChooseOut`, opclass FmgrInfo lookups
- `source/src/include/access/spgist.h` — `spgChooseFn` opclass contract

## Entry point — `spgdoinsert`

The signature at `spgdoinsert.c:1908-1910` [verified-by-code]:

```c
bool
spgdoinsert(Relation index, SpGistState *state,
            const ItemPointerData *heapPtr,
            const Datum *datums, const bool *isnulls)
```

The **return** is `bool`, not `void` — the boolean carries the
"please retry from scratch" signal that the conditional-locking
machinery raises when it can't get a child page lock.  The header
comment at `spgdoinsert.c:1901-1906` [from-comment] is explicit:
*"Returns true on success, false if we failed to complete the
insertion (typically because of conflict with a concurrent
insert).  In the latter case, caller should re-call spgdoinsert()
with the same args."*  Callers (the `aminsert` path in
`spginsert.c`) loop on the return value.

The function does four things in order:

1. **Compress and detoast the leaf datum.**
   `spgdoinsert.c:1928-1979` [verified-by-code]: look up the
   opclass `SPGIST_COMPRESS_PROC` (`index_getprocid` for proc id
   1), call it if present to map the indexed value to a leaf-key
   datum, then force-detoast any varlena leaf or INCLUDE values
   because SP-GiST does not use `index_form_tuple` and so
   `FormIndexDatum` does *not* detoast for us.

2. **Compute leaf size and bail early if it can't ever fit.**
   `spgdoinsert.c:1984-2001` [verified-by-code].  If the leaf
   would exceed `SPGIST_PAGE_CAPACITY` and the opclass didn't
   declare `longValuesOK`, we don't even start the loop — we
   raise `index row size %zu exceeds maximum %zu`.

3. **Pick the right root.**  `spgdoinsert.c:2003-2008`
   [verified-by-code]:

   ```c
   current.blkno = isnull ? SPGIST_NULL_BLKNO : SPGIST_ROOT_BLKNO;
   ```

   The nulls tree (block 2) and main tree (block 1) share the
   same loop — only the root differs and the `isnull` flag is
   threaded through so the choose / leaf-consistent callbacks
   are skipped when working in the nulls tree.

4. **Run the descent loop** (`spgdoinsert.c:2025-2317`)
   [verified-by-code].  Until the loop exits via `break`, it
   alternates between resolving the `current` buffer and acting
   on whatever tuple it finds there.

## The loop body, in three branches

Each iteration ends with `current` pointing at a fresh page.
What happens depends on the page kind:

### Branch A — `current.page` is a leaf page

`spgdoinsert.c:2102-2147` [verified-by-code].  Three sub-cases
in priority order:

| Condition | Action | Reference |
|---|---|---|
| `leafTuple` fits in `SpGistPageGetFreeSpace(page, 1)` | `addLeafTuple` (in-place insert), `break` | line 2109-2116 |
| Chain is small enough to move to another page (`sizeToSplit < SPGIST_PAGE_CAPACITY/2 && nToSplit < 64`) | `moveLeafs` (entire chain hops to a fresh leaf page, redirect tuple left behind), `break` | line 2117-2129 |
| Otherwise | `doPickSplit` — convert the leaf chain into a brand-new inner tuple | line 2131-2146 |

The 64-tuple / half-page threshold for `moveLeafs` is a heuristic
documented in the README §INSERTION ALGORITHM note (7): *"Actually,
current implementation can move the whole list of leaf tuples and
a new tuple to another page, if the list is short enough.  This
improves space utilization, but doesn't change the basis of the
algorithm."*  [from-README]

After `doPickSplit` returns `true`, the new leaf is already
installed and the loop breaks.  If it returns `false` (picksplit
was too unbalanced or the leaf is still too big), the code falls
through to `process_inner_tuple` to retry against the freshly
inserted inner tuple:

```c
if (doPickSplit(index, state, &current, &parent,
                leafTuple, level, isnull, isNew))
    break;          /* doPickSplit installed new tuples */

/* leaf tuple will not be inserted yet */
pfree(leafTuple);
Assert(!SpGistPageIsLeaf(current.page));
goto process_inner_tuple;
```

### Branch B — `current.page` is an inner page — call `choose`

`spgdoinsert.c:2148-2316` [verified-by-code].  This is where the
opclass `choose` method runs.  The `spgChooseIn` struct is
populated from the inner tuple's prefix + node array, plus the
incoming value and current descent level:

```c
in.datum = datums[spgKeyColumn];
in.leafDatum = leafDatums[spgKeyColumn];
in.level = level;
in.allTheSame = innerTuple->allTheSame;
in.hasPrefix = (innerTuple->prefixSize > 0);
in.prefixDatum = SGITDATUM(innerTuple, state);
in.nNodes = innerTuple->nNodes;
in.nodeLabels = spgExtractNodeLabels(state, innerTuple);
```

For the **nulls tree**, the choose function is **not called** —
the code forces `out.resultType = spgMatchNode` and the random
prng picks one of the nodes (line 2193-2197).

The `allTheSame` check at `spgdoinsert.c:2199-2212`
[verified-by-code] is the hardest invariant the opclass author
has to observe: when the inner tuple has all-equivalent nodes,
`choose` *must* return `spgMatchNode`; `spgAddNode` is an error
and the core code overrides any `matchNode.nodeN` with a random
selection.

Three result types dispatch (line 2214-2315):

#### `spgMatchNode` — descend to N'th child

`spgMatchNodeAction` at `spgdoinsert.c:1454-1503`
[verified-by-code] makes the current buffer the new parent,
walks the inner-tuple node array via `SGITITERATE` to find node N,
and points `current` at either the downlink TID (if non-NIL) or
"please allocate a new leaf page" (NIL downlink → invalid blkno).

Then the loop goes around.  Subtle bit at
`spgdoinsert.c:2255-2278` [verified-by-code]: after MatchNode, the
opclass can shorten the leaf datum (e.g. radix-tree opclasses
strip the prefix that was just consumed) by setting
`out.result.matchNode.restDatum`.  The loop recomputes leaf size;
if the new size still doesn't fit and `longValuesOK` is set, the
code tolerates **up to 10** no-progress iterations before
declaring infinite loop:

```c
else if (++numNoProgressCycles < 10)
    ok = true;
```

The 10-cycle limit guards against broken opclasses that "just
repeatedly generate an empty-string leaf datum once it runs out
of data" (comment line 2240-2244)  [from-comment].

#### `spgAddNode` — add a node and retry

`spgAddNodeAction` at `spgdoinsert.c:1508-1705`
[verified-by-code] tries to fit a new node into the existing
inner tuple.  Two paths:

- **In-place replace** (line 1536-1568): if
  `PageGetExactFreeSpace(current->page) >= newInnerTuple->size -
  innerTuple->size`, just `PageIndexTupleDelete` +
  `PageAddItem` at the same offset.  WAL record is
  `XLOG_SPGIST_ADD_NODE`.
- **Move-to-another-page** (line 1571-1704): no room on the
  current page, so allocate a fresh inner page in the same
  parity group (`GBUF_INNER_PARITY(current->blkno)`,
  line 1596-1599), insert there, update the parent inner
  tuple's downlink via `saveNodeLink`, and replace the old
  inner tuple with either a **REDIRECT** (concurrent scans
  exist) or a **PLACEHOLDER** (during index build, no
  concurrent scans).  See lines 1644-1662:

  ```c
  if (state->isBuild)
      dt = spgFormDeadTuple(state, SPGIST_PLACEHOLDER,
                            InvalidBlockNumber, InvalidOffsetNumber);
  else
      dt = spgFormDeadTuple(state, SPGIST_REDIRECT,
                            current->blkno, current->offnum);
  ```

After AddNode, the loop jumps **back to `process_inner_tuple`**
(line 2301) — *not* to the top of the descent loop.  The
comment is precise: *"Retry insertion into the enlarged node.
We assume that we'll get a MatchNode result this time."*  If the
opclass repeatedly returns AddNode against the same enlarged
inner tuple, the CHECK_FOR_INTERRUPTS at the top of
`process_inner_tuple` (line 2164-2169) is what breaks the loop.

The Assert at line 1583-1584 catches a corruption case: *"It
should not be possible to get here for the root page"* — the
root inner tuple is sized so AddNode never has to move it
elsewhere.

#### `spgSplitTuple` — split inner tuple into prefix + postfix

`spgSplitNodeAction` at `spgdoinsert.c:1710-1907`
[verified-by-code].  This is the "the prefix only partially
matches my new value" case — used by radix-tree opclasses.  The
README §INSERTION ALGORITHM note (4) gives the canonical
example: inserting `'www.gogo.com'` into `{1}(www.google.com/)[a,
i]` becomes `{2}(www.go)[o] → {3}(gle.com/)[a, i]`, with a node
[g] then added to {2} on the AddNode-retry pass [from-README].

Core invariant from line 196-198 of README: *"SP-GiST core
assumes that prefix tuple is not larger than old inner tuple.
That allows us to store prefix tuple directly in place of old
inner tuple."*  The postfix tuple lives on the same page if
there's room, otherwise on a freshly allocated inner page.

After SplitTuple, like AddNode, the loop jumps back to
`process_inner_tuple` (line 2308-2309) — but now `current`
points at the prefix tuple (the new, smaller inner tuple), so
the next `choose` call sees a tuple that *should* match the
incoming value.

## The concurrency protocol — two locks, conditional, restart on fail

This is described in README §CONCURRENCY (lines 217-244)
[from-README] and lives in `spgdoinsert.c:2060-2087`
[verified-by-code]:

```c
else if (current.blkno != parent.blkno)
{
    /* descend to a new child page */
    current.buffer = ReadBuffer(index, current.blkno);

    /*
     * Attempt to acquire lock on child page.  We must beware of
     * deadlock against another insertion process descending from that
     * page to our parent page (see README).  If we fail to get lock,
     * abandon the insertion and tell our caller to start over.
     */
    if (!ConditionalLockBuffer(current.buffer))
    {
        ReleaseBuffer(current.buffer);
        UnlockReleaseBuffer(parent.buffer);
        return false;
    }
}
```

The protocol:

1. **At most two pages locked at once** — current and parent.
   When the loop descends, the old current becomes parent and
   the new current is locked.
2. **The child lock is conditional.**  If we can't get it
   immediately, we release both buffers and return `false`.
   The caller retries `spgdoinsert` from the root.
3. **The triple-parity rule** (see
   [[spgist-tree-and-tuples]] §Triple-parity) makes the
   deadlock cases rare in practice — `(N+1) mod 3` parity
   ensures the simple two-process A → B + B → A cycle can't
   form.  Three-way deadlocks remain possible, hence the
   conditional-lock fallback.
4. **`addLeafPage`'s extra buffer** (line 246-250 of README):
   when insertion needs to allocate an additional leaf or
   inner buffer (e.g. for a PickSplit that produces two new
   pages), the additional buffers are also conditionally
   locked but we have the freedom to *retry with a different
   page* rather than restart from the root, because we don't
   care exactly which fresh page we land on.

## PickSplit — the heaviest opclass callback

`doPickSplit` at `spgdoinsert.c:672-1453` is the big one — almost
800 lines.  At a high level (header comment, lines 660-671)
[from-comment]:

> Returns true if we successfully inserted newLeafTuple during
> this function, false if caller still has to do it (meaning
> another picksplit operation is probably needed).  Failure
> could occur if the picksplit result is fairly unbalanced, or
> if newLeafTuple is just plain too big to fit on a page.

The phases:

### Phase 1 — gather the leaf tuples to be split

`spgdoinsert.c:737-799` [verified-by-code].  Two cases:

- **Root page** (lines 738-765): no chain links, so just scan
  every offset and pick up every LIVE tuple.
- **Non-root** (lines 766-799): follow the `nextOffset` chain
  starting at `current->offnum`, collecting LIVE tuples and
  noting any DEAD tuple at the head as the redirect-target slot.

Each picked-up datum goes into `in.datums[]`; the line-pointer
indices go into `toDelete[]`; the space they'd free up is
accumulated in `spaceToDelete`.

### Phase 2 — call the opclass picksplit

The opclass `SPGIST_PICKSPLIT_PROC` runs against the gathered
`in.datums[]`; `out.prefixDatum`, `out.nNodes`,
`out.nodeLabels[]`, and the per-tuple `out.mapTuplesToNodes[]`
come back.

### Phase 3 — `checkAllTheSame` rescue path

`checkAllTheSame` at `spgdoinsert.c:594-672` [verified-by-code]
handles the "opclass put everything in one node" case (or "all
nodes have equivalent labels").  When PickSplit can't actually
partition, the code force-marks `allTheSame = 1` on the new
inner tuple; subsequent `choose` calls are constrained to
return `spgMatchNode` and the descent picks a random node.
This guarantees forward progress — eventually some `choose`
will accept a node and the next PickSplit will see fewer
tuples.

### Phase 4 — distribute tuples to one or two leaf pages

The result is at most two new leaf pages (one or two, per the
opclass's mapping).  `leafPageSelect[i]` says which page tuple
`i` goes to.  The current leaf page can be reused for one of
the two new lists (saving an allocation).  WAL record:
`XLOG_SPGIST_PICKSPLIT`.

### Phase 5 — install the new inner tuple

The new inner tuple replaces the old inner-tuple downlink (or
becomes the root's single inner tuple if we were splitting the
former leaf-root).  Old leaf tuples are converted to REDIRECTs
pointing at where their new chain head lives, or PLACEHOLDERs
if doing an index build.

### Failure mode — unbalanced PickSplit

If PickSplit produced just one non-empty chain that still
won't fit on a page, the function returns `false` and the
outer loop will recurse: descend into the freshly-installed
inner tuple and PickSplit again.  The opclass is responsible
for making progress — the header comment again:

> Because we force the picksplit result to be at least two
> chains, each cycle will get rid of at least one leaf tuple
> from the chain, so the loop will eventually terminate if
> lack of balance is the issue.

The spgdoinsert wrapper's `numNoProgressCycles < 10` check
(see MatchNode §) catches the other failure mode: the opclass
returns the same enlarged datum forever.

## REDIRECT placement — why insertions leave them behind

Every time an insert moves a tuple (chain or inner) to a new
location, it leaves a REDIRECT in the old slot **iff** scans may
be in flight.  The "scans may be in flight" check is
`state->isBuild` — during index build there are no concurrent
scans, so a PLACEHOLDER is enough.

The README §CONCURRENCY (lines 257-266) explains the race:

> by the time we arrive at a pointed-to page, a concurrent
> insertion could have replaced the target inner tuple (or
> leaf tuple chain) with data placed elsewhere.  To handle
> that, whenever the insertion algorithm changes a nonempty
> downlink in an inner tuple, it places a "redirect tuple" in
> place of the lower-level inner tuple or leaf-tuple chain
> head that the link formerly led to.

The REDIRECT also carries the inserter's XID
(`SpGistDeadTupleData.xid`) — this is `state->redirectXid`,
which is `GetTopTransactionId()` at scan-start.  VACUUM uses
the XID to decide *when* it's safe to convert REDIRECT to
PLACEHOLDER (`spgvacuum.c`, not covered here): once
`OldestXmin > redirectXid`, no extant scan can still be in
flight from before the move.

## Recap — the state diagram

The five things that can happen at each loop iteration, and what
each one does to the descent:

| Result | Re-enter | Why |
|---|---|---|
| Leaf insert succeeded | break | done |
| Leaf chain moved to new page | break | done; old chain now a REDIRECT |
| PickSplit installed new tuples | break | done; either inner tuple or new leaf inserted |
| MatchNode | top of outer loop | descend to child |
| AddNode | `process_inner_tuple` | retry, expect MatchNode this time |
| SplitTuple | `process_inner_tuple` | retry against new prefix tuple |
| Conditional lock failed | `return false` | caller retries from root |

## Invariants worth holding in your head

1. **One value of `current` becomes the parent of the next
   iteration.**  Two locks max.
2. **`allTheSame` inner tuples accept only `spgMatchNode`.**
   `spgAddNode` is an elog error; `spgSplitTuple` is also
   forbidden by convention (the random `matchNode.nodeN` is
   chosen by core).
3. **`choose` and the consistent functions never see NULL
   inputs.**  The nulls tree (block 2) uses hardwired logic.
4. **`compress` (if defined) must return an untoasted value.**
   The insert path detoasts other columns; it trusts `compress`.
5. **PickSplit always produces ≥ 2 chains.**  This is what
   guarantees termination of the outer "leaf-still-doesn't-fit
   → PickSplit again" recursion.
6. **REDIRECT iff isBuild == false.**  This is the only signal
   the dead-tuple constructor needs to choose between
   PLACEHOLDER and REDIRECT.
7. **The first conditional-lock failure aborts the whole
   insert and returns false.**  No partial state survives.
8. **`SpGistSetLastUsedPage` is called on every buffer we
   release.**  This feeds the per-backend LUP cache so the next
   insert tries to land on a page with known free space.

## Useful greps

```bash
# Every call into an opclass function
grep -n "FunctionCall.*procinfo\|FunctionCall.*compressProcinfo\|FunctionCall.*innerConsistentFn\|FunctionCall.*leafConsistentFn" \
    source/src/backend/access/spgist/*.c

# The choose-result enum (per the opclass contract)
grep -n "spgMatchNode\|spgAddNode\|spgSplitTuple" \
    source/src/include/access/spgist.h \
    source/src/backend/access/spgist/spgdoinsert.c

# Conditional-lock restart sites
grep -n "ConditionalLockBuffer\|return false" \
    source/src/backend/access/spgist/spgdoinsert.c

# REDIRECT vs PLACEHOLDER selection
grep -n "isBuild.*SPGIST_PLACEHOLDER\|isBuild.*SPGIST_REDIRECT" \
    source/src/backend/access/spgist/spgdoinsert.c

# The 10-cycle infinite-loop guard
grep -n "numNoProgressCycles\|bestLeafSize" \
    source/src/backend/access/spgist/spgdoinsert.c
```



## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/access/spgist/spgdoinsert.c`](../files/src/backend/access/spgist/spgdoinsert.c.md) | — | whole insert path |
| [`src/include/access/spgist.h`](../files/src/include/access/spgist.h.md) | — | spgChooseFn opclass contract |
| [`src/include/access/spgist_private.h`](../files/src/include/access/spgist_private.h.md) | — | spgChooseIn / spgChooseOut, opclass FmgrInfo lookups |

<!-- /callsites:auto -->

## Cross-references

- [[spgist-tree-and-tuples]] — the structs (inner / leaf / node /
  dead) and tuple-state alphabet this doc dispatches on.
- [[spgist-scan-and-consistent]] — the scan side: how REDIRECTs
  get followed by share-locked scanners and why their XID
  matters.
- [[buffer-manager]] — `ConditionalLockBuffer`, `START_CRIT_SECTION`,
  and `XLogInsert` are all from there.
- [[gin-fastupdate-pending]] — GIN's analog for "deferred work
  protected by ExclusiveLock on the metapage" — different
  trade-off than SP-GiST's conditional-lock retry.
- [[brin-summarize-and-scan]] — for the contrast between AMs
  where insert is cheap (BRIN summarize-on-demand) vs SP-GiST
  where every insert can trigger PickSplit.
- [[wal-record-types]] — `XLOG_SPGIST_ADD_NODE`,
  `XLOG_SPGIST_PICKSPLIT`, `XLOG_SPGIST_SPLIT_TUPLE`.
