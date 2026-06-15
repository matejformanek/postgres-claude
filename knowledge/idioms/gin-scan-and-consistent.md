# GIN scan — extractQuery + tri-valued consistentFn + multi-entry merge

A GIN scan is structured as an N-way merge over entry streams plus
tri-valued consistency logic. The query operator (e.g. `tsvector @@
tsquery`) decomposes into multiple keys; the opclass'
`extractQueryFn` returns those keys plus per-key metadata; each key
becomes a `GinScanEntry` that streams ItemPointers from the entry
tree (or its posting tree, or the pending list); a `GinScanKey`
groups entries that share the same SQL-level operator argument; the
`consistentFn` (or `triConsistentFn`) decides whether a candidate
TID actually matches given which entries' streams contain it.

The trickiness comes from **partial information**. Posting trees
return TIDs precisely, but the leaf pages also encode **lossy
pointers** (`offset = 0xFFFF`) when a whole heap page matched but
individual offsets were lost (e.g. compressed posting list overflow).
For lossy entries, the consistentFn might say "if any other entry
matches this page, the whole page must be returned" — and the
scanner must pass that as a tri-state `MAYBE` to a `triConsistentFn`
that knows how to combine the certain entries with the uncertain
ones.

This doc walks the scan setup (`ginNewScanKey` →
`extractQueryFn` → `GinScanKey`/`GinScanEntry`), the
`startScan` initialization (`startScanEntry`'s entry-tree descent +
posting-tree open), the `scanGetItem` ordered merge with
`keyGetItem` per-key advancement, the tri-state lossy-pointer
combinator, the `gingetbitmap` top-level (pending list first,
then main index), and the `recheck` propagation.

Companion docs:
- [[gin-tree-structure]] — the trees the scan walks.
- [[gin-fastupdate-pending]] — the pending list scan must consult first.

## Anchors

- `source/src/backend/access/gin/README` — sections "Scanning", "Multi-key scans".
- `source/src/backend/access/gin/ginscan.c:156-450` — `ginNewScanKey` (initialize scan keys from index quals).
- `source/src/backend/access/gin/ginget.c:69-300` — `scanPostingTree` (descend into a posting tree for a key).
- `source/src/backend/access/gin/ginget.c:319-505` — `startScanEntry`.
- `source/src/backend/access/gin/ginget.c:507-604` — `startScanKey`.
- `source/src/backend/access/gin/ginget.c:605-1003` — `startScan` + `scanPendingInsert`.
- `source/src/backend/access/gin/ginget.c:1005-1300` — `keyGetItem` (per-key advancement + consistentFn call).
- `source/src/backend/access/gin/ginget.c:1300-1930` — `scanGetItem` (N-way merge across keys).
- `source/src/backend/access/gin/ginget.c:1931-1983` — `gingetbitmap` (top-level entry).
- `source/src/include/access/gin_private.h:80-95` — `GinState` (per-relation cached FmgrInfo for the four support fns).
- `source/src/include/access/gin_private.h:255-340` — `GinScanKey` / `GinScanEntry` structs.
- `source/src/backend/access/gin/ginlogic.c` — tri-valued consistency shim.

## Opclass support functions

A GIN opclass declares up to **seven** support procedures (the
README lists them in the "Gin API" section). The four scan-relevant
ones, called from `GinState.{extractQueryFn, consistentFn,
triConsistentFn, comparePartialFn}`:

| Support # | Name              | Signature (roughly)                                |
|-----------|-------------------|----------------------------------------------------|
| 2         | `extractValue`    | item → array of keys (insert/build side)           |
| 3         | `extractQuery`    | query + strategy → array of keys + matchMode flags |
| 4         | `consistent`      | bool[] entryRes + query + nentries + strategy → bool|
| 5         | `comparePartial`  | partialQuery + indexKey → cmp (for `GIN_SEARCH_MODE_*`) |
| 6         | `triConsistent`   | char[] entryRes + ... → GIN_TRUE/FALSE/MAYBE       |

`extractQueryFn` is called once at scan start; it returns:
- `nkeys` keys (Datum array).
- `nullFlags[]` — which keys are null.
- `pmatch[]` (optional) — flags for partial-match support.
- `extra_data[]` (optional) — opaque per-key payload passed to
  consistentFn.
