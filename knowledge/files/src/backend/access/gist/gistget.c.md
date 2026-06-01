# gistget.c

- **Source path:** `source/src/backend/access/gist/gistget.c` (814 lines)
- **Last verified commit:** `ef6a95c7c64`

## Purpose

The scan engine: `gistgettuple` (next-row), `gistgetbitmap` (TIDBitmap fill), queue-based search, KNN distance ordering, and `gistkillitems` (the LP_DEAD-setting opportunistic delete). [from-comment, gistget.c:1-13]

## Search queue

A **pairing heap** (`lib/pairingheap.h`) holds `GISTSearchItem`s — either heap tuple matches or pinned-index-page descents. Heap items are pulled first (depth-first preference) unless KNN ordering applies. KNN: items carry distances; index pages carry the *minimum-possible* distance for any descendant. Pop in smallest-distance-first order. [from-README, README:71-117]

## NSN/F_FOLLOW_RIGHT race handling

When dequeueing an index page, the scan compares the child's **NSN** with the **parent's LSN saved at queue time**. If `child_NSN > parent_LSN`, the parent was visited *before* the child's split was linked into the parent. In that case, the right sibling is added to the **front** of the queue, ensuring its items are scanned in the same order they would have been on the unsplit page. [from-README, README:97-107; verified-by-code in `gistScanPage`]

If the page has `F_FOLLOW_RIGHT` set (only possible after a crashed split, normally cleared by the inserter), the scan also follows the rightlink. [from-README, README:286-291]

## `gistkillitems`

Sets `LP_DEAD` on items the executor said are dead (no longer match the snapshot after recheck). Cleaned up in place at next page modification. **Unlike nbtree, GiST does NOT emit a WAL record for kill-items** — the LP_DEAD bits are dirty-hint only. This is why `XLOG_GIST_DELETE` (which removes LP_DEAD items at insert time) carries `snapshotConflictHorizon`: that's the conflict gate for standby. [verified-by-code; cross-ref gistxlog.c:182-198]

## Locking

Per-page share lock during scan; release before queueing children to honor README's "lock only one page at a time during search" rule. [from-README, README:97-99]

## SSI

`PredicateLockPage` is taken on each scanned leaf (and on internal pages for KNN range coverage). [verified-by-code at `gistgetbitmap` predicate-lock calls]
