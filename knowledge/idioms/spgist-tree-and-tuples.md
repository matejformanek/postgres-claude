# SP-GiST — tree shape and tuple formats

SP-GiST (Space-Partitioned GiST) is the access-method scaffold for
**non-balanced** disk-resident search trees: quadtrees, k-d trees, and
radix tries.  The opclass picks the partitioning rule (centroid /
coordinate / prefix string); the core supplies page layout, the four
tuple states, and the lock protocol.  This doc is the **shape** half:
how pages are laid out, the inner/leaf/node/dead structs, and what
the four `tupstate` codes mean.  The dynamic half — insert flow,
PickSplit, scan traversal — lives in [[spgist-insert-and-picksplit]]
and [[spgist-scan-and-consistent]].

**Anchors** (all cites against `source/` at commit `e18b0cb7344`):
- `source/src/backend/access/spgist/README` — authoritative algorithm doc
- `source/src/include/access/spgist_private.h` — every struct in this doc
- `source/src/backend/access/spgist/spgdoinsert.c` — insert side using these tuples
- `source/src/backend/access/spgist/spgscan.c` — scan side using these tuples

## Big picture: where the data lives

An SP-GiST index has **two disjoint sub-trees** sharing the same file:

| Block | Role |
|---|---|
| 0 | metapage — magic, last-used-page cache |
| 1 | root of **main tree** (non-null entries) |
| 2 | root of **nulls tree** (null entries) |

The fixed-location BlockNumbers and the `SpGistBlockIsRoot` /
`SpGistBlockIsFixed` macros are at
`source/src/include/access/spgist_private.h:47-55`
[verified-by-code]:

```c
#define SPGIST_METAPAGE_BLKNO    (0)
#define SPGIST_ROOT_BLKNO        (1)
#define SPGIST_NULL_BLKNO        (2)
```

Null entries get their own tree so opclass authors never have to
think about NULL in their `choose` / `picksplit` /
`inner_consistent` / `leaf_consistent` callbacks; the README says it
plainly at lines 92-103: *"the main tree of an SPGiST index does
not include any null entries… Insertions and searches in the nulls
tree do not use any of the opclass-supplied functions, but just use
hardwired logic"*  [from-README].

Inside each tree, every non-fixed page is **either** an inner page
**or** a leaf page — never mixed.  The `SPGIST_LEAF` and
`SPGIST_NULLS` flags in the page-opaque area (`spgist_private.h:71-76`)
[verified-by-code] tag which kind:

```c
#define SPGIST_META           (1<<0)
#define SPGIST_DELETED        (1<<1)  /* never set; back-compat */
#define SPGIST_LEAF           (1<<2)
#define SPGIST_NULLS          (1<<3)
```

Asymmetry to remember: the root **can** be a leaf, briefly.  Early
in an index's life, before the first PickSplit, the root page holds
an unorganized soup of leaf tuples; after the first split, the rule
is *"the root is required to contain exactly one inner tuple"*
(README §COMMON STRUCTURE DESCRIPTION) [from-README].  That single
inner tuple is the topmost partitioning of the search space.

## Page opaque — what's at the end of every page

`SpGistPageOpaqueData` lives in the page's special-space tail
(`spgist_private.h:60-67`) [verified-by-code]:

```c
typedef struct SpGistPageOpaqueData
{
    uint16  flags;            /* META / LEAF / NULLS / DELETED */
    uint16  nRedirection;     /* REDIRECT tuples on page */
    uint16  nPlaceholder;     /* PLACEHOLDER tuples on page */
    /* note there's no count of either LIVE or DEAD tuples ... */
    uint16  spgist_page_id;   /* 0xFF82, for pg_filedump */
} SpGistPageOpaqueData;
```

