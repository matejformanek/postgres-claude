# nbtpage.c

- **Source path:** `source/src/backend/access/nbtree/nbtpage.c` (3152 lines)
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `nbtree.h` (`BTMetaPageData`, `BTPageOpaqueData`, `BTDeletedPageData`), `nbtxlog.c` (replay), `nbtree.c` (VACUUM driver), `nbtinsert.c` (page split is in there, but every buffer acquisition goes through `_bt_getbuf` here).

## Purpose

Btree page-level operations: metapage management, buffer acquisition wrappers (`_bt_getbuf`/`_bt_allocbuf`/`_bt_relbuf` and the lock helpers), the `_bt_pageinit`/`_bt_checkpage` invariants enforcer, all of the **page deletion** logic (two-stage: mark-half-dead + unlink), the in-place LP_DEAD/posting-update mutators (`_bt_delitems_vacuum`, `_bt_delitems_delete`, `_bt_delitems_delete_check`), and the pending-FSM bookkeeping that batches recyclable pages until the end of a VACUUM. [from-comment, nbtpage.c:14-21]

## Top-of-file note

> "Postgres btree pages look like ordinary relation pages. The opaque data at high addresses includes pointers to left and right siblings and flag data describing page state. The first page in a btree, page zero, is special — it stores meta-information describing the tree." [from-comment, nbtpage.c:14-19]

## Function map

### Metapage

- `_bt_initmetapage` (68) — fresh metapage layout, version `BTREE_VERSION` (=4), captures `allequalimage`.
- `_bt_upgrademetapage` (108) — upgrade v2 → v3 in place.
- `_bt_getmeta` (143, static) — get a typed pointer + handle the legacy versions.
- `_bt_vacuum_needs_cleanup` (180) — read `btm_last_cleanup_num_delpages` to decide if `btvacuumcleanup` can skip the scan.
- `_bt_set_cleanup_info` (233) — write back updated `btm_last_cleanup_num_delpages` (only if it actually changed, to avoid WAL noise).
- `_bt_getroot` / `_bt_gettrueroot` / `_bt_getrootheight` / `_bt_metaversion` (347 / 585 / 680 / 744) — root navigation via the relcache cache (`rd_amcache`), with the "fast root" indirection.

### Buffer helpers (the layer every other nbtree file uses)

- `_bt_checkpage` (802) — sanity-check page contents (size, special-area pointer, special-area magic) before any access. Used in lots of debug paths and in `btvacuumpage`.
- `_bt_getbuf` (850) — read existing buffer + optionally lock.
- `_bt_allocbuf` (874) — allocate a new buffer for write: first try FSM; for each FSM hit, verify the page is actually recyclable via `BTPageIsRecyclable`; on a fresh page allocation, extend with `ExtendBufferedRel(EB_LOCK_FIRST)`. **This is the function that emits `XLOG_BTREE_REUSE_PAGE` for Hot Standby conflict generation when a recycled deleted page's `safexid` is grabbed from the FSM.** [verified-by-code, nbtpage.c:874-1007]
- `_bt_relandgetbuf` (1008) — atomic release-and-acquire (used while descending the tree).
- `_bt_relbuf` (1044), `_bt_lockbuf` (1067), `_bt_unlockbuf` (1098), `_bt_conditionallockbuf` (1121), `_bt_upgradelockbufcleanup` (1137) — thin wrappers over `bufmgr.h` primitives.
- `_bt_pageinit` (1157) — `PageInit` + zero a full opaque area.

### Bulk-item mutation (LP_DEAD / VACUUM / dedup) under the buffer's exclusive lock

- `_bt_delitems_vacuum` (1182) — used by `btvacuumpage`. Deletes the listed offsets and applies posting-list "updates" (partial dead-TID removal from posting tuples). Emits `XLOG_BTREE_VACUUM`. Requires cleanup lock at entry.
- `_bt_delitems_delete` (1313, static) — analogous, but emits `XLOG_BTREE_DELETE` with a `snapshotConflictHorizon` for non-VACUUM deletion (simple/bottom-up delete from insert paths).
- `_bt_delitems_update` (1435, static) — common helper that builds the WAL payload describing posting-list updates.
- `_bt_delitems_delete_check` (1543, public) — wraps `_bt_delitems_delete`, but first asks the **tableam** (`heap_index_delete_tuples`) to confirm which TIDs are really dead and to produce the conflict horizon. This is the entry called from `_bt_simpledel_pass` and `_bt_bottomupdel_pass`.

### Page deletion — two-stage [HIGH-RISK SECTION]

#### Phase 1: `_bt_mark_page_halfdead` (2122)

Preconditions enforced at entry: leafbuf is **not** rightmost, **not** root, is leaf, is empty, is not half-dead yet. [verified-by-code, nbtpage.c:2142-2144]

Step-by-step:
1. Pre-flight: right sibling must not also be half-dead (`_bt_rightsib_halfdeadflag`). [verified-by-code, nbtpage.c:2160-2165]
2. **`_bt_lock_subtree_parent`** (2850, recursive): walk up the stack to find the parent of the *root* of the to-be-deleted subtree (which is usually just the leaf, but can be a "skinny" chain of internal pages when the leaf is the only descendant). Refuse if the chosen root is the rightmost child of the parent (with no siblings to absorb the keyspace). Returns the subtreeparent buffer locked in **BT_WRITE**. [from-comment, nbtpage.c:2168-2175; verified-by-code]
3. Verify the parent's two consecutive items: the one at `poffset` points to `topparent`, the next one points to `topparentrightsib`. [verified-by-code, nbtpage.c:2207-2227]
4. `PredicateLockPageCombine(rel, leafblkno, leafrightsib)` — SSI sees the keyspace transfer. [verified-by-code, nbtpage.c:2233]
5. **START_CRIT_SECTION.** Overwrite `topparent`'s downlink with `topparentrightsib`, delete the next pivot. Mark the leaf `BTP_HALF_DEAD` and overwrite its high key with a dummy `IndexTupleData` whose `t_tid.ip_blkid` field stores the topparent (via `BTreeTupleSetTopParent`). [verified-by-code, nbtpage.c:2235-2278]
6. Emit `XLOG_BTREE_MARK_PAGE_HALFDEAD`: block 0 = leaf (`REGBUF_WILL_INIT`), block 1 = subtree parent (incremental). [verified-by-code, nbtpage.c:2295-2308]

