# nbtree/README — summary

- **Source path:** `source/src/backend/access/nbtree/README` (1082 lines)
- **Last verified commit:** `ef6a95c7c64`

## Purpose

Canonical narrative for the nbtree access method. It is the spec the C files implement and the authoritative source for the locking, deletion, recovery, and deduplication invariants. [from-README, README:1-12]

## The 12 ideas you must hold

1. **Lehman & Yao base.** Every page has a right-link and a high key, so a search can detect a concurrent split and recover by moving right; consequently, descending readers hold no inter-level locks. [from-README, README:6-29]
2. **Pivot vs non-pivot tuples.** Internal-page items and leaf high-keys are *pivot* tuples used only for navigation; leaf data items are non-pivot. Suffix truncation builds pivots that may have fewer attributes than the index. [from-README, README:31-55]
3. **Heap TID as final key column (v4 / "heapkeyspace").** Logical duplicates are physically ordered by heap TID, which makes every key in the tree unique and lets L&Y's "Ki < v <= Ki+1" invariant hold. [from-README, README:42-49]
4. **PG additions vs textbook L&Y.** Page-level read locks (because buffers are shared), left-sibling links (for backward scans), conservative parent-lock coupling during ascent, root-split handling, variable-size keys. [from-README, README:57-165]
5. **Scans only lock the leaf they're examining.** A scan reads a whole page's matching items into local memory, releases the lock, and processes off-page. The scan may keep a *pin* on the leaf to interlock against VACUUM TID recycling, or drop it and rely on an MVCC snapshot. [from-README, README:88-104, 443-489]
6. **VACUUM uses a "cycle ID" mechanism.** A 16-bit per-page counter set into both halves of any split that happens during a VACUUM run lets `btvacuumscan()` detect "split since I started" pages and backtrack via the right link to avoid missing tuples. [from-README, README:204-230]
7. **Page deletion is two-phase, never deletes rightmost pages, and works on entire skinny subtrees.** Phase 1 ("mark half-dead") removes the downlink and marks the leaf `BTP_HALF_DEAD`; phase 2 ("unlink") removes it from the sibling chain and stamps `BTPageSetDeleted(safexid)`. The key space moves *right*. [from-README, README:232-317]
8. **Deleted pages are kept as tombstones; recycled only after their safexid is globally invisible.** This is Lanin & Shasha's "drain technique"; implemented by stamping `FullTransactionId safexid` into the page contents and gating recycle on `GlobalVisCheckRemovableFullXid`. PG14 added "in-pass" recycling via per-VACUUM bookkeeping. [from-README, README:383-441]
9. **Backward scans handle deleted pages and split-left siblings via the move-left algorithm.** Original page is remembered; on left-link follow, the scan may have to walk right to find a live page whose right-link matches the original. [from-README, README:330-360]
10. **WAL split is two atomic actions.** One record covers the child-level split (left page update + right page formation + right-sibling left-link fixup + INCOMPLETE_SPLIT flag on left page); a *separate* record covers the parent downlink insertion that clears the flag. Crash between them leaves a recoverable inconsistency: the next inserter (or VACUUM) finishes the split via `_bt_finish_split`. [from-README, README:620-700]
11. **Three flavors of leaf-tuple deletion**: (a) opportunistic LP_DEAD setting by scans + later in-place removal under exclusive lock; (b) bottom-up deletion driven by executor hints (version churn); (c) deduplication that merges equal non-pivots into posting list tuples. All three share WAL records and the tableam delete infrastructure. [from-README, README:510-619]
12. **Fast-path insertion.** A backend caches the block number of the last leaf page it inserted into; if still the rightmost leaf with room, descend is skipped. Cache invalidation needs no interlock because there is only one rightmost leaf at any time. [from-README, README:491-509]

## Where each section is implemented

| README section | Implementing files |
|---|---|
| Base L&Y / search / move-right | `nbtsearch.c`, `nbtreadpage.c` |
| Insert + split + parent insert | `nbtinsert.c`, `nbtsplitloc.c` |
| Insert WAL emission | `nbtinsert.c` `_bt_insertonpg`, `_bt_split` |
| VACUUM linear scan + cycle ID | `nbtree.c` `btvacuumscan`/`btvacuumpage`, `nbtutils.c` `_bt_start_vacuum`/`_bt_vacuum_cycleid` |
| Page deletion 2-stage | `nbtpage.c` `_bt_pagedel`, `_bt_mark_page_halfdead`, `_bt_unlink_halfdead_page` |
| Deferred FSM recycling | `nbtpage.c` `_bt_pendingfsm_*`, `nbtree.h` `BTPageIsRecyclable` |
| Simple + bottom-up deletion | `nbtinsert.c` `_bt_delete_or_dedup_one_page`, `_bt_simpledel_pass`, `nbtdedup.c` `_bt_bottomupdel_pass` |
| Deduplication / posting lists | `nbtdedup.c`, `nbtree.h` `BTreeTuple{IsPosting,SetPosting,...}` |
| Suffix truncation | `nbtutils.c` `_bt_truncate`, `_bt_keep_natts*` |
| Split-location choice | `nbtsplitloc.c` `_bt_findsplitloc` |
| Build-from-sorted-input | `nbtsort.c` |
| WAL replay | `nbtxlog.c`, records typed in `nbtxlog.h` |
| Hot Standby quirks (no LP_DEAD set, ignore_killed_tuples=false) | `nbtree.c` btrescan, `nbtutils.c` `_bt_killitems` |
| Opclass validation | `nbtvalidate.c` |
| Scan-key preprocessing (incl. SAOP/skip arrays) | `nbtpreprocesskeys.c` |

## Highest-risk claims to spot-check before relying on this doc

1. **Page-split locking order** — see `nbtinsert.c.md` §locking. The README does not state the order in one place; it is reconstructed from `_bt_split` source and the comment at `nbtinsert.c:1908-1910` ("we couple the locks in the standard order: left to right"). [from-comment]
2. **`BTPageOpaque.btpo_cycleid` semantics for recovery-conflict** — actually used only by VACUUM to detect splits; **not** the recovery-conflict gate. The conflict gate is `BTDeletedPageData.safexid` written into the page contents at delete time, replayed via `XLOG_BTREE_REUSE_PAGE` carrying `snapshotConflictHorizon`. [verified-by-code, nbtxlog.c:967-1001, nbtree.h:232-318]
3. **"never delete rightmost"** — enforced both in primary `_bt_pagedel` (`nbtpage.c:1926`) and in `_bt_mark_page_halfdead`. [verified-by-code]

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