- `searchMode` — sets one of:
  - `GIN_SEARCH_MODE_DEFAULT` — return matches of any key.
  - `GIN_SEARCH_MODE_INCLUDE_EMPTY` — include items with empty key set.
  - `GIN_SEARCH_MODE_ALL` — full-index scan; consistentFn arbitrates.
  - `GIN_SEARCH_MODE_EVERYTHING` — like ALL, but consistentFn unused.

The `extractQueryFn` may return **zero keys** with a non-default
searchMode — this is how full-index scans work (`SEARCH_MODE_ALL`).

## Scan structures

```c
/* gin_private.h:80-95 (paraphrased) */
typedef struct GinState {
    /* Cached FmgrInfo for the four scan support functions, per attno */
    FmgrInfo  extractQueryFn[INDEX_MAX_KEYS];
    FmgrInfo  consistentFn[INDEX_MAX_KEYS];
    FmgrInfo  triConsistentFn[INDEX_MAX_KEYS];
    FmgrInfo  comparePartialFn[INDEX_MAX_KEYS];
    ...
} GinState;

/* gin_private.h:255-340 (paraphrased) */
typedef struct GinScanKeyData {
    /* User-supplied operator + strategy */
    StrategyNumber  strategy;
    Datum           query;
    bool            queryCategory;
    AttrNumber      attnum;

    /* Per-entry streams */
    uint32          nentries;
    uint32          nuserentries;       /* "user" entries first; others added by GIN for special cases */
    GinScanEntry   *scanEntry;          /* the streams */

    /* Required / additional partition for lossy-pointer handling */
    uint32          nrequired;
    uint32          nadditional;
    GinScanEntry   *requiredEntries;
    GinScanEntry   *additionalEntries;

    /* Check-flag buffer reported to consistentFn */
    bool           *entryRes;
    GinTernaryValue *triEntryRes;

    /* Cached consistentFn pointers (real or "shim" from ginlogic.c) */
    bool        (*boolConsistentFn) (GinScanKey key);
    GinTernaryValue (*triConsistentFn) (GinScanKey key);
    bool            excludeOnly;        /* matches if no entry matches */

    /* Current matched item + recheck flag */
    ItemPointerData curItem;
    bool            curItemMatches;
    bool            recheckCurItem;
    bool            isFinished;
} GinScanKeyData;

typedef struct GinScanEntryData {
    ScanKey         scanKey;            /* upstream IndexScanDescData key */
    OffsetNumber    attno;
    Datum           queryKey;
    GinNullCategory queryCategory;
    bool            isPartialMatch;
    StrategyNumber  strategy;
    int32           searchMode;

    /* Output stream state */
    Buffer          buffer;                /* posting-tree leaf currently held */
    ItemPointerData curItem;               /* current TID from this stream */
    bool            matchResult;
    bool            isFinished;
    Pointer         list;
    int             nlist;                 /* compressed posting list count */
    OffsetNumber    offset;
    ...
} GinScanEntryData;
```

The **required/additional** partitioning is the key abstraction for
multi-key queries. An "AND" semantic puts all entries in
`requiredEntries`; the scan advances by taking the MAX of their
`curItem`s. An "OR" semantic puts entries in `additionalEntries`;
the scan looks at the MIN. Mixed-mode (e.g. `tsquery 'a & (b | c)'`)
needs `keyGetItem` to advance required entries and then peek at
additional entries for lossy-page resolution.

## `gingetbitmap` — top-level

```c
/* ginget.c:1931 (skeleton) */
int64 gingetbitmap(IndexScanDesc scan, TIDBitmap *tbm)
{
    ginFreeScanKeys(so);
    ginNewScanKey(scan);
    if (GinIsVoidRes(scan)) return 0;          /* unsatisfiable */

    /* Step 1: pending list */
    scanPendingInsert(scan, tbm, &ntids);

    /* Step 2: main index */
    startScan(scan);
    ItemPointerSetMin(&iptr);
    for (;;) {
        if (!scanGetItem(scan, iptr, &iptr, &recheck)) break;

        if (ItemPointerIsLossyPage(&iptr))
            tbm_add_page(tbm, ItemPointerGetBlockNumber(&iptr));
        else
            tbm_add_tuples(tbm, &iptr, 1, recheck);
        ntids++;
    }
    return ntids;
}
```

[verified-by-code] (`ginget.c:1931-1982`).

### Pending list before main index — the ordering matters

