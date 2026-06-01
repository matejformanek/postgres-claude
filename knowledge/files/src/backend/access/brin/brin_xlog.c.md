# brin_xlog.c

- **Source path:** `source/src/backend/access/brin/brin_xlog.c` (367 lines)
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `access/brin_xlog.h` (record formats + `XLOG_BRIN_*` info bits), `brin_pageops.c` (emitters), `brin_revmap.c` (`brinSetHeapBlockItemptr` reused at replay).

## Purpose

WAL redo (`brin_redo`) and masking (`brin_mask`). One handler per `XLOG_BRIN_*` op code. [from-comment, brin_xlog.c:1-22]

## Record-to-handler table

| Info byte | Handler | Buffers |
|---|---|---|
| `XLOG_BRIN_CREATE_INDEX` | `brin_xlog_createidx` (24) | 0 = metapage (WILL_INIT) |
| `XLOG_BRIN_INSERT` | `brin_xlog_insert` (123) → `brin_xlog_insert_update` | 0 = regular page (WILL_INIT if `XLOG_BRIN_INIT_PAGE`), 1 = revmap page |
| `XLOG_BRIN_UPDATE` | `brin_xlog_update` (134) | 2 = old page (delete), 0 = new page (insert), 1 = revmap page |
| `XLOG_BRIN_SAMEPAGE_UPDATE` | `brin_xlog_samepage_update` (169) | 0 = page only; uses `PageIndexTupleOverwrite` |
| `XLOG_BRIN_REVMAP_EXTEND` | `brin_xlog_revmap_extend` (207) | 0 = metapage, 1 = new revmap page (WILL_INIT — **no FPI possible**) |
| `XLOG_BRIN_DESUMMARIZE` | `brin_xlog_desummarize_page` (268) | 0 = revmap page, 1 = regular page |

## Recovery-correctness notes [HIGH-RISK]

### Insert + update share `brin_xlog_insert_update`

Replay order is: (a) regular page receives `PageAddItem` at the recorded offnum (or `XLogInitBufferForRedo` if `INIT_PAGE`), (b) revmap page receives `brinSetHeapBlockItemptr` pointing at `(regpgno, offnum)`. `regpgno` comes from `BufferGetBlockNumber(buffer)` **after** locking — i.e. the physical block number, not from the record. This means the WAL record does **not** need to carry the regular page's block number — block 0's tag does. [verified-by-code, brin_xlog.c:71-115]

The integrity assert `tuple->bt_blkno == xlrec->heapBlk` (line 83) catches WAL corruption where the embedded summary heapBlk and the WAL header disagree.

### Update (cross-page) replay

`brin_xlog_update` processes block 2 (old page: delete) **first**, then calls the shared insert helper which handles blocks 0/1. The old buffer is **kept locked** until after the shared helper finishes (line 162-163), so block 0/1 replay overlaps with block 2 lock held. **The locking order during replay is therefore: old (block 2) → new (block 0) → revmap (block 1)** — which is *not* the primary's order (revmap is acquired last on primary inside `brin_doupdate` — primary order is new + old already locked, then revmap). This is **safe** because replay is single-threaded against concurrent backends (no other writers on standby for redo) and `XLogReadBufferForRedo` itself takes content locks per block in the order they're processed. The README does not formally state replay lock-order; this is inferred from code. [inferred, brin_xlog.c:142-164]

### `brin_xlog_revmap_extend` corner

The new revmap page is **always** rebuilt via `XLogInitBufferForRedo` (line 256) — there is no full-page image because the page is re-initialized from scratch and the WAL record was registered with `REGBUF_WILL_INIT`. The metapage is updated incrementally (`lastRevmapPage` bumped, `pd_lower` reset). The `pd_lower` reset on the metapage is replicated *exactly* from `brin_pageops.c:metapage_init` rationale: pre-v11 indexes after pg_upgrade may have wrong `pd_lower` and xlog page-compression would otherwise lose metadata. [from-comment, brin_xlog.c:238-247]

### No FSM updates during replay

Comments at lines 117 ("XXX no FSM updates here") and 201 explicitly note that FSM is not updated by replay. The FSM is rebuilt by `brinvacuumcleanup` post-recovery. [from-comment, brin_xlog.c:117, 201]

## Masking (`brin_mask`)

- Always masks LSN + checksum + hint bits.
- For regular pages and metapages with valid `pd_lower`, masks unused space.
- **Strips `BRIN_EVACUATE_PAGE`** from page flags before checksum-equality check — because the flag is set as a dirty hint without WAL logging and primary/standby may disagree. [from-comment, brin_xlog.c:362-366]

## Cross-references

- **Dispatched from:** `access/transam/rmgr.c` via `RM_BRIN_ID`.
- **Calls into:** `brin_pageops.c::brin_metapage_init` / `brin_page_init`, `brin_revmap.c::brinSetHeapBlockItemptr`, `access/transam/xlogutils.c` (`XLogReadBufferForRedo`, `XLogInitBufferForRedo`).

## Open questions

- `XLOG_BRIN_INSERT` and `_UPDATE` do not emit a recovery conflict, even though they may delete the old summary. This is correct because BRIN summaries are lossy and not visibility-bearing — but the absence is not justified by a comment. [unverified]
- Whether `brin_xlog_revmap_extend`'s assertion `metadata->lastRevmapPage == xlrec->targetBlk - 1` is safe under partial WAL replay (e.g. after a crash mid-recovery) is not analyzed. [unverified]
