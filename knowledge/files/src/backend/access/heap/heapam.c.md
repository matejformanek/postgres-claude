# heapam.c

- **Source path:** `source/src/backend/access/heap/heapam.c`
- **Lines:** 9264
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `heapam.h` (its public surface), `heapam_handler.c` (the tableam shim), `heapam_visibility.c`, `pruneheap.c`, `hio.c`, `heaptoast.c`, `README.HOT`, `README.tuplock`.

## Purpose

The heart of the heap access method. Implements relation scans (seq, page-at-a-time, TID-range, parallel), index-driven fetches, and all DML: `heap_insert`, `heap_multi_insert`, `heap_delete`, `heap_update`, `heap_lock_tuple`, plus speculative insertion (`heap_finish_speculative`/`heap_abort_speculative`), in-place updates for catalogs, and freeze preparation/execution. Also contains the `heap_index_delete_tuples` bottom-up deletion entry, MultiXact resolution helpers, replica-identity extraction, and the WAL-emission helpers for INSERT/UPDATE/DELETE. The file is the SPINE of the access-method. [verified-by-code, heapam.c:1-58]

## Top-of-file comment
> "heap access method code … This file contains the heap_ routines which implement the POSTGRES heap access method used for all POSTGRES relations." — Lists 9 INTERFACE ROUTINES (heap_beginscan, heap_rescan, heap_endscan, heap_getnext, heap_fetch, heap_insert, heap_multi_insert, heap_delete, heap_update). [from-comment, heapam.c:1-30]

## Public surface (non-static functions, grouped)

**Scan setup/teardown/iteration:** `heap_beginscan` (1167), `heap_setscanlimits` (502), `heap_prepare_pagescan` (618), `heap_rescan` (1331), `heap_endscan` (1390), `heap_getnext` (1435), `heap_getnextslot` (1474), `heap_set_tidrange` (1504), `heap_getnextslot_tidrange` (1577).

**Single-tuple fetch:** `heap_fetch` (1684), `heap_get_latest_tid` (1793).

**Bulk insert state:** `GetBulkInsertState` (1937), `FreeBulkInsertState` (1954), `ReleaseBulkInsertStatePin` (1966).

**Read-stream callbacks:** `heap_scan_stream_read_next_parallel` (254), `heap_scan_stream_read_next_serial` (294), `bitmapheap_stream_read_next` (319), `heap_fetch_next_buffer` (710).

**DML:** `heap_insert` (2004), `heap_multi_insert` (2282), `simple_heap_insert` (2659), `heap_delete` (2717), `simple_heap_delete` (3153), `heap_update` (3201), `simple_heap_update` (after 3201), `heap_lock_tuple` (much later), `heap_finish_speculative`, `heap_abort_speculative`.

**Inplace update (catalogs):** `heap_inplace_lock`, `heap_inplace_update_and_unlock`, `heap_inplace_unlock`.

**Freeze:** `heap_prepare_freeze_tuple`, `heap_pre_freeze_checks`, `heap_freeze_prepared_tuples`, `heap_freeze_tuple`, `heap_tuple_should_freeze`, `heap_tuple_needs_eventual_freeze`.

**Bottom-up index delete:** `heap_index_delete_tuples`.

**MultiXact + visibility helpers:** `UpdateXmaxHintBits` (1915), `HeapTupleGetUpdateXid` (declared in htup.h, defined here).

**WAL emitters (some are static, some are not; the public ones are):** `log_heap_new_cid` (and several static `log_heap_*` helpers).

## Static spine (selection)

