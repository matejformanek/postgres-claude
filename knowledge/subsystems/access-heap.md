# Heap access method

## Owners (as of 2026-06-12)

- **Top committers (last 24mo):** Melanie Plageman (75), Peter Eisentraut (19), Álvaro Herrera (18), Noah Misch (14)
- **Top reviewers (last 24mo):** Andres Freund (42), Chao Li (29), Kirill Reshke (22), Masahiko Sawada (13)
- **Recent landmark commits (12mo):**
  - `64bf53dd61e (Noah Misch, 2025-12-15): Revisit cosmetics of "For inplace update, send nontransactional invalidations."`
  - `8b9d42bf6bd (Melanie Plageman, 2026-03-02): Save prune cycles by consistently clearing prune hints on all-visible pages`
  - `0839fbe400d (Noah Misch, 2025-12-15): Correct comments of "Fix data loss at inplace update after heap_update()".`

See `knowledge/personas/domain-ownership.md` for the cross-subsystem index, methodology, and committer/reviewer affinity clusters.

---

- **Source path:** `source/src/backend/access/heap/`
- **Header path:** `source/src/include/access/` (`heapam.h`, `heapam_xlog.h`, `htup.h`, `htup_details.h`, `hio.h`, `visibilitymap.h`)
- **Last verified commit:** `4b0bf0788b06` (2026-06-01); §6 cites re-audited 2026-06-07 (pg-quality-auditor) — heapam_visibility.c / visibilitymap.c / heapam_xlog.c comment cites corrected for refactor drift
- **README anchor:** `source/src/backend/access/heap/README.HOT` + `README.tuplock` (the directory has no plain `README`; the two design docs are the canonical narratives)

## 1. Purpose

The heap access method is PostgreSQL's default `TableAmRoutine` implementation: it stores rows as variable-length tuples inside 8 KB pages, retains every version of each tuple for MVCC, and arbitrates concurrent insert/update/delete/lock through a combination of per-tuple xmin/xmax bookkeeping, hint bits, and two auxiliary forks (the visibility map and the free space map). The directory contains the DML spine (`heapam.c`), the visibility oracle (`heapam_visibility.c`), the single-page cleanup machinery for HOT and freezing (`pruneheap.c`), the table rewriter for VACUUM FULL/CLUSTER (`rewriteheap.c`), the lazy-VACUUM driver (`vacuumlazy.c`), the WAL emit/redo split (`heapam.c` emits, `heapam_xlog.c` replays), the tableam shim (`heapam_handler.c`), the I/O placement layer (`hio.c`), and the visibility-map fork (`visibilitymap.c`). [verified-by-code, heapam.c:1-30] [via knowledge/files/src/backend/access/heap/heapam.c.md]

## 2. Mental model

- **Tuple = row version.** Every UPDATE/DELETE leaves the old version on disk with `xmax` set; only VACUUM (or HOT prune) reclaims the space. The 23-byte `HeapTupleHeaderData` carries `t_xmin`/`t_xmax`/`t_cid`/`t_ctid`/`t_infomask`/`t_infomask2` plus a null bitmap. [from-comment, htup_details.h:50-120] [via knowledge/files/src/include/access/htup_details.h.md]
- **MVCC visibility via xmin/xmax + hint bits + procarray.** A tuple is visible to a snapshot iff its inserting xact is committed-and-not-in-snapshot and its deleting xact is not-yet-committed-or-aborted (modulo lock-only xmax). `heapam_visibility.c` is the canonical authority; hint bits cache the answer but are not themselves WAL-logged. [from-comment, heapam_visibility.c:6-37] [via knowledge/files/src/backend/access/heap/heapam_visibility.c.md]
- **HOT (Heap-Only Tuple).** When an UPDATE changes no indexed column and the new version fits on the same page, the new tuple is marked `HEAP_ONLY_TUPLE` and chained from its predecessor via `t_ctid`; indexes are not touched. Single-page pruning collapses dead chain members and converts root line pointers into `LP_REDIRECT` so existing index TIDs keep pointing at the chain head. [from-README, README.HOT] [via knowledge/files/src/backend/access/heap/README.md]
- **Freeze / vacuum cycle.** Lazy VACUUM scans the heap (skipping all-visible runs using the VM), prunes/freezes each page in one shot, accumulates dead TIDs in a TID store, vacuums every index, then revisits the heap to convert `LP_DEAD` line pointers to `LP_UNUSED`. Freezing replaces still-live old xids with `FrozenTransactionId` (encoded as `HEAP_XMIN_FROZEN`) so they survive xid wraparound. [from-comment, vacuumlazy.c:1-225] [via knowledge/files/src/backend/access/heap/vacuumlazy.c.md]
- **WAL is the source of truth for crash + replica.** Every mutating heap operation emits a WAL record from one of two resource managers (`RM_HEAP_ID`, `RM_HEAP2_ID` — split because the first ran out of opcodes); redo lives in `heapam_xlog.c` and shares `heap_page_prune_execute` with the emitter to keep emit/redo bit-identical. [from-comment, heapam_xlog.h:27-66] [via knowledge/files/src/include/access/heapam_xlog.h.md]
- **VM + FSM auxiliary forks.** The visibility map is 2 bits/page (`ALL_VISIBLE`, `ALL_FROZEN`) and is *conservative* (set bit authoritative, clear bit unknown); it's not independently WAL-logged — the heap WAL record drives both forks. The FSM caches per-page free space so `RelationGetBufferForTuple` can find a target page without scanning. [from-comment, visibilitymap.c:1-95] [via knowledge/files/src/backend/access/heap/visibilitymap.c.md]

## 3. Key files