The `nRedirection` and `nPlaceholder` counts let VACUUM and the
free-space-recycle code decide quickly whether a sweep would be
productive.  There is no live-tuple count because the offset
machinery (live, dead, placeholder, redirect all use line pointers)
already tells you that by walking item IDs.  The `spgist_page_id`
trailer matches GIN/BRIN's convention — pg_filedump uses it to
distinguish index file types  [from-comment].

The capacity macro at `spgist_private.h:450-453` [verified-by-code]
is what the insertion path checks against before failing the
"row too large for index" error:

```c
#define SPGIST_PAGE_CAPACITY  \
    MAXALIGN_DOWN(BLCKSZ -    \
                  SizeOfPageHeaderData -    \
                  MAXALIGN(sizeof(SpGistPageOpaqueData)))
```

`SpGistPageGetFreeSpace(p, n)` (`spgist_private.h:459-462`) is the
**realistic** free-space measurement — it includes up to `n`
recyclable PLACEHOLDER slots, because a fresh insert can overwrite
a placeholder in-place without growing the page  [verified-by-code].

## Inner tuple — branches with optional prefix and an array of nodes

The inner tuple at `spgist_private.h:295-304` [verified-by-code]:

```c
typedef struct SpGistInnerTupleData
{
    unsigned int tupstate:2,    /* LIVE/REDIRECT/DEAD/PLACEHOLDER */
                 allTheSame:1,  /* all nodes equivalent */
                 nNodes:13,     /* up to 8191 children */
                 prefixSize:16; /* size of prefix, or 0 if none */
    uint16       size;          /* total size of inner tuple */
    /* prefix datum follows, then nodes */
} SpGistInnerTupleData;
```

Three things fit in the bit-packed header word:

- **`tupstate`** — same 2-bit code as leaf tuples; LIVE is the
  steady state, the other three are the dead-tuple alphabet
  described below.
- **`allTheSame`** — set when the opclass `picksplit` couldn't
  partition; every node label is equivalent and `choose` must
  return `spgMatchNode` (the doinsert code Asserts this at
  `spgdoinsert.c:2199-2212`) [verified-by-code].
- **`nNodes` (13 bits)** — cap of 8191 children per inner tuple
  (`SGITMAXNNODES = 0x1FFF`, `spgist_private.h:309`)
  [verified-by-code].  Radix-tree opclasses lean on this; quad/k-d
  trees use a single-digit fan-out.

The layout after the header is **prefix-then-nodes** — the
`SGITDATAPTR(x)` and `SGITNODEPTR(x)` macros at
`spgist_private.h:315-321` [verified-by-code] reflect that:

```c
#define _SGITDATA(x)        (((char *) (x)) + SGITHDRSZ)
#define SGITDATAPTR(x)      ((x)->prefixSize ? _SGITDATA(x) : NULL)
#define SGITNODEPTR(x)      ((SpGistNodeTuple) (_SGITDATA(x) + (x)->prefixSize))
```

To iterate the nodes you use `SGITITERATE(x, i, nt)`
(`spgist_private.h:324-327`) [verified-by-code] — the next-pointer
walk is `nt = nt + IndexTupleSize(nt)` because each `SpGistNodeTuple`
is variable-length.

### The prefix-as-Datum quirk

Pass-by-value prefix datums are stored in their full `Datum`-width
on-disk representation (8 bytes on 64-bit, 4 bytes on 32-bit), not
in a per-type-size form.  The comment at
`spgist_private.h:284-294` [from-comment] flags this as historical:
*"This is a fairly unfortunate choice, because in no other place
does Postgres use Datum as an on-disk representation… Going
forward, we will be using a fixed size of Datum so that there's no
longer any pressing reason to change this."*  Practical impact: the
hazard for binary upgrades on 32-bit builds is theoretical for the
opclasses shipped in core.

## Node tuple — one entry in the inner tuple's node array

Each node inside an inner tuple is itself a tuple — header plus
optional label — reusing the `IndexTupleData` layout
(`spgist_private.h:338-346`) [verified-by-code]:

```c
typedef IndexTupleData SpGistNodeTupleData;

#define SGNTDATAPTR(x)      (((char *) (x)) + SGNTHDRSZ)
#define SGNTDATUM(x, s)     ((s)->attLabelType.attbyval ? \
                             *(Datum *) SGNTDATAPTR(x) : \
                             PointerGetDatum(SGNTDATAPTR(x)))
```

The node's `t_tid` carries the **downlink** to the child — either
an inner tuple's (block, offset) on an inner page, or the head of
a leaf-tuple chain on a leaf page.  The `INDEX_NULL_MASK` bit in
the node's `t_info` flags a NIL pointer (no child yet); the README
covers this at lines 204-210 — when descending, if the picked node
has a NIL downlink, the insertion code allocates a fresh leaf page
from the LUP cache  [from-README].

Why no nulls bitmap on a node tuple?  *"we know there is only one
column so the INDEX_NULL_MASK bit suffices"*
(`spgist_private.h:331-335`) [from-comment].

## Leaf tuple — heap pointer plus indexed value

The leaf tuple at `spgist_private.h:385-394` [verified-by-code]:

```c
typedef struct SpGistLeafTupleData
{
    unsigned int tupstate:2,    /* LIVE/REDIRECT/DEAD/PLACEHOLDER */
                 size:30;
    uint16       t_info;        /* nextOffset (14 bits) + flag bits */
    ItemPointerData heapPtr;    /* heap tuple TID */
    /* nulls bitmap follows if t_info has-nulls flag is set */
    /* leaf datum + INCLUDE datums follow on MAXALIGN boundary */
} SpGistLeafTupleData;
```

The fields that matter when reading code:

| Field | Width | Meaning |
|---|---|---|
| `tupstate` | 2 bits | shared with inner tuples — same alphabet |
| `size` | 30 bits | total tuple size; *much* wider than needed because the in-memory form is used during build  [from-comment, lines 367-371] |
| `t_info` low 14 bits | nextOffset of next tuple in same-parent chain |
| `t_info` bit 15 | has-nulls-bitmap flag |
| `t_info` bit 14 | reserved, free |
| `heapPtr` | 6 bytes | TID of the heap tuple |

The `nextOffset` chain is **per-page only** — README §COMMON
STRUCTURE DESCRIPTION line 28-31 *"the list of leaf tuples reached
from a single inner-tuple node all be stored on the same page…
allows the list links to be stored as simple 2-byte
OffsetNumbers"*  [from-README].  When you arrive at a leaf chain,
you walk `SGLT_GET_NEXTOFFSET(tup)` (`spgist_private.h:397-398`)
[verified-by-code] until it returns `InvalidOffsetNumber`.

The accessor macros `SGLT_GET_NEXTOFFSET` /
`SGLT_GET_HASNULLMASK` and their setters at
`spgist_private.h:397-406` [verified-by-code] do the bit-fiddling
in one place; you should not access `t_info` directly anywhere
else.  Constants:

- `0x3FFF` — 14-bit mask for nextOffset.
- `0x8000` — has-nulls flag bit (bit 15).
- `0xC000` — both flags, used by `SGLT_SET_NEXTOFFSET` to preserve
  flag bits when overwriting offset.

### The nulls-bitmap-only-with-INCLUDE quirk

