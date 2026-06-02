# Subsystem: access/nbtree (B-tree access method)

- **Path:** `source/src/backend/access/nbtree/` (13 `.c` files + `README`),
  `source/src/include/access/nbtree.h`, `source/src/include/access/nbtxlog.h`
- **Verified against commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
  (2026-06-01 refresh anchor)
- **Confidence:** verified=42, from-README=13, from-comment=20, inferred=3,
  unverified=5 (Open Questions §9)
- **Primary README:** `source/src/backend/access/nbtree/README` (1082 lines —
  the canonical Lehman-Yao + page-deletion + dedup + WAL essay; everything
  else implements what this file specifies)

## 1. Purpose

`nbtree` is the default index AM in PostgreSQL — the workhorse behind every
B-tree the user creates (and the only AM that meets every catalog index
requirement: unique, includes, included key, parallel build, parallel scan,
backward scan, SAOP/skip-scan, index-only scan, ordered scan, SSI predicate
locks). The README is the authoritative spec; the C files are its
implementation.

Conceptually nbtree is **Lehman-Yao + PG additions** plus three large
post-LY systems built on top:

1. **Lehman-Yao (L&Y) base.** Right-links + high keys let readers recover
   from concurrent splits without inter-level locks; descent holds at most
   one buffer lock at a time. [from-README] `README:6-29`,
   [verified-by-code] `nbtsearch.c:182-186`.
2. **Page deletion** (Lanin-Shasha-style two-phase) — NOT in textbook L&Y;
   handles VACUUM-driven removal of empty pages without breaking readers.
3. **Deduplication + posting-list tuples** — last-resort space saving
   before a split, with executor-hinted "bottom-up deletion" pruning
   version churn.
4. **Parallel index build + parallel scan** — DSM-resident coordination
   over a sorted bulk-write loader, and a CV-based "claim next page"
   protocol for read scans.

The reason this subsystem is so large (~35 KB of `.h`, ~70 KB of `.c` +
1000 lines of README) is that those four systems compose: every "simple"
operation (insert, delete-one-row, scan-forward) must be safe against
concurrent invocations of all the others, AND replayable on a Hot Standby
where the WAL records are observed in a different lock regime.

This synthesis distills the 15 per-file docs under
`knowledge/files/src/backend/access/nbtree/` (+ the two header docs) into
the directory-level map.

## 2. Key files

| File | Role | Per-file doc |
|---|---|---|
| `README` (1082 lines) | Canonical L&Y / page-deletion / dedup / WAL design essay | [via `knowledge/files/src/backend/access/nbtree/README.md`] |
| `nbtree.c` (1854 lines) | Public AM surface — `bthandler` `IndexAmRoutine`, scan lifecycle, VACUUM driver loop, parallel-scan coordinator | [via `nbtree.c.md`] |
| `nbtsearch.c` (2237 lines) | Tree descent: `_bt_search`, `_bt_moveright`, `_bt_binsrch`, `_bt_compare`, `_bt_first`, `_bt_next`, the move-left algorithm for backward scans | [via `nbtsearch.c.md`] |
| `nbtinsert.c` (3064 lines) | Insert path + page split + parent-downlink insertion + opportunistic delete/dedup. The split lock-coupling lives here. | [via `nbtinsert.c.md`] |
| `nbtpage.c` (3152 lines) | Buffer helpers (`_bt_getbuf`/`_bt_allocbuf`/`_bt_relbuf`), metapage management, two-phase **page deletion**, in-place item mutation under buffer lock | [via `nbtpage.c.md`] |
| `nbtxlog.c` (1117 lines) | WAL replay (`btree_redo`) — one handler per `XLOG_BTREE_*` info byte | [via `nbtxlog.c.md`] |
| `nbtutils.c` (1218 lines) | Miscellaneous helpers — `_bt_mkscankey`, `_bt_killitems` (LP_DEAD batching), `_bt_truncate` (suffix truncation), `_bt_check_third_page` (1/3-page-size limit), vacuum-cycle-ID slot mgmt | [via `nbtutils.c.md`] |
| `nbtdedup.c` (1105 lines) | Deduplication + bottom-up deletion + posting-list tuple ops (`_bt_swap_posting`, `_bt_form_posting`, `_bt_update_posting`) | [via `nbtdedup.c.md`] |
| `nbtsplitloc.c` (1185 lines) | `_bt_findsplitloc` — multi-objective split-point heuristic (byte-balance × truncation depth × duplicate-run avoidance × single-value strategy × fillfactor only on rightmost) | [via `nbtsplitloc.c.md`] |
| `nbtsort.c` (1971 lines) | Build from sorted input — parallel build, bulk_write bypassing buffer cache, build-time dedup | [via `nbtsort.c.md`] |
| `nbtpreprocesskeys.c` (2857 lines) | Scan-key preprocessing — dedup/contradict, SAOP arrays, skip arrays, REQFWD/REQBKWD flags | [via `nbtpreprocesskeys.c.md`] |
| `nbtvalidate.c` | Opclass validator: strategies 1..5, support fns 1..6 | [via `nbtvalidate.c.md`] |
| `nbtcompare.c` | Built-in `BTORDER_PROC` for trivial datatypes | [via `nbtcompare.c.md`] |
| `nbtreadpage.c` | Per-page read loop and array-key advancement (extracted from `nbtsearch.c`) | (no per-file doc — covered in `nbtsearch.c.md`) |

### Header anchors

| Header | What it defines |
|---|---|
| `include/access/nbtree.h` (1334 lines) | AM-internal types: `BTPageOpaqueData`, `BTMetaPageData`, `BTDeletedPageData`, the three tuple shapes (non-pivot/pivot/posting), scan/insert/dedup/vacuum state structs, `BTPageIsRecyclable` static-inline, `BTPageSetDeleted` static-inline | [via `nbtree.h.md`] |
| `include/access/nbtxlog.h` (367 lines) | 14 `XLOG_BTREE_*` info bytes + record structs + the canonical comment block on split WAL design (`:89-152`) | [via `nbtxlog.h.md`] |

## 3. Key data structures

### Page layout — `BTPageOpaqueData` (`nbtree.h:63-72`)

Five fields in the special area at the page tail: `btpo_prev`, `btpo_next`,
`btpo_level` (0 = leaf), `btpo_flags` (`BTP_*` bits), `btpo_cycleid`
(16-bit VACUUM cycle ID). The `BTP_*` flag bits (`nbtree.h:76-85`):
`LEAF`, `ROOT`, `DELETED`, `META`, `HALF_DEAD`, `SPLIT_END`,
`HAS_GARBAGE` (deprecated), `INCOMPLETE_SPLIT`, `HAS_FULLXID`.

