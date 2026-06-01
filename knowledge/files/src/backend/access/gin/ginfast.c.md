# ginfast.c

- **Source path:** `source/src/backend/access/gin/ginfast.c` (1091 lines)
- **Last verified commit:** `ef6a95c7c64`

## Purpose

The **fastupdate pending-list** mechanism: with `fastupdate=on`, new entries are appended to a linear chain of "list pages" hung off the metapage instead of merged into the entry tree. A later **cleanup pass** (`ginInsertCleanup`) drains the pending list into the regular tree in one bulk operation. [from-comment, ginfast.c:1-15]

## GUC

- `gin_pending_list_limit` (kB) — soft cap; once the pending list exceeds it, the next inserter triggers a cleanup.

## Key entry points

- `ginHeapTupleFastInsert` — append one heap-tuple's worth of entries (a "row" — keys for one heap row) to the pending list tail. Manages metapage exclusive lock for the tail-pointer update; uses `GIN_LIST_FULLROW` flag to mark "page contains complete rows" vs "page contains a partial row of one heap tuple".
- `ginInsertCleanup` — scan pending list head-to-tail, accumulate entries in a `BuildAccumulator`, then call `ginEntryInsert` for each merged group; finally call `shiftList` to bulk-delete the consumed head pages.
- `ginPageGetLinkItup` / `writeListPage` — page-level helpers for list-page layout.
- `shiftList` — atomically delete N head pages and update metapage's `head`/`nPendingPages` counters; emits `XLOG_GIN_DELETE_LISTPAGE`.

## Locking [HIGH-RISK]

- **Metapage lock** is the central serialization point: shared during scan to find current pending head, exclusive during tail append and cleanup. This is also the SSI predicate-lock anchor (per README §"Predicate Locking" — fastupdate effectively requires a full-index predicate lock). [from-README, README:501-508]
- During `ginInsertCleanup`, a separate transaction-internal lock prevents two concurrent cleanups; comment notes that autovacuum may also be triggered to run cleanup.
- `shiftList` takes exclusive locks on **all** deleted listpages simultaneously on the primary, even though replay can lock them one at a time (see `ginxlog.c::ginRedoDeleteListPages`'s explanatory comment).

## WAL records emitted

- `XLOG_GIN_UPDATE_META_PAGE` — combined metapage update + tail-page item append (or new tail-page link).
- `XLOG_GIN_INSERT_LISTPAGE` — initialize a new listpage from scratch (with full content).
- `XLOG_GIN_DELETE_LISTPAGE` — drop N head listpages after merge.

Tags: [from-comment, ginfast.c:1-15], [from-README, README:97-105, 501-508]; specifics [verified-by-code via record-emitter sites].

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
