# TidStore — radix-tree dead-TID accumulator with adaptive bitmap/short-list encoding

When VACUUM scans the heap, it accumulates the TIDs of dead tuples that
need to be removed from indexes. Before PG 17 this was a flat sorted
array sized to `maintenance_work_mem`; that meant a fixed-cost
`bsearch` per index probe and a hard memory cap that, when exceeded,
forced VACUUM to split the work into multiple `(scan-heap, vacuum-each-
index, vacuum-heap)` cycles.

The current implementation is **`TidStore`** (`access/common/tidstore.c`),
a radix tree keyed by `BlockNumber` with values that are either a tiny
inline array of offsets (up to `NUM_FULL_OFFSETS`) or a per-block bitmap
of offsets. The radix tree itself comes from `lib/radixtree.h` — a
generic header-template radix tree compiled twice (once for local
memory, once for DSA shared memory) using the `RT_PREFIX` macro
convention.

The win over the old flat array:

- **Compact for common workloads.** A page with ≤ `NUM_FULL_OFFSETS`
  dead tuples (~4 on 64-bit) uses no bitmap at all — the offsets fit
  inline in the entry header.
- **Dense for hot pages.** A page with many dead tuples uses a sparse
  bitmap over the page's offset range.
- **Per-block O(1)** member lookup (radix-tree find + bitmap test) vs
  O(log N) bsearch on a flat sorted array of all dead TIDs cluster-wide.
- **DSA-shared** for parallel vacuum workers — the same tree backs
  every worker's read.

This doc walks the `BlocktableEntry` two-mode encoding, the
`TidStoreSetBlockOffsets` write path (sorted-array → entry), the
`TidStoreIsMember` per-block lookup, the iterator that drives the
index-vacuum pass, and the local-vs-shared duality via the `RT_PREFIX
local_ts` / `shared_ts` template instantiations.

Companion docs:
- [[vacuum-hot-prune]] — produces the dead-TID set written here.
- [[vacuum-two-pass-heap]] — vacuumlazy.c's orchestration of TidStore usage.

## Anchors

