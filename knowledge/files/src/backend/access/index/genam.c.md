# genam.c

- **Source path:** `source/src/backend/access/index/genam.c`
- **Lines:** 916
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `genam.h`, `indexam.c` (per-tuple workhorses), `amapi.c`, `tableam.c`.

## Purpose

The "general index AM" facade with two distinct roles:

1. **`RelationGetIndexScan` / `IndexScanEnd`** — the AM-agnostic boilerplate that every index AM's `ambeginscan` callback uses to allocate and initialise an `IndexScanDesc`.
2. **systable_*** — convenience layer that lets catalog code issue an index-driven scan against a system table without dealing with the lower-level `index_beginscan` API. This is the path through which `SearchSysCache` misses and most catalog inserts/updates/deletes ultimately read.

[from-comment, genam.c:13-15, 41-62]

## Top-of-file comment

> "general index access method routines… many of the old access method routines have been turned into macros and moved to genam.h -cim 4/30/91" — Followed by a multi-paragraph block on the contract between `RelationGetIndexScan` and AM-private `beginscan` routines: every AM's `ambeginscan` MUST return the object built by `RelationGetIndexScan`. [from-comment, genam.c:41-62]

## Public surface

- **AM scaffolding:**
  - `RelationGetIndexScan` (80) — Allocate and zero-initialise an `IndexScanDesc`, populating the heap-rel pointer to NULL, the ScanKey/orderby arrays, the snapshot to InvalidSnapshot. Used inside every AM's `ambeginscan`.
  - `IndexScanEnd` (145) — Free the ScanKey/orderby arrays and the descriptor itself (after the AM's `amendscan` has done its own work).
  - `BuildIndexValueDescription` (178) — Format the indexed column values as a human-readable string `(col1, col2) = (a, b)` for unique-violation `errdetail`. Honours RLS / column-level ACL: returns NULL if the user couldn't see those columns in a regular query.
- **Bottom-up xid horizon:** `index_compute_xid_horizon_for_tuples` (295) — Given a set of heap TIDs an index AM intends to recycle, compute the snapshot horizon under which they're safe to recycle. Wraps `table_index_delete_tuples` and is the canonical xid-horizon producer for `_bt_killitems`-style work.
- **systable_***
  - `systable_beginscan` (388) — Open an index-based catalog scan; if no usable index, fall back to a seqscan with manual key filtering.
  - `systable_getnext` (515), `systable_recheck_tuple` (574), `systable_endscan` (604).
  - `systable_beginscan_ordered` (651), `systable_getnext_ordered` (734), `systable_endscan_ordered` (759) — Ordered variants that REQUIRE a real index and return tuples in index order.
  - `systable_inplace_update_begin` (810), `systable_inplace_update_finish` (886), `systable_inplace_update_cancel` (905) — Coordinated three-step protocol for the rare catalog in-place updates (`pg_class.relfrozenxid`, etc.) that must not break HOT chains.

## Key invariants

- `RelationGetIndexScan` allocates the descriptor in `CurrentMemoryContext`; AMs MUST NOT free it themselves — `IndexScanEnd` (called by `indexam.c::index_endscan`) handles the free. [verified-by-code, genam.c:80-145]
- `systable_beginscan` chooses an index path iff `indexOK == true`, an OID is supplied, AND `IsSystemRelation || IgnoreSystemIndexes == false`. Otherwise it does a heap seqscan and applies the ScanKeys manually via `HeapKeyTest`. [verified-by-code, genam.c:388-490]
- `systable_recheck_tuple` is the standard way to re-examine a previously fetched catalog tuple after a concurrent update — it builds a fresh "dirty" snapshot and re-applies the scan keys to detect a row that has been newly-updated. [verified-by-code, genam.c:574-603]
- `systable_inplace_update_begin` takes a `LOCKTAG_TUPLE` heavyweight lock before reading the to-be-updated tuple — this is the synchronization that lets a concurrent reader of `pg_class.relfrozenxid` see a torn write only if it explicitly waits. [verified-by-code, genam.c:810-905]
- `BuildIndexValueDescription` MUST respect `pg_class_aclcheck` + RLS for every column it would print; if any column would be hidden, it returns NULL so the error message doesn't leak data. [verified-by-code, genam.c:178-294]

## Functions of note

1. **`systable_beginscan`** (388) — Decides between index scan (`index_open` + `index_beginscan`) and heap seqscan (`table_beginscan_catalog`). Returns a `SysScanDesc` that hides the distinction from callers. [verified-by-code]
2. **`systable_getnext`** (515) — If using an index: `index_getnext_slot` then materialise to `HeapTuple`. If seqscan: walk the heap, manually apply ScanKeys. Handles concurrent CIC aborts via `HandleConcurrentAbort` (492). [verified-by-code]
3. **`systable_inplace_update_begin`** (810) — Takes `LOCKTAG_TUPLE` via `LockTuple`, then issues a `systable_beginscan` to find the target tuple. Returns a state object the caller passes to `systable_inplace_update_finish` (which calls `heap_inplace_update_and_unlock`). [verified-by-code]

## Cross-references

- AM-side users: every index AM (`nbtree.c`, `gist.c`, `hash.c`, `spgist.c`, `brin.c`, `gin.c`) builds its scandesc via `RelationGetIndexScan`.
- Catalog users: `SearchSysCache*` (`syscache.c`), `catalog/*` (every catalog read/write).
- `BuildIndexValueDescription` is called by `_bt_check_unique` (nbtree) to populate unique-violation error messages.

## Open questions

- The exact failure mode if a systable caller forgets `systable_recheck_tuple` after seeing an update conflict — likely "silent stale read of catalog row". Not traced. [unverified]

## Confidence tag tally
`[verified-by-code]=10 [from-comment]=3 [from-readme]=0 [inferred]=0 [unverified]=1`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
- [data-structures/indexamroutine.md](../../../../../data-structures/indexamroutine.md)