> First, scan the pending list and collect any matching entries
> into the bitmap. After we scan a pending item, some other backend
> could post it into the main index, and so we might visit it a
> second time during the main scan. This is okay because we'll just
> re-set the same bit in the bitmap. (The possibility of duplicate
> visits is a major reason why GIN can't support the amgettuple
> API, however.) Note that it would not do to scan the main index
> before the pending list, since concurrent cleanup could then make
> us miss entries entirely.

[from-comment] (`ginget.c:1950-1958`).

This is **the** correctness-critical ordering of the GIN scan. Doing
it backwards risks dropped tuples because cleanup races with the
scan.

### `gingetbitmap` only, no `gingettuple`

GIN provides `amgetbitmap` but **not** `amgettuple`. Two reasons:

1. The pending-list-then-main-tree two-phase scan can return
   duplicates; only a TIDBitmap (which dedups by setting the same
   bit twice harmlessly) can absorb them.
2. The scan's tri-state lossy-pointer semantics return TIDs in
   sorted-per-key order but not in heap-physical order; reordering
   into heap order is what BitmapHeapScan does for us.

[from-comment] (`ginget.c:1953-1956`).

## `ginNewScanKey` — set up scan keys

```c
/* ginscan.c:156-450 (skeleton) */
void ginNewScanKey(IndexScanDesc scan) {
    so->keys = palloc_array(GinScanKeyData, scan->numberOfKeys);
    so->nkeys = 0;

    for (skey in scan->keyData) {
        /* Call extractQueryFn(skey->sk_argument, skey->sk_strategy, ...) */
        keys = FunctionCall7Coll(&so->ginstate.extractQueryFn[attno - 1],
                                  collation,
                                  skey->sk_argument,
                                  &nkeys,
                                  Int16GetDatum(skey->sk_strategy),
                                  &nullFlags,
                                  &searchMode,
                                  &pmatch,
                                  &extra_data);

        /* Allocate GinScanKey + nkeys GinScanEntry */
        key = &so->keys[so->nkeys++];
        for (i = 0; i < nkeys; i++) {
            entry = ginFillScanEntry(so, attno, sk_strategy, searchMode,
                                     keys[i], category, partial_match, ...);
            key->scanEntry[i] = entry;
        }
        ...
    }

    /* For full-index scans (no keys), add a synthetic "all entries" entry */
    /* Compute the bool / tri consistent function pointers based on the strategy */
    /* If any extractQueryFn returns 0 with default searchMode → result is unsatisfiable */
}
```

The "shim" in `ginlogic.c` provides a bool→tri-valued adapter for
opclasses that only implement `consistent` (not `triConsistent`).
The shim re-calls the bool function multiple times with varying
inputs to derive a tri-valued answer — expensive but correct.

## `startScan` + `startScanEntry` — entry tree descent

```c
/* ginget.c:319-450 (skeleton) */
void startScanEntry(GinState *ginstate, GinScanEntry entry, Snapshot snapshot)
{
    /* Step 1: find the entry in the entry tree */
    GinBtreeStack *stack = ginPrepareEntryScan(...);
    page = BufferGetPage(stack->buffer);

    /* Step 2: locate the key on the leaf page */
    findItemInPostingPage(...);

    /* Step 3: if the entry has an inline posting list, capture it; else open posting tree */
    if (GinIsPostingTree(itup)) {
        rootPostingTree = GinGetPostingTree(itup);
        entry->buffer = scanPostingTree(index, entry, rootPostingTree);
    } else {
        /* Decompress the inline posting list */
        entry->list = palloc(...);
        ginPostingListDecode(GinGetPosting(itup), &entry->nlist);
    }

    /* Step 4: handle partial-match (range searches) */
    if (entry->isPartialMatch)
        collectMatchBitmap(...);    /* uses comparePartialFn for prefix-like matches */
}
```

[verified-by-code] (`ginget.c:319-505`).

`scanPostingTree` descends into the posting tree and positions on
the leftmost leaf, leaving the leaf buffer pinned. Subsequent
`entryGetItem` calls advance through that leaf's compressed
segments, then follow `rightlink` to the next leaf.

## `scanGetItem` + `keyGetItem` — the merge