- `heapam.c` (9264 lines) — the DML spine: `heap_insert`, `heap_multi_insert`, `heap_delete`, `heap_update`, `heap_lock_tuple`, speculative insertion, freeze prepare/execute, scan iteration (`heapgettup_pagemode`), `heap_index_delete_tuples`, MultiXact resolution helpers, replica-identity extraction. Top comment at `heapam.c:1-30`. [via knowledge/files/src/backend/access/heap/heapam.c.md]
- `heapam_visibility.c` (1753 lines) — every `HeapTupleSatisfies*` routine; the MVCC oracle. Top comment at `heapam_visibility.c:1-100`. [via knowledge/files/src/backend/access/heap/heapam_visibility.c.md]
- `pruneheap.c` (2735 lines) — on-access pruning (`heap_page_prune_opt`) and the unified VACUUM `heap_page_prune_and_freeze` (prune + freeze + VM-set in one WAL record). `heap_page_prune_execute` is shared with redo. [via knowledge/files/src/backend/access/heap/pruneheap.c.md]
- `vacuumlazy.c` (3883 lines) — the three-phase lazy VACUUM driver, eager-freeze logic, anti-wraparound failsafe, post-vacuum truncation. Entry point `heap_vacuum_rel` at `vacuumlazy.c:624`. [via knowledge/files/src/backend/access/heap/vacuumlazy.c.md]
- `heapam_handler.c` (2734 lines) — the `TableAmRoutine` table; thin shims forwarding to `heap_*` functions plus the CLUSTER/VACUUM FULL rewrite driver `heapam_relation_copy_for_cluster` (`heapam_handler.c:594`). [via knowledge/files/src/backend/access/heap/heapam_handler.c.md]
- `heapam_xlog.c` (1359 lines) — WAL redo for `RM_HEAP_ID` and `RM_HEAP2_ID`; `heap_redo`/`heap2_redo` dispatchers; `heap_mask` for `wal_consistency_checking`. [via knowledge/files/src/backend/access/heap/heapam_xlog.c.md]
- `hio.c` (884 lines) — placement layer: `RelationPutHeapTuple` (assumes exclusive buffer lock; PANIC on failure) and `RelationGetBufferForTuple` (find/extend page, coordinates two-buffer locking for cross-page UPDATE). [via knowledge/files/src/backend/access/heap/hio.c.md]
- `rewriteheap.c` (1256 lines) — full-table rewriter used by CLUSTER/VACUUM FULL; preserves xmin/xmax/cmin/cmax verbatim, rewrites `t_ctid` chains using two hash tables, emits logical-rewrite mapping files. [via knowledge/files/src/backend/access/heap/rewriteheap.c.md]
- `visibilitymap.c` (630 lines) — VM-fork I/O: pin/clear/set/get, truncation; the 95-line top comment is the authoritative crash-safety discussion. [via knowledge/files/src/backend/access/heap/visibilitymap.c.md]
- `heaptoast.c` — TOAST (out-of-line large attribute) compress/decompress entry; consumed by `heap_insert`/`heap_update` when a tuple exceeds the inline threshold. [verified-by-code, directory listing]
- `heapam_indexscan.c` — `heap_hot_search_buffer` and index-fetch glue. [verified-by-code]
- `README.HOT` (24 KB) + `README.tuplock` (12 KB) — design narratives for HOT and tuple locking, respectively. [via knowledge/files/src/backend/access/heap/README.md]

## 4. Key data structures

- **`HeapTupleHeaderData`** (`htup_details.h:153`) — 23-byte on-disk header: union of `HeapTupleFields` (xmin/xmax/cid|xvac) and `DatumTupleFields`; then `t_ctid`, `t_infomask2`, `t_infomask`, `t_hoff`, null bitmap `t_bits[]`. Fields below `t_infomask2` MUST match `MinimalTupleData` so executor-internal tuples can be cast. [from-comment, htup_details.h:164] [via knowledge/files/src/include/access/htup_details.h.md]
  - Visibility bits in `t_infomask` (high byte): `HEAP_XMIN_COMMITTED 0x0100`, `HEAP_XMIN_INVALID 0x0200`, `HEAP_XMIN_FROZEN = both = 0x0300`, `HEAP_XMAX_COMMITTED 0x0400`, `HEAP_XMAX_INVALID 0x0800`, `HEAP_XMAX_IS_MULTI 0x1000`, `HEAP_UPDATED 0x2000`. [verified-by-code, htup_details.h:204-217]
  - Lock bits: `HEAP_XMAX_KEYSHR_LOCK 0x0010`, `HEAP_XMAX_EXCL_LOCK 0x0040`, `HEAP_XMAX_LOCK_ONLY 0x0080`. `HEAP_LOCKED_UPGRADED` detects a 9.2-era pg_upgrade legacy multixact that must not be resolved locally. [from-comment, htup_details.h:237-261]
  - `t_infomask2`: low 11 bits = nattrs (`HEAP_NATTS_MASK 0x07FF`); `HEAP_KEYS_UPDATED 0x2000`, `HEAP_HOT_UPDATED 0x4000`, `HEAP_ONLY_TUPLE 0x8000`. [verified-by-code, htup_details.h:291-296]
  - Hint bits are *hints* only; an unset hint never lies, a set hint may only be written after the relevant xact's commit WAL is flushed (else crash recovery can lose data). [from-comment, heapam_visibility.c:115-124] [via knowledge/files/src/backend/access/heap/heapam_visibility.c.md]
