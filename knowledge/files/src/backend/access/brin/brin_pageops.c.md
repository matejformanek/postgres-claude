# brin_pageops.c

- **Source path:** `source/src/backend/access/brin/brin_pageops.c` (925 lines)
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `brin.c` (callers), `brin_revmap.c` (`brinLockRevmapPageForUpdate`, `brinSetHeapBlockItemptr`), `brin_xlog.c` (replay of records emitted here).

## Purpose

Page-level update/insert/init/evacuate primitives for BRIN. Owns the lock-ordering for cross-page summary updates and the relation-extension dance. [from-comment, brin_pageops.c:1-10]

## Key functions

| Function | Line | Role |
|---|---|---|
| `brin_doupdate` | 52 | Replace existing summary tuple; samepage if possible, else allocate new page + repoint revmap |
| `brin_can_do_samepage_update` | 321 | Cheap check: newsz fits in oldpage |
| `brin_doinsert` | 340 | First-time summary insert for a fresh range; sets revmap entry |
| `brin_page_init` | 472 | `PageInit` + stamp `BrinPageType` in special area |
| `brin_metapage_init` | 483 | Initialize metapage at block 0 with magic/version/pagesPerRange. Sets `pd_lower` past metadata so full-page-image compression preserves it. [verified-by-code, brin_pageops.c:503-509] |
| `brin_start_evacuating_page` | 521 | Sets `BRIN_EVACUATE_PAGE` flag (note: **not WAL-logged**, except accidentally) so future inserts skip the page. [from-comment, brin_pageops.c:544-545] |
| `brin_evacuate_page` | 561 | Move every tuple off a page via `brin_doupdate` cross-page. Used to vacate a regular page about to become a revmap page |
| `brin_page_cleanup` | 621 | VACUUM helper: initialize PageIsNew pages, record freespace in FSM |
| `brin_getinsertbuffer` | 687 (static) | The buffer-pair locking core; deadlock-avoidance via "lower blkno first" |
| `brin_initialize_empty_new_buffer` | 881 (static) | WAL-log empty page init + record in FSM after extension corner cases |

## Locking — the hot section [HIGH-RISK]

### `brin_doupdate` cross-page path (line 228-316)

Lock acquisition order: **revmap buffer (via `brinLockRevmapPageForUpdate`) → oldbuf+newbuf already exclusive from `brin_getinsertbuffer`**. CRIT section spans `PageIndexTupleDeleteNoCompact(old) + PageAddItem(new) + brinSetHeapBlockItemptr(revmap) + XLogInsert`. Release order: revmap, oldbuf, newbuf. [verified-by-code, brin_pageops.c:240-306]

### `brin_getinsertbuffer` deadlock-avoidance (line 687)

The lock pair (oldbuf, newbuf) is acquired in **block-number ascending order**: if `oldblk < newblk`, lock oldbuf first then newbuf (lines 766-768, 800); otherwise lock newbuf first then oldbuf (line 825). This is the deadlock-avoidance rule. [verified-by-code, brin_pageops.c:760-829] (The earlier brin.c.md flagged this as `[inferred]` — it is here in code as explicit branching but the source has no in-line comment naming the rule. Still inferred-from-pattern.)

If between lock-of-oldbuf and lock-of-newbuf the FSM/concurrent activity turned oldbuf into a revmap page, the function aborts returning `InvalidBuffer` so caller restarts. [verified-by-code, brin_pageops.c:769-797]

### Re-check after share→exclusive transition

`brin_doupdate` is called from `brininsert` after it released a share lock and the caller no longer holds the page. Once exclusive lock is reacquired, `brin_doupdate` verifies:
1. Page is still regular (not turned into revmap),
2. Offset still in range and `ItemIdIsNormal`,
3. Tuple content equals the snapshot `origtup` via `brin_tuples_equal`.

Failure → unlock, return false, caller retries. [verified-by-code, brin_pageops.c:115-164]

## WAL records emitted

- `XLOG_BRIN_SAMEPAGE_UPDATE` (line 188) — single-buffer overwrite; only the new tuple bytes are logged.
- `XLOG_BRIN_UPDATE` (line 274) — 3 buffers: new, revmap, old. May OR-in `XLOG_BRIN_INIT_PAGE`.
- `XLOG_BRIN_INSERT` (line 430) — 2 buffers: target, revmap; may carry `XLOG_BRIN_INIT_PAGE`.
- `log_newpage_buffer` (line 897) — for stray extension-then-not-used pages.

## Oversized-tuple policy

Both `brin_doupdate` and `brin_doinsert` `ereport(ERROR)` if `itemsz > BrinMaxItemSize`. BRIN tolerates **only one item per regular page** as a worst case (`BrinMaxItemSize = MAXALIGN_DOWN(BLCKSZ - header - special)`). [from-comment, brin_pageops.c:24-32; verified-by-code]

## Open questions

- The `BRIN_EVACUATE_PAGE` flag is dirty-hint only (not WAL-logged). On crash it may be lost on the primary, causing a now-evacuating page to receive a fresh insert. Comment says "except accidentally" via FPI. Whether replicas can durably diverge is unclear. [unverified, brin_pageops.c:544-545]

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
- [idioms/brin-summarize-and-scan.md](../../../../../idioms/brin-summarize-and-scan.md)

