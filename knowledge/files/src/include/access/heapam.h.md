# heapam.h

- **Source path:** `source/src/include/access/heapam.h`
- **Lines:** 547
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `heapam.c` (implementations), `heapam_xlog.h` (WAL types it includes), `tableam.h` (the abstract AM contract this implements)

## Purpose

Public API of the heap table access method: scan descriptors, insert/update/delete/lock operations, freeze data structures, pruning/freezing entry points, vacuum entry point, and visibility-test prototypes. Bridges the table-AM abstraction (`tableam.h`) with the concrete heap implementation files. [verified-by-code, heapam.h:3-13]

## Top-of-file comment
> "POSTGRES heap access method definitions." (terse)

## Public surface

**Flag bits:**
- `HEAP_INSERT_SKIP_FSM`, `HEAP_INSERT_FROZEN`, `HEAP_INSERT_NO_LOGICAL`, `HEAP_INSERT_SPECULATIVE 0x0010` (heapam.h:36-39).
- `HEAP_PAGE_PRUNE_MARK_UNUSED_NOW`, `_FREEZE`, `_ALLOW_FAST_PATH`, `_SET_VM` (heapam.h:42-45).
- `HEAP_FREEZE_CHECK_XMIN_COMMITTED 0x01`, `HEAP_FREEZE_CHECK_XMAX_ABORTED 0x02` (heapam.h:149-150).

**Scan API:** `heap_beginscan`, `heap_rescan`, `heap_endscan`, `heap_getnext`, `heap_getnextslot`, `heap_set_tidrange`, `heap_getnextslot_tidrange`, `heap_setscanlimits`, `heap_prepare_pagescan`, `heap_fetch`, `heap_get_latest_tid` (heapam.h:350-371).

**Bulk insert:** `GetBulkInsertState`, `FreeBulkInsertState`, `ReleaseBulkInsertStatePin` (heapam.h:373-375).

**DML:** `heap_insert`, `heap_multi_insert`, `heap_delete`, `heap_update`, `heap_lock_tuple`, `heap_finish_speculative`, `heap_abort_speculative` (heapam.h:377-396).

**Inplace update (catalog only):** `heap_inplace_lock`, `heap_inplace_update_and_unlock`, `heap_inplace_unlock` (heapam.h:398-405).

**Freezing:** `heap_prepare_freeze_tuple`, `heap_pre_freeze_checks`, `heap_freeze_prepared_tuples`, `heap_freeze_tuple`, `heap_tuple_should_freeze`, `heap_tuple_needs_eventual_freeze`, plus the inline `heap_execute_freeze_tuple` at heapam.h:532. (heapam.h:406-422 + 532-545)

**Wrappers:** `simple_heap_insert/delete/update` (heapam.h:424-427).

**Index-side helpers:** `heap_index_delete_tuples`, and in `heapam_indexscan.c`: `heapam_index_fetch_begin/reset/end`, `heap_hot_search_buffer`, `heapam_index_fetch_tuple` (heapam.h:429-442).

**Pruning (in pruneheap.c):** `heap_page_prune_opt`, `heap_page_prune_and_freeze`, `heap_page_prune_execute`, `heap_get_root_tuples`, `log_heap_prune_and_freeze` (heapam.h:444-465).

**Vacuum (in vacuumlazy.c):** `heap_vacuum_rel`, plus assert-only `heap_page_is_all_visible` (heapam.h:468-476).

**Visibility (in heapam_visibility.c):** `HeapTupleSatisfiesVisibility`, `HeapTupleSatisfiesUpdate`, `HeapTupleSatisfiesVacuum`, `HeapTupleSatisfiesVacuumHorizon`, `HeapTupleSetHintBits`, `HeapTupleHeaderIsOnlyLocked`, `HeapTupleIsSurelyDead`, `HeapTupleSatisfiesMVCCBatch` (heapam.h:479-508).

**Misc:** `ResolveCminCmaxDuringDecoding` (in `reorderbuffer.c`), `HeapCheckForSerializableConflictOut` (heapam.h:514-521).

## Key types / structs