- **`HeapTupleData`** (`htup.h:62`) — in-memory wrapper: `t_len`, `t_self`, `t_tableOid`, `HeapTupleHeader t_data`. Has *five* documented usage modes (pointer-into-buffer, NULL, palloc'd-adjacent, palloc'd-separate, minimal-tuple-overlay); when `t_data` points into a shared buffer the caller MUST hold a pin on that buffer — and this is not encoded in the struct. **Footgun.** [from-comment, htup.h:30-60] [via knowledge/files/src/include/access/htup.h.md]
- **`BulkInsertStateData`** (`hio.h:29`) — strategy ring + `current_buf` (an *extra* pin held when non-Invalid) + bulk-extension scratch (`next_free`, `last_free`, `already_extended_by`). Used by COPY and the multi-insert path. [from-comment, hio.h:23-50] [via knowledge/files/src/include/access/hio.h.md]
- **`HeapTupleFreeze`** (`heapam.h:153`) and **`HeapPageFreeze`** (`heapam.h:191`) — split between *plan* (computed by `heap_prepare_freeze_tuple` outside any crit section) and *execution* (`heap_freeze_prepared_tuples` inside the prune/freeze critical section). `HeapPageFreeze` keeps TWO tracker sets (`FreezePageRelfrozenXid` vs `NoFreezePageRelfrozenXid`) because VACUUM may *choose* not to freeze a page and the relfrozenxid candidates differ. [from-comment, heapam.h:191-246] [via knowledge/files/src/include/access/heapam.h.md]
- **`PruneState`** (`pruneheap.c` ~line 520) — per-page working buffer with pre-sized arrays (sized for `MaxHeapTuplesPerPage`) holding planned redirects, dead lp's, unused lp's, freeze plans, and accumulators `set_all_visible`/`set_all_frozen`. No per-page allocation. [verified-by-code] [via knowledge/files/src/backend/access/heap/pruneheap.c.md]
- **`LVRelState`** (`vacuumlazy.c`) — the dominant VACUUM state object: relation/indexes/cutoffs/dead-items TID store/scan counters/eager-scan accounting/parallel handle/error-context info. [verified-by-code] [via knowledge/files/src/backend/access/heap/vacuumlazy.c.md]
- **`HeapScanDescData`** (`heapam.h:58`) — page-at-a-time scan state: `rs_cbuf`, `rs_vmbuffer`, `rs_vistuples[MaxHeapTuplesPerPage]`, `rs_read_stream`. Pin-when-non-Invalid contract is by comment, not by type. [from-comment, heapam.h:73] [via knowledge/files/src/include/access/heapam.h.md]
- **`PruneFreezeParams`** / **`PruneFreezeResult`** (`heapam.h:260`, `:307`) — inputs/outputs for `heap_page_prune_and_freeze`; `PruneReason` enum tags the record as `PRUNE_ON_ACCESS` / `PRUNE_VACUUM_SCAN` / `PRUNE_VACUUM_CLEANUP`. [verified-by-code, heapam.h:250-310]

## 5. Control flow — the common paths

### 5.1 `heap_insert` (heapam.c:2004)

1. `heap_prepare_insert` (`heapam.c:2202`) — set `xmin = GetCurrentTransactionId()`, `cmin = GetCurrentCommandId(true)`, `xmax = 0`, infomask (`HEAP_HASNULL`, `HEAP_HASVARWIDTH` per tuple); if total size > toast threshold, call `heap_toast_insert_or_update` first.
2. `RelationGetBufferForTuple(rel, len, InvalidBuffer, options, bistate, &vmbuffer, NULL, num_pages)` (`hio.c:500`) — find/extend a page; may pin a VM page. [via knowledge/files/src/backend/access/heap/hio.c.md]
3. `START_CRIT_SECTION()`.
4. `RelationPutHeapTuple(rel, buffer, tup, false)` — `PageAddItem`; set `tup->t_self`; fix `t_ctid` (unless speculative). PANIC on `PageAddItem` failure — no `ereport(ERROR)` allowed in this region. [from-comment, hio.c:28-33]
5. If `PD_ALL_VISIBLE` was set on the heap page, `visibilitymap_clear` — and this MUST happen inside the critical section so crash recovery sees heap + VM as one unit. [verified-by-code, heapam.c:2004-2200; from-comment, visibilitymap.c:76-90] [via knowledge/files/src/backend/access/heap/heapam.c.md]
6. Emit `XLOG_HEAP_INSERT` (with `XLH_INSERT_*` flags), `MarkBufferDirty`.
7. `END_CRIT_SECTION()`; release VM pin; release buffer lock.

### 5.2 `heap_update` (heapam.c:3201) — the most complex function in the file (~1000 lines)

