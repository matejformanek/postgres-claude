# nbtinsert.c

- **Source path:** `source/src/backend/access/nbtree/nbtinsert.c` (3064 lines)
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `nbtsearch.c` (`_bt_search`, `_bt_binsrch_insert`), `nbtsplitloc.c` (`_bt_findsplitloc` — the split-point heuristic), `nbtdedup.c` (`_bt_dedup_pass`, `_bt_bottomupdel_pass`), `nbtutils.c` (`_bt_mkscankey`, `_bt_truncate`), `nbtxlog.c` (`btree_xlog_insert`, `btree_xlog_split`, `btree_xlog_newroot`).

## Purpose

Insert path for nbtree: from `_bt_doinsert` (the entry called by `btinsert`) all the way through page splits, root-creation, parent-downlink insertion, and on-the-fly LP_DEAD / simple / bottom-up deletion when a page is about to overflow. The page-split machinery and its WAL emission live here. [from-comment, nbtinsert.c:1-13; verified-by-code]

## Functions (with line offsets)

- `_bt_doinsert` (105) — top-level insert. Builds a `BTScanInsertData`, descends via `_bt_search_insert`, runs uniqueness check if requested, finds the insert location, then calls `_bt_insertonpg`.
- `_bt_search_insert` (320) — wrapper around `_bt_search` (nbtsearch.c) plus the rightmost-leaf cache "fastpath" optimization (see README §"Fastpath For Index Insertion").
- `_bt_check_unique` (411) — uniqueness check for `UNIQUE_CHECK_YES` / `UNIQUE_CHECK_EXISTING` / `UNIQUE_CHECK_PARTIAL`. Returns the xact ID conflicting with our insert (for speculative wait), or `InvalidTransactionId` if unique. Sets LP_DEAD on dead duplicates it sees in passing.
- `_bt_findinsertloc` (829) — once at a leaf, walks right via `_bt_stepright` if needed (page splits since descent) and picks the final target offset. Also opportunistically triggers `_bt_delete_or_dedup_one_page` to free space.
- `_bt_stepright` (1041) — locking-careful right walk during insertion.
- `_bt_insertonpg` (1119) — the actual page mutation. Either fits in place (writes `XLOG_BTREE_INSERT_LEAF`/`_UPPER`/`_META`/`_POST`) or calls `_bt_split` + `_bt_insert_parent`.
- `_bt_split` (1489) — splits one page; emits `XLOG_BTREE_SPLIT_L`/`_R`.
- `_bt_insert_parent` (2130) — inserts the new downlink into the parent (recursively splitting if needed); handles root split via `_bt_newlevel`.
- `_bt_finish_split` (2272) — finish an `INCOMPLETE_SPLIT` left behind by a crash or error; callable from search paths.
- `_bt_getstackbuf` (2351) — re-find the parent's downlink offset, walking right if the parent has since split.
- `_bt_newlevel` (2492) — create a new root one level up; emits `XLOG_BTREE_NEWROOT`.
- `_bt_pgaddtup` (2678) — `PageAddItem` wrapper that handles the "first data item on internal page → minus infinity / truncated to zero attrs" rule.
- `_bt_delete_or_dedup_one_page` (2730) — opportunistic last-line-of-defense to avoid splitting: simple-delete (LP_DEAD) → bottom-up delete → dedup.
- `_bt_simpledel_pass` (2859) — emits `XLOG_BTREE_DELETE` for any tuples confirmed dead by tableam.
- `_bt_deadblocks` (2985) / `_bt_blk_cmp` (3058) — heap-block coalescing helper for the delete batch.

## Key invariants and locking [HIGH-RISK SECTION]

### Page split (`_bt_split`)

The split holds **up to four** buffer locks simultaneously, acquired in a strict order:

1. **Origpage (left)** — already write-locked on entry by caller. [verified-by-code, nbtinsert.c:1463-1466]
2. **`cbuf` (child being completed, internal-page splits only)** — already write-locked on entry; will have its `BTP_INCOMPLETE_SPLIT` cleared. [verified-by-code, nbtinsert.c:1469-1473]
3. **New right page (`rbuf`)** — allocated and write-locked via `_bt_allocbuf` *after* the new left high key was prepared. [verified-by-code, nbtinsert.c:1741]
4. **Old right sibling (`sbuf`)** — `_bt_getbuf(rel, oopaque->btpo_next, BT_WRITE)`, acquired last. Comment at lines 1908-1910 explicitly states: *"We are guaranteed that this is deadlock-free, since we couple the locks in the standard order: left to right."* [from-comment, nbtinsert.c:1907-1911]

The order matters because every other writer that needs both pages will acquire them in the same left-to-right order. **No upward locking** is held during the split itself; the parent downlink insertion is a *separate* WAL record, performed under a different set of locks by `_bt_insert_parent`. This is what produces transient `INCOMPLETE_SPLIT` pages on crash.