```c
/* ginget.c:1300+ (skeleton) */
bool scanGetItem(IndexScanDesc scan, ItemPointerData advancePast,
                 ItemPointerData *item, bool *recheck) {
    for (;;) {
        ItemPointerData minItem;
        ItemPointerSetMax(&minItem);

        /* Step 1: each scan key advances to its min item > advancePast */
        for each GinScanKey key:
            if (key->isFinished) continue;
            if (ginCompareItemPointers(&key->curItem, &advancePast) <= 0)
                keyGetItem(ginstate, tempCtx, key, advancePast);
            if (key->isFinished) continue;

            if (ginCompareItemPointers(&key->curItem, &minItem) < 0)
                minItem = key->curItem;

        if (allFinished) return false;

        /* Step 2: probe each key to see if it matches minItem */
        match = true;
        recheckFlag = false;
        for each key:
            if (ginCompareItemPointers(&key->curItem, &minItem) != 0)
                ... call keyGetItem with advancePast = minItem-1 ...
            if (!key->curItemMatches) { match = false; break; }
            recheckFlag = recheckFlag || key->recheckCurItem;

        if (match) {
            *item = minItem;
            *recheck = recheckFlag;
            return true;
        }
        advancePast = minItem;     /* advance past this candidate */
    }
}
```

(Heavily paraphrased; the actual code is more elaborate due to
lossy-page handling.)

### `keyGetItem` — per-key advancement

The crucial routine. Three responsibilities:

1. **Advance required entries past `advancePast`**, find the min
   `minItem` across them.
2. **Advance additional entries** up to `minItem`. They may
   contribute lossy-page information that affects consistent-fn
   results.
3. **Call `triConsistentFn`** with:
   - `entryRes[i] = TRUE` if entry i has `curItem == minItem` exactly.
   - `entryRes[i] = MAYBE` if entry i has a lossy-page entry for
     `minItem`'s page.
   - `entryRes[i] = FALSE` otherwise.

   If the result is `TRUE` → `curItemMatches = true,
   recheckCurItem = false`. If `MAYBE` → either return a
   lossy-page pointer (recheck=true) or set
   `curItemMatches = false`. If `FALSE` → `curItemMatches = false`.

The tri-valued combinator is the heart of GIN's correctness story:

```
A query "a AND b":
  TRUE  AND TRUE  = TRUE          (definitely match)
  TRUE  AND MAYBE = MAYBE         (need to recheck)
  MAYBE AND MAYBE = MAYBE         (need to recheck)
  any   AND FALSE = FALSE         (definitely no match)
```

[from-comment] (`ginget.c:1149-1170`).

The "MAYBE" path returns a lossy-page pointer for the TIDBitmap;
BitmapHeapScan will then re-execute the operator on every tuple of
that page.

### Required / additional partition

