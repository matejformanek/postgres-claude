# `src/backend/utils/mmgr/freepage.c`

- **File:** `source/src/backend/utils/mmgr/freepage.c` (1886 lines)
- **Header:** `source/src/include/utils/freepage.h`
- **Last verified commit:** `ef6a95c7c64de07dff4dd1f1da88ffae7b086ef3` (2026-06-01)

## Purpose

Per-segment page allocator used inside `dsa.c`. A `FreePageManager`
tracks runs of free 4 KB pages (`FPM_PAGE_SIZE`) within some region of
memory it was given. It can *only* allocate and free in whole pages,
and the caller must pass the *length* (in pages) of an allocation when
freeing it. The bookkeeping lives **inside the pages it manages** (it
has no underlying allocator) and consists of (a) size-binned freelists
of run-leaders, threaded through the first page of each run, and
(b) an in-memory btree keyed by page number, used to coalesce adjacent
free runs on `Put`. When the btree is trivial (one free range) it
collapses into the `FreePageManager` proper.

## Top-of-file comment (verbatim, key paragraphs)

```
The intention of this code is to provide infrastructure for memory
allocators written specifically for PostgreSQL.  At least in the case
of dynamic shared memory, we can't simply use malloc() or even
relatively thin wrappers like palloc() which sit on top of it, because
no allocator built into the operating system will deal with relative
pointers.

A FreePageManager keeps track of which 4kB pages of memory are currently
unused from the point of view of some higher-level memory allocator.
Unlike a user-facing allocator such as palloc(), a FreePageManager can
only allocate and free in units of whole pages, and freeing an
allocation can only be done given knowledge of its length in pages.

Since a free page manager has only a fixed amount of dedicated memory,
and since there is no underlying allocator, it uses the free pages
it is given to manage to store its bookkeeping data.

To avoid memory fragmentation, it's important to consolidate adjacent
spans of pages whenever possible ... we maintain an in-memory btree of
free page ranges ordered by page number.  If a range being freed
precedes or follows a range that is already free, the existing range
is extended; if it exactly bridges the gap between free ranges, then
the two existing ranges are consolidated with the newly-freed range to
form one great big range of free pages.
```
(`freepage.c:6-43` [from-comment])

## Public surface

- `FreePageManagerInitialize(FreePageManager *fpm, char *base)` (`:183`)
  — init an FPM in caller-provided memory; `base` is the start of the
  page region under management.
- `FreePageManagerGet(FreePageManager *fpm, Size npages,
  Size *first_page) → bool` (`:210`) — pop a run of `npages`
  consecutive pages from any freelist that has one large enough;
  returns the page index (relative to `base`) and decrements the run.
- `FreePageManagerPut(FreePageManager *fpm, Size first_page,
  Size npages)` (`:379`) — return a run of pages; coalesces with
  neighbors via the btree.
- `FreePageManagerDump(FreePageManager *fpm) → char *` (`:424`) —
  debugging dump as palloc'd string.

## Key data structures

- `FreePageManager` (declared in `freepage.h`) — embedded in caller
  memory; contains the freelist heads (relative pointers via
  `RelptrFreePageSpanLeader`), a self-relative `RelptrFreePageBtree`
  root, and a "single span fast path" when the entire free space is
  one contiguous run (see top-of-file comment `:39-43`).
- `FreePageSpanLeader` (`:68-74`) — header at the start of a free page
  run: magic, `npages`, prev/next-in-freelist relptrs.
- `FreePageBtreeHeader`, `FreePageBtreeInternalKey`,
  `FreePageBtreeLeafKey` (`:76-97`) — the in-place btree. Leaf keys
  are `(first_page, npages)` records ordered by `first_page`; internal
  keys are `(first_page-lower-bound, child-relptr)` pairs.
- `FPM_PAGE_SIZE` — `4096` bytes (defined in `freepage.h`).

## Key invariants

- **Bookkeeping is parasitic on the managed memory.** Each free run's
  first page hosts a `FreePageSpanLeader`. The btree's leaf and
  internal pages each occupy one full 4 KB page of managed memory.
  When you allocate the last free run, the btree consequently
  shrinks; when you allocate all pages, the FPM is back to its
  initial empty state with all bookkeeping reclaimed
  (`:20-43` [from-comment]).
- **Magic numbers**: `FREE_PAGE_SPAN_LEADER_MAGIC = 0xea4020f0`,
  `FREE_PAGE_LEAF_MAGIC = 0x98eae728`,
  `FREE_PAGE_INTERNAL_MAGIC = 0x19aa32c9` (`:62-65`
  [verified-by-code]). These let `FreePageManagerDump` and asserts
  catch corruption.
- **Coalescing on Put**: every `FreePageManagerPut(first, npages)`
  consults the btree to find adjacent free ranges. If the put range
  exactly bridges two existing ranges, all three merge into one.
  This is what keeps very-fragmented heaps recoverable
  (`:29-38` [from-comment]).
- **Relative pointers throughout** (`utils/relptr.h`) — every pointer
  inside the FPM region is encoded as an offset from `base`, so the
  same FPM state remains valid across processes that map the region
  at different virtual addresses. This is what makes FPM usable
  inside a DSM segment shared by multiple backends.

## Functions of note

1. **`FreePageManagerInitialize` (`:183-208`)** — sets up an empty FPM
   in caller memory. Records the `base` pointer (so relative offsets
   are computable), zeros the freelist heads, marks the btree root
   invalid.

2. **`FreePageManagerGet` (`:210-377`)** — find a free run of at least
   `npages` consecutive pages. Walks freelists from the smallest
   bucket that *might* contain a suitable run, splits the head of the
   chosen freelist if it's larger than requested (the leftover goes
   back into the appropriate freelist), updates the btree to drop or
   shrink the satisfying range. Returns `false` if no run is large
   enough.

3. **`FreePageManagerPut` (`:379-422`)** — the more complex of the
   two. Looks up the btree to find the immediately-preceding free
   range (if any) and the immediately-following free range (if any).
   Three sub-cases: extend prev, extend next, merge prev+new+next.
   In each sub-case the freelist memberships of the modified ranges
   change (they may move buckets), and the btree leaf/internal pages
   may need split/merge/rebalance — same kinds of operations a
   normal disk btree does, but on in-memory 4 KB pages drawn from
   the FPM's own free space.

4. **`FreePageManagerDump` (`:424+`)** — emits human-readable text of
   the freelists and btree contents into a `StringInfo`. Used by
   `dsa_dump`.

## Cross-references

- `dsa.c` is the only in-tree caller of `FreePageManagerGet/Put` (see
  `dsa.c:757, 878`). FPM is otherwise designed to be a building
  block for other PG-specific shared-memory allocators.
- `source/src/include/utils/relptr.h` — relative-pointer macros used
  pervasively here.
- `source/src/include/utils/freepage.h` — the public type definitions
  and `FPM_PAGE_SIZE` constant.

## Open questions

- The btree's split/merge code is the largest single chunk of this
  file (lines ~430–1800 [unverified — not deeply read in this pass]).
  Coverage in extensive `freepage`-specific tests is desirable; the
  PG regression suite exercises it primarily through `dsa.c`'s use.
- Behavior on receipt of `npages == 0` to `Put`: presumably an
  Assert / no-op, but [unverified] in this pass.

## Confidence tag tally

- `[verified-by-code]` × ~5
- `[from-comment]` × ~6
- `[unverified]` × 2

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/utils-mmgr.md](../../../../../subsystems/utils-mmgr.md)
