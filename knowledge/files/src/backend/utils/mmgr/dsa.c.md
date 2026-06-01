# `src/backend/utils/mmgr/dsa.c`

- **File:** `source/src/backend/utils/mmgr/dsa.c` (2421 lines)
- **Header:** `source/src/include/utils/dsa.h`
- **Last verified commit:** `ef6a95c7c64de07dff4dd1f1da88ffae7b086ef3` (2026-06-01)

## Purpose

**Dynamic Shared Area** — a shared-memory heap layered on top of DSM
(`storage/ipc/dsm.c`). Provides `dsa_allocate` / `dsa_free` that hand
out `dsa_pointer` values (an opaque integer encoding *segment index*
+ *offset within segment*) which any backend with `dsa_attach` to the
area can convert to a process-local pointer via `dsa_get_address`.
Internally a slab-of-spans allocator: small objects come from
size-class pools of superblocks (16 × 4 KB pages = 64 KB), large
objects (>8 KB) take a contiguous run of pages directly from a per-
segment `FreePageManager` (see `freepage.c`). Segments grow on demand,
up to `DSA_MAX_SEGMENTS = 1024` (or fewer on 32-bit / `USE_SMALL_DSA_POINTER`).

## Top-of-file comment (verbatim, key paragraphs)

```
This module provides dynamic shared memory areas which are built on top of
DSM segments.  ...  A DSA area is a shared memory heap usually backed by one
or more DSM segments which can allocate memory using dsa_allocate() and
dsa_free().  Alternatively, it can be created in pre-existing shared memory,
including a DSM segment ...  Unlike the regular system heap, it deals in
pseudo-pointers which must be converted to backend-local pointers before
they are dereferenced.  These pseudo-pointers can however be shared with
other backends, and can be used to construct shared data structures.

Each DSA area manages a set of DSM segments, adding new segments as
required and detaching them when they are no longer needed.  Each segment
contains a number of 4KB pages, a free page manager for tracking
consecutive runs of free pages, and a page map for tracking the source of
objects allocated on each page.  Allocation requests above 8KB are handled
by choosing a segment and finding consecutive free pages in its free page
manager.  Allocation requests for smaller sizes are handled using pools of
objects of a selection of sizes.  Each pool consists of a number of 16 page
(64KB) superblocks ...  Allocation of large objects and new superblocks is
serialized by a single LWLock, but allocation of small objects from
pre-existing superblocks uses one LWLock per pool.
```
(`dsa.c:7-31` [from-comment])

## Public surface (`dsa.h`)

- Lifecycle: `dsa_create` / `dsa_create_ext(tranche_id, init_seg, max_seg)`
  (`:420`), `dsa_create_in_place` / `_ext` (`:470`),
  `dsa_attach(handle)` (`:509`), `dsa_attach_in_place(place, segment)`
  (`:559`), `dsa_detach` (`:619`), `dsa_release_in_place` (`:590`),
  `dsa_is_attached` (`:539`), `dsa_pin` / `dsa_unpin` (`:1008, 1032`),
  `dsa_pin_mapping` (`:649`), `dsa_get_handle` (`:497`),
  `dsa_set_size_limit` (`:1041`), `dsa_minimum_size` (`:1057`).
- Allocation: `dsa_allocate(area, size)` / `dsa_allocate0` / 
  `dsa_allocate_extended(area, size, flags)` (`:685`),
  `dsa_free(area, dp)` (`:840`).
- Address: `dsa_get_address(area, dp)` (`:956`) — *must* be called in
  the local backend; pointers cannot be cached across backends.
- Maintenance: `dsa_trim(area)` (`:1092`),
  `dsa_get_total_size(area)` (`:1245`), `dsa_dump(area)` (`:2001`).
- Detach hooks: `dsa_on_dsm_detach_release_in_place` (resource owner
  cleanup), `dsa_on_shmem_exit_release_in_place`.