`startScanKey` (`ginget.c:507`) decides at scan-setup time which
entries are **required** (must match for any TID to be returned)
vs **additional** (may contribute but aren't required). The
classification is based on the consistentFn's behavior for the
strategy:

- Pure AND: all entries required.
- Pure OR: no entries required (all additional); the consistentFn
  is called against each entry's TID stream separately.
- Mixed AND/OR (e.g. `tsquery 'a & (b | c)'`): some required, some
  additional.

The `nrequired = 0` case is the **`excludeOnly`** scan: matches are
defined by what's NOT in the index (e.g. `NOT t @@ 'foo'`). The
scan iterates every TID and lets the consistent function filter.

[verified-by-code] (`ginget.c:1063-1109`).

## The "shim" tri-state consistent function

Many opclasses only implement `consistent` (bool), not
`triConsistent`. `ginlogic.c` provides a **shim**:

```
shim_triConsistentFn(entryRes_with_MAYBE):
    /* Try each combination of MAYBE → TRUE/FALSE and call boolConsistentFn */
    if (no MAYBEs) return boolConsistentFn(entryRes) ? TRUE : FALSE;

    /* Mark all MAYBE positions, then enumerate 2^k combinations
       (k = number of MAYBEs).
       If all combinations return TRUE → TRUE
       If all combinations return FALSE → FALSE
       Otherwise → MAYBE
    */
```

[verified-by-code] (`ginlogic.c`).

Expensive when many MAYBEs (`2^k` calls), but correct. New
opclasses are encouraged to implement `triConsistent` directly to
avoid the shim cost.

## The pending-list scan — `scanPendingInsert`

Pending-list entries are `(column, key, category, TID)` quadruples
in arbitrary order on each page. To match them against the scan
keys, `scanPendingInsert`:

1. **Walk every pending-list page**, reading entries.
2. **For each heap TID** (entries are grouped consecutively by TID),
   gather all its entries.
3. **For each scan key**, set `entryRes[i] = TRUE` if there's a
   matching pending-list entry, else FALSE. (No MAYBE — pending-list
   entries are exact.)
4. **Call the (bool) consistentFn**. If true, add the TID to the
   output TIDBitmap.

The lack of MAYBE here is because pending-list entries don't have
compressed posting lists to make lossy — they're one TID per entry.

## The `recheck` flag

Two sources of recheck:

1. **Lossy page pointers** in the entry tree (compressed posting
   list overflow) → caller (BitmapHeapScan) must re-run the
   operator on every tuple of the page.
2. **`pmatch` partial-match** keys (where `comparePartialFn` could
   be approximate) → caller must re-run the operator on the
   matched tuple.

The `consistent`/`triConsistent` functions report this via the
`recheck` flag; `scanGetItem` propagates it to `tbm_add_tuples`,
which marks the bitmap entry for recheck.

The downstream `BitmapHeapScan` then re-evaluates the SQL
expression on every recheck-marked TID. GIN's lossy/recheck strategy
amounts to "the index gives you a fast filter; the heap-scan does
exact filtering."

[from-comment] (the README design overview).

## Multi-key strategies — AND vs OR

A query like `WHERE col @@ 'a' AND col @@ 'b'` could be:

- Two scan keys (`numberOfKeys == 2`), each calling `extractQuery`
  separately and returning their own entries.
- One scan key with a compound query (`'a & b'` for tsquery).

GIN handles either, but the latter is more efficient because the
opclass's consistentFn can short-circuit per-key as a tree of
boolean ops, instead of computing two TIDBitmaps and intersecting
them at the executor level.

[from README and `ginscan.c` setup code].

## Invariants and races

1. **Pending list always scanned before main index** to avoid
   missing entries that concurrent cleanup might move. Duplicates
   are okay (TIDBitmap dedups). [from-comment] (`ginget.c:1950-1958`).
2. **GIN can't support `amgettuple`** because the two-phase scan
   produces duplicates that only a TIDBitmap can dedup.
3. **`gingetbitmap` returns TIDs in sorted order per posting-list
   segment**, then merges via N-way comparison. The output to
   the TIDBitmap is in sorted order overall.
4. **Lossy posting list entries** (offset = 0xFFFF) sort after
   exact entries for the same page, ensuring we prefer exact
   pointers when both are available. [from-comment]
   (`ginget.c:1030-1034`).
5. **`triConsistentFn` returns one of**: `GIN_TRUE`, `GIN_FALSE`,
   `GIN_MAYBE`. The shim composes from a `bool consistent` by
   enumerating MAYBE combinations.
6. **`extractQueryFn` may return 0 keys** with non-default
   `searchMode` — used for full-index scans.
7. **`GinIsVoidRes(scan)`** is set when extractQueryFn returns 0
   keys with default searchMode → unsatisfiable, return 0 immediately.
8. **`isPartialMatch` entries** use `comparePartialFn` to enumerate
   matching entry-tree keys via prefix-like comparison. Used for
   `text @@ 'foo:*'` prefix queries.
9. **The `recheck` flag is propagated per-TID** to the TIDBitmap;
   BitmapHeapScan re-runs the operator on every recheck-marked TID.

## Useful greps

```bash
# Scan-time entry points:
grep -nE "^gingetbitmap|^ginNewScanKey|^startScan|^scanGetItem|^keyGetItem|^startScanEntry" \
       source/src/backend/access/gin/ginget.c \
       source/src/backend/access/gin/ginscan.c

# Tri-state plumbing:
grep -n "GinTernaryValue\|GIN_TRUE\|GIN_FALSE\|GIN_MAYBE\|triConsistentFn" \
       source/src/include/access/gin_private.h \
       source/src/backend/access/gin/ginlogic.c

# extractQueryFn callers / setup:
grep -n "extractQueryFn\|searchMode\|GIN_SEARCH_MODE_" \
       source/src/backend/access/gin/ginscan.c

# Pending-list scan:
grep -n "scanPendingInsert" source/src/backend/access/gin/

# Lossy-page pointers:
grep -n "ItemPointerIsLossyPage\|ItemPointerSetLossyPage" source/src/backend/
```

## Cross-references

- [[gin-tree-structure]] — entry tree + posting tree the scan walks.
- [[gin-fastupdate-pending]] — the pending list scanned before the main index.
- [[parallel-bitmap-heap]] — downstream consumer of `gingetbitmap`'s TIDBitmap.
- [[heap-tuple-visibility-mvcc]] — recheck path for lossy entries.
- `source/src/backend/access/gin/README` — design overview.