1. Read old tuple at given TID; pin+share-lock its page.
2. Resolve `xmax` — may force MultiXact disk I/O via `HeapTupleGetUpdateXid` → `multixact.c`. [from-comment, htup_details.h:380-386]
3. `HeapTupleSatisfiesUpdate` (`heapam_visibility.c:511`) → `TM_Ok` / `TM_Updated` / `TM_BeingModified` / `TM_Deleted` / `TM_Invisible` / `TM_SelfModified`. [via knowledge/files/src/backend/access/heap/heapam_visibility.c.md]
4. If `TM_BeingModified`: `heap_acquire_tuplock` takes a heavyweight `LOCKTAG_TUPLE` (fairness) **before** waiting on the conflicting xact's xmax. README.tuplock spells out why this two-level mechanism exists. [from-README, README.tuplock] [via knowledge/files/src/backend/access/heap/README.md]
5. `HeapDetermineColumnsInfo` (`heapam.c:4360`) decides which columns changed → drives HOT eligibility (no indexed column changed) and replica-identity logging.
6. HOT eligibility: indexed columns unchanged AND new tuple fits on same page AND no expression index column changed. If yes, predecessor gets `HEAP_HOT_UPDATED`, new tuple gets `HEAP_ONLY_TUPLE`, no index entries. [from-README, README.HOT]
7. If not HOT (or doesn't fit): `RelationGetBufferForTuple(rel, len, oldBuffer, ...)` — the two-buffer case. **Lock order: lower block-number first**, both for the heap buffers and via `GetVisibilityMapPins` for their VM pages. [verified-by-code, hio.c:138, 500]
8. `START_CRIT_SECTION`, write new tuple, update old tuple's header (set xmax, infomask, `t_ctid → new TID`), clear VM bits on both pages if needed, emit `XLOG_HEAP_UPDATE` or `XLOG_HEAP_HOT_UPDATE` with prefix/suffix compression (`XLH_UPDATE_PREFIX_FROM_OLD` / `_SUFFIX_FROM_OLD`). [verified-by-code, heapam.c; verified-by-code, heapam_xlog.h:84-96]

### 5.3 `heap_delete` (heapam.c:2717)

Same skeleton as the old-side of `heap_update` minus the new-tuple work: resolve xmax → acquire `LOCKTAG_TUPLE` if waiting → `HeapTupleSatisfiesUpdate` → set xmax/infomask under crit section → emit `XLOG_HEAP_DELETE` (with `XLH_DELETE_*` flags including `_CONTAINS_OLD_KEY` for logical decoding and `_IS_SUPER` for super-deletion of failed speculative inserts). [via knowledge/files/src/backend/access/heap/heapam.c.md]

### 5.4 `lazy_vacuum_heap_page` — phase III of VACUUM (vacuumlazy.c:2758)

1. Re-read the heap page (phase I already recorded its dead-item offsets in the TID store).
2. Take **`BUFFER_LOCK_EXCLUSIVE`** (NOT cleanup lock — phase III only converts `LP_DEAD → LP_UNUSED`, no tuple data is moved). [verified-by-code, vacuumlazy.c:2758] [via knowledge/files/src/backend/access/heap/vacuumlazy.c.md]
3. Call `heap_page_prune_and_freeze` with `PruneReason = PRUNE_VACUUM_CLEANUP` (no freeze attempts in this pass) — turns each TID-store offset into `LP_UNUSED`.
4. `RecordPageWithFreeSpace`.
5. Emit a `XLOG_HEAP2_PRUNE_VACUUM_CLEANUP` record (no `XLHP_CLEANUP_LOCK` flag — redo also runs under exclusive lock only). [from-comment, heapam_xlog.h:302-310]

### 5.5 On-access HOT prune (`heap_page_prune_opt`, pruneheap.c:271)

Cheap pre-check (relation read-only? no candidate prunable hint?) → `ConditionalLockBufferForCleanup` (give up if it fails) → fast-path `heap_page_prune_and_freeze` (no freeze, no VM-set) → emit `XLOG_HEAP2_PRUNE_ON_ACCESS`. The crucial property: pruning that moves tuple data requires a **cleanup lock** (pin count = 1); freeze-only or LP_DEAD→LP_UNUSED-only can run under exclusive lock. [from-comment, heapam_xlog.h:302-310] [via knowledge/files/src/backend/access/heap/pruneheap.c.md]

## 6. Locking and invariants — CRITICAL SECTION

The heap AM relies on locks at five layers; the buffer-manager rules (pin before content lock, etc.) from `knowledge/subsystems/storage-buffer.md` are presupposed. Heap-specific rules:

### 6.1 MVCC visibility ordering rule [HIGHEST-RISK CLAIM]

When testing visibility of an xid, code **MUST** check `TransactionIdIsInProgress` **before** `TransactionIdDidCommit`. Reason: `xact.c` records commit in `pg_xact` *before* clearing `MyProc->xid`. Doing it the other way around can briefly see a just-committed xact as "crashed" because pg_xact says "no" while procarray hasn't been cleared yet. For MVCC snapshots, `XidInMVCCSnapshot` plays the same role as `TransactionIdIsInProgress`, with the same ordering rule. `TransactionIdDidAbort` cannot be used — it doesn't treat crashed-while-running xids as aborted; aborted-ness is determined by elimination (not in progress AND not committed). [from-comment, heapam_visibility.c:13-37] [via knowledge/files/src/backend/access/heap/heapam_visibility.c.md] **This is the rule that broke Multigres; getting it wrong is silent data corruption.**

### 6.2 Hint-bit WAL-flush rule [HIGH-RISK]

A hint bit (`HEAP_XMIN_COMMITTED`, `HEAP_XMAX_COMMITTED`, …) may only be set on a tuple after the corresponding xact's commit WAL is flushed to disk. `SetHintBitsExt` (`heapam_visibility.c:142-198`) enforces this with `XLogNeedsFlush(commit_lsn)`: if the WAL is not yet on disk, the function silently skips setting the bit; a later visitor will succeed. **Failing this rule causes data loss after a crash** (the bit survives, the commit doesn't, the tuple becomes visible to a snapshot that should not see it). [verified-by-code, heapam_visibility.c:142-198] [via knowledge/files/src/backend/access/heap/heapam_visibility.c.md]

### 6.3 HOT chain rules

- A HOT chain is fully contained on a single page. If an update can't fit on the same page, it cannot be HOT. [from-README, README.HOT]
- Every chain member after the root has `HEAP_ONLY_TUPLE`; every member that has been HOT-updated has `HEAP_HOT_UPDATED`. The chain ends at a member whose `t_ctid` points to itself, whose xmin is aborted, or whose `t_ctid` points off-page. [from-README, README.HOT] [verified-by-code, pruneheap.c::heap_prune_chain at pruneheap.c:1483] [via knowledge/files/src/backend/access/heap/pruneheap.c.md]
- Indexes never store entries for `HEAP_ONLY_TUPLE` rows; index TIDs reference only chain roots. [from-README, README.HOT]
- The root line pointer is reused: when the root tuple dies but the chain continues with a live successor, the root LP is converted to `LP_REDIRECT` pointing at the successor's offset; indexes follow the redirect transparently. [from-README, README.HOT]
- Following a `t_ctid` chain requires checking that the referenced slot is non-empty AND that the referenced tuple's `xmin` equals the referencing tuple's `xmax` — VACUUM can reclaim the newer tuple before the older. [from-comment, htup_details.h:86-103] [via knowledge/files/src/include/access/htup_details.h.md] **This is the single most-cited invariant for any code that walks update chains.**
- `HeapTupleHeaderIsHotUpdated` is a three-part check: `HEAP_HOT_UPDATED` AND `!HEAP_XMAX_INVALID` AND `!HeapTupleHeaderXminInvalid`. The chain auto-breaks when the updating xact aborts. [from-comment, htup_details.h:519-523]

