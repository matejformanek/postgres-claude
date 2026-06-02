---
name: access-method-apis
description: PostgreSQL pluggable access method internals for hackers implementing an index or table AM — IndexAmRoutine callbacks (ambuild, aminsert, amgettuple, amgetbitmap, ambulkdelete, amvacuumcleanup), TableAmRoutine callbacks (scan_begin, scan_getnextslot, tuple_insert, tuple_insert_speculative, slot_callbacks), opclass/strategy numbers and support functions, TID semantics for non-heap stores, genam.c and tableam.h wrappers, CREATE ACCESS METHOD + pg_am/pg_opclass registration. Use whenever a patch implements or modifies an index AM or table AM. Skip user-facing "which index should I use" or query-tuning questions.
---

# Access-method APIs — operational guide

This skill is for code that **implements** an AM (or significantly extends one).
Read-only "how does btree work" questions don't need it — go straight to the
per-AM README.

## Two completely separate plug points

| | Index AM | Table AM |
|---|---|---|
| Struct | `IndexAmRoutine` in `src/include/access/amapi.h` | `TableAmRoutine` in `src/include/access/tableam.h` |
| Resolver | `GetIndexAmRoutine(amhandler)` in `src/backend/access/index/amapi.c` | `GetTableAmRoutine(amhandler)` in `src/backend/access/table/tableamapi.c` |
| Catalog | `pg_am.amtype = 'i'` | `pg_am.amtype = 't'` |
| Executor wrapper | `genam.c` / `indexam.c` | inline wrappers in `tableam.h` (`table_beginscan`, `table_tuple_insert`, …) |
| Canonical impl | `nbtree.c`, also `brin.c`, `gin.c`, `gist.c`, `hash.c`, `spgist.c` | `heapam_handler.c` (the only in-tree one) |
| Minimal stub | `src/test/modules/dummy_index_am/dummy_index_am.c` | none in tree |
| Added | Index AM API since 9.6 (`amapi.h`); table AM since v12 | |

Both APIs work the same way at the dispatch level: a `pg_am` row's `amhandler`
column names a SQL-callable C function (`PG_FUNCTION_INFO_V1`) that returns a
pointer to a **statically allocated** `IndexAmRoutine`/`TableAmRoutine`. The
core never copies or frees the struct.

```c
Datum
myhandler(PG_FUNCTION_ARGS)
{
    static const IndexAmRoutine amroutine = { .type = T_IndexAmRoutine, ... };
    PG_RETURN_POINTER(&amroutine);
}
```

## Index AM (IndexAmRoutine)

### Flag/property fields (~22 booleans + counts)
Declarative facts the planner needs *before* it ever calls a function pointer:

- `amstrategies` — count of operator strategies (e.g. btree has 5: `<`, `<=`, `=`,
  `>=`, `>`). 0 if the AM doesn't use a fixed strategy set (gin/gist).
- `amsupport` — count of mandatory support functions per opclass.
- `amoptsprocnum` — opclass-options procedure number, or 0.
- `amcanorder`, `amcanorderbyop`, `amcanhash`, `amcanbackward`, `amcanunique`,
  `amcanmulticol`, `amoptionalkey`, `amsearcharray`, `amsearchnulls`,
  `amstorage`, `amclusterable`, `ampredlocks`, `amcanparallel`,
  `amcanbuildparallel`, `amcaninclude`, `amusemaintenanceworkmem`,
  `amsummarizing`, `amconsistentequality`, `amconsistentordering`.
- `amparallelvacuumoptions` — bitmask of `VACUUM_OPTION_*` (`PARALLEL_BULKDEL`,
  `PARALLEL_COND_CLEANUP`, `PARALLEL_CLEANUP`). Set to `VACUUM_OPTION_NO_PARALLEL`
  (= 0) to opt out of parallel vacuum entirely — the right default for a brand-new AM.
- `amkeytype` — fixed key type OID, or `InvalidOid` if variable.