The bitmap appears *"only if there are null values (among the leaf
value and the INCLUDE values) **and** there is at least one
INCLUDE column"* (README §COMMON STRUCTURE DESCRIPTION lines
83-89) [from-README].  Rationale: a null leaf value alone can be
inferred from "is this tuple on a nulls page?" (block 2's tree),
so a bitmap for that case would be redundant.

## Dead tuple — REDIRECT / DEAD / PLACEHOLDER share a struct

The four `tupstate` codes from `spgist_private.h:272-275`
[verified-by-code]:

```c
#define SPGIST_LIVE         0    /* normal */
#define SPGIST_REDIRECT     1    /* points elsewhere */
#define SPGIST_DEAD         2    /* dead but cannot be removed */
#define SPGIST_PLACEHOLDER  3    /* dead with no incoming links */
```

The three non-LIVE states share a single struct
(`spgist_private.h:429-436`) [verified-by-code]:

```c
typedef struct SpGistDeadTupleData
{
    unsigned int tupstate:2,
                 size:30;
    uint16       t_info;        /* unused, alignment padding */
    ItemPointerData pointer;    /* redirect target (REDIRECT only) */
    TransactionId xid;          /* inserter XID (REDIRECT only) */
} SpGistDeadTupleData;
```

`size`, `tupstate`, and `t_info` are in the same positions as a
leaf tuple, and `pointer` is in the same position as `heapPtr` —
the comment at `spgist_private.h:418-428` [from-comment] explains
why: *"Also, the pointer field must be in the same place as a
leaf tuple's heapPtr field, to satisfy some Asserts that we make
when replacing a leaf tuple with a dead tuple."*  So upgrading a
leaf tuple to a dead tuple is an in-place overwrite; the line
pointer's offset and length don't change.

### The four states in plain English

These match the README §DEAD TUPLES discussion (lines 269-318)
[from-README]:

- **LIVE (0)** — the steady state.  Inner-tuple `LIVE` means the
  tuple has live downlinks; leaf-tuple `LIVE` means the heap TID is
  current.
- **REDIRECT (1)** — *"placeholder that contains a link to another
  place in the index"*.  Set when a chain of leaf tuples (or an
  inner tuple) moved to a different page because PickSplit or
  MoveLeafs needed the space.  The parent inner tuple's downlink
  is updated atomically, but **share-locked scans may already be
  in flight** from the parent to the old location; the REDIRECT
  tells them where to follow up.  VACUUM converts it to
  PLACEHOLDER once all old transactions have drained.
- **DEAD (2)** — *"tuple is dead, but it cannot be removed or
  moved to a different offset on the page because there is a link
  leading to it"*.  Only on leaf pages; happens when VACUUM kills
  every entry in a leaf chain but the parent inner-tuple downlink
  is still pointing at the chain head.  Searches ignore; insertions
  may overwrite in place.
- **PLACEHOLDER (3)** — *"tuple is dead, and there are known to
  be no links to it from elsewhere"*.  Free for replacement on the
  next insert; trailing placeholders at the end of the page are
  garbage-collected by VACUUM.

The opaque-area counters `nRedirection` and `nPlaceholder` exist
precisely to track these two recyclable categories — code that
needs free space queries `SpGistPageGetFreeSpace(page, n)` which
adds back up to `n` recyclable PLACEHOLDER slots.

### Which states are legal where