`BTP_HAS_FULLXID` is the critical recent addition — when set, the special
area is followed by a `BTDeletedPageData` in the tuple area containing a
`FullTransactionId safexid` (see §4 "Page deletion").

### Three tuple shapes — `nbtree.h:372-549`

Distinguished by status bits in `t_info` (`INDEX_ALT_TID_MASK`) and the
top nibble of `t_tid.ip_posid` (`BT_STATUS_OFFSET_MASK = 0xF000`):

1. **Non-pivot plain** (leaf data tuple): `INDEX_ALT_TID_MASK` clear.
   `t_tid` is a real heap TID. Attribute count implicit.
2. **Pivot** (internal pages + leaf high keys): `INDEX_ALT_TID_MASK` set,
   `BT_IS_POSTING` clear. `t_tid.ip_blkid` is the downlink (for internal
   pages) or `topparent` (for half-dead leaves). Low 12 bits of
   `ip_posid` = number of key attributes; bit `BT_PIVOT_HEAP_TID_ATTR`
   (`0x1000`) signals an appended tiebreaker heap TID at the tuple tail.
3. **Posting-list tuple** (deduplicated group on leaf):
   `INDEX_ALT_TID_MASK` set, `BT_IS_POSTING` (`0x2000`) set.
   `t_tid.ip_blkid` is the byte offset within the tuple to the start of
   the posting list (`ItemPointerData[]`); low 12 bits of `ip_posid` =
   TID count.

This encoding is **the single most error-prone convention in the
codebase** — the inline accessors `BTreeTupleIsPivot`,
`BTreeTupleIsPosting`, `BTreeTupleGet/SetNAtts`,
`BTreeTupleGet/SetDownLink`, `BTreeTupleGet/SetTopParent`,
`BTreeTupleGetHeapTID` (`nbtree.h:480-677`) are not optional. Direct
field access will produce wrong results. [via `nbtree.h.md`]

### Metapage — `BTMetaPageData` (`nbtree.h:104-120`)

`btm_root`/`btm_level` (real root) vs `btm_fastroot`/`btm_fastlevel`
(Lanin-Shasha fast-root optimisation — points at the lowest level whose
upper part is just a chain). `btm_allequalimage` (true iff every
opclass provides `BTEQUALIMAGE_PROC` — gates deduplication safety).
`btm_last_cleanup_num_delpages` (counter that lets the next VACUUM's
`btvacuumcleanup` short-circuit). Version 4 since 2019; v2/v3 read-only.

### `BTDeletedPageData` (`nbtree.h:234-237`)

A single `FullTransactionId safexid` written into the tuple area of a
deleted page (NOT into the opaque area). Stamped by `BTPageSetDeleted`
(`nbtree.h:239-258`). **This is the recycle gate.** Both the primary
(`_bt_unlink_halfdead_page`) and standby replay (`btree_xlog_unlink_page`)
must write the same value. [verified-by-code]

### `BTPageIsRecyclable` static-inline (`nbtree.h:291-319`)

The canonical "safe to recycle this page from the FSM?" test. Reads the
embedded `safexid` and calls `GlobalVisCheckRemovableFullXid(heaprel,
safexid)`. The standby mirror is the `XLOG_BTREE_REUSE_PAGE`
snapshot-conflict mechanism — see §4 "WAL replay invariants".

### Scan/insert state

- `BTStackData` (`nbtree.h:743-750`): descent stack — (block, offset) of
  each pivot tuple visited. Used by insert/page-delete to find the
  parent later.
- `BTScanInsertData` (`nbtree.h:795-805`): the insertion scankey —
  `heapkeyspace`/`allequalimage`/`anynullkeys`/`nextkey`/`backward`/
  `scantid`/`keysz`/`scankeys[INDEX_MAX_KEYS]`.
- `BTInsertStateData` (`nbtree.h:820-844`): per-insert working area
  including the `bounds_valid`/`low`/`stricthigh` cache for
  `_bt_binsrch_insert`, and `postingoff` (-1 for "overlaps an LP_DEAD
  posting").
- `BTScanPosData` (`nbtree.h:962-1000`): per-page item cache built by
  `_bt_readpage` — holds `currPage`/`prevPage`/`nextPage`/`lsn`,
  cursors, `items[MaxTIDsPerBTreePage]`.
- `BTScanOpaqueData` (`nbtree.h:1053-1095`): per-scan opaque state.
  `qual_ok`/`numberOfKeys`/`keyData[]` from preprocessing;
  `arrayKeys[]`/`orderProcs[]`/`arrayContext`; `killedItems[]`/`numKilled`
  for `kill_prior_tuple` batching; `dropPin` decision; `currPos`/`markPos`.

### VACUUM state — `BTVacState` (`nbtree.h:331-347`)

Per-VACUUM-pass state passed through `btvacuumpage` → `_bt_pagedel` →
`_bt_pendingfsm_*`. Includes the `pagedelcontext` AllocSet (to throw
away deletion-time allocations) and the `pendingpages[]` buffer of
`(target_blkno, safexid)` pairs deferred until end of VACUUM.

### Parallel-scan state — `BTParallelScanDescData` (`nbtree.c:69-93`)

DSM-resident coordination struct: `LWLock btps_lock` +
`ConditionVariable btps_cv`, next/last page block numbers, trailing
`btps_arrElems[FLEXIBLE_ARRAY_MEMBER]` for SAOP/skip-array state.
`BTPS_State` enum (`nbtree.c:56-63`): `NOT_INITIALIZED` / `NEED_PRIMSCAN`
/ `ADVANCING` / `IDLE` / `DONE`.

## 4. Core algorithms / control flow

### Descent — `_bt_search` (`nbtsearch.c:100`)

```
_bt_search(rel, heaprel, key, *bufP, access, snapshot)
  for each level from root to leaf:
    _bt_moveright(bufP, ...)   ← L&Y right-walk on concurrent split
    binary-search the page for the next downlink
    _bt_relandgetbuf(rel, *bufP, downlink, ...)   ← atomic release-and-acquire
  return descent stack
```

[verified-by-code] `nbtsearch.c:100-241`.

**Lock-coupling discipline:** descent holds at most ONE buffer lock at a
time. The L&Y promise. `_bt_relandgetbuf` (`nbtpage.c:1008`) is the
atomic primitive. Optimisation: when `access == BT_WRITE` and the next
level is the leaf level, the caller takes the leaf buffer with
`BT_WRITE` directly to save a release/reacquire cycle (line 179-180).

### Right-walk — `_bt_moveright` (`nbtsearch.c:242`)

Walks right while the current page's high key is `< scankey` (`<=` for
`nextkey`). Pages along the way may be `P_IGNORE` (half-dead or
deleted). The walk terminates because pages are never re-renamed and
the rightmost page has `btpo_next == P_NONE`.

