# nbtree.c

- **Source path:** `source/src/backend/access/nbtree/nbtree.c` (1854 lines)
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `nbtree.h` (public + AM-internal types), `nbtinsert.c` (the actual insert path), `nbtsearch.c` + `nbtreadpage.c` (the scan path), `nbtpage.c` (page deletion called from `btvacuumpage`).

## Purpose

**Public-interface module** of the btree AM. Defines the `bthandler` PG_FUNCTION that fills the `IndexAmRoutine` vtable; implements the user-facing entry points (`btinsert`, `btgettuple`, `btgetbitmap`, scan begin/rescan/end, mark/restore, bulk delete, vacuum cleanup); and houses the parallel-scan coordinator (the `BTParallelScanDescData` shared struct and the `_bt_parallel_*` helpers). All of the heavy lifting (`_bt_doinsert`, `_bt_first`, `_bt_pagedel`, etc.) is in sibling files; this file is glue + the VACUUM driver loop. [from-comment, nbtree.c:1-9; verified-by-code]

## Top-of-file comment

> "This file contains only the public interface routines." [from-comment, nbtree.c:7-8]

## Public surface

| Function | Line | Role |
|---|---|---|
| `bthandler` | 118 | `IndexAmRoutine` constructor, declared in pg_proc as `bthandler(internal)` returning `index_am_handler`. Lists every capability bit (`amcanorder`, `amcanbackward`, `amcanunique`, `amcanparallel`, `amcanbuildparallel`, `amsearcharray`, `amsearchnulls`, `amcaninclude`, `ampredlocks`, ...) and binds every method slot. [verified-by-code, nbtree.c:118-177] |
| `btbuildempty` | 183 | Builds an empty init-fork via `smgr_bulk_*`, writing just a metapage that points at no root. [verified-by-code] |
| `btinsert` | 206 | Wraps `_bt_doinsert` (nbtinsert.c). [verified-by-code] |
| `btgettuple` | 230 | Scan iterator. Handles `kill_prior_tuple` bookkeeping into `so->killedItems[]` and loops while there are array keys to start a new primitive scan. [verified-by-code, nbtree.c:230-285] |
| `btgetbitmap` | 291 | Bitmap-scan variant; same primitive-scan loop. [verified-by-code] |
| `btbeginscan` / `btrescan` / `btendscan` | 339 / 388 / 455 | Scan lifecycle. `btrescan` is where `so->dropPin` is computed (drop leaf pin iff non-itup, MVCC-like snapshot, with heap relation). [verified-by-code, nbtree.c:419-421] |
| `btmarkpos` / `btrestrpos` | 491 / 517 | Save/restore mark for nested-loop rewind. |
| `btestimateparallelscan` / `btinitparallelscan` / `btparallelrescan` | 575 / 814 / 830 | DSM sizing + init for parallel scans. Size includes per-array slots for SAOP and skip-array state. [verified-by-code, nbtree.c:575-655] |
| `btbulkdelete` / `btvacuumcleanup` | 1122 / 1152 | Two halves of index VACUUM. `btbulkdelete` wraps `btvacuumscan` in `PG_ENSURE_ERROR_CLEANUP(_bt_end_vacuum_callback)` to release the vacuum-cycle-ID slot on error. [verified-by-code, nbtree.c:1134-1141] |
| `btcanreturn` / `btgettreeheight` | 1802 / 1811 | Cheap predicates over relcache. |
| `bttranslatestrategy` / `bttranslatecmptype` | 1817 / 1837 | StrategyNumber ↔ CompareType bridge. |

## Internal coordination surface (exported as `_bt_*`)

- `_bt_parallel_seize` (873) — atomic "claim next page" for parallel workers, returns `next_scan_page` + `last_curr_page`. Loops on the `btps_cv` condition variable while another worker is advancing. [verified-by-code]
- `_bt_parallel_release` (1011) — publishes a new `next_scan_page` after this worker advanced, broadcasts CV.
- `_bt_parallel_done` (1038) — transitions state to `BTPARALLEL_DONE`.
- `_bt_parallel_primscan_schedule` (1088) — schedules another primitive index scan (for SAOP/skip arrays) by writing `BTPARALLEL_NEED_PRIMSCAN` and serializing array-key state.

## Key types

- `BTPS_State` enum (`NOT_INITIALIZED`/`NEED_PRIMSCAN`/`ADVANCING`/`IDLE`/`DONE`) at lines 56-63.
- `BTParallelScanDescData` (69-93) — the DSM-resident coordination struct. Holds an `LWLock btps_lock` + `ConditionVariable btps_cv`, the next/last page block numbers, and trailing `btps_arrElems[FLEXIBLE_ARRAY_MEMBER]` for SAOP/skip-array state. [verified-by-code]

