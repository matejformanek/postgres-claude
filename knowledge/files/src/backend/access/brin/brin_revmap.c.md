# brin_revmap.c

- **Source path:** `source/src/backend/access/brin/brin_revmap.c` (645 lines)
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `access/brin_page.h` (revmap layout macros), `brin_pageops.c` (`brin_evacuate_page`, `brin_start_evacuating_page`), `brin_xlog.c` (replay of `XLOG_BRIN_REVMAP_EXTEND` / `XLOG_BRIN_DESUMMARIZE`).

## Purpose

The revmap is "a translation structure for BRIN indexes: for each page range there is one summary tuple, and its location is tracked by the revmap." Lives in contiguous pages immediately after the metapage. Constant-time `heapBlk → ItemPointer(summary)` via integer arithmetic. [from-comment, brin_revmap.c:3-13]

## Address arithmetic

```
HEAPBLK_TO_REVMAP_BLK(ppr, hb)   = (hb / ppr) / REVMAP_PAGE_MAXITEMS
HEAPBLK_TO_REVMAP_INDEX(ppr, hb) = (hb / ppr) % REVMAP_PAGE_MAXITEMS
```
Physical revmap block = `HEAPBLK_TO_REVMAP_BLK(...) + 1` (skipping the metapage at block 0). [verified-by-code, brin_revmap.c:40-43, 447]

## BrinRevmap struct (line 46)

| Field | Role |
|---|---|
| `rm_irel` | the index relation |
| `rm_pagesPerRange` | cached from metapage at init |
| `rm_lastRevmapPage` | **cached** highest allocated revmap block |
| `rm_metaBuf` | persistently pinned metapage buffer |
| `rm_currBuf` | last revmap page touched (one-slot cache) |

`rm_lastRevmapPage` may go stale; `revmap_physical_extend` re-reads the metapage under exclusive lock and tells caller to retry if its cached value was wrong. [verified-by-code, brin_revmap.c:540-550]

## Key functions

| Function | Line | Role |
|---|---|---|
| `brinRevmapInitialize` | 69 | Pin metapage, copy `pagesPerRange` + `lastRevmapPage` under share lock |
| `brinRevmapTerminate` | 99 | Release both buffers, pfree |
| `brinRevmapExtend` | 111 | Ensure revmap covers given heapBlk; calls extend loop |
| `brinLockRevmapPageForUpdate` | 133 | Get revmap page buffer + take EXCLUSIVE lock |
| `brinSetHeapBlockItemptr` | 154 | Write one TID slot. **Used both at runtime AND in WAL replay** [from-comment, brin_revmap.c:152] |
| `brinGetTupleForHeapBlock` | 193 | The hot read path; loops to handle concurrent re-points |
| `brinRevmapDesummarizeRange` | 322 | SQL-level "forget this range"; requires `ShareUpdateExclusiveLock` on index |
| `revmap_get_blkno` | 441 (static) | Compute address; returns InvalidBlockNumber if not yet allocated |
| `revmap_get_buffer` | 462 (static) | Cached lookup of revmap page buffer |
| `revmap_extend_and_get_blkno` | 499 (static) | Loop `revmap_physical_extend` until covered |
| `revmap_physical_extend` | 521 (static) | Allocate one more revmap page; evacuate regular page if needed |

## Read-path locking (`brinGetTupleForHeapBlock`)

1. Pin revmap page (`rm_currBuf`); SHARE-lock it. [line 237]
2. Read TID. If invalid → unsummarized → return NULL.
3. **Drop the revmap share lock** (line 265).
4. Pin/lock the target regular page in `mode` (caller chooses SHARE for read path, EXCLUSIVE only on demand).
5. **Sanity check**: page must be `BRIN_IS_REGULAR_PAGE`; offset ≤ maxoff; `tup->bt_blkno == heapBlk` (the embedded heapBlk in the summary tuple is the integrity check).
6. If any check fails → revmap was repointed under us → unlock target, **loop and re-read revmap**. The `previptr` sanity check (line 256) prevents infinite loops by ERROR-ing if the same TID is returned twice in a row. [verified-by-code, brin_revmap.c:222-310]

## Extension protocol (`revmap_physical_extend`)

Lock order: **metapage EXCLUSIVE → relation extension lock → target page EXCLUSIVE**. The metapage lock serializes concurrent revmap extensions; the relation extension lock is still required because *non-revmap* page extensions can race. [from-comment, brin_revmap.c:532-536; verified-by-code, brin_revmap.c:537-577]

If the target physical block is already in use as a regular page, `brin_start_evacuating_page` sets `BRIN_EVACUATE_PAGE`, the metapage is released, and `brin_evacuate_page` migrates the tuples; caller then retries. The retry happens at the `revmap_extend_and_get_blkno` outer loop. [verified-by-code, brin_revmap.c:588-596, 508-512]

Once the target is empty, under CRIT: `brin_page_init(page, BRIN_PAGETYPE_REVMAP)` → bump `metadata->lastRevmapPage` → reset `pd_lower` past metadata → WAL-log `XLOG_BRIN_REVMAP_EXTEND` registering both metapage (STANDARD) and new page (WILL_INIT). [verified-by-code, brin_revmap.c:602-640]

## Desummarize (`brinRevmapDesummarizeRange`)

Requires `ShareUpdateExclusiveLock` on index (so no concurrent summarization). Lock order: **revmap page EXCLUSIVE → regular page EXCLUSIVE**. Aborts and returns false (caller retries) if the regular page was concurrently repurposed (e.g. became a revmap page itself during a concurrent extend). WAL: `XLOG_BRIN_DESUMMARIZE`, both buffers registered. [verified-by-code, brin_revmap.c:339-433]

## Cross-references

- **Called from:** `brin.c` (`brininsert`, `bringetbitmap`, `brinsummarize`, `brin_desummarize_range`), `brin_pageops.c` (`brin_doupdate`, `brin_doinsert`), `brin_xlog.c` (replay re-uses `brinSetHeapBlockItemptr`).
- **Calls into:** `brin_pageops.c` (page evacuation), `storage/bufmgr.c`, `access/xloginsert.c`.

## Open questions

- The `*off > PageGetMaxOffsetNumber(page)` path at line 285 silently returns NULL on "page was desummarized concurrently". This is correct only because `brininsert` re-reads the revmap on its next call. Whether a parallel `bringetbitmap` could miss a tuple in this window is not formally argued; the lossy semantics make it acceptable in principle. [inferred]
- The `previptr` corruption-loop check (line 256) ERRORs on a legitimate-looking double-read; whether an adversarial concurrent updater could trigger it spuriously is not analyzed by the code comments. [unverified]

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
- [idioms/brin-revmap.md](../../../../../idioms/brin-revmap.md)

