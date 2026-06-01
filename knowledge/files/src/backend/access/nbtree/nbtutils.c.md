# nbtutils.c

- **Source path:** `source/src/backend/access/nbtree/nbtutils.c` (1218 lines)
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `nbtpreprocesskeys.c` (scan-key preprocessing — extracted from this file in PG18), `nbtinsert.c` (consumes `_bt_truncate`, `_bt_check_third_page`), `nbtree.c` (consumes `_bt_killitems`, `_bt_start_vacuum`/`_bt_end_vacuum`).

## Purpose

The "miscellaneous utilities" file for nbtree. Builds insertion scankeys (`_bt_mkscankey`), handles the `kill_prior_tuple` deferred-LP_DEAD batching (`_bt_killitems`), manages the global vacuum-cycle-ID slot in shared memory (`_bt_start_vacuum`/`_bt_end_vacuum`/`_bt_vacuum_cycleid`), implements **suffix truncation** for new leaf high keys (`_bt_truncate`, `_bt_keep_natts*`), validates per-page tuple layout (`_bt_check_natts`), enforces the 1/3-page-size item limit (`_bt_check_third_page`), and decides whether an index is `allequalimage` (safe for deduplication) via `_bt_allequalimage`. [from-comment, nbtutils.c:1-13; verified-by-code]

## Public surface (representative)

- `_bt_mkscankey` (40) — build an insertion scankey from an `IndexTuple` (or a NULL itup for "all truncated"). Used by inserts, by `_bt_pagedel`'s downlink lookup, and by tests.
- `_bt_killitems` — bulk-flush `BTScanOpaque.killedItems[]` into LP_DEAD bits on the leaf page. Re-checks the page LSN to detect concurrent modification (per the README rule that LP_DEAD must not be set if anything else changed; uses fake LSNs for unlogged indexes). [from-README, README:478-489]
- `_bt_vacuum_cycleid`, `_bt_start_vacuum`, `_bt_end_vacuum`, `_bt_end_vacuum_callback` — shared-memory slot management (a small per-database table guarded by `BtreeVacuumLock`). Each running `btbulkdelete` consumes one slot for the duration of the scan.
- `_bt_truncate(rel, lastleft, firstright, itup_key)` — generate the new left page high key during a leaf split, removing trailing attributes that are unnecessary for distinguishing the two halves. Returns a freshly palloc'd `IndexTuple`.
- `_bt_keep_natts_fast(rel, lastleft, firstright)` — fast-path attribute-count chooser used by `nbtsplitloc.c` for choosing a split point.
- `_bt_check_natts(rel, heapkeyspace, page, offnum)` — validate that a tuple's number of attributes is consistent with its position (pivot/non-pivot/posting/with-heap-tid). Called from assertions and from amcheck.
- `_bt_check_third_page(rel, heap, needheaptidspace, page, newtup)` — error out if an incoming tuple is larger than `BTMaxItemSize` (1/3 of page).
- `_bt_allequalimage(rel, debugmessage)` — at index-build time, check whether all attribute opclasses are `BTEQUALIMAGE_PROC` and thus deduplication-safe; the result is recorded in `BTMetaPageData.btm_allequalimage`.
- `btoptions`, `btproperty`, `btbuildphasename` — relopts and progress-name infrastructure.

## Key invariants

- **Suffix truncation never produces a high key that is `< lastleft` or `>= firstright`.** The post-condition is a tuple with key columns where the first distinguishing attribute appears as early as possible, ensuring the L&Y subtree-invariant Ki < v <= Ki+1. [from-README, README:822-855]
- **Heap-TID truncation** is special — it is *omitted* rather than truncated (different representation from key columns), tracked by `BT_PIVOT_HEAP_TID_ATTR` in t_tid offset. [from-comment, nbtree.h:392-411]
- `_bt_check_third_page` is the single chokepoint enforcing `BTMaxItemSize` — every insert must pass through it. [verified-by-code]
- The cycle-ID allocator uses values 1..`MAX_BT_CYCLE_ID` (0xFF7F), reserving 0 for "no vacuum running" and the top byte for pg_filedump's index-type marker. [from-comment, nbtree.h:87-94]

## Cross-references

- **Called by:** every file in nbtree (this is the "everyone's helpers" module).
- **Calls into:** `access/skey.c` (ScanKey initialization), `storage/lwlock.c` (`BtreeVacuumLock`), `storage/shmem.c` (shared-memory cycle-ID table init).

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