| Page kind | LIVE | REDIRECT | DEAD | PLACEHOLDER |
|---|---|---|---|---|
| Inner page | ✓ | ✓ | not possible (VACUUM doesn't remove inner tuples) | ✓ |
| Leaf page (non-root) | ✓ | ✓ | ✓ | ✓ |
| Root page while it's still a leaf | ✓ only | — | — | — |

Sources: README §DEAD TUPLES lines 308-318 + `spgdoinsert.c`
asserts.  When a search arrives at an unexpected state code at
`spgscan.c:793` [verified-by-code], the code elogs *"unexpected
SPGiST tuple state: %d"* — it should genuinely never happen.

## Triple-parity rule — what makes deadlocks unlikely

The README §CONCURRENCY (lines 234-244) [from-README] explains a
trick the insertion path uses to keep deadlocks rare without paying
for deterministic global ordering:

> if inner tuple is on page with BlockNumber N, then its child
> tuples should be placed on the same page, or else on a page
> with BlockNumber M where (N+1) mod 3 == M mod 3.

The implementation lives in the `GBUF_INNER_PARITY` macro at
`spgist_private.h:485-491` [verified-by-code]:

```c
#define GBUF_LEAF               0x03
#define GBUF_INNER_PARITY(x)    ((x) % 3)
#define GBUF_NULLS              0x04
```

Three "parity groups" of inner pages (mod 3), one separate "leaf"
slot, and the `GBUF_NULLS` orthogonal flag give the
`SpGistGetBuffer` function its 8-slot working set — which lines up
exactly with the `SPGIST_CACHED_PAGES = 8` (`spgist_private.h:106`)
[verified-by-code] in the per-backend last-used-page cache:

```c
typedef struct SpGistLUPCache
{
    SpGistLastUsedPage cachedPage[SPGIST_CACHED_PAGES];
} SpGistLUPCache;
```

Why three?  *"this rule ensures that tuples on page M will have
no children on page N, since (M+1) mod 3 != N mod 3"*
(README §CONCURRENCY) [from-README].  It's not a deadlock-free
proof — three-way deadlocks are still possible — but combined
with conditional locking (release both buffers and restart if you
can't get the child lock; `spgdoinsert.c:2081-2087`)
[verified-by-code] it's cheap and Good Enough.

## Last-used-page cache — why insert rarely hits SpGistNewBuffer

`SpGistLastUsedPage` at `spgist_private.h:99-103` [verified-by-code]:

```c
typedef struct SpGistLastUsedPage
{
    BlockNumber blkno;       /* InvalidBlockNumber if not set */
    int         freeSpace;   /* could be stale! */
} SpGistLastUsedPage;
```

The cache is **per-backend** in `index->rd_amcache`
(README §LAST USED PAGE MANAGEMENT, lines 376-383)
[from-README].  It's seeded from the metapage on first use and
written back occasionally; updates to the on-disk copy are **not
WAL-logged** because the data is hint-quality — picking a
sub-optimal page never produces a wrong index, just wastes a
little space.  The slot count of 8 lines up with the
`GBUF_INNER_PARITY × 3 + GBUF_LEAF + GBUF_NULLS` working set so
each "kind of page I might want" gets one cached slot per tree.

## Reading the per-scan opaque

The scan path (covered in [[spgist-scan-and-consistent]]) uses
`SpGistScanOpaqueData` at `spgist_private.h:189-243`
[verified-by-code].  Fields worth knowing on first read:

| Field | Role |
|---|---|
| `scanQueue` | pairing-heap of `SpGistSearchItem` — used as a stack for plain scans, as a priority queue (closest-first) for KNN |
| `tempCxt` / `traversalCxt` | per-tuple-test and per-scan memory contexts; opclass callbacks allocate in `tempCxt` and the scan walker resets it after each item |
| `searchNulls` / `searchNonNulls` | extracted from the IS NULL / IS NOT NULL clauses by `spgPrepareScanKeys` |
| `innerConsistentFn` / `leafConsistentFn` | cached `FmgrInfo` for the opclass-provided consistent functions |
| `recheck[]` / `recheckDistances[]` | one per leaf TID buffered for `amgettuple`; bitmap scans use the `tbm` field instead |

The two memory contexts are the place to look first when reading a
new opclass `consistent` implementation: anything allocated in
`tempCxt` is freed before the next inner/leaf test; anything that
must survive into the next inner-step (a reconstructed value, a
traversal value carrying e.g. a quadrant's bounding box) must be
copied into `traversalCxt`.

## Invariants worth remembering

These should hold at every quiescent point; violating any of them
in your reading of code means you've gotten lost.

1. **Block 1 is the root of the main tree; block 2 is the root of
   the nulls tree.**  Search always starts at one of these
   depending on whether the qual has a non-null arm.
2. **Inner pages and leaf pages never mix tuples.**  Once a page
   has the `SPGIST_LEAF` flag set it stays a leaf for life.
3. **The root is exceptional: it may be a leaf early on, but only
   one inner tuple after the first split.**  README §INSERTION
   ALGORITHM note (1).
4. **Leaf tuples in one chain are on one page.**  This is a
   hard rule — `nextOffset` is 14 bits because it's an
   OffsetNumber, not a TID.
5. **An inner tuple's `nNodes` fits in 13 bits.**  Opclasses
   that want millions of children would have to invent their own
   chaining — quad/k-d/radix trees stay well below 8191.
6. **An inner-tuple node with NIL `t_tid` means "no child yet" —
   the insert path picks a leaf page from the LUP cache and
   writes the link back.**
7. **REDIRECT and PLACEHOLDER counters in the page opaque are
   authoritative.**  Code that re-derives them by scanning the
   page is testing the invariant; it doesn't get to disagree.
8. **The `tupstate` byte at the start of a dead tuple is in the
   same position as the leaf-tuple's `tupstate`** — so a single
   `tupstate` check at the top of any tuple handler is safe.
9. **Pass-by-value prefix and label datums are stored as
   on-disk `Datum`-width words.**  Don't try to use the catalog
   type's size to skip ahead — use the macros.
10. **The nulls tree is searched without calling any
    opclass-supplied function.**  If you're debugging a hang in a
    `consistent` callback, that callback never runs against a
    nulls-tree page.

## Useful greps

Reproducible navigation, all relative to the worktree root with
`source/` linked to the upstream tree:

```bash
# Every tuple-state code in one place
grep -n "SPGIST_LIVE\|SPGIST_REDIRECT\|SPGIST_DEAD\|SPGIST_PLACEHOLDER" \
    source/src/include/access/spgist_private.h

# Page-opaque accessors
grep -n "SpGistPageGetOpaque\|SpGistPageIsLeaf\|SpGistPageStoresNulls" \
    source/src/include/access/spgist_private.h

# Inner-tuple iteration macro
grep -n "SGITITERATE\|SGITNODEPTR\|SGITDATUM" \
    source/src/include/access/spgist_private.h

# Triple-parity in action
grep -rn "GBUF_INNER_PARITY\|GBUF_LEAF\|GBUF_NULLS" source/src/backend/access/spgist/

# Where the README rules become asserts
grep -n "elog(ERROR, \"unexpected SPGiST tuple state" \
    source/src/backend/access/spgist/*.c
```



## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/access/spgist/spgdoinsert.c`](../files/src/backend/access/spgist/spgdoinsert.c.md) | — | insert side using these tuples |
| [`src/backend/access/spgist/spgscan.c`](../files/src/backend/access/spgist/spgscan.c.md) | — | scan side using these tuples |
| [`src/include/access/spgist_private.h`](../files/src/include/access/spgist_private.h.md) | 47 | 55 |
| [`src/include/access/spgist_private.h`](../files/src/include/access/spgist_private.h.md) | — | every struct in this doc |

<!-- /callsites:auto -->

## Cross-references

- [[spgist-insert-and-picksplit]] — how `spgdoinsert` consumes these
  tuples (choose → MatchNode / AddNode / SplitTuple → PickSplit).
- [[spgist-scan-and-consistent]] — the scan side: `spgWalk`
  pairing-heap, `inner_consistent` and `leaf_consistent`
  dispatch, KNN closest-first traversal.
- [[gin-tree-structure]] — for contrast, GIN's posting-tree layout
  reuses `IndexTupleData` slots in a different pattern (`t_tid`
  abuse).
- [[brin-revmap]] — another AM that ties block-number arithmetic
  to a fixed metapage layout.
- [[buffer-manager]] — `LockBuffer(... BUFFER_LOCK_EXCLUSIVE)` and
  the conditional-locking idiom used by the insertion path.
- [[memory-contexts]] — `tempCxt` reset-per-iteration and
  `traversalCxt` long-lived pattern.