### Function pointers — mandatory
Must be non-NULL (planner/executor will dereference unconditionally):

| Callback | Purpose |
|---|---|
| `ambuild` | Build a new index from scratch over `heapRelation`. Drives parallel build internally. |
| `ambuildempty` | Build the **init fork** for unlogged indexes. |
| `aminsert` | Insert one tuple. Called inside `ExecInsertIndexTuples`. |
| `ambulkdelete` | Vacuum pass that drops index entries whose heap TID matches a callback (returns `IndexBulkDeleteResult *`). |
| `amvacuumcleanup` | Final vacuum pass (returns `IndexBulkDeleteResult *`); may return stats and reclaim empty pages. |
| `amcostestimate` | Planner cost callback. Fill in start/total/selectivity/correlation/pages. |
| `amoptions` | Parse `WITH (...)` reloptions via `build_reloptions`. May return NULL. |
| `amvalidate` | Sanity-check an opclass at `CREATE OPERATOR CLASS` time. |
| `ambeginscan` | Must call `RelationGetIndexScan()` and return its result. |
| `amrescan` | (Re)bind scan keys. |
| `amendscan` | Tear down scan-private state (don't free the IndexScanDesc itself). |

> **GOTCHA — `ambeginscan` return identity.**
> `ambeginscan` **MUST return the exact `IndexScanDesc` that `RelationGetIndexScan()`
> gave it** — not a copy, not a wrapper. `index_endscan` (in `genam.c`) reaches
> inside that struct *after* the AM's `amendscan` has already run, so any
> reallocation breaks teardown. The comment at the top of `genam.c` calls this
> "kinda ugly". Allocate your private state separately and hang it off
> `scan->opaque`.

### Function pointers — optional (may be NULL)
`aminsertcleanup`, `amcanreturn` (for index-only scans), `amgettreeheight`,
`amproperty`, `ambuildphasename`, `amadjustmembers`, `amgettuple` (NULL ⇒ no
plain indexscan, only bitmap), `amgetbitmap` (NULL ⇒ no bitmap scan),
`ammarkpos`/`amrestrpos` (NULL ⇒ no mark/restore — fine if `amcanbackward=false`
or no merge-join support is needed), the three `amestimate/init/parallelrescan`
parallel-scan hooks (required iff `amcanparallel=true`), `amtranslatestrategy`/
`amtranslatecmptype`.

You need **either** `amgettuple` or `amgetbitmap` (typically both — gin is
bitmap-only).

### Lifecycle — build / insert / scan / vacuum

```
CREATE INDEX  → ambuild
SELECT ...    → ambeginscan → amrescan → (loop) amgettuple|amgetbitmap → amendscan
INSERT/UPDATE → (per row) aminsert → (once at end of statement) aminsertcleanup
VACUUM        → ambulkdelete (may be called many times) → amvacuumcleanup
DROP INDEX    → catalog work only; storage smgr handles file
```

`amvalidate` runs at `CREATE OPERATOR CLASS` / `ALTER OPERATOR FAMILY ADD`. It
should check that all required strategy numbers and support function numbers
are present and have sane signatures. See `amvalidate.c` for the shared
helpers (`identify_opfamily_groups`, `check_amop_signature`, etc.).

### Opclass / strategy / support function

`pg_amop` rows declare operators (`<`, `=`, `&&`, …) and tag each with a
**strategy number** that's AM-private (btree: 1=less, 5=greater; gist:
1..n varies per opclass). `pg_amproc` rows declare **support functions**, also
numbered 1..`amsupport` per AM. The AM code looks them up via
`index_getprocinfo()` (cached FmgrInfo) inside its callbacks.

`amtranslatestrategy`/`amtranslatecmptype` is the bridge to generic
`CompareType` enum values (`COMPARE_LT` etc.) so the planner can reason about
btree-compatible opclasses on other AMs.

## Table AM (TableAmRoutine)