The critical section starts only after the right sibling is locked (line 1952), because everything before is on a temporary `PGAlignedBlock leftpage_buf` that can be discarded on error. [from-comment, nbtinsert.c:1944-1951]

Order of dirty-marking and PageSetLSN inside the crit section: `MarkBufferDirty(buf)` then `MarkBufferDirty(rbuf)` then (if not rightmost) `MarkBufferDirty(sbuf)` then (if internal) `MarkBufferDirty(cbuf)`. Same order for `PageSetLSN`. [verified-by-code, nbtinsert.c:1974-2094]

WAL: `XLOG_BTREE_SPLIT_L` if `newitemonleft`, else `_R`. Block 0 = original/left page (incremental), block 1 = new right page (full image, `REGBUF_WILL_INIT`), block 2 = original right sibling (left-link updated) if not rightmost, block 3 = child page (`INCOMPLETE_SPLIT` cleared) if not leaf. [verified-by-code, nbtinsert.c:1996-2083]

### Parent insertion (`_bt_insert_parent`)

- After split, the caller still holds locks on **both** `buf` (left/origpage) and `rbuf` (new right). The right lock is released early; the left lock survives until the parent insertion completes because the `INCOMPLETE_SPLIT` flag on left **must** be cleared as part of the *same* atomic WAL record as the parent downlink insertion. [from-comment, nbtinsert.c:2113-2123]
- If `stack` is `NULL` and we just split the true root: `_bt_newlevel` creates the new root atomically and writes `XLOG_BTREE_NEWROOT`. [verified-by-code, nbtinsert.c:2152-2164]
- If `stack` is stale (parent split too since our descent), we re-descend to the right level and walk right via `_bt_getstackbuf`. [from-README, README:124-137]
- Parent insert is a normal call to `_bt_insertonpg` with `cbuf = buf` (the left child), which is how the WAL record `XLOG_BTREE_INSERT_UPPER` carries the child block as backup block 1 and clears its `INCOMPLETE_SPLIT` flag inside the parent's WAL record. [verified-by-code, nbtinsert.c:1322-1330, 1362-1363]

### Other invariants

- `_bt_insertonpg` assertion: `!P_INCOMPLETE_SPLIT(opaque)` — caller is responsible for finishing splits via `_bt_finish_split` before reaching this point. [verified-by-code, nbtinsert.c:1160-1161]
- Internal pages always have exactly one "minus infinity" item at `P_FIRSTDATAKEY`; new items are inserted at offsets strictly greater than that. [verified-by-code, nbtinsert.c:1163-1169]
- Posting list split + page split is handled as a single atomic action, with `origpagepostingoff` standing in for "the imaginary pre-split posting tuple position". The `xl_btree_split.postingoff` field is non-zero only when the REDO routine must rebuild a posting tuple for the left page. [from-comment, nbtinsert.c:1604-1620; nbtxlog.h:116-139]
- Suffix truncation for the new left high key: leaf splits truncate via `_bt_truncate(rel, lastleft, firstright, itup_key)` (nbtutils.c). Internal-page splits use `firstright` *as-is* — suffix truncation on internal pages would break the "unbroken seam of identical separator keys" invariant. [from-comment, nbtinsert.c:1685-1714]
- `PredicateLockPageSplit(rel, buf-blk, rbuf-blk)` is called after `_bt_split` returns and *before* `_bt_insert_parent`, so SSI sees the split atomically. [verified-by-code, nbtinsert.c:1234-1236]

## Cross-references

- **Called by:** `nbtree.c:btinsert` via `_bt_doinsert`.
- **Calls into:** `nbtsearch.c` (`_bt_search`, `_bt_binsrch_insert`, `_bt_moveright`), `nbtsplitloc.c` (`_bt_findsplitloc`), `nbtutils.c` (`_bt_mkscankey`, `_bt_truncate`, `_bt_check_third_page`), `nbtdedup.c` (`_bt_dedup_pass`, `_bt_bottomupdel_pass`), `nbtpage.c` (`_bt_getbuf`, `_bt_allocbuf`, `_bt_relbuf`, `_bt_delitems_delete_check`), `storage/predicate.c` (`PredicateLockPageSplit`, `CheckForSerializableConflictIn`).

## Open questions

- **Lock-ordering proof for `_bt_insert_parent` re-finding a stale stack.** When `_bt_getstackbuf` walks right past several split parents, it acquires/releases the parent lock between pages; this is documented as safe but the formal argument (no deadlock with another inserter ascending) is in the README, not in the code comments. [from-README, README:139-156] **Highest-risk locking claim.**
- **Speculative insertion path** (`UNIQUE_CHECK_INSERT_INPROGRESS`) interacts with `_bt_check_unique` via `speculativeToken`; the heap-side handshake was not traced. [unverified]

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
- [subsystems/access-nbtree.md](../../../../../subsystems/access-nbtree.md)