- `HeapScanDescData` (heapam.h:58) — extends `TableScanDescData`. Carries page-at-a-time state: `rs_cbuf` (current pinned buffer), `rs_vmbuffer` (current VM pinned page), `rs_vistuples[MaxHeapTuplesPerPage]` (offsets of visible tuples on the current page), `rs_read_stream` (PG 17 read-stream API), parallel-scan worker data. [verified-by-code]
- `BitmapHeapScanDescData` (heapam.h:109) — extends `HeapScanDescData` (empty extension; placeholder for AM-specific bitmap state).
- `IndexFetchHeapData` (heapam.h:120) — heap state during index-driven fetches: `xs_cbuf`, `xs_blk`, `xs_vmbuffer`.
- `HTSV_Result` enum (heapam.h:136) — DEAD / LIVE / RECENTLY_DEAD / INSERT_IN_PROGRESS / DELETE_IN_PROGRESS.
- `HeapTupleFreeze` (heapam.h:153) — per-tuple freeze plan: new xmax, new infomask bits, frzflags, checkflags, offset.
- `HeapPageFreeze` (heapam.h:191) — per-page freeze accumulator with TWO tracker sets (`FreezePageRelfrozenXid`/`FreezePageRelminMxid` vs `NoFreezePageRelfrozenXid`/`NoFreezePageRelminMxid`) plus `FreezePageConflictXid` for the WAL conflict horizon. The long comment (heapam.h:191-246) explains why two trackers — VACUUM may *choose* not to freeze a page, and the relfrozenxid candidates differ in each case.
- `PruneReason` enum (heapam.h:250) — `PRUNE_ON_ACCESS` / `PRUNE_VACUUM_SCAN` / `PRUNE_VACUUM_CLEANUP`.
- `PruneFreezeParams` (heapam.h:260) — inputs to `heap_page_prune_and_freeze` (relation, buffer, vmbuffer, options, vistest, cutoffs).
- `PruneFreezeResult` (heapam.h:307) — outputs (ndeleted, nnewlpdead, nfrozen, live_tuples, recently_dead_tuples, newly_all_visible*, hastup, lpdead_items, deadoffsets[]).
- `BatchMVCCState` (heapam.h:499) — pre-sized arrays so the batch MVCC check doesn't blow the x86-64 reg-args budget. Explicit comment about avoiding on-stack arg passing.

## Key invariants and locking

- The inline `heap_execute_freeze_tuple` (heapam.h:532) **requires** the caller to hold an exclusive buffer lock OR have the tuple in private storage. CLUSTER and old VACUUM FULL use the private-storage path; lazy VACUUM uses the exclusive-buffer-lock path. [from-comment, heapam.h:524-532]
- `HeapScanDescData.rs_cbuf` — "if not InvalidBuffer, we hold a pin on that buffer" — pin lifetime not encoded in type, must be maintained by hand. [from-comment, heapam.h:73]
- `IndexFetchHeapData.xs_cbuf` — same pin-implied-by-non-invalid contract. [from-comment, heapam.h:126-128]
- `HeapPageFreeze.NoFreezePageRelfrozenXid` etc. are valid **only** if the no-freeze path is taken; the "freeze" trackers are valid only on the freeze path. The "conflict xid" tracker is only used if freezing executes. [from-comment, heapam.h:230-244]

## Functions of note

- `heap_beginscan` — implementation at `heapam.c:1167`. Sets up the read-stream for serial/parallel/TID-range scans. [verified-by-code]
- `heap_update` — at `heapam.c:3201`. Decides HOT-eligibility, may move tuple to a new page, may need TOAST work. [verified-by-code]
- `heap_lock_tuple` — at `heapam.c` (referenced by README.tuplock). Encodes the 4-mode lock conflict matrix; cooperates with heavyweight LOCKTAG_TUPLE. [from-readme]
- `heap_prepare_freeze_tuple` / `heap_freeze_execute_prepared` — split design: VACUUM computes plans page-wide first, then a single critical section applies them. [from-comment, heapam.h:407-413]
- `HeapTupleSatisfiesMVCCBatch` (heapam.h:505) — batch version added for hot-path scans. The `BatchMVCCState` argument-passing trick is explicit anti-regression for x86-64. [from-comment, heapam.h:493-498]

## Cross-references

- This header is included by every backend C file that touches heap tables (scans, executor, catalog ops, vacuum, replication). [inferred]
- Its includes pull in `heapam_xlog.h`, `tableam.h`, `relscan.h`, `read_stream.h`, `snapshot.h`. [verified-by-code, heapam.h:17-32]

## Open questions

- `heap_inplace_lock` mechanism for catalog-only in-place updates — interface is exposed here but the locking discipline lives in `heapam.c`. [unverified]
- Whether `BitmapHeapScanDescData` is destined to grow real fields or remains a marker — comment says "Holds no data". [from-comment, heapam.h:113]

## Confidence tag tally
`[verified-by-code]=14 [from-comment]=7 [from-readme]=1 [inferred]=1 [unverified]=2`