### 6.4 Cleanup-lock vs exclusive-lock split for pruning

- Pruning that **moves tuple data** (creates redirects, reassigns LP_DEAD where a tuple body exists) requires a **buffer cleanup lock** (pin count = 1). [from-comment, heapam_xlog.h:302-310] [via knowledge/files/src/include/access/heapam_xlog.h.md]
- Freeze-only OR `LP_DEAD→LP_UNUSED`-only modifications can run under an ordinary `BUFFER_LOCK_EXCLUSIVE`. [from-comment, heapam_xlog.h:302-310]
- The `XLHP_CLEANUP_LOCK` WAL flag encodes which one redo must acquire. `heap_xlog_prune_freeze` asserts: if `XLHP_CLEANUP_LOCK` is not set, then `XLHP_HAS_REDIRECTIONS | XLHP_HAS_DEAD_ITEMS` must also be unset. [verified-by-code, heapam_xlog.c:53-54] [via knowledge/files/src/backend/access/heap/heapam_xlog.c.md]

### 6.5 Critical-section discipline

Between `START_CRIT_SECTION()` and `END_CRIT_SECTION()` **no `ereport(ERROR)` is permitted** — it would PANIC. The page lock is held throughout. `RelationPutHeapTuple` runs inside this region: the comment block at `hio.c:28-33` is emphatic ("EREPORT(ERROR) IS DISALLOWED HERE! Must PANIC on failure!!!"). VM-bit changes for the same operation are bundled into the same critical section so crash recovery sees both as a single unit. [from-comment, hio.c:28-33] [via knowledge/files/src/backend/access/heap/hio.c.md]

### 6.6 Freeze plan/execute split

