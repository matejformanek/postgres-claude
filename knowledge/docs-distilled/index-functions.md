---
source_url: https://www.postgresql.org/docs/current/index-functions.html
fetched_at: 2026-06-12T20:50:00Z
anchor_sha: e18b0cb
chapter: "63.2 Index Access Method Functions"
---

# Index Access Method Functions (docs §63.2)

The per-callback contract for `IndexAmRoutine`. This is the authoritative
"what each `am*` function must do and when it's called" reference. `[from-docs]`.

## Build / maintenance callbacks

- **`ambuild(heap, index, indexInfo) → IndexBuildResult*`** — the index relation
  exists but is *empty*; the AM fills its fixed metadata plus entries for every
  existing heap tuple, typically via `table_index_build_scan()`. Returns a
  palloc'd stats struct. `amcanbuildparallel` gates whether the system tries to
  hand it parallel workers. `[from-docs]`
- **`ambuildempty(index)`** — builds an empty index into the **init fork**
  (`INIT_FORKNUM`); called *only for unlogged indexes*, and that empty image is
  re-copied to the main fork on every server restart. `[from-docs]`
- **`aminsert(...) → bool`** — inserts one entry. `heapRelation` is normally only
  needed for the uniqueness heap-liveness check. The **`indexUnchanged` hint**
  (true ⇒ this is a logically-unchanged MVCC successor from an UPDATE that
  touched no indexed column) lets the AM trigger bottom-up index deletion;
  it is computed cheaply, **allows false positives *and* negatives, and must
  NOT be treated as authoritative** about visibility/versioning. The return
  value is *only significant for `UNIQUE_CHECK_PARTIAL`* (false ⇒ schedule a
  deferred uniqueness recheck); return constant `false` otherwise. The AM may
  cache cross-insert state in `indexInfo->ii_AmCache` (allocated in
  `ii_Context`). `[from-docs]`
- **`aminsertcleanup(index, indexInfo)`** — releases non-memory state (e.g.
  pinned buffers) cached in `ii_AmCache`, called before that memory is freed.
  `[from-docs]`
- **`ambulkdelete(info, stats, callback, cb_state) → IndexBulkDeleteResult*`** —
  scans the whole index; for each entry calls `callback(TID, cb_state)→bool` to
  decide deletion. May be called **multiple times per VACUUM** (bounded by
  `maintenance_work_mem`); `stats` carries the previous call's accumulator (NULL
  on first call). `[from-docs]`
- **`amvacuumcleanup(info, stats) → IndexBulkDeleteResult*`** — post-VACUUM
  cleanup (reclaim empty pages, finalize stats that update `pg_class` /
  VACUUM VERBOSE). **Also invoked at ANALYZE end with `stats=NULL` and return
  ignored** — distinguish via `info->analyze_only` and do near-nothing there
  (and only in an autovacuum worker). `[from-docs]`

## Scan-support / introspection callbacks

- **`amcanreturn(index, attno) → bool`** — 1-based column; can the AM return the
  original indexed value for index-only scans? Should be true for INCLUDE
  columns. Set the slot to NULL if the AM has no IOS support at all. `[from-docs]`
- **`amcostestimate(...)`** — see §63.6 (`index-cost-estimation.md`). `[from-docs]`
- **`amgettreeheight(rel) → int`** — height of a tree index, delivered to
  `amcostestimate` via `path->indexinfo->tree_height`; may cache in
  `rd_amcache`. `[from-docs]`
- **`amoptions(reloptions, validate) → bytea*`** — parses `name=value` reloptions
  into `rd_options`; with `validate=false` it must *silently ignore* unknown
  entries (loading already-stored options). `[from-docs]`
- **`amproperty(...)`** — overrides `pg_index[am]_column_has_property`. Return
  true (and set `*res`/`*isnull`) when the AM decides; false to fall back to core.
  Recommended for `AMPROP_DISTANCE_ORDERABLE` (core returns NULL otherwise) and
  `AMPROP_RETURNABLE` (cheaper than opening the index). `[from-docs]`
- **`ambuildphasename(phasenum) → char*`** — names build phases for
  `pg_stat_progress_create_index`. `[from-docs]`