- `heap_prepare_insert` (2202) — Set xmin/cmin, infomask bits, oid/etc. before storage.
- `heap_multi_insert_pages` (2250) — estimate page count needed for a batch.
- `log_heap_update` (declared at line 62) — emit XLOG_HEAP_UPDATE/HOT_UPDATE with prefix/suffix compression.
- `compute_new_xmax_infomask` (86) — central decision for what xmax/infomask to write when locking/updating, given current state.
- `heap_lock_updated_tuple` (91) — apply a tuple lock to the latest version when following an update chain.
- `compute_infobits` (2672), `xmax_infomask_changed` (2694) — small helpers for WAL info-bits encoding.
- `HeapDetermineColumnsInfo` (4360) — figure out which columns changed in an update (drives HOT eligibility and replica-identity logging).
- `heap_acquire_tuplock` (79) — acquire the heavyweight LOCKTAG_TUPLE before waiting for a tuple xmax (see README.tuplock).
- `GetMultiXactIdHintBits`, `MultiXactIdGetUpdateXid`, `DoesMultiXactIdConflict`, `MultiXactIdWait`, `ConditionalMultiXactIdWait` — MultiXact-resolution helpers used by lock/update/delete paths.
- `index_delete_sort` (109), implementing the bottom-up-deletion batching.
- `ExtractReplicaIdentity` (112) — pulls the replica-identity tuple for WAL when logical decoding requires it.
- `heapgettup` (963) and `heapgettup_pagemode` (1073) — the two scan-iteration cores (non-page-at-a-time vs page-at-a-time).
- `heapgettup_initial_block` / `_start_page` / `_continue_page` / `_advance_block` (755, 802, 833, 879) — scan-state transitions.

## Key types / structs

This file does not define many top-level structs (the scan descs live in heapam.h). It does define numerous static helper-arg structs inline. The major *types it operates on* are `HeapScanDescData`, `BulkInsertStateData`, `HeapTupleData`, `Snapshot`, and the WAL record types from `heapam_xlog.h`.

## Key invariants and locking [HIGH-RISK SECTION]

- **`heap_insert` / `heap_multi_insert` flow:** prepare tuple (xmin = current xact xid; cmin = current command id unless FROZEN; xmax = 0; appropriate infomask), call `RelationGetBufferForTuple` to acquire a buffer (which may extend the relation), enter critical section, call `RelationPutHeapTuple`, optionally update VM (clear `ALL_VISIBLE`/`ALL_FROZEN`), emit WAL, exit critical section. The VM clearing must happen *inside* the critical section so that crash recovery sees both the heap change and the VM-clearing as a single unit. [verified-by-code, heapam.c:2004-2200; from-comment, visibilitymap.c:797-812]
- **`heap_delete` / `heap_update`:** acquire heavyweight LOCKTAG_TUPLE before waiting on the tuple's xmax xact (avoids starvation, see README.tuplock); when xmax indicates a multi, may need to wait on multiple members. Crosses-page update needs two-buffer locking in canonical order (lower block first; see hio.c). HOT eligibility decided by `HeapDetermineColumnsInfo` plus the page-fits constraint. [from-readme, README.tuplock; verified-by-code]
- **Update chain follow** in `heap_lock_updated_tuple`: takes pin on next page, locks, checks `t_self == t_ctid` (chain end) or `xmin == previous_xmax` (validate chain). [verified-by-code]
- **MultiXactId** for xmax encodes 1..N concurrent lockers and optional updater. Decoding involves `multixact.c` (`MultiXactIdGetMembers`); `compute_new_xmax_infomask` decides when to allocate a new multi vs reuse vs collapse. [from-readme, README.tuplock]
- **Speculative insertion**: insert with infomask bit set + `t_ctid = SpecToken`; on success, `heap_finish_speculative` writes the real ctid; on collision, `heap_abort_speculative` issues a super-delete (which the redo treats as a no-WAL-ALL_VISIBLE_CLEARED special case). [verified-by-code; the `XLH_DELETE_IS_SUPER` flag]
- **Replica identity logging** (`ExtractReplicaIdentity`): for UPDATE/DELETE on a table that publishes for logical decoding, log the old-tuple key (`XLH_UPDATE_CONTAINS_OLD_KEY`/`XLH_DELETE_CONTAINS_OLD_KEY`) so logical replication can find the row at the subscriber. [verified-by-code]
- **HOT update**: only allowed if (a) the new tuple fits on the same page, (b) no indexed column changed value, (c) the page wasn't recently HOT-pruned in a way that would create chain ambiguity. Marks predecessor `HEAP_HOT_UPDATED`, new tuple `HEAP_ONLY_TUPLE`. Skips creating index entries for the new tuple. [from-readme, README.HOT]
- **Critical-section discipline**: between `START_CRIT_SECTION` and `END_CRIT_SECTION` no ereport(ERROR) is allowed (would PANIC). The page lock is held throughout. `RelationPutHeapTuple` is inside this region and must PANIC on PageAddItem failure. [from-comment, hio.c:35-38]
- **`heap_inplace_lock`**: special path for in-place catalog updates (`pg_class.relfrozenxid`, `pg_database.datfrozenxid`, …). Uses a dedicated lock to serialise with concurrent readers that cannot tolerate a torn write. The companion `heap_inplace_update_and_unlock` emits an `xl_heap_inplace` record carrying shared-invalidation messages. [verified-by-code]
- **Freeze split**: `heap_prepare_freeze_tuple` produces a `HeapTupleFreeze` plan but does NOT modify the tuple. `heap_pre_freeze_checks` validates xmin-committed / xmax-aborted assumptions. `heap_freeze_prepared_tuples` (called inside the prune/freeze critical section in `pruneheap.c`) applies the plans via the inline `heap_execute_freeze_tuple`. This separation lets VACUUM batch all per-page checks before entering the crit section. [from-comment, heapam.h around lines 406-413]