Pluggable since v12. There is exactly **one in-tree implementation: heap.**
The struct surface is much larger than the index-AM one (~45-callback struct;
`tableamapi.c::GetTableAmRoutine` asserts 37 of them non-NULL, the rest have
soft "may be NULL" contracts inside specific call sites) because table AMs own
MVCC, storage layout, vacuum, sampling, and the per-tuple slot type.

### What "heap is just a table-AM" means in practice

- The `Relation` cache stores `rd_tableam` (a `TableAmRoutine *`); every
  `heap_*` style access in the executor went through a `table_*` inline wrapper
  in `tableam.h` since v12.
- The TID-addressed visibility map, FSM, and toast machinery are **not** part
  of the API — they're heap implementation details. A non-heap AM has to
  reinvent or skip them.
- WAL, buffer manager, smgr, snapshots are still core — table AMs live above
  bufmgr.

### Slot interface
`slot_callbacks(rel)` returns a `TupleTableSlotOps *` (e.g. `TTSOpsHeapTuple`,
`TTSOpsBufferHeapTuple`, `TTSOpsMinimalTuple`, `TTSOpsVirtual`). All tuple
movement in/out of the AM is through `TupleTableSlot`; raw `HeapTuple` only
appears inside the heap AM. A new AM defines its own `TupleTableSlotOps`.

### Scan family

| Group | Callbacks |
|---|---|
| Plain | `scan_begin`, `scan_end`, `scan_rescan`, `scan_getnextslot` |
| TID range | `scan_set_tidrange`, `scan_getnextslot_tidrange` (both or neither) |
| Parallel | `parallelscan_estimate`, `parallelscan_initialize`, `parallelscan_reinitialize` |
| Index fetch | `index_fetch_begin`, `index_fetch_reset`, `index_fetch_end`, `index_fetch_tuple` |
| Analyze | `scan_analyze_next_block`, `scan_analyze_next_tuple` |
| Sample | `scan_sample_next_block`, `scan_sample_next_tuple` |

### Tuple ops
`tuple_insert`, `tuple_insert_speculative`, `tuple_complete_speculative`,
`multi_insert`, `tuple_delete`, `tuple_update`, `tuple_lock`,
`tuple_fetch_row_version`, `tuple_tid_valid`, `tuple_get_latest_tid`,
`tuple_satisfies_snapshot`, `index_delete_tuples`.

Return type `TM_Result` (`TM_Ok`, `TM_Invisible`, `TM_SelfModified`, `TM_Updated`,
`TM_Deleted`, `TM_BeingModified`, `TM_WouldBlock`) carries MVCC outcomes.
`TU_UpdateIndexes` tells the executor which indexes still need re-insert after
update (`TU_None` / `TU_All` / `TU_Summarizing` enables HOT-like
optimizations for non-heap AMs).

### DDL / storage
`relation_set_new_filelocator`, `relation_nontransactional_truncate`,
`relation_copy_data`, `relation_copy_for_cluster`, `relation_vacuum`,
`relation_size`, `relation_needs_toast_table`, `relation_estimate_size`,
`index_build_range_scan`, `index_validate_scan`.

### All mandatory
`tableamapi.c::GetTableAmRoutine` runs 37 `Assert(routine->X != NULL)` lines.
Only `finish_bulk_insert` and the TID-range pair are truly optional.

### The hard part: TID semantics

`ItemPointer` is a 6-byte (block, offset) pair, baked into the index AM
interface, WAL, syscaches, and `pg_class` rowcount estimation. A table AM that
doesn't store tuples in (block, offset) pages (columnar, LSM, external) has to
**fabricate stable, 48-bit, monotone-ish TIDs** for every row and route
`index_fetch_tuple` and `tuple_fetch_row_version` against them. This is the
single biggest reason most experimental table AMs never become production
ready. See `MaxHeapTuplesPerPage` and the warnings in `tableam.sgml`.

