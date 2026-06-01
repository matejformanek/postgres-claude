# brin/README — summary

- **Source path:** `source/src/backend/access/brin/README` (189 lines)
- **Last verified commit:** HEAD

## Purpose

Canonical narrative for the **Block Range Index (BRIN)** access method. Establishes the design as a *summary-per-page-range* index rather than a per-row index. "BRIN indexes intend to enable very fast scanning of extremely large tables." [from-README, README:1-13]

## The ideas you must hold

1. **One summary tuple per page range, not per row.** Each index tuple summarizes a fixed-width group of contiguous heap pages (default 128). The summary is opclass-specific: minmax keeps `(min, max)`; minmax-multi keeps several disjoint intervals; inclusion keeps a bounding box; bloom keeps a Bloom filter. [from-README, README:5-13, 60-63]
2. **Bitmap-only, no `amgettuple`.** Because no heap TIDs are stored, BRIN can only return a *lossy* `TIDBitmap` covering every heap page in matching ranges; the bitmap-heap-scan recheck does row filtering. [from-README, README:19-25]
3. **The revmap.** A fixed-size translation array in the first index blocks (after metapage) maps `heapBlk → ItemPointer(summary tuple)`. Constant-time lookup by arithmetic on `pagesPerRange`. [from-README, README:73-106]
4. **Required opclass support procs.** `opcinfo` (1), `addValue` (2), `consistent` (3), `union` (4) — and opclass-specific extras (minmax procs 11-14 = `<`, `<=`, `>=`, `>`). Procnums up to 10 are reserved. [from-README, README:27-47]
5. **Tuple null bitmap is doubled.** For each indexed column there are two generic bits: `bt_hasnulls` (any NULL in range) and `bt_allnulls` (every value NULL in range). [from-README, README:55-59]
6. **Insert is "compare to summary, expand if outside".** If the new heap value is consistent with the existing summary, do nothing. Otherwise update the index tuple — same-page if it fits, else move to a new page and re-point the revmap. Unsummarized ranges receive *no* insert. [from-README, README:82-94]
7. **Summarization runs at build time, at VACUUM, and on demand.** `brin_summarize_new_values()` / `brin_summarize_range()` SQL functions exist; autosummarize-on-insert can be enabled via reloption. [from-README, README:115-133]
8. **Vacuum does not need to scan the index for tuple removal.** No heap TIDs in the index → nothing to remove when heap tuples die. Summaries may grow stale-loose but never wrong; re-summarization tightens them. [from-README, README:135-152]
9. **Optimizer picks BRIN via `pg_amop` strategy entries**, same mechanism as other AMs. [from-README, README:154-159]
10. **Open design questions** (called out in the README §"Future improvements"): variable-size page ranges, more compact TIDBitmap for lossy ranges, block-level vacuum callback to drive auto re-summarization. [from-README, README:161-189]

## Where each section is implemented

| README section | Implementing files |
|---|---|
| AM handler + amgetbitmap + insert wrapper + summarize functions | `brin.c` |
| Page formatting (insert tuple, update tuple, evacuate page, page-init) | `brin_pageops.c` |
| Revmap lookup + extension | `brin_revmap.c` |
| WAL record formats + redo | `brin_xlog.c`, `access/brin_xlog.h` |
| Tuple encoding / on-disk form | `brin_tuple.c` |
| Built-in opclasses | `brin_minmax.c`, `brin_minmax_multi.c`, `brin_bloom.c`, `brin_inclusion.c` |
| Opclass validator | `brin_validate.c` |
| Metapage / page-type layout | `access/brin_page.h` |

## Highest-risk claims worth spot-checking

1. **"No heap TIDs in BRIN index"** → confirmed by absence of `amgettuple` in `brinhandler` (`brin.c:300`) and by revmap entry being a *page-range → index-tuple-TID* mapping, not a heap-TID list. [verified-by-code, brin.c:254-313]
2. **"Range map page 0 = metapage; subsequent N blocks = revmap"** → metapage at `BRIN_METAPAGE_BLKNO = 0` (`brin_page.h:75`), revmap extension is `revmap_physical_extend` in `brin_revmap.c`, evacuating any regular tuples that already sat on the target block. [verified-by-code, brin_revmap.c:60-63]
3. **Autosummarize trigger** is per-`brininsert` call when the first row lands on the first block of a fresh page range, via `AutoVacuumRequestWork(AVW_BRINSummarizeRange, ...)`. [verified-by-code, brin.c:398-422]