**Opportunistic split-finish:** when `forupdate == true`, if
`_bt_moveright` encounters a page with `BTP_INCOMPLETE_SPLIT`, it
upgrades to write lock if needed and calls `_bt_finish_split`
(`nbtinsert.c:2272`). [verified-by-code] `nbtsearch.c:283-305`.

### Insert — `_bt_doinsert` → `_bt_insertonpg` (`nbtinsert.c:105, :1119`)

```
_bt_doinsert(rel, itup, ...)
  build BTScanInsert key (incl. scantid = itup's heap TID)
  _bt_search_insert(...)         ← _bt_search + rightmost-leaf cache
  if (unique) _bt_check_unique(...)
  _bt_findinsertloc(...)         ← may step right + opportunistic delete/dedup
  _bt_insertonpg(...)            ← page mutation + WAL
    if fits in place:
      emit XLOG_BTREE_INSERT_{LEAF,UPPER,META,POST}
    else:
      _bt_split(...)             ← page-split machinery
      _bt_insert_parent(...)
```

[verified-by-code] `nbtinsert.c:105-1117`. `_bt_findinsertloc`
(`:829`) handles the "page split since descent" case by walking right
via `_bt_stepright` (`:1041`). Before signalling "no space, must
split", it opportunistically calls `_bt_delete_or_dedup_one_page`
(`:2730`) which tries, in order: (1) simple-delete of LP_DEAD-marked
items, (2) bottom-up deletion driven by executor hints, (3) deduplication.

### Page split — `_bt_split` (`nbtinsert.c:1489`) [HIGH-RISK]

Holds **up to four buffer locks simultaneously**, acquired in strict
left-to-right order:

1. **Origpage (left)** — already write-locked on entry.
2. **`cbuf` (child being completed, internal-page splits only)** —
   already write-locked on entry; will have `BTP_INCOMPLETE_SPLIT`
   cleared atomically with the parent insert (line 1469-1473).
3. **New right page (`rbuf`)** — allocated via `_bt_allocbuf`
   (`nbtpage.c:874`) and write-locked (line 1741).
4. **Old right sibling (`sbuf`)** — `_bt_getbuf` last (line 1908-1910).
   The comment at `nbtinsert.c:1907-1911` is canonical:

   > *"We are guaranteed that this is deadlock-free, since we couple
   > the locks in the standard order: left to right."*

The critical section starts only after the right sibling is locked
(line 1952), because everything before is on a temporary
`PGAlignedBlock leftpage_buf` discardable on error (line 1944-1951).
Dirty-mark + `PageSetLSN` order: left → right → original right sibling
(if not rightmost) → child (if internal). [verified-by-code]
`nbtinsert.c:1974-2094`.

**No upward locking** during the split itself. The parent downlink
insertion is a SEPARATE WAL record. This is what produces transient
`BTP_INCOMPLETE_SPLIT` pages on crash, recovered by `_bt_finish_split`.

WAL emitted: `XLOG_BTREE_SPLIT_L` if `newitemonleft`, else `_R`. Backup
blocks: 0=left (incremental), 1=right (full image via `_bt_restore_page`),
2=original right sibling (if not rightmost), 3=child (if internal).
[verified-by-code] `nbtinsert.c:1996-2083`.

### Parent insertion — `_bt_insert_parent` (`nbtinsert.c:2130`)

After split, both `buf` (left) and `rbuf` (right) are still locked.
`rbuf` is released early; `buf` survives until the parent insertion
completes because `BTP_INCOMPLETE_SPLIT` on the left page must clear
atomically with the parent downlink insertion. [from-comment]
`nbtinsert.c:2113-2123`.

Three branches:
- `stack == NULL` AND we just split the true root → `_bt_newlevel`
  (`nbtinsert.c:2492`) creates the new root and writes
  `XLOG_BTREE_NEWROOT`.
- Stack stale (parent itself split) → re-descend via `_bt_getstackbuf`
  (`nbtinsert.c:2351`) which walks right to find the parent that now
  contains our downlink. [from-README] `README:124-137`.
- Otherwise → normal recursive `_bt_insertonpg(cbuf = buf)`, emitting
  `XLOG_BTREE_INSERT_UPPER` whose backup block 1 is the left child (so
  REDO clears `INCOMPLETE_SPLIT` atomically with the parent insert).

### Split-point choice — `_bt_findsplitloc` (`nbtsplitloc.c`)

Multi-objective heuristic balancing:

1. Even byte-balance between halves (primary goal).
2. Maximize suffix-truncation effectiveness — pick a point where the
   first non-equal attribute between `lastleft` and `firstright`
   appears as early as possible, so the new left high key (future
   parent downlink) is as short as possible.
3. Avoid breaking duplicate runs across pages.
4. Special "all-same-value" page → `SPLIT_SINGLE_VALUE` (96% fillfactor
   on the left, near-empty right).
5. `BTREE_DEFAULT_FILLFACTOR` only applies to RIGHTMOST-page splits;
   non-rightmost splits go even.

[from-README] `README:158-164, :822-901`. The fillfactor distinction is
hardcoded in `nbtree.h:190-203`.

**Internal-page splits cannot use suffix truncation** — would break the
"unbroken seam of identical separator keys" invariant. So
`firstright` is used as-is on internal-page splits. [from-comment]
`nbtinsert.c:1685-1714`.

### Page deletion — two-phase, in `nbtpage.c` [HIGH-RISK]

Driver: `_bt_pagedel` (`nbtpage.c:1832`). Iterates phase 1 → phase 2
→ optionally chase rightward chain of empty pages.

#### Phase 1 — `_bt_mark_page_halfdead` (`nbtpage.c:2122`)

Preconditions: leaf is not rightmost, not root, is empty, not already
half-dead. `_bt_rightsib_halfdeadflag` pre-flight check (line
2160-2165).

**`_bt_lock_subtree_parent`** (`nbtpage.c:2850`, recursive): walks up
the stack to find the parent of the *root of the to-be-deleted subtree*
(usually just the leaf; can be a chain of skinny internal pages whose
only descendant is the empty leaf). **Refuses** if the chosen subtree
root is the rightmost child of the parent — there's nowhere to send
the keyspace.

Then under critical section:
1. Overwrite `topparent`'s downlink with `topparentrightsib`.
2. Delete the next pivot in the parent.
3. Mark leaf `BTP_HALF_DEAD`.
4. Overwrite the leaf's high key with a dummy `IndexTupleData` whose
   `t_tid.ip_blkid` stores the topparent (via `BTreeTupleSetTopParent`).
