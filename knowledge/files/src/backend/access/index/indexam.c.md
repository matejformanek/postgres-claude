# indexam.c

- **Source path:** `source/src/backend/access/index/indexam.c`
- **Lines:** 1059
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `indexam.h`, `amapi.h` (IndexAmRoutine vtable), `genam.c` (sibling), `tableam.c` (the heap fetch side), `relcache.c`.

## Purpose

The per-tuple dispatch layer of the index AM API. Every read/insert/scan operation on an index goes through `index_*` here, which translates to the AM-private callback via `indexRelation->rd_indam->am{insert,beginscan,gettuple,…}`. Also owns parallel-scan setup, the AM ↔ tableam interaction during `index_fetch_heap` (HOT-chain following), and the `index_getprocid` / `index_getprocinfo` opclass support-fn cache. [from-comment, indexam.c:13-40]

## Top-of-file comment

> "general index access method routines" — Then a 30-line "INTERFACE ROUTINES" listing (`index_open`, `index_close`, `index_beginscan`, …, `index_bulk_delete`, `index_vacuum_cleanup`, `index_can_return`, `index_getprocid`, `index_getprocinfo`). [from-comment, indexam.c:13-40]

## Public surface (grouped)

- **Open/close:** `index_open` (134), `try_index_open` (153), `index_close` (178), `validate_relation_as_index` (198, internal sanity).
- **Inserts:** `index_insert` (214), `index_insert_cleanup` (242).
- **Scan setup:** `index_beginscan` (257), `index_beginscan_bitmap` (301), `index_beginscan_internal` (326, static common code), `index_rescan` (368), `index_endscan` (394), `index_markpos` (424), `index_restrpos` (448).
- **Parallel scan:** `index_parallelscan_estimate` (470), `index_parallelscan_initialize` (505), `index_parallelrescan` (538), `index_beginscan_parallel` (560).
- **Per-tuple:** `index_getnext_tid` (599), `index_fetch_heap` (657), `index_getnext_slot` (698), `index_getbitmap` (743).
- **Maintenance:** `index_bulk_delete` (773), `index_vacuum_cleanup` (794), `index_can_return` (813).
- **Opclass procs:** `index_getprocid` (851), `index_getprocinfo` (885).
- **Misc:** `index_store_float8_orderby_distances` (953), `index_opclass_options` (1016).

## Key macros (top of file)

- `RELATION_CHECKS` — Validates `indexRelation`, `rd_indam`, and trips if `ReindexIsProcessingIndex(relid)`. [from-comment, indexam.c:63-75]
- `SCAN_CHECKS` — Same on a scan descriptor.
- `CHECK_REL_PROCEDURE(pname)` / `CHECK_SCAN_PROCEDURE(pname)` — `elog(ERROR, ...)` if the AM left that callback NULL.

## Key invariants

- **Reindex re-entrancy guard:** `RELATION_CHECKS` blocks user-driven access (scans, retail inserts) on an index that's currently being rebuilt. The rebuild itself calls the AM's `ambuild` directly, bypassing this file. [from-comment, indexam.c:63-75]
- **Predicate locking:** `index_beginscan_internal` (335) calls `PredicateLockRelation(indexRelation, snapshot)` when the AM has `ampredlocks == false`. AMs that take per-page or per-tuple predicate locks themselves (`ampredlocks == true`, e.g. btree, hash, gist) skip this. [verified-by-code, indexam.c:335-337]
- **Snapshot rules:** `index_beginscan` rejects historic MVCC snapshots on non-catalog tables (`ERRCODE_INVALID_TRANSACTION_STATE`). [verified-by-code, indexam.c:268-276]
- **HOT-chain follow:** `index_getnext_slot` (698) loops calling `index_getnext_tid` + `index_fetch_heap`; `scan->xs_heap_continue` (set by the tableam) tells us to keep fetching from the same HOT chain. [verified-by-code, indexam.c:698-740]
- **Bottom-up kill_prior_tuple hint:** When `index_fetch_heap` finds every tuple in a HOT chain dead under our snapshot, it sets `scan->kill_prior_tuple = true` so the NEXT `amgettuple` can mark the index TID `LP_DEAD`. Suppressed during recovery (`xactStartedInRecovery`) since hint-marking on a standby could violate MVCC for other backends. [verified-by-code, indexam.c:657-680]
- **Parallel scan:** `index_parallelscan_initialize` does NOT take an MVCC snapshot — workers attach to the leader's snapshot via `RestoreSnapshot`. The `ParallelIndexScanDesc` lives in the leader's DSM. [verified-by-code, indexam.c:505-560]
- **Opclass support-fn cache:** `index_getprocinfo` (885) lazily fills the cached `FmgrInfo` arrays in `RelationData->rd_supportinfo`; supports up to `RelationGetIndexNumberOfSupportProcedures(idx)` per column. [verified-by-code]

## Functions of note

1. **`index_beginscan`** (257) — Creates the scan descriptor via the AM's `ambeginscan`, attaches the heap relation, calls `table_index_fetch_begin` to set up the table-side state needed for `index_fetch_heap`. [verified-by-code]
2. **`index_getnext_tid`** (599) — Pure dispatch to `amgettuple`; resets `kill_prior_tuple` and `xs_heap_continue`. The TID gets written into `scan->xs_heaptid`. [verified-by-code]
3. **`index_fetch_heap`** (657) — Calls `table_index_fetch_tuple` (which dispatches through `tableam`); on HOT-chain follow `all_dead` triggers `kill_prior_tuple = true` for the next round. [verified-by-code]
4. **`index_insert`** (214) — Plain dispatch to `aminsert`. The caller is responsible for whether or not a unique check is desired (`IndexUniqueCheck` flag). [verified-by-code]
5. **`index_bulk_delete`** (773), **`index_vacuum_cleanup`** (794) — VACUUM-side dispatch into `ambulkdelete` / `amvacuumcleanup`. The IndexAmRoutine docs (in amapi.h) explain the two-phase contract. [verified-by-code]

## Cross-references

- Called by: executor (`nodeIndexscan.c`, `nodeIndexonlyscan.c`, `nodeBitmapIndexscan.c`), `commands/vacuum.c` (via `index_bulk_delete` / `index_vacuum_cleanup`), catalog code that does retail inserts (`CatalogIndexInsert`).
- Calls into: per-AM via `IndexAmRoutine` callbacks; `tableam.c` (`table_index_fetch_*`); `predicate.c` (predicate locks); `genam.c::RelationGetIndexScan`.

## Open questions

- Behaviour of `kill_prior_tuple` for indexes that don't support it (`amcanmarkpos == false`? — actually `amgettuple == NULL` AMs). The reset path looks defensive but I didn't construct a counter-example. [unverified]

## Confidence tag tally
`[verified-by-code]=12 [from-comment]=3 [from-readme]=0 [inferred]=0 [unverified]=1`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
