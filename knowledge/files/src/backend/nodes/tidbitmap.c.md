# tidbitmap.c

- **Source:** `source/src/backend/nodes/tidbitmap.c` (~1650 lines)
- **Last verified commit:** `ef6a95c7c64`
- **Depth:** read (top comment + key entry points)

## Purpose

Set-of-TIDs structure powering the bitmap-scan family
(`BitmapIndexScan` → `BitmapAnd`/`BitmapOr` → `BitmapHeapScan`).
Specially adapted to TID structure (`(BlockNumber, OffsetNumber)`) and,
critically, supports **lossy** storage so that very large TID sets
remain bounded in memory. `:1-29 tidbitmap.c` `[from-comment]`

## Data model

- Per-page entries hold one bit per tuple slot, up to
  `TBM_MAX_TUPLES_PER_PAGE = MaxHeapTuplesPerPage`. `tidbitmap.h:34`
  `[verified-by-code]`
- When memory is tight, the TBM switches to **lossy chunks**: one bit
  per **page**, `PAGES_PER_CHUNK = BLCKSZ/32` pages per chunk. At 8K
  pages, that's 256 pages/chunk → ~1 MB tracks 64 GB. `:51-66`
  `[from-comment]`
- Exact and lossy entries share one hashtable. A lossy chunk for a
  page range removes all per-page entries in that range — there can't
  be both. `:58-66, :78-91` `[from-comment]`
- Recheck flag per exact page indicates the index quals only
  approximate; the heap scan must re-evaluate. Set on insert
  (`tbm_add_tuples(tbm, tids, n, recheck=true)`) or implicitly when
  ANDing a lossy with a non-lossy page. `:22-29` `[from-comment]`

## Iteration model

Three iterator APIs `tidbitmap.h:101-115` `[verified-by-code]`:

- **Private** (`TBMPrivateIterator`): in-process, used by a serial
  BitmapHeapScan.
- **Shared** (`TBMSharedIterator`): backed by DSA, multiple parallel
  workers consume the same TBM.
- **Unified** (`TBMIterator`): tagged union (`.shared`) over the two,
  so callers can write one loop.

`tbm_iterate` yields `TBMIterateResult { blockno, lossy, recheck,
internal_page }`. For a non-lossy page the caller uses
`tbm_extract_page_tuple` to enumerate offsets into a small array.
`tidbitmap.h:60-79, :95-97` `[verified-by-code]`

## Key entry points

| Line | Function | Notes |
|---|---|---|
| 256 | `tbm_create` | allocate, possibly in DSA |
| 312 | `tbm_free` | free hashtable, page lists |
| 367 | `tbm_add_tuples` | per-tuple insert |
| 432 | `tbm_add_page` | add a whole page (used by BRIN, etc.) |
| 447 | `tbm_union` | a |= b |
| 528 | `tbm_intersect` | a &= b, may upgrade to lossy mid-flight |
| 657 | `tbm_is_empty` | |
| 752 | `tbm_prepare_shared_iterate` | turn TBM into a shared, sorted DSA structure |
| 1571 | `tbm_begin_iterate` | unified iterator constructor |
| 1594 | `tbm_end_iterate` | |
| 1614 | `tbm_iterate` | yields the next `TBMIterateResult` |

## Memory-limit upgrade path

The TBM tracks live memory usage; when it would exceed `maxbytes`
(passed to `tbm_create`), it converts the oldest/largest exact pages
into lossy chunks. The upgrade strategy keeps the working set
bounded but trades precision (and increased heap-recheck volume).

## Parallel correctness

Shared-iterate path: `tbm_prepare_shared_iterate` constructs a sorted
DSA-resident page array, then workers grab block ranges via
`tbm_shared_iterate`. The DSA pointer is stamped into the parallel
context so workers can `tbm_attach_shared_iterate`.
`tidbitmap.h:102-108` `[verified-by-code]`

## Cross-references

- Header: `source/src/include/nodes/tidbitmap.h`
- Consumers: `executor/nodeBitmapIndexscan.c`,
  `executor/nodeBitmapAnd.c`, `executor/nodeBitmapOr.c`,
  `executor/nodeBitmapHeapscan.c`, and BRIN.
- Cousins: `nodes/bitmapset.c` (the small-int set; this file uses its
  word type but otherwise unrelated).