## Functions of note (deep-read selection)

1. **`heap_insert`** (line 2004) — Sets xmin, cid, fills infomask (`HEAP_HASNULL`, `HEAP_HASVARWIDTH` based on the tuple). If TOASTing is required, calls `heap_toast_insert_or_update` first. Calls `RelationGetBufferForTuple`. Enters crit section, calls `RelationPutHeapTuple`, optionally calls `visibilitymap_clear` (if PD_ALL_VISIBLE is set), emits XLOG_HEAP_INSERT (with `XLH_INSERT_*` flags), sets buffer dirty. [verified-by-code]

2. **`heap_multi_insert`** (line 2282) — Bulk-insert path used by COPY. Forms tuples, calls `RelationGetBufferForTuple` repeatedly, packs as many as fit per buffer, emits a single `XLOG_HEAP2_MULTI_INSERT` per buffer. Supports `HEAP_INSERT_FROZEN` (initdb / pg_upgrade) which sets `HEAP_XMIN_FROZEN` and marks the page all-visible/all-frozen up-front. [verified-by-code]

3. **`heap_update`** (line 3201) — The most complex function in the file. Steps: read old tuple; resolve xmax (may force MultiXact I/O); apply `HeapTupleSatisfiesUpdate` to decide TM_Ok / TM_Updated / TM_BeingModified / etc.; under TM_BeingModified, wait on the conflicting xact via LOCKTAG_TUPLE; check whether key columns changed (`HeapDetermineColumnsInfo`); decide HOT eligibility (key columns unchanged AND no expression index column changed AND new tuple fits on same page after pruning); if not HOT, find new buffer via `RelationGetBufferForTuple(otherBuffer = oldBuf)`; enter critical section; modify old tuple header (set xmax, infomask, t_ctid → new TID); insert new tuple; clear VM bits on both pages; emit `XLOG_HEAP_UPDATE` (or `_HOT_UPDATE`) with prefix/suffix compression. The function is **~1000 lines**. [verified-by-code]

4. **`heap_lock_tuple`** (offset later, see prototype in heapam.h:393) — Implements the row-lock state machine. Maps the four LockTupleMode values (KeyShare/Share/NoKeyExclusive/Exclusive) into the conflict matrix; cooperates with `compute_new_xmax_infomask` to combine with any existing xmax. Uses LOCKTAG_TUPLE to serialise waiters fairly. Returns TM_Result + TM_FailureData. [from-readme, README.tuplock; verified-by-code]

5. **`heap_index_delete_tuples`** (declared in heapam.h:429) — Bottom-up deletion. Index AM passes a batch of candidate TIDs; this function reads the heap pages, checks `HeapTupleSatisfiesVacuum` against the snapshot horizon, and returns the subset that are reclaimable. The `index_delete_sort` static helper batches by block to amortise buffer pins. [verified-by-code]

