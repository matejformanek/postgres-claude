# ginvacuum.c

- **Source path:** `source/src/backend/access/gin/ginvacuum.c` (882 lines)
- **Last verified commit:** `ef6a95c7c64`

## Purpose

VACUUM (`ginbulkdelete` / `ginvacuumcleanup`) for GIN. Drives the two-stage posting-tree page-deletion algorithm described in the README §"Page deletion". [from-comment, ginvacuum.c:1-13]

## `GinVacuumState`

Holds index, callback (heap-row-still-live test), per-vacuum tmpCxt, ginstate, buffer access strategy.

## Algorithm

1. **Walk entry-tree leaves in right-link order** (no parent traversal; entry tree leaves never get deleted, so right-link walk is safe). For each leaf:
   - For each key entry: if inline posting list → remove dead TIDs in place (recompress on the fly, emit `XLOG_GIN_VACUUM_DATA_LEAF_PAGE`-style recompression on the entry page via `XLOG_GIN_VACUUM_PAGE` FPI).
   - If posting-tree pointer → recursive vacuum of that posting tree.
2. **Posting-tree vacuum (stage 1)**: walk every leaf; remove dead TIDs via `ginRedoRecompress`-style segment recompression; emit `XLOG_GIN_VACUUM_DATA_LEAF_PAGE`. Track whether any leaf became empty.
3. **Posting-tree vacuum (stage 2, only if stage 1 found empty leaves)**: call `ginScanPostingTreeToDelete` which takes a **full cleanup lock on the root** (excludes all concurrent reads/inserts on this tree) and depth-first deletes empty pages. Page deletion emits `XLOG_GIN_DELETE_PAGE` after the left-sibling-pre-lock pattern.

## Locking [HIGH-RISK]

- **Entry-tree leaf scan**: pin+share-lock one page at a time during right-link walk. No parent pinning needed; entry-tree pages don't get deleted.
- **Posting-tree page deletion**: keeps E-lock on the left sibling of every page on the deletion path, per README §"Page deletion". This is the "pre-lock everything needed before unlinking" pattern that avoids right→left deadlock with `ginStepRight`.
- **Posting-tree cleanup lock on root**: blocks all new inserts and serializes against in-progress scans (which must release the root before stepping further). [from-README, README:398-403]
- **`GIN_DELETED` page recycling**: stamped with `deleteXid`; the page is gated against reuse by `ginPageRecyclable(page)` which checks `TransactionIdPrecedes(deleteXid, GlobalVisIndexLimitFor*)` (or equivalent globally-invisible test). Standby uses the same `deleteXid` for its conflict-equivalent gate (no recovery-conflict record emitted; the gate is purely XID-based at allocation time, mirroring nbtree's `BTPageIsRecyclable`). [from-README, README:419-470]

## WAL records emitted

- `XLOG_GIN_VACUUM_PAGE` — entry-tree leaf vacuum (full-page image).
- `XLOG_GIN_VACUUM_DATA_LEAF_PAGE` — posting-tree leaf incremental recompression.
- `XLOG_GIN_DELETE_PAGE` — posting-tree page deletion (3 blocks: target, parent, left sibling).

## Cross-references

- **Called by:** vacuum.c via `IndexAmRoutine` slots.
- **Calls into:** `gindatapage.c::ginScanPostingTreeToDelete`, `ginpostinglist.c` (decode/merge), `ginutil.c::ginPageRecyclable`.

## Open questions

- Whether the "first stage detects empty" optimization (delay calling `ginScanPostingTreeToDelete` unless stage 1 cleared a whole leaf) is correctness-required or just performance. The README presents it as performance. [inferred]

Tags: [from-README, README:389-470 — extensively cited]; behavior [verified-by-code at function dispatch sites].