- Flags: `DSA_ALLOC_HUGE`, `DSA_ALLOC_NO_OOM`, `DSA_ALLOC_ZERO`
  (mirror the palloc flags) (`dsa.h:73-75`).

## Key types

- `dsa_pointer` (`dsa.h:52-69`) — `uint32` on 32-bit / `USE_SMALL_DSA_POINTER`,
  else `uint64`. Encoded as `(segment_index << DSA_OFFSET_WIDTH) | offset`;
  `DSA_OFFSET_WIDTH = 27` (32 × 128 MB) or `40` (1024 × 1 TB).
  `InvalidDsaPointer = 0` (so segment 0 offset 0 = the control block
  header, never a valid allocation).
- `dsa_area_control` (`dsa.c:287-319`) — lives at start of the first
  DSM segment. Has: `handle`, `segment_handles[DSA_MAX_SEGMENTS]`,
  `segment_bins[DSA_NUM_SEGMENT_BINS=16]` (segments binned by largest
  contiguous free-page run), `pools[DSA_NUM_SIZE_CLASSES]`,
  `init_segment_size`, `max_segment_size`, `total_segment_size`,
  `max_total_segment_size`, `high_segment_index`, `refcnt`, `pinned`,
  `freed_segment_counter`, `lwlock_tranche_id`, area-wide `lock`.
- `dsa_area_pool` (`dsa.c:274-281`) — one per size class. Owns its
  own `LWLock`, and `spans[DSA_FULLNESS_CLASSES=4]` linked lists of
  superblocks binned by fullness.
- `dsa_area_span` (`dsa.c:183-196`) — one per superblock. Tracks
  `start` (dsa_pointer to first page), `npages`, `size_class`,
  `ninitialized` (high-water), `nallocatable`, `firstfree` (head of
  in-block freelist), `nmax`, `fclass`, prev/next-span links.
- `dsa_segment_map` (`dsa.c:332-339`) — *backend-private*. One per
  segment-index slot, in the per-backend `dsa_area` struct. Holds
  the local `dsm_segment *`, mapped address, the segment header, the
  `FreePageManager *fpm`, and the `pagemap` (dsa_pointer per page →
  the span that owns it).
- `dsa_area` (`dsa.c:347-373`) — per-backend handle. Holds
  `dsa_area_control *control`, optional `ResourceOwner`, the
  `segment_maps[DSA_MAX_SEGMENTS]` array, last-observed
  `freed_segment_counter` (for lazy detach of dropped segments).

## Key invariants

- **DSM segments are explicitly pinned** by `dsa_create` via
  `dsm_pin_segment` (`:438`) so they outlive any individual backend's
  mapping; the area's own refcount/`pinned` flag controls when they
  actually go away [verified-by-code, [from-comment]].
- **Size classes are fixed** (`dsa_size_classes[]` at `:225-235`):
  span-sized + zero special class, then 8B steps to 64B, 16B to 128B,
  32B to 256B, 64B to 512B, 128B to 1024B, ~256B to 2048B, ~512B to
  4096B, ~1024B to 8192B. Mapping `size → size_class` uses
  `dsa_size_class_map[]` (`:248-257`) for sizes < 1024B
  (table-lookup), binary search for the rest (`:790-811`
  [verified-by-code]).
- **Two special size classes** at indices 0 and 1:
  `DSA_SCLASS_BLOCK_OF_SPANS` — spans for "spans of spans", solving
  the bootstrap "need a span to make a superblock, need a superblock
  to make a span" cycle; and `DSA_SCLASS_SPAN_LARGE` — span objects
  describing large (>8 KB) allocations that own a contiguous run of
  pages directly (`:178-181, 238-240, 707-778` [from-comment]).