5. Emit `XLOG_BTREE_MARK_PAGE_HALFDEAD` (block 0 = leaf REGBUF_WILL_INIT,
   block 1 = subtree parent incremental).

[verified-by-code] `nbtpage.c:2235-2308`.

#### Phase 2 — `_bt_unlink_halfdead_page` (`nbtpage.c:2349`)

**Lock acquisition order, explicitly documented at lines 2429-2437**:

1. **leaf** (if target is not the leaf itself).
2. **left sibling** of target — write-lock, walking right if it has
   since split (lines 2445-2493 — the `while (P_ISDELETED(opaque) ||
   opaque->btpo_next != target)` loop).
3. **target page** itself.
4. **right sibling** of target.
5. **metapage** — only if deleting the next-to-last page on its level
   may bump `btm_fastroot`/`btm_fastlevel` (lines 2596-2602).

The comment is canonical:
> *"We have to lock the pages we need to modify in the standard order:
> moving right, then up. Else we will deadlock against other writers."*

Then critical section: fix left sibling's `btpo_next` → fix right
sibling's `btpo_prev` → if subtree-internal target, update leaf's
topparent link → `BTPageSetDeleted(page, ReadNextFullTransactionId())`.

**`safexid = ReadNextFullTransactionId()` at delete time is THE recycle
gate.** Any in-flight scan that holds a stale link to this page is
advertising a snapshot xmin ≤ this; `BTPageIsRecyclable` checks
`GlobalVisCheckRemovableFullXid` against this safexid before allowing
the page back into use.

WAL: `XLOG_BTREE_UNLINK_PAGE` (or `_META`). Blocks: 0=target
(REGBUF_WILL_INIT), 1=left sib, 2=right sib, 3=leaf if separate,
4=metapage if applicable.

After WAL: `_bt_pendingfsm_add` records `(target, safexid)` in the
`BTVacState.pendingpages[]` buffer. At end of VACUUM,
`_bt_pendingfsm_finalize` (`nbtpage.c:3033`) checks each entry's
safexid and `RecordFreeIndexPage` if globally visible — PG 14+ "in-pass"
recycling.

### Scan iteration — `_bt_first` / `_bt_next` / `_bt_steppage`

`_bt_first` (`nbtsearch.c:883`) — initial scan positioning. Builds the
insertion scankey from preprocessed search keys, descends via
`_bt_search`, hands off to `_bt_readfirstpage`.

`_bt_next` (`nbtsearch.c:1586`) — return next item from the cached
`BTScanPosData`; if exhausted, calls `_bt_steppage` to cross to sibling.

**Drop-pin policy** (`_bt_drop_lock_and_maybe_pin`, `nbtsearch.c:55`):
always drop the lock between page accesses; drop the pin too iff
`so->dropPin`. The decision was set once in `btrescan` (`nbtree.c:419-421`)
and never changes mid-scan:

```c
so->dropPin = !xs_want_itup && IsMVCCLikeSnapshot && heapRelation != NULL;
```

Index-only scans must keep the pin (need to keep visibility-map
interlock); non-MVCC scans must keep the pin (TID-recycle race).

**Backward scans use `_bt_lock_and_validate_left`** (`nbtsearch.c:1975`),
the move-left algorithm. After taking the left-link, the page must
have `btpo_next == lastcurrblkno`, else re-walk right. Handles
concurrently-deleted intermediate pages. [from-README] `README:330-360`.

### `kill_prior_tuple` / LP_DEAD setting

`btgettuple` (`nbtree.c:230`) appends to `so->killedItems[]` whenever
the executor sets `xs_heap_continue=false` because the row turned out
to be invisible/expired. The actual LP_DEAD bit set happens
**lazily** at page-leave time via `_bt_killitems` (in `nbtutils.c`):
under a SHARE buffer lock, re-checks the page LSN to make sure nothing
changed (uses fake LSNs for unlogged indexes), then sets the LP_DEAD
bits on confirmed-dead items.

[from-README] `README:478-489`. The LSN check is what makes setting
LP_DEAD safe without holding an exclusive lock.

### Three flavors of leaf-tuple deletion [from-README] `README:510-619`

1. **Opportunistic LP_DEAD setting by scans** (above) + later in-place
   removal under exclusive lock via `_bt_simpledel_pass`
   (`nbtinsert.c:2859`) — emits `XLOG_BTREE_DELETE` with a
   `snapshotConflictHorizon`.
2. **Bottom-up deletion** (`_bt_bottomupdel_pass` in `nbtdedup.c`) —
   triggered by executor hint `indexUnchanged` (version churn). Batches
   up duplicates, asks the tableam (`heap_index_delete_tuples`) to
   confirm which TIDs are actually dead, then deletes them. Same
   `XLOG_BTREE_DELETE` shape.
3. **Deduplication** (`_bt_dedup_pass`) — merges consecutive equal
   non-pivots into one posting-list tuple. Emits `XLOG_BTREE_DEDUP`.

All three are "last line of defense before a split" via
`_bt_delete_or_dedup_one_page` (`nbtinsert.c:2730`). The order matters:
simple-delete → bottom-up delete → dedup.

### VACUUM driver — `btbulkdelete` → `btvacuumscan` → `btvacuumpage`

`btbulkdelete` (`nbtree.c:1122`) wraps `btvacuumscan` in
`PG_ENSURE_ERROR_CLEANUP(_bt_end_vacuum_callback)` so the
vacuum-cycle-ID slot in shared memory is always released.

`btvacuumscan` (`nbtree.c:1240`) uses a `READ_STREAM_MAINTENANCE |
READ_STREAM_FULL | READ_STREAM_USE_BATCHING` read stream over the
index in **block order**. On each outer iteration, re-reads the
relation length under `LockRelationForExtension(ExclusiveLock)` to
pick up pages added during the scan (the XXX at `nbtree.c:1310-1312`
suggests this lock may now be removable).

`btvacuumpage` (`nbtree.c:1415`) — per-block worker. The `backtrack:`
label (line 1432) handles the case where a previously processed page
was the right half of a split *done during this vacuum cycle*: detected
by `btpo_cycleid == vstate->cycleid` on the right page, then follow
the right-link to catch tuples that may have migrated. [from-README]
`README:204-230`.

For each live leaf page: collect deletable offsets + posting-list
"updates", upgrade to cleanup-lock, emit `XLOG_BTREE_VACUUM` via
`_bt_delitems_vacuum`. Empty pages set `attempt_pagedel=true` and
trigger `_bt_pagedel` after the read-stream loop.

After scan: `_bt_pendingfsm_finalize` (above) pushes newly-deleted
pages with globally-visible safexids into the FSM.