`heap_prepare_freeze_tuple` (`heapam.c`) only *plans* a freeze into a `HeapTupleFreeze` and sets `pagefrz->freeze_required`; it does NOT touch the tuple. `heap_pre_freeze_checks` validates xmin-committed / xmax-aborted invariants before execution. `heap_freeze_prepared_tuples` (called inside `heap_page_prune_and_freeze`'s critical section) applies the plans via the inline `heap_execute_freeze_tuple`. This separation lets VACUUM batch all per-page checks before entering the crit section. [from-comment, heapam.h around lines 406-413] [via knowledge/files/src/include/access/heapam.h.md]

### 6.7 Tuple locking — two-level mechanism

`heap_lock_tuple` implements four lock modes (KeyShare / Share / NoKeyExclusive / Exclusive) with a 4×4 conflict matrix. The first level is *cheap*: store lock state in `xmax` + infomask bits. When multiple lockers concurrently hold the tuple, or a locker coexists with an updater, the state is encoded as a MultiXactId. The second level uses the heavyweight lock manager with `LOCKTAG_TUPLE` — but **only to serialise waiters fairly** (FIFO via the lmgr wait queue), not as the lock itself. A waiter acquires `LOCKTAG_TUPLE` *before* sleeping on the conflicting xact's xmax. [from-README, README.tuplock] [via knowledge/files/src/backend/access/heap/README.md]

### 6.8 Two-buffer locking order (cross-page UPDATE)

When `heap_update` needs to write a new tuple on a different page from the old one, **both buffer locks** plus possibly both VM pins must be acquired in **lower-block-first** order to avoid deadlock against another concurrent UPDATE that picks the opposite pair. `GetVisibilityMapPins` (`hio.c:138`) and `RelationGetBufferForTuple` (`hio.c:500`) both implement this. [verified-by-code, hio.c:138, 500] [via knowledge/files/src/backend/access/heap/hio.c.md]

### 6.9 VM bit invariants

- `ALL_FROZEN` may be set only if `ALL_VISIBLE` is also set. [from-comment, visibilitymap.c:31; verified-by-code, visibilitymap.c:279]
- VM bit changes are NOT independently WAL-logged — the heap WAL record drives both forks. [from-comment, visibilitymap.c:37-42]
- VM is **conservative**: set bit authoritative, clear bit means "unknown". [from-comment, visibilitymap.c:33-35]
- `PD_ALL_VISIBLE` on the heap page MUST stay in sync with the VM bit. [from-comment, visibilitymap.c:50-51]
- The "examine page → pin VM → re-lock" dance: a modifier inspects the heap page (unlocked or share-locked), decides whether it might be all-visible; if maybe, releases lock, pins the VM page (because VM-page read can block on I/O — never hold a buffer lock across VM I/O), then re-acquires the heap lock and re-checks. The race window is documented and ubiquitous. [from-comment, visibilitymap.c:76-90] [via knowledge/files/src/backend/access/heap/visibilitymap.c.md]

### 6.10 In-place catalog updates

`heap_inplace_lock` / `heap_inplace_update_and_unlock` is the path for `pg_class.relfrozenxid`, `pg_database.datfrozenxid`, and similar single-tuple catalog updates that must avoid creating a new HOT chain (the new chain would have a newer xmin than `relfrozenxid` expects). Uses a dedicated lock plus the buffer exclusive lock; the WAL record `xl_heap_inplace` carries shared-invalidation messages so standbys' relcaches are invalidated. [verified-by-code, heapam.c] [via knowledge/files/src/backend/access/heap/heapam.c.md]

## 7. Interactions with other subsystems

- **`storage/buffer`** — every heap operation pins + content-locks the target buffer(s); presupposes the buffer-mgr ordering rules (`knowledge/subsystems/storage-buffer.md`). `MarkBufferDirty` and `MarkBufferDirtyHint` are called pervasively (the latter for hint-bit writes). [verified-by-code]
- **`access/transam` (xlog, xact, multixact)** — every mutating op emits a WAL record (see `heapam_xlog.h` opcodes); visibility consults `TransactionIdIsInProgress` (procarray), `TransactionIdDidCommit` (transam), `XidInMVCCSnapshot`, `MultiXactIdGetMembers`. `xlog.c` rmgr dispatch is the entry to `heap_redo`/`heap2_redo`. [verified-by-code, heapam_xlog.c:1-30; via knowledge/files/src/backend/access/heap/heapam_xlog.c.md]
- **`storage/freespace` (FSM)** — `RelationGetBufferForTuple` consults `GetPageWithFreeSpace`; pruning and vacuum-cleanup call `RecordPageWithFreeSpace`. [via knowledge/files/src/backend/access/heap/hio.c.md]
- **`access/heap/visibilitymap`** (in-subsystem) — heap modifiers clear VM bits; pruning and vacuum set them via the unified prune+freeze WAL record. [via knowledge/files/src/backend/access/heap/visibilitymap.c.md]
- **Index AMs** — call back into heap via `heap_index_delete_tuples` (bottom-up deletion) and `heap_hot_search_buffer` (HOT-chain following from a root TID); index-only scans rely on the VM `ALL_VISIBLE` bit. [verified-by-code, heapam.h:429-442]
- **MVCC / snapshot manager** — `HeapTupleSatisfiesVisibility` switches on `snapshot->snapshot_type` and dispatches to MVCC/Self/Dirty/Any/Toast/HistoricMVCC. [via knowledge/files/src/backend/access/heap/heapam_visibility.c.md]
- **`commands/vacuum` and `commands/vacuumparallel`** — drive `heap_vacuum_rel`; the parallel path runs index vacuum across workers using a shared TID store. [via knowledge/files/src/backend/access/heap/vacuumlazy.c.md]
- **`replication/logical`** — `log_heap_new_cid`, `ExtractReplicaIdentity`, the rewrite-mapping files in `rewriteheap.c`, and `XLH_DELETE_NO_LOGICAL` / `XLH_UPDATE_CONTAINS_OLD_KEY` flags exist so logical decoding can reconstruct row identity across rewrites and key-changing updates. [verified-by-code; via knowledge/files/src/backend/access/heap/rewriteheap.c.md]
- **`utils/time/combocid`** — `HeapTupleHeaderGetCmin/Cmax/AdjustCmax` live there; needed because cmin/cmax/xvac share one 4-byte slot. [from-comment, htup_details.h:73-84]
- **`access/toast`** — `heaptoast.c` is called from `heap_insert`/`heap_update` whenever a tuple exceeds the inline threshold; TOAST chunks use their own visibility rule (`HeapTupleSatisfiesToast` at `heapam_visibility.c:452`). [via knowledge/files/src/backend/access/heap/heapam_visibility.c.md]
- **Executor (`executor/nodeModifyTable.c`, scan nodes, `commands/copy*.c`, `catalog/*`)** — call through `heapam_handler.c`'s function pointers. [via knowledge/files/src/backend/access/heap/heapam_handler.c.md]

## 8. Tests

- **Regress** (`source/src/test/regress/sql/`) — `vacuum.sql`, `vacuum_parallel.sql`, `update.sql`, `delete.sql`, `insert*.sql`, `cluster.sql`, `combocid.sql`, `tidscan.sql`, `tidrangescan.sql`. The HOT mechanism is exercised throughout but most directly via `vacuum.sql` and `update.sql`. [verified-by-code, directory listing]
- **Isolation** (`source/src/test/isolation/specs/`) — `vacuum-no-cleanup-lock.spec` (the `lazy_scan_noprune` fallback), `freeze-the-dead.spec`, `tuplelock-*.spec` (the four-mode conflict matrix), `multiple-row-versions.spec`, `hot-update-*.spec` if present. [verified-by-code]
- **TAP** — `src/test/recovery/` exercises crash-recovery of heap WAL; `src/test/modules/test_aio/` exercises read-stream-driven scans. [verified-by-code]
- **`USE_ASSERT_CHECKING` only**: `heap_page_is_all_visible` (`vacuumlazy.c:3550`) re-derives the all-visible flag from scratch and compares to claim. [verified-by-code]
- `pg_visibility` contrib provides SQL inspection of VM bits; useful as a debugging probe.

## 9. Open questions / unverified claims

Carried forward from the per-file docs:

1. **Lock-ordering proof for cross-page UPDATE.** Code follows lower-block-first via `GetVisibilityMapPins` and `RelationGetBufferForTuple`, but the deadlock-freedom proof relies on global TID ordering across concurrent updaters and was not fully enumerated. [unverified] [carried from heapam.c.md] **Highest-risk locking claim in the subsystem.**
2. **MultiXact starvation under contention.** README.tuplock describes the LOCKTAG_TUPLE fairness mechanism, but the exact enqueue path in `heap_lock_tuple` was not deep-read. [unverified] [carried from heapam.c.md]
3. **Replica-identity old-key extraction.** For `REPLICA IDENTITY USING INDEX`, key columns are looked up via `RelationGetIndexAttrBitmap`; interaction with concurrent index drops was not traced. [unverified] [carried from heapam.c.md]
4. **WAL flag enumeration.** Many flag combinations (e.g. `XLH_INSERT_ALL_FROZEN_SET` on UPDATE's new buffer, `XLH_DELETE_NO_LOGICAL`) — emit-side conditions not exhaustively enumerated. [unverified] [carried from heapam.c.md]
5. **Pre-9.0 `HEAP_MOVED_OFF/IN` paths in `heap_prepare_freeze_tuple`.** Still present; not verified whether reachable only via pg_upgrade or fully dead. [unverified] [carried from heapam.c.md, htup_details.h.md]
6. **`SetHintBits` legacy-bits cases.** Rules for setting `HEAP_XMIN_FROZEN` from inside visibility code (vs explicit freeze) not fully traced. [unverified] [carried from heapam_visibility.c.md]
7. **`HeapTupleSatisfiesHistoricMVCC` sub-transaction interaction** with logical decoding — comment is brief. [unverified] [carried from heapam_visibility.c.md]
8. **`HeapTupleIsSurelyDead` precondition adherence.** Comment says "pin only, no content lock required"; not all callers were audited. [unverified — high-risk if not] [carried from heapam_visibility.c.md]
9. **`lazy_scan_noprune` VM-bit branches.** It claims to set `ALL_FROZEN` only when no data needs moving, but each branch was not verified. [unverified — important for correctness] [carried from vacuumlazy.c.md]
10. **`heap_page_will_freeze` eager-freeze heuristic.** Decision formula not deep-read. [unverified] [carried from pruneheap.c.md]
11. **Behaviour when an `LP_REDIRECT` target itself becomes `LP_DEAD`.** Chain walker handles it but transitions were not enumerated. [unverified] [carried from pruneheap.c.md]
12. **Prune-and-freeze ordering: "drop pin, take cleanup lock, re-pin".** Relies on bufmgr API but not summarised in README. [unverified] [carried from README.md]
13. **`dead_items_alloc` parallel-VACUUM dispatch.** Phase III reap work distribution across workers not traced. [unverified] [carried from vacuumlazy.c.md]
14. **VM `vm_extend` extension-lock scope.** Whether still held for the full extension or refactored to the bulk-extend pattern. [unverified] [carried from visibilitymap.c.md]
15. **`visibilitymap_set` LSN-skip rule for unlogged tables.** Not enumerated. [unverified] [carried from visibilitymap.c.md]
16. **`heapam_relation_copy_data` post-rewrite usage** — still used outside `CREATE TABLE AS` / no-rewrite ALTER? [unverified] [carried from heapam_handler.c.md]
17. **Concurrent index-build snapshot mgmt in `heapam_index_build_range_scan`.** Changed multiple times across versions. [unverified] [carried from heapam_handler.c.md]
18. **FPI fast-path branches per redo handler.** `XLogReadBufferForRedo` return value drives this but per-handler branches not enumerated. [unverified] [carried from heapam_xlog.c.md]
19. **`XLOG_HEAP_TRUNCATE` emission today.** Still emitted by main `heap_truncate` or only partition paths? [unverified] [carried from heapam_xlog.h.md]
20. **`XLH_DELETE_IS_PARTITION_MOVE` × logical-decoding handling.** Exact relationship not traced. [unverified] [carried from heapam_xlog.h.md]
21. **`heap_inplace_lock` discipline.** Interface in heapam.h, mechanism in heapam.c not deep-read. [unverified] [carried from heapam.h.md]
22. **`unresolved_tups` overflow in `rewriteheap.c`.** Comment says "shouldn't happen" but no spill-to-disk. [unverified] [carried from rewriteheap.c.md]
23. **`MINIMAL_TUPLE_PADDING` on non-8-byte-aligned platforms.** Macro arithmetic correct, alignof cases not enumerated. [unverified] [carried from htup_details.h.md]
24. **`RelationAddBlocks` batch-size heuristic.** `already_extended_by` formula not deep-read. [unverified] [carried from hio.c.md]
25. **`RelationGetBufferForTuple` VM pin contract.** Whether it ever returns without pinning the VM page. [unverified] [carried from hio.c.md]

## 10. Glossary

- **HOT (Heap-Only Tuple)** — A new tuple version chained on the same page as its predecessor via `t_ctid`, with `HEAP_ONLY_TUPLE` set; produced by an UPDATE that changed no indexed column. Not pointed at by any index. [from-README, README.HOT]
- **HOT chain** — A linked list of HOT tuples + their non-HOT root, all on one page. Root LP may be converted to `LP_REDIRECT` after pruning. [from-README]
- **`LP_REDIRECT`** — Line-pointer state where the LP's offset is reused to point at another LP on the same page (a surviving chain member). Indexes hitting the old root TID transparently follow the redirect. [from-README, README.HOT]
- **`LP_DEAD`** — Line pointer whose tuple was reclaimed by pruning but whose LP cannot yet be reused because index entries may still point at it. Converted to `LP_UNUSED` by VACUUM's phase III after the indexes are vacuumed. [from-README, README.HOT]
- **`LP_UNUSED`** — Free line pointer; can be reused by a new insert. [verified-by-code]
- **Infomask bits** — `HEAP_XMIN_COMMITTED`/`_INVALID`/`_FROZEN`, `HEAP_XMAX_COMMITTED`/`_INVALID`/`_IS_MULTI`/`_LOCK_ONLY`/`_KEYSHR_LOCK`/`_EXCL_LOCK`, `HEAP_HASNULL`, `HEAP_HASVARWIDTH`, `HEAP_HASEXTERNAL`, `HEAP_UPDATED`, `HEAP_COMBOCID`, `HEAP_MOVED_*`. In `t_infomask2`: `HEAP_NATTS_MASK`, `HEAP_KEYS_UPDATED`, `HEAP_HOT_UPDATED`, `HEAP_ONLY_TUPLE`. [verified-by-code, htup_details.h:190-296]
- **Hint bits** — `HEAP_XMIN_COMMITTED`/`HEAP_XMAX_COMMITTED` (and friends): commit-status caches set lazily by visibility routines. Not WAL-logged; written under share-exclusive content lock; cannot be set before the relevant commit-WAL is flushed. [from-comment, heapam_visibility.c:6-11,115-124]
- **Freeze** — Replace a still-live old xmin with `FrozenTransactionId` (encoded as `HEAP_XMIN_FROZEN = HEAP_XMIN_COMMITTED|HEAP_XMIN_INVALID`) so the tuple survives 32-bit xid wraparound. Also strip lock-only xmax bits below the multixact cutoff. [verified-by-code, htup_details.h:204-208]
- **Vacuum cycle id** — Per-VACUUM identifier used by index AMs (e.g. btree) to detect concurrent splits; the heap AM doesn't carry it on tuples but supplies it via VACUUM driver parameters. [verified-by-code]
- **`ItemPointer` / TID** — `(BlockNumber, OffsetNumber)` pair identifying an LP slot on a page. `t_self` is the tuple's own TID; `t_ctid` points to the successor or to itself (= no successor or speculative-insert token). [verified-by-code, htup_details.h:86-112]
- **MultiXactId** — Composite xid used in `xmax` whenever ≥2 transactions concurrently hold a tuple lock, or a locker coexists with an updater. Resolved via `multixact.c::MultiXactIdGetMembers` and `HeapTupleGetUpdateXid`. May force disk I/O. [from-README, README.tuplock]
- **`HEAP_LOCKED_UPGRADED`** — A 9.2-era share-lock-only multixact form that survived pg_upgrade; must not be resolved locally because it may reference xids outside the current valid multixact range. [from-comment, htup_details.h:237-261]
- **Speculative insertion** — INSERT … ON CONFLICT machinery: insert a tuple with a speculative token stored in `t_ctid`; on success, `heap_finish_speculative` replaces the token with the real `t_self`; on conflict, `heap_abort_speculative` "super-deletes" the tuple (`XLH_DELETE_IS_SUPER`). [verified-by-code, heapam.h:393-396]
- **VM (visibility map)** — Auxiliary fork holding 2 bits per heap page (`ALL_VISIBLE`, `ALL_FROZEN`). Conservative. Not independently WAL-logged. [from-comment, visibilitymap.c:1-95]
- **FSM (free space map)** — Auxiliary fork tracking per-page free space; consulted by `RelationGetBufferForTuple` and updated by pruning/vacuum. [verified-by-code, hio.c]
- **`PRUNE_VACUUM_CLEANUP`** — Second-pass mode in `heap_page_prune_and_freeze` used by `lazy_vacuum_heap_page`: converts `LP_DEAD → LP_UNUSED` for offsets in the dead-items TID store. No data movement; exclusive lock suffices. [from-comment, heapam_xlog.h]
- **`LOCKTAG_TUPLE`** — Heavyweight lock used purely to serialise tuple-lock waiters in FIFO order; not the lock itself (the lock state lives in xmax+infomask). [from-README, README.tuplock]

## Files owned
<!-- files-owned:auto -->

*Files under this subsystem's owned paths (by slug derivation + include-header filters). Auto-refreshed by `scripts/populate-subsystem-files.py`.*

**23 files.**

| File |
|---|
| [`src/backend/access/heap/README`](../files/src/backend/access/heap/README.md) |
| [`src/backend/access/heap/heapam.c`](../files/src/backend/access/heap/heapam.c.md) |
| [`src/backend/access/heap/heapam_handler.c`](../files/src/backend/access/heap/heapam_handler.c.md) |
| [`src/backend/access/heap/heapam_indexscan.c`](../files/src/backend/access/heap/heapam_indexscan.c.md) |
| [`src/backend/access/heap/heapam_visibility.c`](../files/src/backend/access/heap/heapam_visibility.c.md) |
| [`src/backend/access/heap/heapam_xlog.c`](../files/src/backend/access/heap/heapam_xlog.c.md) |
| [`src/backend/access/heap/heaptoast.c`](../files/src/backend/access/heap/heaptoast.c.md) |
| [`src/backend/access/heap/hio.c`](../files/src/backend/access/heap/hio.c.md) |
| [`src/backend/access/heap/pruneheap.c`](../files/src/backend/access/heap/pruneheap.c.md) |
| [`src/backend/access/heap/rewriteheap.c`](../files/src/backend/access/heap/rewriteheap.c.md) |
| [`src/backend/access/heap/vacuumlazy.c`](../files/src/backend/access/heap/vacuumlazy.c.md) |
| [`src/backend/access/heap/visibilitymap.c`](../files/src/backend/access/heap/visibilitymap.c.md) |
| [`src/include/access/brin_tuple.h`](../files/src/include/access/brin_tuple.h.md) |
| [`src/include/access/gin_tuple.h`](../files/src/include/access/gin_tuple.h.md) |
| [`src/include/access/heapam.h`](../files/src/include/access/heapam.h.md) |
| [`src/include/access/heapam_xlog.h`](../files/src/include/access/heapam_xlog.h.md) |
| [`src/include/access/heaptoast`](../files/src/include/access/heaptoast.md) |
| [`src/include/access/hio.h`](../files/src/include/access/hio.h.md) |
| [`src/include/access/htup.h`](../files/src/include/access/htup.h.md) |
| [`src/include/access/htup_details.h`](../files/src/include/access/htup_details.h.md) |
| [`src/include/access/rewriteheap.h`](../files/src/include/access/rewriteheap.h.md) |
| [`src/include/access/visibilitymap.h`](../files/src/include/access/visibilitymap.h.md) |
| [`src/include/access/visibilitymapdefs.h`](../files/src/include/access/visibilitymapdefs.h.md) |

<!-- /files-owned:auto -->