- **Locking hierarchy**:
  1. `DSA_AREA_LOCK(area) = &area->control->lock` protects segment
     creation, segment bins, the page-level free-page-manager calls
     (each segment's FPM is treated as inside the area lock).
  2. `DSA_SCLASS_LOCK(area, sclass) = &area->control->pools[sclass].lock`
     protects each pool's fullness-class lists and per-span allocation.
  3. Small-object alloc/free *only* takes the per-pool lock if it can
     satisfy from an existing span; allocating a fresh superblock or
     destroying one takes both. Large-object alloc/free *always* takes
     the area lock (page-manager work) plus the per-span-class lock
     for span bookkeeping. (`:728-771, 877-947` [verified-by-code].)
- **Allocation failure is FATAL inside the allocator if the FPM
  reports "out of pages" after `get_best_segment` claimed it had
  them** (`:757-759`): "If it does fail, something in our backend
  private state is out of whack, so use FATAL to kill the process."
  Genuine OOM (no more segments and `make_new_segment` returns NULL)
  is ERROR, or returns `InvalidDsaPointer` if `DSA_ALLOC_NO_OOM` set
  (`:734-748` [from-comment]).
- **Active superblock hysteresis** (`dsa_free` `:933-945`): the
  active superblock for a size class is *not* freed when it goes
  empty — otherwise repeated alloc-then-free of the only chunk would
  pingpong malloc the underlying pages. Only non-active fully-empty
  blocks return pages to the FPM.
- **`dsa_get_address` may map segments lazily and unmap freed ones**
  via `check_for_freed_segments` (`:407, 853`). This means
  `dsa_get_address` is *not* free of side effects and must be called
  in a backend-local code path with a valid resource owner
  [verified-by-code, [from-comment]].
- **`dsa_pin` / `dsa_unpin` are not refcounts** in the usual sense —
  `dsa_pin` raises a flag that makes the area survive past the
  detach of its creator; refcount tracks attached backends
  (`:993-1039` [verified-by-code, [from-comment]]).
- **In-place areas** (`dsa_create_in_place`) live in caller-provided
  storage and don't manage a "first segment" via DSM; release order
  must be coordinated by caller via `dsa_release_in_place` or an
  on_dsm_detach hook (`:454-490, 590-617` [from-comment]).

## Functions of note

1. **`dsa_create_ext` (`:420-452`) / `dsa_attach` (`:509-532`)** — the
   two entry points for shared use. Creator calls `dsm_create` +
   `dsm_pin_segment`, builds the control block via `create_internal`,
   registers `dsa_on_dsm_detach_release_in_place` so a backend exit
   tears down its share of the area. Attacher just `dsm_attach`'s the
   first segment by handle and calls `attach_internal`.

2. **`dsa_allocate_extended` (`:685-835`)** — the hot path.
   - `size > 8192` → large path: alloc a span object (recursive call
     into `alloc_object(area, DSA_SCLASS_BLOCK_OF_SPANS)`), take area
     lock, `get_best_segment(npages)` or `make_new_segment`,
     `FreePageManagerGet` to get a contiguous page run, init a
     `DSA_SCLASS_SPAN_LARGE` span, write `pagemap[first_page] =
     span_pointer`, optionally zero. (`:707-778`)
   - Otherwise compute size_class (lookup or binary search), call
     `alloc_object` which is the small-object pool path
     (`alloc_object` → `ensure_active_superblock` →
     `transfer_first_span` between fullness classes; under the per-
     pool lock).
   - OOM is `ereport(ERROR, ERRCODE_OUT_OF_MEMORY)` unless
     `DSA_ALLOC_NO_OOM`.

3. **`dsa_free` (`:840-948`)** — symmetric to allocate. Calls
   `check_for_freed_segments` first (lazy detach). Locates the span
   via `segment_map->pagemap[pageno]`. Large case returns pages to
   the FPM directly and frees the span recursively. Small case pushes
   the object onto `span->firstfree` (NextFreeObjectIndex stored in
   the first 16 bits of the freed object's memory — same trick as
   slab.c). If the span transitions to empty and isn't the active
   block for its class, calls `destroy_superblock` (returns the 16
   pages to the FPM, removes the span). Has explicit handling for
   "block was completely full and lives in highest fullness class
   which is never scanned" to demote it.

4. **`dsa_get_address` (`:956+`)** — converts a `dsa_pointer` to a
   local address. Demaps freed segments lazily; maps unmapped ones
   on first use. **Must not** be called from a signal handler or any
   context that lacks a `ResourceOwner` if the area was attached
   without `dsa_pin_mapping`.

5. **`dsa_trim` (`:1092+`)** — opportunistically returns empty
   segments to the OS. Walks segment_bins, identifies segments whose
   FPM holds all their pages, calls `dsm_unpin_segment` +
   bumps the global `freed_segment_counter` so other backends see
   the change at their next `check_for_freed_segments`.

6. **`init_span` / `destroy_superblock`** — internal helpers that
   handle the bootstrapping cycle (a "block of spans" is itself a
   superblock whose objects are spans, allocated through the same
   `alloc_object` machinery; size_class `DSA_SCLASS_BLOCK_OF_SPANS`
   resolves this).

7. **`get_best_segment` / `make_new_segment` / `rebin_segment`** —
   segment management. Segments are binned in
   `segment_bins[DSA_NUM_SEGMENT_BINS]` by the largest contiguous free
   run they offer (`contiguous_pages_to_segment_bin(n) = log2(n)+1`,
   capped at 15). New segments are created at growing sizes
   (`DSA_NUM_SEGMENTS_AT_EACH_SIZE = 2`, then double) up to
   `max_segment_size`, capped at `DSA_MAX_SEGMENTS` (`:62-76`).

## Cross-references

- `freepage.c` / `source/src/include/utils/freepage.h` — the
  per-segment `FreePageManager`. DSA does not implement free-page
  bookkeeping itself; it delegates.
- `source/src/backend/storage/ipc/dsm.c` — DSM segment infrastructure
  that DSA segments are backed by.
- `source/src/backend/storage/lmgr/lwlock.c` — DSA areas allocate
  LWLocks from a caller-supplied tranche; the comment at `:415-418`
  notes tranche IDs are scarce and must be passed in.
- `dsa.h` — public type/flag/macro definitions and the size-policy
  constants `DSA_DEFAULT_INIT_SEGMENT_SIZE = 1 MB`,
  `DSA_MIN_SEGMENT_SIZE = 256 KB`, `DSA_MAX_SEGMENT_SIZE = 1 << 40`.
- Major consumers: parallel-query shared state (`nodes/execParallel.c`
  [unverified]); shared hash tables (`dshash.c`); pg_stat_kcache /
  cumulative stats (`pgstat.c` shared regions).

## Open questions

- The recursive `dsa_free(area, span_pointer)` inside `dsa_free`
  (`:892`) on the large-object path — re-entering with the area
  unlocked but the span-class lock held briefly. The locking order
  there is subtle; the comment "Free the span object so it can be
  reused" doesn't explicitly state the lock-order argument. The
  invariant must be that area-lock and per-sclass-lock are leaf
  locks acquired in a strict order, but I haven't audited every
  release/reacquire pair in the file [unverified].
- **`dsa_set_size_limit`** allows pegging the area at a fixed size
  (e.g. for `dsa_create_in_place` in a fixed-size shmem region). What
  happens to a span request that fits in the size limit but no
  contiguous-page run is large enough — does it `make_new_segment`
  and then fail? — [unverified, would need to trace
  `make_new_segment`'s `total_segment_size` check].
- **Tranche ID exhaustion**: with only 64K tranche IDs, long-running
  servers that repeatedly create DSAs (e.g. one per parallel query
  group with a new tranche) could in theory exhaust them. In practice
  callers reuse a fixed tranche per subsystem; not enforced by dsa.c
  itself [from-comment at `:415-418`, [unverified] as a real concern].

## Confidence tag tally

- `[verified-by-code]` × ~14
- `[from-comment]` × ~10
- `[unverified]` × 3