`btvacuumcleanup` (`nbtree.c:1152`) updates the metapage's
`btm_last_cleanup_num_delpages` (only if changed, to avoid WAL noise)
so the next VACUUM can short-circuit via `_bt_vacuum_needs_cleanup`.

### Parallel index build — `nbtsort.c`

Build path: tuplesort → sequential bulk load via `storage/bulk_write.c`
(bypasses buffer cache). The bulk_write path emits WAL efficiently
via `XLOG_FPI_FOR_HINT`-like records. [from-comment] `nbtsort.c:26-28`.

`_bt_buildadd` (`nbtsort.c:789`) appends to the per-level
`BTPageState.btps_buf`; when full, finalize (truncate suffix, set high
key, write via bulk_write), allocate next, recurse to insert downlink
in the upper level (creating a new level if needed).

Leaf fillfactor = `BTREE_DEFAULT_FILLFACTOR` (90%, user-tunable);
upper levels always 70% (`BTREE_NONLEAF_FILLFACTOR`).

Parallel: `_bt_begin_parallel` (`nbtsort.c:1399`) sets up DSM with
`BTShared`, launches workers via `CreateParallelContext`. Each worker
runs `_bt_parallel_scan_and_sort` producing one sorted run; the leader
merges in `_bt_load`. `nulls_not_distinct=false` unique indexes use
**two spools** so dead tuples bypass the uniqueness check.

### Parallel scan — `_bt_parallel_seize/release/done` (`nbtree.c:873/1011/1038`)

CV-based "claim next page" protocol. `_bt_parallel_seize` atomically
claims the next page; loops on `btps_cv` while another worker is
advancing. `_bt_parallel_release` publishes the new
`next_scan_page` after this worker advanced, broadcasts the CV.
`_bt_parallel_primscan_schedule` (`nbtree.c:1088`) schedules another
primitive index scan (for SAOP/skip arrays) by writing
`BTPARALLEL_NEED_PRIMSCAN` and serializing array-key state to the
flexible-array tail.

### WAL replay — `nbtxlog.c`

15 redo functions, one per `XLOG_BTREE_*` info byte. Helpers
`_bt_restore_page` (`nbtxlog.c:36`), `_bt_restore_meta` (`:80`),
`_bt_clear_incomplete_split` (`:137`).

**Lock acquisition at replay matches primary order: left → right →
original right sibling → child** for splits; **leaf → left → target →
right → meta** for unlink. The explicit comment at
`nbtxlog.c:813-819` (in `btree_xlog_unlink_page`):

> *"In normal operation, we would lock all the pages this WAL record
> touches before changing any of them. In WAL replay, we at least lock
> the pages in the same standard left-to-right order."*

Concurrent standby readers cannot observe inconsistent same-level
state. [from-comment] `nbtxlog.c:813-819`.

### `XLOG_BTREE_REUSE_PAGE` and the standby conflict gate

The standalone explanatory comment at `nbtxlog.c:966-991` is the
canonical reference:

> *"the GlobalVisCheckRemovableFullXid() test in BTPageIsRecyclable()
> is used to determine if it's safe to recycle a page. This mirrors our
> own test: the PGPROC->xmin > limitXmin test inside
> GetConflictingVirtualXIDs(). Consequently, one XID value achieves the
> same exclusion effect on primary and standby."*

