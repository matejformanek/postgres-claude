# 2026-06-02 — access/nbtree spine synthesis

**Type:** interactive (worktree `ft_corpus_access_nbtree`).
**Outcome:** `knowledge/subsystems/access-nbtree.md`, 892 lines, 60
confidence-tagged cites, verified against source commit `4b0bf0788b0`.

## What this session did

Closed the priority-5 spine gap from `pg-claude-plan.md` §5.3. nbtree
had 15 per-file docs + 2 header docs already (the file-by-file phase
landed it in deep-read depth), but no directory-level synthesis. This
session distilled them.

The synthesis covers:

1. **Lehman-Yao base + the 3 large post-LY systems** (page deletion,
   dedup + bottom-up deletion, parallel build + parallel scan). Frames
   why the README is so much longer than a textbook L&Y proof.
2. **All seven key data structures** with `nbtree.h` line anchors:
   `BTPageOpaqueData`, the three tuple shapes, `BTMetaPageData`,
   `BTDeletedPageData`, `BTPageIsRecyclable` static-inline,
   `BTScanInsertData`, `BTInsertStateData`, `BTScanPosData`,
   `BTScanOpaqueData`, `BTVacState`, `BTParallelScanDescData`.
3. **23 invariants** tagged INV-nbt-1 to -23. The load-bearing ones:
   - INV-nbt-2: page-split lock-coupling left → child → right → original
     right sibling (`nbtinsert.c:1907-1911` canonical comment).
   - INV-nbt-3: split holds NO upward lock; parent insert is a SEPARATE
     WAL record; crash leaves recoverable `BTP_INCOMPLETE_SPLIT`.
   - INV-nbt-6: page deletion lock order leaf → left → target → right →
     meta — "moving right, then up" (`nbtpage.c:2429-2437`).
   - INV-nbt-9: `safexid` (`FullTransactionId`) is the SINGLE recycle
     gate, written identically by primary and standby; `BTPageIsRecyclable`
     is the runtime test.
   - INV-nbt-10: Hot Standby conflict for recycled pages is at RECYCLE
     time (`XLOG_BTREE_REUSE_PAGE`), not at delete time.
   - INV-nbt-12: `_bt_killitems` is safe under SHARE lock because of
     LSN re-check; uses fake LSNs for unlogged indexes.
   - INV-nbt-18: tuple-shape encoding is a hard upgrade event.
   - INV-nbt-21: drop-pin decision is per-rescan and immutable mid-scan.
4. **Three flavors of leaf-tuple deletion** (LP_DEAD simple; bottom-up;
   dedup) and the ordering inside `_bt_delete_or_dedup_one_page`.
5. **VACUUM driver** including the cycle-ID `backtrack:` mechanism, the
   `READ_STREAM_MAINTENANCE | FULL | USE_BATCHING` read stream, the
   pending-FSM deferral via `BTVacState.pendingpages[]`.
6. **Parallel index build** (DSM + `BTShared` + tuplesort + bulk_write
   bypass of bufmgr; two-spool unique-build).
7. **Parallel scan** (CV-based "claim next page" via `_bt_parallel_seize`
   / `_bt_parallel_release` / `_bt_parallel_primscan_schedule`).
8. **WAL replay** — 15 redo functions, replay lock order matching primary,
   the standby reuse-page conflict mechanism (the load-bearing comment
   at `nbtxlog.c:966-991`).
9. **§11 most-cited file:line table** as a quick-glance index — 55+
   anchors across `README`, `nbtree.c`, `nbtsearch.c`, `nbtinsert.c`,
   `nbtpage.c`, `nbtxlog.c`, `nbtree.h`, `nbtxlog.h`.
10. **§9 Open Questions** — 6 items. Most-asserted lock-ordering claim
    (O1: `_bt_getstackbuf` walking right past stale parents) lives in
    the README, not in code.

## Verification

All called-out line numbers were checked with `grep -n` against the
live source at commit `4b0bf0788b0` for:
- `nbtinsert.c`: `_bt_doinsert:105`, `_bt_check_unique:411`,
  `_bt_findinsertloc:829`, `_bt_insertonpg:1119`, `_bt_split:1489`,
  `_bt_insert_parent:2130`, `_bt_finish_split:2272`, `_bt_newlevel:2492`,
  `_bt_delete_or_dedup_one_page:2730`.
- `nbtpage.c`: `_bt_allocbuf:874`, `_bt_delitems_vacuum:1182`,
  `_bt_delitems_delete_check:1543`, `_bt_pagedel:1832`,
  `_bt_mark_page_halfdead:2122`, `_bt_unlink_halfdead_page:2349`,
  `_bt_lock_subtree_parent:2850`, `_bt_pendingfsm_finalize:3033`.
- `nbtree.c`: `bthandler:118`, `_bt_parallel_seize:873`,
  `_bt_parallel_release:1011`, `btbulkdelete:1122`, `btvacuumscan:1240`,
  `btvacuumpage:1415`.
- `nbtsearch.c`: `_bt_search:100`, `_bt_moveright:242`, `_bt_compare:689`,
  `_bt_first:883`, `_bt_next:1586`.

## What I did NOT do

- Did not register new rows in `files-examined.md` — all 15 nbtree files
  + 2 headers already in the registry from the original deep-read pass.
- Did not run amcheck, tests, or the dev cluster.
- Did not trace the speculative-insertion heap-side handshake (left as
  O6 in the per-file doc).
- Did not formalize the `_bt_getstackbuf` no-deadlock argument beyond
  citing the README (left as O1).

## Ledger updates

- `progress/coverage.md` — appended `access-nbtree` row.
- `progress/STATE.md` — bumped subsystem count 16→18 (22 incl.
  data-structures), updated Phase + Last-activity, added this session
  log + the earlier parser-rewrite session log to Recent.

## Followup candidates

- §9 O1: write a worked example walking `_bt_getstackbuf` through 3
  concurrent parent splits + 1 ancestor recycle. Pin the safety proof
  in code (not just README).
- §9 O4: spike the `LockRelationForExtension` removal in
  `btvacuumscan` — the XXX at `nbtree.c:1310-1312` has been there for
  a while. A small isolation-test should be enough to prove it.
- Add a `knowledge/data-structures/btpageopaque.md` (and a similar
  doc for `BTScanOpaqueData`) — the tuple-shape encoding is the kind
  of focused doc the data-structures/ tier exists for.
- Cross-link from `knowledge/architecture/access-methods.md` to this
  new subsystem doc as the reference implementation.

## Why this matters

nbtree's deletion + split paths are exactly the kind of "confident but
wrong" failure mode the Multigres lesson warned about. Concrete
mistakes this synthesis is structured to catch:

- Claiming readers take inter-level locks during descent (they don't).
- Claiming the split holds a parent lock through the downlink insert
  (it doesn't — that's a separate WAL record).
- Claiming the Hot Standby conflict for a page-delete is at delete
  time (it's at recycle time via `XLOG_BTREE_REUSE_PAGE`).
- Claiming `_bt_killitems` requires an exclusive lock (it doesn't —
  LSN re-check under SHARE).
- Claiming LP_DEAD on a posting tuple means SOME TIDs are dead (no —
  it means ALL TIDs in the list are dead).
- Treating internal pages as suffix-truncatable (they aren't).
- Calling `IndexTupleData->t_info` directly on a pivot tuple to read
  attribute count (gives wrong result — count is in `t_tid.ip_posid`).