- **`amvalidate(opclassoid) → bool`** — validates opclass catalog entries (e.g.
  all required support functions present); reports via `ereport(INFO,...)`,
  returns false if invalid. `[from-docs]`
- **`amadjustmembers(...)`** — validates/sets dependency strength of new
  operator/function family members at `CREATE OPERATOR CLASS` /
  `ALTER OPERATOR FAMILY ADD` (opclassoid is InvalidOid in the latter). GIN/GiST/
  SP-GiST make their operator members *soft* opfamily deps so they can be
  freely added/removed. `[from-docs]`

## Scan lifecycle callbacks

- **`ambeginscan(index, nkeys, norderbys) → IndexScanDesc`** — **must** build the
  descriptor via `RelationGetIndexScan()`; scan-key *values* aren't supplied yet,
  so do little beyond allocation/locks here. `[from-docs]`
- **`amrescan(scan, keys, nkeys, orderbys, norderbys)`** — (re)starts the scan
  with (possibly new) keys; NULL keys ⇒ reuse prior keys. Counts may not exceed
  what `ambeginscan` was told. This is where the *real* scan startup work lives.
  `[from-docs]`
- **`amgettuple(scan, direction) → bool`** — next matching TID; "match" means the
  *index* matches the keys, **not** that the heap tuple still exists or is
  visible. **Must set `scan->xs_recheck`** (true ⇒ lossy op, core rechecks
  conditions — but never the partial-index predicate — against the heap tuple).
  For IOS, if `scan->xs_want_itup`, return the indexed data at `xs_itup`
  (`xs_itupdesc`) or `xs_hitup` (`xs_hitupdesc`); that data must stay valid until
  the next `amgettuple`/`amrescan`/`amendscan`. NULL the slot if no plain-scan
  support. `[from-docs]`
- **`amgetbitmap(scan, tbm) → int64`** — ORs *all* matching TIDs into the caller's
  `TIDBitmap`, returns a (possibly approximate) count. **Mutually exclusive with
  `amgettuple` in one scan.** `[from-docs]`
- **`amendscan(scan)`** — release internal locks/pins/memory; **do not free the
  scan struct itself.** `[from-docs]`
- **`ammarkpos` / `amrestrpos`** — one remembered position per scan; NULL the
  slots unless the AM supports ordered scans. `[from-docs]`

## Parallel-scan callbacks (all optional)

- **`amestimateparallelscan(index, nkeys, norderbys) → Size`** — extra DSM bytes
  *beyond* `ParallelIndexScanDescData`. `aminitparallelscan(target)` initializes
  that DSM; `amparallelrescan(scan)` resets it. Protocol: each worker returns a
  disjoint subset whose union equals the serial result; ordering need only hold
  *within* each worker. `[from-docs]`

## Strategy-translation callbacks (optional)

- **`amtranslatestrategy` / `amtranslatecmptype`** — convert between fixed
  `CompareType` values and the AM's strategy numbers. Implement only if the AM is
  btree/hash-like; doing so lets the planner/executor substitute the AM where it
  would use btree/hash. Skipping them leaves the AM fully functional but ignored
  for certain planner decisions. `[from-docs]`

## Links into corpus

- [[knowledge/files/src/backend/access/index/indexam.c.md]] — the generic
  `index_*` wrappers that dispatch to these slots.
- [[knowledge/files/src/backend/access/index/amapi.c.md]] — IndexAmRoutine
  validation; [[knowledge/files/src/backend/access/index/amvalidate.c.md]].
- [[knowledge/subsystems/access-nbtree.md]] — the reference implementation of
  every callback here.
- [[knowledge/docs-distilled/index-scanning.md]],
  [[knowledge/docs-distilled/index-unique-checks.md]],
  [[knowledge/docs-distilled/index-cost-estimation.md]] — the sub-protocols.
- Skill: `access-method-apis` (IndexAmRoutine slot-by-slot).

## Citations

- All `[from-docs]`. `IndexAmRoutine` is declared in
  `source/src/include/access/amapi.h`; the wrappers are in
  `source/src/backend/access/index/indexam.c`. Verify line numbers at anchor
  e18b0cb.