The unlink record does **not** generate a snapshot conflict — that's
deferred to the eventual `XLOG_BTREE_REUSE_PAGE` at recycle time. The
reuse record carries `snapshotConflictHorizon` (FullTransactionId
matching the page's stored safexid) + `isCatalogRel` and triggers
`ResolveRecoveryConflictWithSnapshotFullXid`. The record does NOT
register a buffer — see `nbtxlog.h:182-184`. [from-comment]
`nbtxlog.c:966-991`.

### Delete vs Vacuum conflict

`btree_xlog_delete` carries `snapshotConflictHorizon` + `isCatalogRel`
and calls `ResolveRecoveryConflictWithSnapshot` early in replay.

`btree_xlog_vacuum` does NOT generate a conflict — because the
heap-vacuum WAL record already raised the conflict for the same TIDs.
[from-comment] `nbtxlog.h:202-208`, `nbtxlog.c`.

## 5. Invariants

- INV-nbt-1: **Descent holds at most one buffer lock at a time.** The
  L&Y promise. `_bt_relandgetbuf` is the only buffer transition in
  `_bt_search`'s loop. [verified-by-code] `nbtsearch.c:182-186`.
- INV-nbt-2: **Page split lock order is left → child → right → original
  right sibling.** Comment at `nbtinsert.c:1907-1911` is canonical;
  every other writer must honor it. [verified-by-code]
- INV-nbt-3: **Page split does NOT hold any upward lock.** Parent
  downlink insertion is a SEPARATE WAL record. Crash between them
  leaves a recoverable `BTP_INCOMPLETE_SPLIT` page. [from-README]
  `README:620-700`, [verified-by-code] `nbtinsert.c:1119-1488`.
- INV-nbt-4: **`_bt_insertonpg` asserts `!P_INCOMPLETE_SPLIT(opaque)`.**
  Caller must finish splits via `_bt_finish_split` first.
  [verified-by-code] `nbtinsert.c:1160-1161`.
- INV-nbt-5: **`_bt_moveright(forupdate=true)` finishes incomplete
  splits opportunistically.** [verified-by-code] `nbtsearch.c:283-305`.
- INV-nbt-6: **Page deletion lock order is leaf → left → target → right
  → meta** (moving right, then up). `nbtpage.c:2429-2431` comment is
  canonical. Identical principle to split's left-to-right.
- INV-nbt-7: **Never delete rightmost pages.** Enforced both in
  `_bt_pagedel` and `_bt_mark_page_halfdead`. [verified-by-code]
  `nbtpage.c:1926`.
- INV-nbt-8: **`_bt_lock_subtree_parent` refuses if the subtree root
  is the rightmost child of its parent** — no sibling to absorb the
  keyspace. [verified-by-code] `nbtpage.c:2850`.
- INV-nbt-9: **`safexid` is the recycle gate.** Both primary and
  standby write the SAME FullTransactionId
  (`ReadNextFullTransactionId()` on the primary, replayed from the WAL
  record on the standby). `BTPageIsRecyclable` is the single source of
  truth. [verified-by-code] `nbtree.h:291-319`, `nbtpage.c:2666-2697`.
- INV-nbt-10: **Hot Standby conflict for recycled pages is generated
  at RECYCLE TIME (`XLOG_BTREE_REUSE_PAGE`), not at delete time.**
  [from-comment] `nbtxlog.c:966-991`.
- INV-nbt-11: **`btree_xlog_vacuum` does NOT generate a snapshot
  conflict.** The matching heap-vacuum record already did.
  [from-comment] `nbtxlog.h:202-208`.
- INV-nbt-12: **`_bt_killitems` is safe under SHARE lock** because it
  re-checks the page LSN under the lock; if anything changed since the
  scan saw the items, the LP_DEAD bits are NOT set. Uses fake LSNs for
  unlogged indexes. [from-README] `README:478-489`.
- INV-nbt-13: **LP_DEAD bit on a posting-list tuple means ALL TIDs in
  the list are dead.** Granular partial-TID dead-marking does not
  exist; partial deletion happens via `_bt_update_posting` in VACUUM /
  delete paths. [from-README] `README:545-555`.
- INV-nbt-14: **Deduplication requires `btm_allequalimage == true`** —
  all opclasses must provide `BTEQUALIMAGE_PROC`. [from-comment]
  `nbtree.h:130-148`, `nbtdedup.c`.
- INV-nbt-15: **Posting-list compression (varbyte) is explicitly
  rejected** because it would break page-split space accounting.
  [from-README] `README:930-941`.
- INV-nbt-16: **Internal-page splits do NOT use suffix truncation** —
  would break the "unbroken seam of identical separator keys"
  invariant. [from-comment] `nbtinsert.c:1685-1714`.
- INV-nbt-17: **`_bt_check_third_page` is the single chokepoint
  enforcing `BTMaxItemSize` (1/3 page).** Every insert must pass
  through it. [verified-by-code] `nbtutils.c`.
- INV-nbt-18: **Tuple-shape encoding (`INDEX_ALT_TID_MASK` +
  `BT_IS_POSTING`) is shared with `_bt_swap_posting`,
  `_bt_form_posting`, `btree_xlog_insert(_POST)`, `btree_xlog_split`,
  and amcheck.** Changing it is a hard upgrade event. [verified-by-code]
  `nbtree.h:372-549`.
- INV-nbt-19: **WAL replay lock acquisition matches primary
  left-to-right order.** [from-comment] `nbtxlog.c:813-819`.
- INV-nbt-20: **Fast-path insertion** (cached rightmost-leaf blkno)
  needs no cache-invalidation interlock because there is only one
  rightmost leaf at any time. [from-README] `README:491-509`.
- INV-nbt-21: **Drop-pin decision is per-rescan and immutable
  mid-scan.** `so->dropPin = !xs_want_itup && IsMVCCLikeSnapshot &&
  heapRelation != NULL`. Index-only and non-MVCC scans must keep the
  pin. [verified-by-code] `nbtree.c:419-421`.
- INV-nbt-22: **`_bt_pendingfsm_finalize` and `BTPageIsRecyclable`
  duplicate logic by design** — finalize tests without re-reading the
  page; `BTPageIsRecyclable` is the runtime gate at recycle. Comment at
  `nbtree.h:280-290` warns to update both in lock-step. [from-comment]
- INV-nbt-23: **Vacuum-cycle-ID slot allocator reserves 0 ("no vacuum")
  and the top byte for `pg_filedump`.** `MAX_BT_CYCLE_ID = 0xFF7F`.
  [from-comment] `nbtree.h:87-94`.

## 6. Entry points (how the rest of the backend calls in)

Public AM surface — the `bthandler` `IndexAmRoutine` (`nbtree.c:118`).
All callable via `commands/indexcmds.c` and `access/index/indexam.c`.

- `btbuild` (`nbtsort.c:299`) — index build (parallel or serial).
- `btbuildempty` (`nbtree.c:183`) — empty init-fork metapage.
- `btinsert` (`nbtree.c:206`) → `_bt_doinsert` (`nbtinsert.c:105`).
- `btgettuple` (`nbtree.c:230`) — scan iterator; handles
  `kill_prior_tuple` bookkeeping.
- `btgetbitmap` (`nbtree.c:291`) — bitmap-scan variant.
- `btbeginscan` / `btrescan` / `btendscan` (`nbtree.c:339, :388, :455`).
- `btmarkpos` / `btrestrpos` (`nbtree.c:491, :517`) — nested-loop
  rewind.
- `btbulkdelete` (`nbtree.c:1122`) — VACUUM bulk delete.
- `btvacuumcleanup` (`nbtree.c:1152`) — VACUUM cleanup.
- `btvalidate` (`nbtvalidate.c`) — opclass validator.
- `btcanreturn` / `btgettreeheight` (`nbtree.c:1802, :1811`) — cheap
  predicates over relcache.
- Parallel-scan API: `btestimateparallelscan` / `btinitparallelscan` /
  `btparallelrescan` (`nbtree.c:575, :814, :830`).
- `_bt_parallel_seize` / `_bt_parallel_release` / `_bt_parallel_done`
  / `_bt_parallel_primscan_schedule` — workers call these inside scan
  loops.

Called by:
- `access/index/indexam.c` (the AM dispatch layer).
- `commands/indexcmds.c` (CREATE INDEX → `index_build` →
  `IndexAmRoutine.ambuild`).
- `commands/vacuum.c` (autovacuum / VACUUM commands →
  `bulkdelete`/`vacuumcleanup`).
- `access/index/genam.c` (parallel-scan executor wiring).
- `executor/nodeIndexscan*.c`, `executor/nodeBitmapIndexscan.c`.

Calls into:
- `storage/bufmgr.c` (every buffer acquisition via the `_bt_*buf`
  wrappers in `nbtpage.c`).
- `storage/predicate.c` (SSI: `PredicateLockPage`,
  `PredicateLockPageSplit`, `PredicateLockPageCombine`,
  `CheckForSerializableConflictIn`).
- `storage/indexfsm.c` (`RecordFreeIndexPage`, `GetFreeIndexPage`).
- `access/transam/xact.c` (`ReadNextFullTransactionId` for safexid).
- `access/transam/xlog*.c` (WAL emission + redo dispatch).
- `access/tableam.h` (`heap_index_delete_tuples` for bottom-up + simple
  delete; `table_index_build_scan` for build).
- `utils/sort/tuplesort.c` (entire sort lifecycle during build).
- `storage/bulk_write.c` (build-time page emission).
- `access/parallel.c` (DSM + worker launch for parallel build).
- `storage/standby.c` (`ResolveRecoveryConflictWithSnapshot[FullXid]`).

## 7. What the tests tell us

### Regression (`src/test/regress/sql/`)

- `btree_index.sql` — basic functional coverage: build, insert, delete,
  scan, ORDER BY, range queries, NULL handling, multi-key combinations.
- `index_including.sql` — INCLUDE clause behavior (non-key columns,
  index-only scans).
- `create_index.sql` — generic AM exercising; the bulk of nbtree
  build-time behavior is here.
- `groupingsets.sql` / `join.sql` / `subselect.sql` — exercise
  ordered-scan + index-only scan paths.
- `vacuum.sql` — drives `btvacuumscan` indirectly; the LP_DEAD →
  simple-delete path.

### Isolation (`src/test/isolation/`)

- `index-only-scan.spec` — visibility-map interlock with concurrent
  heap updates.
- `multixact-no-deadlock.spec` (parts) — concurrent index reads under
  heap-update lock pressure.

### TAP

- `src/bin/pg_amcheck/t/` — runs `amcheck` over a variety of nbtree
  configurations including dedup, posting lists, half-dead pages.
- `src/test/recovery/t/` (multiple files) — exercise btree WAL replay
  during recovery + on Hot Standby.

### amcheck

`contrib/amcheck` is the per-page invariant verifier:
`bt_check_index` (basic) → `bt_index_parent_check` (additional
parent-downlink consistency) → `bt_index_check` with `heapallindexed`
(every heap tuple has a matching index entry). Catches almost every
class of corruption this synthesis names.

## 8. Gotchas / sharp edges

- **`BTP_INCOMPLETE_SPLIT` may persist across crashes and across long
  scans on a standby.** Readers don't care about it; only writers
  finishing the split (`_bt_finish_split`) do. The README §"Scans
  during Recovery" addresses why standby readers are unaffected.
  [from-README] `README:702-734`.
- **Page-split WAL logs the right page WHOLE** (`_bt_restore_page` at
  REDO), not incrementally — `XLogInsert` would full-page-image it
  anyway because the page is brand-new. The comment block at
  `nbtxlog.h:89-152` is the canonical explanation.
- **The left page high key is ALWAYS logged in split WAL** because
  suffix truncation can be user-defined code (`BTORDER_PROC` /
  `BTSORTSUPPORT_PROC` on opclasses can synthesize the new high key).
  Replay must replay it byte-for-byte.
- **`_bt_compare` interprets omitted scan-key attributes as "minus
  infinity" during forward scans, but as "equal to the truncated -inf
  attributes" during backward scans.** Subtle; relied upon by VACUUM
  page-deletion downlink re-find. Comment at `nbtsearch.c:437-446`.
- **`LockRelationForExtension(ExclusiveLock)` in `btvacuumscan`**
  (`nbtree.c:1336-1340`) is held BETWEEN read-stream batches, NOT
  while any buffer lock is held. `vacuum_delay_point` (`nbtree.c:1358-1359`)
  is only called while no buffer lock is held.
- **Parallel-scan `btps_lock`** (LWLock inside the DSM-resident
  `BTParallelScanDescData`) is the ONLY lock taken inside the
  `_bt_parallel_*` helpers. CV waits release the LW.
  [verified-by-code] `nbtree.c:873-1112`.
- **`_bt_getstackbuf` walking right past stale parents** — the
  formal no-deadlock argument lives in README §"Page splits" (lines
  139-156), not in code comments. Single most-asserted lock-ordering
  claim in nbtree. [from-README] `README:139-156`.
- **`speculative insertion`** path
  (`UNIQUE_CHECK_INSERT_INPROGRESS`) interacts with `_bt_check_unique`
  via `speculativeToken`; the heap-side handshake is NOT in nbtree.
  [unverified] (per-file doc raises this).
- **`btestimateparallelscan` sizing for skip arrays** depends on
  `BTArrayKeyInfo` totals computed in `_bt_preprocess_keys`; not traced
  end-to-end. [unverified]
- **Build-time deduplication** (in `nbtsort.c:_bt_load`) shares the
  state machine with insert-time dedup (`_bt_dedup_start_pending` /
  `_bt_dedup_save_htid` / `_bt_dedup_finish_pending` in `nbtdedup.c`).
  Be careful: in the build path, no WAL is emitted per-dedup-interval
  (the full page is bulk-written), but the intervals must still respect
  `allequalimage`.
- **`btm_allequalimage` is a build-time, NOT runtime, decision.** Once
  built without it, a relcache `_bt_allequalimage` call cannot upgrade
  the index. Adding a deduplication-incompatible opclass to a column
  is essentially a hard upgrade event for existing indexes.
  [from-comment] `nbtutils.c`.
- **Pivot-tuple `BTreeTupleGet/SetNAtts` is the load-bearing accessor
  for understanding internal pages.** Direct `IndexTupleData->t_info`
  attribute-count reads on pivots give wrong results — the count is
  encoded in `t_tid.ip_posid`. [verified-by-code] `nbtree.h:480-549`.

## 9. Open questions

- O1: **Lock-ordering proof for `_bt_insert_parent` re-finding a stale
  stack** when `_bt_getstackbuf` walks right past several
  split-and-recycled parents. README §"Page splits" claims it's safe;
  formal argument lives there, not in code. [from-README]
  `README:139-156`. Highest-risk locking claim. [unverified]
- O2: **`_bt_lock_subtree_parent` recursion correctness when the stack
  AND the actual ancestor chain BOTH diverge from the live tree** —
  concurrent split + concurrent recycle of the original ancestor. The
  code defensively re-checks downlinks at each level, but the failure
  mode isn't exhaustively documented. [unverified]
- O3: **Standby ordering between `XLOG_BTREE_UNLINK_PAGE` and
  `XLOG_BTREE_REUSE_PAGE`** when the standby hasn't replayed the unlink
  yet but the primary has already recycled and emitted a reuse record.
  Code path looks correct (the reuse record just resolves the
  conflict; the page itself gets initialized by the next split's WAL)
  but exact ordering guarantee not traced. [inferred]
- O4: **Can the `LockRelationForExtension(ExclusiveLock)` in
  `btvacuumscan` be removed** now that new pages use `RBM_ZERO_AND_LOCK`?
  The XXX at `nbtree.c:1310-1312` raises this; no proof either way.
  [unverified]
- O5: **`_bt_moveright(forupdate=true)` finishing a split concurrently
  with another inserter also in `_bt_finish_split`** — documented as
  safe (idempotent under buffer-lock serialization) but formal argument
  not in code. [unverified]
- O6: **Bottom-up deletion + RLS + foreign keys** — the executor hint
  `indexUnchanged` is set by the planner based on which columns the
  UPDATE touches; how this composes with foreign-key triggers that
  update referencing tables wasn't traced. [unverified]

## 10. Related subsystems

- **Calls into:**
  - `storage/buffer` (`bufmgr.c`) — every buffer-cache primitive via
    the `_bt_*buf` wrappers in `nbtpage.c`.
    [via `knowledge/subsystems/storage-buffer.md`]
  - `storage/lmgr` (`predicate.c`) — SSI predicate locks.
    [via `knowledge/subsystems/storage-lmgr.md`]
  - `storage/freespace` (`indexfsm.c`) — `RecordFreeIndexPage`,
    `GetFreeIndexPage` for deferred FSM placement.
  - `access/transam` (`xact.c`, `xlog*.c`) — `ReadNextFullTransactionId`,
    WAL emission and replay dispatch.
    [via `knowledge/subsystems/access-transam.md`]
  - `access/tableam` — `heap_index_delete_tuples` for bottom-up/simple
    delete; `table_index_build_scan` for build.
    [via `knowledge/subsystems/access-heap.md`]
  - `utils/sort/tuplesort` — entire sort lifecycle during build.
  - `storage/bulk_write` — bypasses bufmgr during build.
  - `access/parallel` — DSM + worker launch for parallel build.
  - `storage/standby` — recovery-conflict resolution.

- **Called by:**
  - `access/index/indexam.c` (AM dispatch layer).
  - `commands/indexcmds.c` (DDL).
  - `commands/vacuum.c` (VACUUM driver).
  - `executor/nodeIndexscan.c` + `nodeIndexonlyscan.c` +
    `nodeBitmapIndexscan.c`.
    [via `knowledge/subsystems/executor.md`]
  - `access/index/genam.c` (parallel-scan executor wiring).

- **Sibling:**
  - Other index AMs in `access/{brin,gin,gist,hash,spgist}/`. nbtree
    is the reference implementation that the others borrow patterns
    from (especially the L&Y-style descent without inter-level locks).

## 11. Source pointers — most-cited file:line summary

| Anchor | What it establishes |
|---|---|
| `README:6-29` | L&Y base — right-link + high key + no inter-level locks |
| `README:42-49` | Heap TID as final key column (v4 / heapkeyspace) |
| `README:88-104` | Scans only lock the leaf they're examining |
| `README:124-156` | `_bt_getstackbuf` walking right past stale parents |
| `README:204-230` | VACUUM cycle ID + backtrack |
| `README:232-317` | Page deletion two-phase |
| `README:330-360` | Move-left for backward scans |
| `README:383-441` | Lanin-Shasha "drain technique" for safexid recycle |
| `README:478-489` | LP_DEAD safe under SHARE via LSN re-check |
| `README:491-509` | Fast-path insertion (cached rightmost leaf) |
| `README:510-619` | Three flavors of leaf-tuple deletion |
| `README:556-619, :889-988` | Dedup + bottom-up deletion design |
| `README:620-700` | Split WAL is two records; INCOMPLETE_SPLIT recovery |
| `README:702-734` | Scans during recovery — readers ignore INCOMPLETE_SPLIT |
| `README:822-901` | Suffix truncation invariants + split-loc heuristic |
| `README:930-941` | Why posting-list compression is rejected |
| `nbtree.c:118` | `bthandler` `IndexAmRoutine` definition |
| `nbtree.c:419-421` | `dropPin` decision in `btrescan` |
| `nbtree.c:873-1112` | Parallel-scan coordination |
| `nbtree.c:1122-1224` | `btbulkdelete` + `btvacuumcleanup` |
| `nbtree.c:1240-1399` | `btvacuumscan` read-stream loop |
| `nbtree.c:1432-1493` | `backtrack:` cycle-ID handling |
| `nbtsearch.c:100` | `_bt_search` descent |
| `nbtsearch.c:182-186` | One-lock-at-a-time invariant |
| `nbtsearch.c:242, :283-305` | `_bt_moveright` + opportunistic split finish |
| `nbtsearch.c:689` | `_bt_compare` |
| `nbtsearch.c:883, :1586` | `_bt_first`, `_bt_next` |
| `nbtsearch.c:1975` | `_bt_lock_and_validate_left` (move-left) |
| `nbtinsert.c:105` | `_bt_doinsert` |
| `nbtinsert.c:411` | `_bt_check_unique` |
| `nbtinsert.c:1119, :1160-1161` | `_bt_insertonpg` + `!P_INCOMPLETE_SPLIT` assert |
| `nbtinsert.c:1489, :1907-1911` | `_bt_split` + canonical left-to-right comment |
| `nbtinsert.c:1944-2094` | Critical section + dirty/LSN ordering |
| `nbtinsert.c:2113-2123` | Parent insert holds left, drops right early |
| `nbtinsert.c:2130, :2272, :2492` | `_bt_insert_parent`, `_bt_finish_split`, `_bt_newlevel` |
| `nbtinsert.c:2730-2859` | `_bt_delete_or_dedup_one_page`, `_bt_simpledel_pass` |
| `nbtpage.c:874-1007` | `_bt_allocbuf` + FSM + `XLOG_BTREE_REUSE_PAGE` emission |
| `nbtpage.c:1182, :1313, :1543` | `_bt_delitems_vacuum`, `_bt_delitems_delete`, `_check_check` |
| `nbtpage.c:1832-2100` | `_bt_pagedel` driver |
| `nbtpage.c:2122-2308` | Phase 1 mark-half-dead |
| `nbtpage.c:2349-2755` | Phase 2 unlink |
| `nbtpage.c:2429-2437` | Canonical "moving right, then up" comment |
| `nbtpage.c:2666-2697` | `BTPageSetDeleted(safexid)` |
| `nbtpage.c:2850` | `_bt_lock_subtree_parent` |
| `nbtpage.c:3033-3100` | Pending-FSM finalize + add |
| `nbtxlog.c:813-819, :966-991` | Replay lock order + reuse-page conflict design |
| `nbtree.h:63-94` | `BTPageOpaqueData` + flags + cycle-ID range |
| `nbtree.h:165-173` | `BTMaxItemSize` (1/3-page) |
| `nbtree.h:234-258` | `BTDeletedPageData` + `BTPageSetDeleted` |
| `nbtree.h:291-319` | `BTPageIsRecyclable` (canonical recycle gate) |
| `nbtree.h:372-549` | Three tuple shapes (the encoding spec) |
| `nbtxlog.h:27-44` | 14 `XLOG_BTREE_*` info bytes |
| `nbtxlog.h:89-152` | Canonical split WAL design comment |
| `nbtxlog.h:198-222` | Vacuum vs delete conflict-generation rule |

## Synthesized over

This synthesis distills the 15 per-file docs under
`knowledge/files/src/backend/access/nbtree/` plus the two header docs
under `knowledge/files/src/include/access/nbt{ree,xlog}.h.md`. The
README is the authoritative spec; everything cited here cross-references
back to it where it overlaps.

See [[knowledge/architecture/access-methods.md]] for nbtree's place
in the wider index-AM landscape, [[knowledge/subsystems/storage-buffer.md]]
for the buffer-cache primitives underneath, and
[[knowledge/subsystems/access-transam.md]] for the WAL infrastructure
that nbtree feeds into.