Stats-leakage corollary: autovacuum's per-table scheduling is driven by the
`n_dead_tup` / `n_live_tup` counters in `pg_stat_all_tables`, which heap
maintains via `pgstat_count_heap_*`. A non-heap AM that doesn't fake equivalent
counters will simply never be visited by autovacuum — plan to call
`pgstat_count_heap_insert`/`_update`/`_delete` (or the lower-level
`pgstat_report_vacuum`) from inside your own tuple ops from day one.

## Registering a new AM

1. **`pg_am` row** via SQL: `CREATE ACCESS METHOD myam TYPE INDEX HANDLER myam_handler;`
   (or `TYPE TABLE`). The handler function must already exist and have
   signature `myam_handler(internal) RETURNS index_am_handler` (or
   `table_am_handler`).

2. **Handler function**: `PG_FUNCTION_INFO_V1(myam_handler);` returning a
   pointer to a static `IndexAmRoutine`/`TableAmRoutine`. Done in an extension's
   shared library or in core.

3. **Opclass(es)** (index AM only): `CREATE OPERATOR CLASS … DEFAULT FOR TYPE
   foo USING myam AS OPERATOR 1 …, FUNCTION 1 …;`. Without at least one
   opclass, the AM is useless — `CREATE INDEX … USING myam (col)` will fail
   to find an opclass for `col`'s type.

4. **Catalog vs SQL**: in-tree AMs (btree, brin, …) get a hard-coded `pg_am`
   row via `src/include/catalog/pg_am.dat`, plus opclasses via
   `src/include/catalog/pg_opclass.dat`, `pg_amop.dat`, `pg_amproc.dat`. See
   the `catalog-conventions` skill.

5. **`default_table_access_method` GUC** controls which table AM `CREATE TABLE`
   uses when no `USING` clause is given. `check_default_table_access_method` in
   `tableamapi.c` validates it.

## Things you almost certainly need an existing AM as reference for

- **Parallel index build** — see `brin.c` for the modern pattern (`BrinShared`,
  `BrinLeader`, `tuplesort` integration), `nbtindex.c` for the canonical one.
- **Predicate locking** (`ampredlocks=true`) — see `nbtree`/`gist`. You must
  call `PredicateLock*` in the right spots for SSI to work.
- **Index-only scans** (`amcanreturn`) — btree, gist.
- **WAL** — every real AM uses a custom rmgr (see `wal-and-xlog` skill).
  Dummy AMs in `src/test/modules` skip WAL and so are useless past a crash.
- **Vacuum two-pass with cycle id** — nbtree (`BTCycleId`) is the reference.
- **Opclass validation** — `amvalidate.c` helpers (`check_amop_signature`,
  `identify_opfamily_groups`).
- **Bottom-up index deletion** (heap's `index_delete_tuples` + the
  `TM_IndexDeleteOp` struct) — table AM side; nbtree drives it.

## Files to read before touching this

- `src/include/access/amapi.h` — entire file, ~336 lines, ~30 function pointers.
- `src/include/access/tableam.h` — first ~900 lines is the struct; rest is
  inline wrappers and helpers.
- `src/backend/access/index/{amapi,genam,indexam,amvalidate}.c` — dispatch and
  shared helpers.
- `src/backend/access/table/tableamapi.c` — dispatch + required-callback Asserts.
- `src/test/modules/dummy_index_am/dummy_index_am.c` — minimal valid handler.
- `src/backend/access/brin/brin.c` (top ~200 lines, `brinhandler` function) —
  modern-style handler with parallel build.
- `src/backend/access/nbtree/nbtree.c` (top, `bthandler`) — canonical handler.
- `src/backend/access/heap/heapam_handler.c` (`heap_tableam_handler`,
  `heapam_methods` near line 2665) — the only table AM.
- `doc/src/sgml/indexam.sgml`, `doc/src/sgml/tableam.sgml` — user-facing chapters
  with extra discussion of locking and semantic requirements.