**Lock order in phase 1**: leaf (held, then dropped, then re-acquired AFTER stack search) → subtree parent (held). The leaf lock is *dropped* before calling `_bt_search` to build a fresh stack, then reacquired — see comments lines 1969-1973 and 2019-2021 explaining why this dance is needed to avoid deadlock.

#### Phase 2: `_bt_unlink_halfdead_page` (2349)

Locking order (explicitly documented at lines 2429-2437):

1. **leaf** (if target page is not the leaf itself), then
2. **left sibling** of the target — write-locked, walking right as needed if it has since split (the `while (P_ISDELETED(opaque) || opaque->btpo_next != target)` loop, lines 2445-2493).
3. **target page** itself (write-lock).
4. **right sibling** of target (write-lock).
5. **metapage** — only if we're deleting the next-to-last page on its level and may need to bump `btm_fastroot`/`btm_fastlevel`. [from-comment, nbtpage.c:2596-2602]

This is the canonical "move right, then up" lock-coupling for nbtree, identical to the order used in `_bt_split`. The comment explicitly says: *"We have to lock the pages we need to modify in the standard order: moving right, then up. Else we will deadlock against other writers."* [from-comment, nbtpage.c:2429-2431]

After all locks: `START_CRIT_SECTION` → fix left sibling's `btpo_next` (skip target) → fix right sibling's `btpo_prev` (skip target) → if a subtree-internal page is the target, update leaf's `topparent` link → call `BTPageSetDeleted(page, safexid)` where `safexid = ReadNextFullTransactionId()`. **This `safexid` is the recovery-conflict gate**: any in-flight scan that retained a stale link is advertising in its `PGPROC.xmin` a value ≤ this, holding back the global xmin horizon until the scan finishes; `BTPageIsRecyclable` checks `GlobalVisCheckRemovableFullXid` against this safexid before allowing the page back into use. [verified-by-code, nbtpage.c:2666-2697; nbtree.h:280-319]

WAL: `XLOG_BTREE_UNLINK_PAGE` (or `_META` variant if metapage updated). Block 0 = target (`REGBUF_WILL_INIT`), block 1 = left sib if any, block 2 = right sib, block 3 = leaf if different from target, block 4 = metapage if applicable. [verified-by-code, nbtpage.c:2708-2755]

After the WAL record: bookkeeping in `BTVacState.pendingpages[]` via `_bt_pendingfsm_add` so the deferred-FSM-add can later push the page into the FSM if its safexid becomes visible-to-all by end of VACUUM. [verified-by-code, nbtpage.c:2811]

#### Driver: `_bt_pagedel` (1832)

The outer loop iterates: phase 1 → repeated phase 2 until the leaf is fully deleted → if `*rightsib_empty`, move to right sibling and try to delete it too (chain of deletions to the right). The first iteration drops the leaf lock to build a search stack via `_bt_search`, then re-acquires it and restarts. [verified-by-code, nbtpage.c:1859-2100]

### Pending FSM finalization

- `_bt_pendingfsm_init` (2991) — palloc a buffer of up to `work_mem` pages worth of `BTPendingFSM` entries, but only if the optimisation is enabled (only `btbulkdelete` path).
- `_bt_pendingfsm_add` (3100) — record (target blkno, safexid) at deletion time.
- `_bt_pendingfsm_finalize` (3033) — at end of VACUUM, check each entry's safexid via the equivalent of `BTPageIsRecyclable` (without re-reading the page) and `RecordFreeIndexPage` if safe.

## Cross-references

- **Called by:** every other nbtree file via the buffer helpers; `nbtree.c:btvacuumpage` for the bulk-deletion path; `nbtinsert.c:_bt_simpledel_pass` and `nbtdedup.c:_bt_bottomupdel_pass` via `_bt_delitems_delete_check`.
- **Calls into:** `storage/bufmgr.c` (buffer acquisition/extension), `storage/predicate.c` (`PredicateLockPageCombine`), `storage/indexfsm.c` (`RecordFreeIndexPage`, `GetFreeIndexPage`), `access/transam/xact.c` (`ReadNextFullTransactionId`), `access/transam/xlog*.c` (WAL emission), `nbtsearch.c` (`_bt_search` from `_bt_pagedel`).

## Open questions

- **`_bt_lock_subtree_parent` recursion depth** — bounded by tree height, but the failure mode if the stack and the actual ancestor chain diverge (concurrent split *and* concurrent recycle of the original ancestor) is not exhaustively documented. The code defensively re-checks downlinks at each level. [unverified — page-deletion code is the second-most-fragile area in nbtree, after split locking]
- **Interaction between `_bt_pendingfsm_finalize` and Hot Standby**: the WAL replay side does not emit `XLOG_BTREE_REUSE_PAGE` until the *next* `_bt_allocbuf` actually pulls a page from the FSM. The replay-side conflict horizon is only at recycle, not at delete. Whether this is intentional vs. relies on the standby's `BTPageIsRecyclable` running on every getroot-side path was not verified. [unverified, but see nbtxlog.c:967-1001 explanatory comment]