- `source/src/backend/access/common/tidstore.c:1-21` — banner.
- `source/src/backend/access/common/tidstore.c:31-89` — `BlocktableEntry` layout + `MaxBlocktableEntrySize`.
- `source/src/backend/access/common/tidstore.c:90-111` — two `RT_PREFIX` template instantiations (`local_ts`, `shared_ts`).
- `source/src/backend/access/common/tidstore.c:113-132` — `TidStore` struct + `TidStoreIsShared` macro.
- `source/src/backend/access/common/tidstore.c:161-198` — `TidStoreCreateLocal`.
- `source/src/backend/access/common/tidstore.c:207-262` — `TidStoreCreateShared` + `TidStoreAttach`.
- `source/src/backend/access/common/tidstore.c:344-417` — `TidStoreSetBlockOffsets`.
- `source/src/backend/access/common/tidstore.c:420-459` — `TidStoreIsMember`.
- `source/src/backend/access/common/tidstore.c:470-526` — iterator (Begin/Next/End).
- `source/src/backend/access/common/tidstore.c:565-608` — `TidStoreGetBlockOffsets`.
- `source/src/include/lib/radixtree.h` — radix-tree template (read sparingly; it's a generic header).

## The two-mode entry — BlocktableEntry

```c
/* tidstore.c:31-77 */
#define NUM_FULL_OFFSETS \
    ((sizeof(uintptr_t) - sizeof(uint8) - sizeof(int8)) / sizeof(OffsetNumber))
                                                        /* = 4 on 64-bit, 2 on 32-bit */

typedef struct BlocktableEntry {
    struct {
        uint8       flags;                              /* radix-tree tag bit */
        int8        nwords;                             /* 0 = inline mode, else bitmap mode */
        OffsetNumber full_offsets[NUM_FULL_OFFSETS];    /* inline mode */
    } header;
    bitmapword  words[FLEXIBLE_ARRAY_MEMBER];           /* bitmap mode */
} BlocktableEntry;
```

The struct is two-faced:

- **Inline mode** (`nwords == 0`): up to `NUM_FULL_OFFSETS` offsets are
  stored directly in `header.full_offsets[]`. No bitmap allocated. Used
  when the page has few dead tuples — the common case.
- **Bitmap mode** (`nwords > 0`): a sparse bitmap over the page's
  offset range. `words[wordnum]` bit `BITNUM(off)` is set for each
  dead offset.

The mode flip happens at `num_offsets > NUM_FULL_OFFSETS`. On a 64-bit
build, `NUM_FULL_OFFSETS = (8 − 1 − 1) / 2 = 3`. The "useful inline
capacity" is small, but the win is the elision of the bitmap-allocation
overhead for the ~30-90% of vacuum pages with only a handful of dead
tuples. [verified-by-code] (`tidstore.c:367-411`).

`MAX_OFFSET_IN_BITMAP = min(BITS_PER_BITMAPWORD × INT8_MAX − 1,
MaxOffsetNumber)`. The `int8 nwords` field caps the bitmap size; the
arithmetic ensures we can address the full page-offset range. On
practical 8 KiB pages, `MaxOffsetNumber` is the limit. [verified-by-code]
(`tidstore.c:80-88`).

The `flags` byte in the header reserves a bit that the radix tree uses
to **tag** the value-pointer when the entry is small enough to be
**embedded** directly inside the radix-tree leaf slot (instead of being
heap-allocated and pointed to). The `RT_RUNTIME_EMBEDDABLE_VALUE` macro
controls this; see the radix-tree header. The struct layout has
endian-conditional reordering (`#ifndef WORDS_BIGENDIAN` vs `#ifdef
WORDS_BIGENDIAN`) to keep the tag-bit at the **lowest** address byte
regardless of architecture. [from-comment] (`tidstore.c:48-68`).

## Why two RT_PREFIX includes — local vs shared

`lib/radixtree.h` is a "header template": it generates inline radix-tree
implementations based on `RT_PREFIX`, `RT_SCOPE`, `RT_VALUE_TYPE`,
etc. macros. The TidStore includes it **twice**:

```c
/* tidstore.c:90-99 */
#define RT_PREFIX local_ts
#define RT_VALUE_TYPE BlocktableEntry
#define RT_VARLEN_VALUE_SIZE(page)  /* size depends on nwords */
#include "lib/radixtree.h"

/* tidstore.c:101-111 */
#define RT_PREFIX shared_ts
#define RT_SHMEM                    /* DSA-shared variant */
#define RT_VALUE_TYPE BlocktableEntry
#include "lib/radixtree.h"
```

This produces two parallel sets of static functions: `local_ts_create`,
`local_ts_set`, `local_ts_find`, `local_ts_iterate_next`, etc. — plus
the `shared_ts_*` analogues that operate on DSA-mapped memory with
internal LWLock-backed concurrency. The `TidStore` wrapper picks one of
the two via the runtime `TidStoreIsShared(ts)` check (`area != NULL`).

```c
/* tidstore.c:113-132 */
struct TidStore {
    MemoryContext rt_context;          /* for local mode only */
    union {
        local_ts_radix_tree   *local;
        shared_ts_radix_tree  *shared;
    } tree;
    dsa_area  *area;                   /* NULL for local mode */
};
#define TidStoreIsShared(ts) ((ts)->area != NULL)
```

This is the canonical PostgreSQL pattern for "same data structure,
local or shared". The two instantiations are compiled-out branches —
zero runtime overhead beyond the `TidStoreIsShared` switch.

## Construction — local vs shared

**Local**: `TidStoreCreateLocal(max_bytes, insert_only)`
(`tidstore.c:161`). Creates the `TidStore` in `CurrentMemoryContext`,
spawns a child memory context (`rt_context`) for the radix tree
allocations. The `insert_only` flag picks between
`AllocSetContextCreate` (general) and `BumpContextCreate`
(append-only, faster for the no-delete workload that vacuum has).

`max_bytes` is **not enforced internally** — it's only used to cap the
memory-context block size:

```c
/* tidstore.c:170-176 */
while (16 * maxBlockSize > max_bytes)
    maxBlockSize >>= 1;
```

The cap ensures the largest single allocation is ≤ `max_bytes / 16`,
avoiding wasteful over-allocation when the user gives a small budget.
The caller must monitor `TidStoreMemoryUsage()` against its own limit
(typically `maintenance_work_mem`). [from-comment] (`tidstore.c:151-159`).

**Shared**: `TidStoreCreateShared(max_bytes, tranche_id)`
(`tidstore.c:207`). Creates a fresh DSA area and a shared radix tree
inside it. The `max_bytes` constraint applies to the DSA segment sizing:

```c
/* tidstore.c:218-222 */
while (8 * dsa_max_size > max_bytes)
    dsa_max_size >>= 1;
```

So shared mode caps the **DSA segment** at `max_bytes / 8` — slightly
more generous than local mode because DSA segments are typically larger
units. The returned `TidStore` is in backend-local memory but points at
shared structures.

**Attach**: `TidStoreAttach(area_handle, handle)` (`tidstore.c:244`).
Parallel vacuum workers call this after the leader has constructed the
shared store. The `(area_handle, handle)` pair is the equivalent of an
on-disk "open this file" handle: passed by value, resolves to a shared
pointer. [verified-by-code] (`tidstore.c:243-262`).

## The write path — TidStoreSetBlockOffsets

```c
/* tidstore.c:344-417 (abridged) */
void TidStoreSetBlockOffsets(TidStore *ts, BlockNumber blkno,
                             OffsetNumber *offsets, int num_offsets) {
    union { char data[MaxBlocktableEntrySize];
            BlocktableEntry force_align_entry; } stack_buf;
    BlocktableEntry *page = (BlocktableEntry *) stack_buf.data;

    /* Caller invariants: offsets sorted ascending, num_offsets > 0 */
    for (i = 1; i < num_offsets; i++) Assert(offsets[i] > offsets[i-1]);

    memset(page, 0, offsetof(BlocktableEntry, words));

    if (num_offsets <= NUM_FULL_OFFSETS) {
        for (i = 0; i < num_offsets; i++) {
            if (off == InvalidOffsetNumber || off > MAX_OFFSET_IN_BITMAP)
                elog(ERROR, "tuple offset out of range");
            page->header.full_offsets[i] = offsets[i];
        }
        page->header.nwords = 0;       /* inline mode */
    } else {
        /* bitmap mode: build dense bitmap from sorted offsets */
        for (wordnum = 0; wordnum <= WORDNUM(offsets[last]); wordnum++) {
            word = 0;
            while (idx < num_offsets && offsets[idx] < next_threshold) {
                word |= (1ULL << BITNUM(offsets[idx]));
                idx++;
            }
            page->words[wordnum] = word;
        }
        page->header.nwords = wordnum;
    }

    if (TidStoreIsShared(ts))
        shared_ts_set(ts->tree.shared, blkno, page);
    else
        local_ts_set(ts->tree.local, blkno, page);
}
```

Three properties pushed onto the caller (per the "designed for vacuum"
comment, `tidstore.c:336-343`):

1. **`offsets` sorted ascending** — enables the single-pass bitmap
   build and the bsearch-free inline-mode comparisons.
2. **Whole-block replacement** — there is no "add a TID to an existing
   block." If a block already has an entry, the new call replaces it.
   This matches vacuum's heap-pass-1 idiom: every page's dead TIDs are
   discovered together in `lazy_scan_prune` and written in one go.
3. **`num_offsets > 0`** — empty blocks are not stored; the radix tree
   should have no entry for blocks with zero dead tuples.

The stack-allocated `BlocktableEntry` buffer (sized to
`MaxBlocktableEntrySize`) is the source data; the radix tree's
`*_ts_set` function copies it into tree-managed storage. The union
trick (`force_align_entry`) ensures correct alignment of the entry
within the byte array. [verified-by-code] (`tidstore.c:348-353`).

## The lookup path — TidStoreIsMember

```c
/* tidstore.c:420-459 */
bool TidStoreIsMember(TidStore *ts, const ItemPointerData *tid) {
    BlockNumber  blk = ItemPointerGetBlockNumber(tid);
    OffsetNumber off = ItemPointerGetOffsetNumber(tid);

    page = TidStoreIsShared(ts)
         ? shared_ts_find(ts->tree.shared, blk)
         : local_ts_find(ts->tree.local, blk);

    if (page == NULL) return false;     /* block not dead at all */

    if (page->header.nwords == 0) {
        for (i = 0; i < NUM_FULL_OFFSETS; i++)
            if (page->header.full_offsets[i] == off)
                return true;
        return false;
    } else {
        wordnum = WORDNUM(off);
        if (wordnum >= page->header.nwords) return false;
        return (page->words[wordnum] & (1ULL << BITNUM(off))) != 0;
    }
}
```

This is the function index vacuum hammers — every index entry is
checked against the dead-TID set. The fast paths:

1. Radix-tree find by BlockNumber → O(log K) where K is the number of
   blocks with dead tuples (much smaller than the heap).
2. If `nwords == 0` → linear scan of up to `NUM_FULL_OFFSETS` (3-4).
3. Else → one bitmap-word load + bit-test.

The "block not dead at all" early return (radix-tree miss) is the
dominant case for any non-bloated relation. [verified-by-code]
(`tidstore.c:435-436`).

## Iteration — driving the index-vacuum pass

`TidStoreBeginIterate` (`tidstore.c:471`) + `TidStoreIterateNext`
(`tidstore.c:493`) walk the dead blocks. Vacuum's index-cleanup pass
isn't a TID-by-TID iteration — it's a **page-by-page** sweep
controlled by the index AM (`amvacuumcleanup` / `ambulkdelete`), which
gets the `TidStore` as a member-test oracle.

But certain code paths do walk the store directly to enumerate dead
TIDs (e.g. heap pass 2 reading the offset list per block to apply
LP_DEAD → LP_UNUSED transitions):

```c
iter = TidStoreBeginIterate(ts);
while ((result = TidStoreIterateNext(iter)) != NULL) {
    blkno = result->blkno;
    n = TidStoreGetBlockOffsets(result, offsets_buf, max_offsets);
    /* process blkno + offsets_buf[0..n) */
}
TidStoreEndIterate(iter);
```

The locking responsibility is **on the caller**: "The caller is
responsible for locking TidStore until the iteration is finished." For
shared mode this means `TidStoreLockShare(ts)` around the iterator;
for local mode no locking is needed because the store is per-process.
[from-comment] (`tidstore.c:466-468`).

`TidStoreGetBlockOffsets` (`tidstore.c:566`) converts a single block's
entry back to a sorted offset array. Returns the count if it fits in
`max_offsets`; otherwise returns the required size for caller to
re-attempt with a larger buffer. The iteration order matches the
radix tree's natural key order, i.e. ascending `BlockNumber`. The bit
sweep within a block is also ascending (low-order bits first), so the
output offsets are sorted. [verified-by-code] (`tidstore.c:570-608`).

## Locking — radix-tree-internal

```c
/* tidstore.c:286-305 */
void TidStoreLockExclusive(TidStore *ts) {
    if (TidStoreIsShared(ts))
        shared_ts_lock_exclusive(ts->tree.shared);
}
void TidStoreLockShare(TidStore *ts) {
    if (TidStoreIsShared(ts))
        shared_ts_lock_share(ts->tree.shared);
}
void TidStoreUnlock(TidStore *ts) {
    if (TidStoreIsShared(ts))
        shared_ts_unlock(ts->tree.shared);
}
```

Local mode has no lock. Shared mode uses **one LWLock** internal to the
radix tree (allocated in the `tranche_id` passed at create), regardless
of the number of blocks. The expectation: vacuum's parallel workers
batch their dead-TID inserts (per-page, not per-tuple) and contention
is acceptable. Inserts under exclusive lock; iteration / `IsMember`
under share lock. [from-comment] (`tidstore.c:281-284`).

Insert-only callers (vacuum's heap-pass-1) only ever exclusive-lock;
the lookup-heavy index-pass-2 only ever share-locks. The two phases
don't overlap in vacuum.

## Memory usage and the maintenance_work_mem cap

`TidStoreMemoryUsage(ts)` returns the current bytes consumed by the
radix tree (`tidstore.c:531-538`). Vacuum's main loop monitors this
against `maintenance_work_mem`:

```c
/* From vacuumlazy.c (paraphrased) */
while (heap_block_remaining(...)) {
    lazy_scan_heap_block(...);                  /* fills TidStore */
    if (TidStoreMemoryUsage(vacrel->dead_items) > maintenance_work_mem) {
        lazy_vacuum_all_indexes(vacrel);         /* drain the store */
        lazy_vacuum_heap(vacrel);
        TidStoreReset(...);                      /* (recreate) */
    }
}
```

This is the **spill loop** — when memory exhausts, vacuum drains the
store via the two-pass index/heap cleanup, then resumes the heap scan.
Pre-PG-17 this was based on a flat-array fill ratio; now it's the
radix tree's actual memory footprint, which is much more accurate
because the radix tree compacts sparse blocks. See
[[vacuum-two-pass-heap]] for the full orchestration.

## Invariants and races

1. **Sorted ascending input** to `TidStoreSetBlockOffsets`. The
   assertion runs in every build; the bitmap-build code assumes it
   for the single-pass bitmap fill. [verified-by-code]
   (`tidstore.c:361-363`).
2. **No "add to existing block"** — the write is whole-page replacement.
   Vacuum produces all dead offsets for a page in one
   `lazy_scan_prune` call, so this is fine.
3. **`InvalidOffsetNumber` (= 0) is rejected** with an explicit
   `elog(ERROR)`. The bitmap uses 1-indexed offsets (bit 0 is
   InvalidOffset and is reserved). [verified-by-code]
   (`tidstore.c:373-375`, `tidstore.c:393-395`).
4. **Inline mode flips to bitmap mode at `NUM_FULL_OFFSETS + 1`** — no
   intermediate hybrid. The transition is symmetric: `IsMember` and
   `GetBlockOffsets` both read `nwords == 0` as inline.
5. **Shared mode requires `tranche_id` for the internal LWLock**. The
   tranche must be registered (e.g.
   `LWLockRegisterTranche(LWTRANCHE_PARALLEL_VACUUM_DSA)`).
   [verified-by-code] (`tidstore.c:230-231`).
6. **`TidStoreDestroy` must be called by exactly one backend** —
   others call `TidStoreDetach`. "The backend that calls
   TidStoreDestroy() must not call TidStoreDetach()." [from-comment]
   (`tidstore.c:309-314`).
7. **Locking is the caller's responsibility** for shared mode. The
   `TidStoreLock*` API is thin pass-through to the radix tree's
   internal lock. [from-comment] (`tidstore.c:280-284`).

## Useful greps

```bash
# Every TidStore API entry point:
grep -nE "^[a-z]+ ?\*?$|^TidStore[A-Z]" \
       source/src/backend/access/common/tidstore.c

# Callers (lazy vacuum, parallel vacuum, bitmap heap scan):
grep -rn "TidStoreCreate\|TidStoreSetBlockOffsets\|TidStoreIsMember\|TidStoreMemoryUsage" \
       source/src/backend/ | head -30

# The radix-tree template internals:
grep -n "RT_PREFIX\|RT_VALUE_TYPE\|RT_VARLEN_VALUE_SIZE\|RT_RUNTIME_EMBEDDABLE_VALUE" \
       source/src/include/lib/radixtree.h | head -20

# DSA segment sizing:
grep -nE "DSA_DEFAULT_INIT_SEGMENT_SIZE|DSA_MAX_SEGMENT_SIZE|DSA_MIN_SEGMENT_SIZE" \
       source/src/include/utils/dsa.h
```



## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/access/common/tidstore.c`](../files/src/backend/access/common/tidstore.c.md) | 1 | banner |
| [`src/backend/access/common/tidstore.c`](../files/src/backend/access/common/tidstore.c.md) | 31 | BlocktableEntry layout + MaxBlocktableEntrySize |
| [`src/backend/access/common/tidstore.c`](../files/src/backend/access/common/tidstore.c.md) | 90 | two RT_PREFIX template instantiations (local_ts, shared_ts) |
| [`src/backend/access/common/tidstore.c`](../files/src/backend/access/common/tidstore.c.md) | 113 | TidStore struct + TidStoreIsShared macro |
| [`src/backend/access/common/tidstore.c`](../files/src/backend/access/common/tidstore.c.md) | 161 | TidStoreCreateLocal |
| [`src/backend/access/common/tidstore.c`](../files/src/backend/access/common/tidstore.c.md) | 207 | TidStoreCreateShared + TidStoreAttach |
| [`src/backend/access/common/tidstore.c`](../files/src/backend/access/common/tidstore.c.md) | 344 | TidStoreSetBlockOffsets |
| [`src/backend/access/common/tidstore.c`](../files/src/backend/access/common/tidstore.c.md) | 420 | TidStoreIsMember |
| [`src/backend/access/common/tidstore.c`](../files/src/backend/access/common/tidstore.c.md) | 470 | iterator (Begin/Next/End) |
| [`src/backend/access/common/tidstore.c`](../files/src/backend/access/common/tidstore.c.md) | 565 | TidStoreGetBlockOffsets |
| [`src/include/lib/radixtree.h`](../files/src/include/lib/radixtree.h.md) | — | radix-tree template (read sparingly; it's a generic header) |

<!-- /callsites:auto -->



## Scenarios that use me
<!-- scenarios:auto -->

*Auto-derived from direct references + transitive file-overlap.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

_(none detected — this idiom is either cross-cutting infrastructure or an internal helper pattern)_

<!-- /scenarios:auto -->

## Cross-references

- [[vacuum-hot-prune]] — heap-pass-1 produces the sorted offset list `TidStoreSetBlockOffsets` consumes.
- [[vacuum-two-pass-heap]] — vacuumlazy.c's three-pass loop; the maintenance_work_mem spill is implemented around this store.
- `knowledge/subsystems/storage-buffer.md` §"DSA areas" — DSA primitives behind `TidStoreCreateShared`.
- `source/src/include/lib/radixtree.h` — radix-tree template header.