6. **`heap_prepare_freeze_tuple`** (declared in heapam.h:406) — For one tuple, decide: can we freeze xmin (yes if `xmin < FreezeLimit`, with care around `HEAP_MOVED_*`)? Can we freeze xmax (yes if invalid OR if locked-only with all lockers ≤ MultiXactCutoff)? Produces a `HeapTupleFreeze` plan, sets `pagefrz->freeze_required` if any tuple cannot be left unfrozen safely. [verified-by-code]

7. **`heapgettup_pagemode`** (line 1073) — Page-at-a-time scan iterator. For each new block: lock buffer; call `heap_prepare_pagescan` (which calls `HeapTupleSatisfiesMVCCBatch` to populate `rs_vistuples[]`); unlock buffer. Subsequent calls just walk `rs_vistuples` and return tuples without re-locking. This is the modern path; old `heapgettup` keeps lock during entire page scan and is used only for non-MVCC scans. [verified-by-code]

8. **`heap_inplace_lock` / `_update_and_unlock`** — The path used for `pg_class.relfrozenxid`, `pg_database.datfrozenxid`, and similar single-tuple catalog updates that must avoid creating a new HOT chain. Uses a per-relation in-place lock (via `LockRelationOid` with a dedicated lockmode) plus the buffer exclusive lock. WAL record `xl_heap_inplace` carries shared-invalidation messages so standbys catch the catalog change. [verified-by-code]

## Cross-references

- **Called by:** `heapam_handler.c` (the tableam shims forward almost every method here), `commands/copy*.c` (via multi_insert), `commands/vacuum.c` (via `heap_vacuum_rel` in vacuumlazy.c, which calls back into freeze helpers), `catalog/*` (catalog DML), `executor/nodeModifyTable.c` (the executor's UPDATE/DELETE/INSERT), `replication/logical/*` (for `log_heap_new_cid`, `ExtractReplicaIdentity`).
- **Calls into:** `hio.c` (`RelationGetBufferForTuple`, `RelationPutHeapTuple`), `heaptoast.c` (TOAST), `heapam_visibility.c` (every Satisfies routine), `pruneheap.c` (`heap_page_prune_opt`, `heap_get_root_tuples`), `visibilitymap.c` (pin/clear/set), `multixact.c` (lock-mode resolution), `xloginsert.c` (WAL), `predicate.c` (SSI conflict checks), `syncscan.c` (`ss_get_location`, `ss_report_location`).

## Open questions

- **Lock-ordering proof for cross-page UPDATE.** The code follows "lower block first" via `GetVisibilityMapPins` and `RelationGetBufferForTuple`, but the proof of deadlock-freedom across concurrent updaters that pick different "lower" pages relies on the global TID ordering — I did not verify every edge of the lattice. [unverified] **Highest-risk locking claim.**
- **MultiXact starvation under contention.** README.tuplock notes the fairness mechanism via LOCKTAG_TUPLE, but the exact code path that enqueues waiters in `heap_lock_tuple` was not deep-read. [unverified]
- **Replica-identity old-key extraction in `ExtractReplicaIdentity`.** For tables with REPLICA IDENTITY USING INDEX, the key columns are looked up via `RelationGetIndexAttrBitmap`; the interaction with concurrent index drops was not traced. [unverified]
- Many WAL flag combinations (e.g. `XLH_INSERT_ALL_FROZEN_SET` on UPDATE's new buffer, `XLH_DELETE_NO_LOGICAL`) — emit-side conditions were not enumerated. [unverified]
- The historical pre-PG-9.0 `HEAP_MOVED_OFF/IN` handling paths inside `heap_prepare_freeze_tuple` are still present; I did not verify they are dead code only or still reachable via pg_upgrade. [unverified]

## Confidence tag tally
`[verified-by-code]=22 [from-comment]=6 [from-readme]=4 [inferred]=1 [unverified]=5`

## Synthesized by
<!-- backlinks:auto -->
- [data-structures/heap-tuple-layout.md](../../../../../data-structures/heap-tuple-layout.md)
- [subsystems/access-heap.md](../../../../../subsystems/access-heap.md)
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
