# tidbitmap.h

- **Source:** `source/src/include/nodes/tidbitmap.h` (127 lines)
- **Last verified commit:** `ef6a95c7c64`
- **Depth:** read

## Purpose

Public API for the TID bitmap used by bitmap index scans. The
internal `TIDBitmap` struct is private to `tidbitmap.c`; callers see
it as an opaque pointer plus iterator types. `:36-44`
`[from-comment]`

## Public types

- `TIDBitmap` (opaque).
- `TBMPrivateIterator`, `TBMSharedIterator` (opaque).
- `TBMIterator` `:50-58` — tagged union over the two iterator kinds:
  ```c
  typedef struct TBMIterator {
      bool shared;
      union {
          TBMPrivateIterator *private_iterator;
          TBMSharedIterator  *shared_iterator;
      } i;
  } TBMIterator;
  ```
- `TBMIterateResult` `:61-79` — result of one iteration step:
  `blockno`, `lossy`, `recheck`, `internal_page` (opaque cookie used
  by `tbm_extract_page_tuple` to enumerate offsets).

## Capacity invariants

- `TBM_MAX_TUPLES_PER_PAGE = MaxHeapTuplesPerPage` — at most 256 with
  8K pages, 1024 with 32K. `:33-34` `[verified-by-code]`

## API (prototypes)

Construction/teardown:
- `tbm_create(maxbytes, dsa)` — pass non-NULL `dsa` to make the TBM
  shareable.
- `tbm_free`, `tbm_free_shared_area`

Insertion:
- `tbm_add_tuples(tbm, tids, n, recheck)`
- `tbm_add_page(tbm, pageno)` — directly insert a lossy page

Set ops:
- `tbm_union(a, b)`, `tbm_intersect(a, b)`

Observation:
- `tbm_is_empty`, `tbm_calculate_entries(maxbytes)`

Iteration:
- Private: `tbm_begin_private_iterate`, `tbm_private_iterate`,
  `tbm_end_private_iterate`
- Shared: `tbm_prepare_shared_iterate` (returns `dsa_pointer`),
  `tbm_attach_shared_iterate`, `tbm_shared_iterate`,
  `tbm_end_shared_iterate`
- Unified: `tbm_begin_iterate`, `tbm_iterate`, `tbm_end_iterate`,
  `tbm_exhausted` (inline) `:117-125`

Per-page tuple extraction:
- `tbm_extract_page_tuple(iteritem, offsets, max_offsets)` —
  enumerate offsets from a non-lossy result.

## Cross-references

- Implementation: `source/src/backend/nodes/tidbitmap.c`
- Consumers: `nodeBitmapHeapscan.c`, `nodeBitmapIndexscan.c`,
  `nodeBitmapAnd.c`, `nodeBitmapOr.c`, BRIN.

## Synthesized by
<!-- backlinks:auto -->
- [idioms/bitmap-heap-scan-flow.md](../../../../idioms/bitmap-heap-scan-flow.md)
- [idioms/tidbitmap-build-and-iterate.md](../../../../idioms/tidbitmap-build-and-iterate.md)
- [idioms/tidbitmap-structure-and-lossy.md](../../../../idioms/tidbitmap-structure-and-lossy.md)