## VACUUM driver flow

`btbulkdelete` → `btvacuumscan` → loops calling `btvacuumpage` per block:

1. `_bt_start_vacuum` allocates a 16-bit cycle ID for this VACUUM run (in `nbtutils.c`). [from-comment, nbtree.c:1132-1138]
2. `btvacuumscan` (1240) creates `vstate.pagedelcontext` (an AllocSet to throw away `_bt_pagedel` allocations), calls `_bt_pendingfsm_init`, then uses a `READ_STREAM_MAINTENANCE | READ_STREAM_FULL | READ_STREAM_USE_BATCHING` read stream over the index in *block order*. On each outer iteration, it re-reads the relation length under `LockRelationForExtension(ExclusiveLock)` to pick up new pages added during the scan. [verified-by-code, nbtree.c:1296-1380] An XXX note (lines 1310-1312) suggests the extension lock may no longer be needed now that new pages use `RBM_ZERO_AND_LOCK`.
3. `btvacuumpage` (1415) is the per-block worker. The `backtrack:` label (1432) is hit when a previously processed page was the right half of a split done during this vacuum cycle — we follow the right-link if `btpo_cycleid == vstate->cycleid` to catch tuples that may have migrated. [verified-by-code, nbtree.c:1432-1493]
4. For a live leaf page, `btvacuumpage` collects deletable offsets + posting-list "updates", upgrades to cleanup-lock semantics, and emits `XLOG_BTREE_VACUUM` via `_bt_delitems_vacuum` (nbtpage.c). Empty leaf pages set `attempt_pagedel=true` and trigger `_bt_pagedel` after the loop. [verified-by-code]
5. After the scan, `_bt_pendingfsm_finalize` (nbtpage.c) walks the per-VACUUM `pendingpages[]` and pushes any newly deleted pages whose `safexid` has become globally-visible into the FSM. [from-comment, nbtree.c:1388-1399]
6. `btvacuumcleanup` updates the metapage's `btm_last_cleanup_num_delpages` so that the next VACUUM can short-circuit via `_bt_vacuum_needs_cleanup`. [verified-by-code, nbtree.c:1196-1224]

## Locking notes [HIGH-RISK SECTION]

- **Parallel-scan lock order**: `btps_lock` (LWLock inside the DSM-resident `BTParallelScanDescData`) is the only lock taken inside the parallel-scan helpers. CV waits release the LW. [verified-by-code, nbtree.c:873-1112]
- **VACUUM extension lock**: `LockRelationForExtension(ExclusiveLock)` is acquired *while* the read stream is between batches, *not* while holding any buffer lock. [verified-by-code, nbtree.c:1336-1340]
- **`vacuum_delay_point` is called only while no buffer lock is held**, per the explicit comment at nbtree.c:1358-1359. [from-comment]
- **Drop-pin decision in `btrescan` is per-rescan**: `so->dropPin = !xs_want_itup && IsMVCCLikeSnapshot && heapRelation != NULL`. Index-only scans must keep the pin; non-MVCC scans must keep the pin. [verified-by-code, nbtree.c:419-421]

## Cross-references

- **Called by:** the indexam dispatch in `access/index/indexam.c` via the function pointers in `IndexAmRoutine`; `commands/vacuum.c` via `bulkdelete`/`vacuumcleanup`; the parallel-scan executor in `access/index/genam.c`.
- **Calls into:** `nbtinsert.c` (`_bt_doinsert`), `nbtsearch.c` (`_bt_first`, `_bt_next`), `nbtpreprocesskeys.c` (`_bt_preprocess_keys`, transitively), `nbtutils.c` (`_bt_killitems`, `_bt_start_vacuum`, `_bt_end_vacuum`), `nbtpage.c` (`_bt_pagedel`, `_bt_delitems_vacuum`, `_bt_pendingfsm_*`, `_bt_getbuf`, `_bt_checkpage`, `_bt_lockbuf`/`_bt_relbuf`), `nbtsort.c` (`btbuild`, `_bt_parallel_build_main` declared in nbtree.h).

## Open questions

- The XXX at nbtree.c:1310-1312 ("now that new pages are locked with RBM_ZERO_AND_LOCK, I don't think the use of the extension lock is still required"). Whether the extension lock can in fact be removed is unverified. [unverified]
- `btestimateparallelscan` sizing for skip arrays (the second flex tail) depends on `BTArrayKeyInfo` totals computed in `_bt_preprocess_keys`; this code path was not traced end-to-end. [unverified]

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
