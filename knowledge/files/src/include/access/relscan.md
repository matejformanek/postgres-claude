# `access/relscan.h` — scan descriptor structs

**Verified against source pin `4b0bf0788b0`** (path: `source/src/include/access/relscan.h`)

## Role
The "base class" descriptors that table and index AMs embed in their own
larger AM-specific structs. Defines `TableScanDescData`,
`ParallelTableScanDescData`, `ParallelBlockTableScanDescData`,
`ParallelBlockTableScanWorkerData`, `IndexFetchTableData`,
`IndexScanDescData`, `ParallelIndexScanDescData`, `SysScanDescData`.

## Public API
- `TableScanDescData` (`relscan.h:33`) — `rs_rd` relation, `rs_snapshot`,
  `rs_nkeys`/`rs_key` scan-key array, union of bitmap iterator or TID range,
  `rs_flags` (ScanOptions bitmask), `rs_parallel`, `rs_instrument`.
- `ParallelTableScanDescData` (`relscan.h:85`) — physical RelFileLocator
  + syncscan/snapshot booleans + snapshot offset for the trailing snapshot.
- `ParallelBlockTableScanDescData` (`relscan.h:97`) — block-oriented:
  `phs_nblocks`, `phs_mutex` (slock), `phs_startblock`, `phs_numblock`,
  `phs_nallocated` (atomic).
- `ParallelBlockTableScanWorkerData` (`relscan.h:114`) — per-backend
  worker state: `phsw_nallocated`, `phsw_chunk_remaining`, `phsw_chunk_size`.
- `IndexFetchTableData` (`relscan.h:128`) — `rel` + `flags` (ScanOptions).
- `IndexScanDescData` (`relscan.h:146`) — heap/index Relation, snapshot,
  scan-key + orderby-key arrays, `xs_want_itup`, `kill_prior_tuple`,
  `ignore_killed_tuples`, `xactStartedInRecovery`, AM-private `opaque`,
  `xs_itup`/`xs_hitup` returned tuple, `xs_heaptid`, `xs_heap_continue`,
  `xs_recheck`, orderby vals/nulls, `parallel_scan`.
- `ParallelIndexScanDescData` (`relscan.h:208`) — physical RelFileLocator
  for table + index, am-specific offset, trailing snapshot data
  (`FLEXIBLE_ARRAY_MEMBER`).
- `SysScanDescData` (`relscan.h:219`) — wraps either a heap scan
  or an index scan for system catalogs.

## Invariants
- `rs_nkeys != 0` ⇒ results filtered by `rs_key`. `[from-comment]`
  (`tableam.h:347`).
- `kill_prior_tuple` set by executor ⇒ previously-returned heap tuple was
  found dead; AM may mark the index tuple LP_DEAD. `[from-comment]`
  (`relscan.h:159`-`161`).
- `xactStartedInRecovery` prevents killing/seeing already-killed tuples on
  hot-standby. `[from-comment]` (`relscan.h:162`-`163`).
- `IndexScanDescData.opaque` is AM-private — core must not touch it.
  `[from-comment]` (`relscan.h:165`-`166`).
- `xs_recheck=true` means scan-key recheck required (e.g., for lossy
  bitmaps). `[from-comment]` (`relscan.h:190`).
- `phs_mutex` (slock_t) protects `phs_startblock` writes;
  `phs_nallocated` is atomic-incremented (no lock). `[from-comment]`
  (`relscan.h:102`-`107`).
- `ParallelIndexScanDescData.ps_snapshot_data[FLEXIBLE_ARRAY_MEMBER]` —
  caller responsible for sizing the allocation. `[verified-by-code]`
  (`relscan.h:213`).

## Notable internals
- The bitmap iterator and TID range form a **union** in
  `TableScanDescData.st` — only one type of scan uses each at a time
  (`relscan.h:44`-`58`).
- `IndexScanDescData` doubles for both amgettuple and amgetbitmap — some
  fields valid only for one mode (`relscan.h:142`-`145`).
- `xs_itup` (IndexTuple) and `xs_hitup` (HeapTuple) are both fillable; if
  both filled, the heap form is used. `[from-comment]` (`relscan.h:174`-`178`).

## Trust-boundary / Phase D surface

These structs are the inter-AM communication channel; every AM writes to
them, every executor node reads from them.

**[ISSUE-api-shape: `IndexScanDescData.opaque` is `void *` with no type-tag
(informational)]** — Casts in AM-specific code rely on convention; a mixed
AM swap (impossible in practice but theoretically) would be silent corruption.
`relscan.h:165`-`166`.

**[ISSUE-concurrency: `phs_mutex` is a spinlock — hold-time matters (low)]** —
Parallel block scan startblock setting is a critical section guarded by a
spinlock. `[from-comment]` `relscan.h:102`-`103`. Any future change to hold
this for non-trivial work would regress parallel-scan startup.

**[ISSUE-memory: ParallelIndexScanDescData uses FLEXIBLE_ARRAY_MEMBER for
snapshot data (low)]** — Standard PG pattern, but improperly-sized
allocations are silent OOB writes. Sizing comes from
`EstimateSnapshotSpace` → `index_parallelscan_estimate`. `relscan.h:213`.

## Cross-refs
- `knowledge/files/src/include/access/tableam.h` — `table_*` wrappers
  populate and consume these structs.
- `knowledge/files/src/include/access/genam.h` — `index_*` and `systable_*`
  wrappers.
- `knowledge/idioms/locking.md` (not yet written) — slock_t/atomic split
  inside ParallelBlockTableScanDesc.

## Issues
1. **[ISSUE-api-shape: opaque void* without type tag (informational)]**
   — `relscan.h:165`-`166`.
2. **[ISSUE-concurrency: spinlock-protected startblock (low)]**
   — `relscan.h:102`-`103`.
3. **[ISSUE-memory: FLEXIBLE_ARRAY_MEMBER snapshot sizing (low)]**
   — `relscan.h:213`.
