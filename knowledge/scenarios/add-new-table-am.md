---
scenario: add-new-table-am
when_to_use: Brand-new heap-replacement table AM (heapless, columnar, etc.) — handler + TableAmRoutine + visibility-map and toast wiring.
companion_skills: ["access-method-apis"]
related_scenarios: ["add-new-index-am","add-new-wal-record"]
canonical_commit: 8586bf7ed88
last_verified_commit: e18b0cb7344
---

# Scenario — Add a new table access method

## Scope — what's in / out

**In scope:**
- A new pluggable table AM that owns its own on-disk storage, exposed via
  `CREATE ACCESS METHOD <name> TYPE TABLE HANDLER <handler>` and
  `CREATE TABLE ... USING <name>`.
- The 40+-callback `TableAmRoutine` vtable (scan / fetch / insert / update /
  delete / DDL / cluster / vacuum / sample / parallel / TOAST). Reference
  impl is `src/backend/access/heap/heapam_handler.c` [verified-by-code](source/src/backend/access/heap/heapam_handler.c:2665-2722).
- Required-callback assertion list in `GetTableAmRoutine` — what the core
  refuses to call you without [verified-by-code](source/src/backend/access/table/tableamapi.c:44-94).
- TOAST wiring (`relation_needs_toast_table`, `relation_toast_am`,
  `relation_fetch_toast_slice`) — your AM decides whether to reuse the
  heap TOAST machinery or roll its own [verified-by-code](source/src/backend/access/heap/heapam_handler.c:2010-2120).
- Visibility-map / FSM ownership — your AM decides whether the relation
  has a `vm` / `fsm` fork at all; `RelationGetSmgr` + `smgrnblocks` are
  the only required calls [inferred].
- Ship-as-extension packaging (`contrib/<name>/` or `src/test/modules/<name>/`
  with `.control`, `--1.0.sql`, handler function `pg_proc` row, `Makefile` /
  `meson.build`).

**Out of scope:**
- Brand-new *index* AM (separate vtable `IndexAmRoutine`, separate
  `amtype='i'`) — see `add-new-index-am`.
- New WAL record kinds the AM emits — see `add-new-wal-record` (you'll
  almost certainly need this, but the WAL plumbing is its own playbook).
- New opclass for an existing AM — see `add-new-operator-class`.
- Replacing the heap as the *default* AM (`default_table_access_method`
  GUC change) — possible but a policy decision; this scenario just makes
  your AM selectable.

## Pre-flight

- **Companion skills:** load `access-method-apis` — covers the
  `IndexAmRoutine` / `TableAmRoutine` shape, OidFunctionCall0 handler
  pattern, and the required-callback assertion contract.
- **Canonical commit:** `8586bf7ed88` — *tableam: introduce table AM
  infrastructure.* The commit that split heap out of the core and
  introduced `TableAmRoutine`. Read it before designing: it tells you
  which functions in `heapam.c` are *AM-internal* and which are
  `TableAmRoutine` callbacks. The "what does heap currently do here"
  question is answered by reading `heapam_handler.c` end-to-end
  [verified-by-code](source/src/backend/access/heap/heapam_handler.c:1-2735).
- **Common pitfalls (one-line each):**
  - Skipping a required callback — `GetTableAmRoutine` asserts ~40
    pointers non-NULL; release builds will SIGSEGV on first scan
    [verified-by-code](source/src/backend/access/table/tableamapi.c:44-94).
  - Returning a non-static `TableAmRoutine` from the handler — the
    struct "must be allocated in a server-lifetime manner, typically as
    a static const struct" [from-comment](source/src/include/access/tableam.h:310-313).
  - Confusing `ItemPointer` semantics — TID is (BlockNumber, OffsetNumber)
    everywhere in the executor and indexams; your AM must encode its
    row identity into that space (heap uses ctid directly; columnar AMs
    typically pack a row group ID + offset).
  - Forgetting `pg_proc.dat` (or `CREATE FUNCTION` in your `--1.0.sql`)
    declaring `prorettype => 'table_am_handler'` — `CREATE ACCESS METHOD`
    rejects handlers whose return type isn't `table_am_handler`
    [verified-by-code](source/src/test/regress/expected/create_am.out:9).
  - Owning your own TOAST: the heap toast tables are themselves heap
    relations; if your AM stores toast pointers but your toast table is
    heap, `relation_toast_am` must return `HEAP_TABLE_AM_OID`, not
    your own oid [verified-by-code](source/src/backend/access/heap/heapam_handler.c:2060-2065).

## File checklist (the FULL sweep)

The AM is normally shipped as an extension, so most "new files" land
under `contrib/<name>/` or `src/test/modules/<name>/`. The in-core changes
are minimal — only if you want to register a built-in AM (like `heap`).

| # | File | Why | Per-file doc | Companion skill |
|---|---|---|---|---|
| 1 | `contrib/<myam>/<myam>_handler.c` (NEW) | The single C entry point: `Datum myam_tableam_handler(PG_FUNCTION_ARGS)` that returns `PG_RETURN_POINTER(&myam_methods)` where `myam_methods` is a `static const TableAmRoutine`. Mirror shape from `heap_tableam_handler` [verified-by-code](source/src/backend/access/heap/heapam_handler.c:2731-2734). | — | access-method-apis |
| 2 | `contrib/<myam>/<myam>.c` (NEW) | The 40+ callback implementations: scan_*, parallelscan_*, index_fetch_*, tuple_insert / _speculative / _complete_speculative / multi_insert, tuple_delete / _update / _lock, tuple_fetch_row_version, tuple_get_latest_tid, tuple_tid_valid, tuple_satisfies_snapshot, index_delete_tuples, relation_set_new_filelocator, relation_nontransactional_truncate, relation_copy_data, relation_copy_for_cluster, relation_vacuum, scan_analyze_next_block / _next_tuple, index_build_range_scan, index_validate_scan, relation_size, relation_needs_toast_table, relation_toast_am, relation_fetch_toast_slice, relation_estimate_size, scan_bitmap_next_tuple, scan_sample_next_block / _next_tuple. Every one is asserted by `GetTableAmRoutine` [verified-by-code](source/src/backend/access/table/tableamapi.c:44-94). | — | access-method-apis |
| 3 | `contrib/<myam>/<myam>--1.0.sql` (NEW) | `CREATE FUNCTION <myam>_tableam_handler(internal) RETURNS table_am_handler AS 'MODULE_PATHNAME' LANGUAGE C STRICT;` followed by `CREATE ACCESS METHOD <myam> TYPE TABLE HANDLER <myam>_tableam_handler;`. Exact pattern is the `tableam.sgml` example [verified-by-code](source/doc/src/sgml/tableam.sgml:45-50). | — | extension-development |
| 4 | `contrib/<myam>/<myam>.control` (NEW) | Standard control file: `comment`, `default_version`, `module_pathname`, `relocatable=false` (AMs are pinned to `pg_catalog` semantics). | — | extension-development |
| 5 | `contrib/<myam>/Makefile` (NEW) and `contrib/<myam>/meson.build` (NEW) | Standard contrib boilerplate; `MODULES = <myam>` (or `MODULE_big`), `EXTENSION = <myam>`, `DATA = <myam>--1.0.sql`, regress tests listed. Mirror `contrib/bloom/Makefile` (bloom is the only in-tree extension that ships an AM, an *index* AM, but the build glue is identical). | — | build-and-run |
| 6 | `contrib/meson.build` and `contrib/Makefile` | Add `<myam>` to the `SUBDIRS` list (Makefile) and to the `contrib_mods` array (meson.build) so the contrib subdir is built. | — | build-and-run |
| 7 | `contrib/<myam>/sql/<myam>.sql` + `expected/<myam>.out` (NEW) | Functional regression. At minimum: `CREATE EXTENSION`, `CREATE TABLE t USING <myam>`, `INSERT`, seqscan, indexscan via a btree on it (exercises `index_fetch_tuple`), `UPDATE` (exercises `tuple_update` + `index_delete_tuples`), `DELETE`, `VACUUM`, `CLUSTER` if supported, `ANALYZE` (exercises `scan_analyze_next_*`), `TABLESAMPLE` (exercises `scan_sample_*`). Shape mirrors `src/test/regress/sql/create_am.sql` `heap2` block [verified-by-code](source/src/test/regress/sql/create_am.sql:102-145). | — | testing |
| 8 | `contrib/<myam>/expected/<myam>_1.out` (optional) | Alternate-expected output when results depend on toast/index/parallel behavior — common when AM uses different TID layout. | — | testing |
| 9 | `doc/src/sgml/<myam>.sgml` (NEW) and `doc/src/sgml/contrib.sgml` | New `<sect1>` describing the AM + entity reference in `contrib.sgml`. Cross-link to `tableam.sgml` [verified-by-code](source/doc/src/sgml/tableam.sgml:3-50) for the interface chapter your reader should already know. | — | — |
| 10 | `doc/src/sgml/filelist.sgml` | `<!ENTITY <myam> SYSTEM "<myam>.sgml">` entry so the docs build finds your file [verified-by-code](source/doc/src/sgml/filelist.sgml:99). | — | — |

### Only if you make the AM built-in (NOT extension-shipped)

These rows are the "fork heap" path — you almost never want this for a
new AM. Listed for completeness because the heap entries live here.

| # | File | Why | Per-file doc | Companion skill |
|---|---|---|---|---|
| B1 | `src/include/catalog/pg_am.dat` | Add `{ oid => '<N>', oid_symbol => '<MYAM>_TABLE_AM_OID', descr => '...', amname => '<myam>', amhandler => '<myam>_tableam_handler', amtype => 't' }`. Mirror the heap row [verified-by-code](source/src/include/catalog/pg_am.dat:14-17). OID picked from 8000-9999 range via `./src/include/catalog/unused_oids`. | — | catalog-conventions |
| B2 | `src/include/catalog/pg_proc.dat` | Add a row for the handler function: `proname => '<myam>_tableam_handler'`, `provolatile => 'v'`, `prorettype => 'table_am_handler'`, `proargtypes => 'internal'`, `prosrc => '<myam>_tableam_handler'`. Mirror heap's entry [verified-by-code](source/src/include/catalog/pg_proc.dat:911-915). | — | catalog-conventions |
| B3 | `src/include/catalog/catversion.h` | Bump `CATALOG_VERSION_NO` — any `.dat` mutation forces a bump. | [catversion.h.md](../files/src/include/catalog/catversion.h.md) | catalog-conventions |
| B4 | `src/backend/access/<myam>/` (NEW dir) | Source dir with `Makefile`, `meson.build`, the handler + callbacks. Mirror `src/backend/access/heap/` layout. | — | build-and-run |
| B5 | `src/backend/access/Makefile` and `src/backend/access/meson.build` | Add `<myam>` to the SUBDIRS / subdir list. | — | build-and-run |
| B6 | `src/include/access/<myam>am.h` (NEW) | Public header exposing `Get<Myam>TableAmRoutine()` if anything in core needs to grab the routine without going through `pg_am` lookup. Mirror `GetHeapamTableAmRoutine` [verified-by-code](source/src/backend/access/heap/heapam_handler.c:2724-2728). | — | access-method-apis |

(Use `—` in the per-file doc column for genuinely-new files; otherwise
the entry should exist in `knowledge/files/` and link.)

## Phases — suggested split for `pg-feature-plan`

The planner will use this as the §8 starting point. Each phase is a
self-contained chunk; the tree must build at the end of each phase.

1. **Phase 1 — Skeleton + handler that compiles.** Files: [1, 3, 4, 5, 6].
   Stub every callback as `elog(ERROR, "not implemented")` *except* the
   ones `GetTableAmRoutine` asserts non-NULL — those must be real
   pointers (can return ERROR at runtime but the pointer must be set).
   Phase-end check: `meson compile -C dev/build-debug` succeeds;
   `psql -c 'CREATE EXTENSION <myam>; SELECT amname FROM pg_am WHERE
   amtype='t';'` lists the AM.
2. **Phase 2 — Read path (scans + index fetch + visibility).** Files:
   [2]. Implement `slot_callbacks`, `scan_begin` / `_end` / `_rescan` /
   `_getnextslot`, `parallelscan_*` (re-use `table_block_parallelscan_*`
   helpers if you store in blocks [verified-by-code](source/src/backend/access/table/tableam.c:408-446)),
   `index_fetch_*`, `tuple_fetch_row_version`, `tuple_satisfies_snapshot`,
   `tuple_get_latest_tid`, `tuple_tid_valid`. Phase-end check:
   `INSERT` via a stub `tuple_insert` of one row, then `SELECT` returns
   it; seqscan and an index lookup both work.
3. **Phase 3 — Write path + DDL + vacuum.** Files: [2]. Implement
   `tuple_insert` / `_speculative` / `_complete_speculative`,
   `multi_insert`, `tuple_update`, `tuple_delete`, `tuple_lock`,
   `relation_set_new_filelocator`, `relation_nontransactional_truncate`,
   `relation_copy_data`, `relation_copy_for_cluster`, `relation_vacuum`,
   `scan_analyze_next_block` / `_next_tuple`, `index_build_range_scan`,
   `index_validate_scan`, `relation_size`, `relation_estimate_size`,
   `relation_needs_toast_table`, `relation_toast_am`,
   `relation_fetch_toast_slice`. Phase-end check: `UPDATE` / `DELETE`,
   `VACUUM`, `CLUSTER`, `REINDEX` on a table created with `USING <myam>`
   all succeed.
4. **Phase 4 — Bitmap, sample, parallel, tests, docs.** Files: [2, 7, 8,
   9, 10]. Implement `scan_bitmap_next_tuple`, `scan_sample_next_block` /
   `_next_tuple`, `index_delete_tuples`. Add regression mirroring
   `create_am.sql` `heap2` block [verified-by-code](source/src/test/regress/sql/create_am.sql:102-145).
   Phase-end check: `meson test -C dev/build-debug --suite contrib
   --test <myam>` is green, docs build clean.



## Idioms invoked
<!-- idioms-invoked:auto -->

*Auto-derived from direct references + transitive file-overlap with idiom Call sites.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

| Idiom | Evidence |
|---|---|
| [`catalog-conventions`](../idioms/catalog-conventions.md) | direct reference |
| [`fmgr`](../idioms/fmgr.md) | direct reference |
| [`memory-contexts`](../idioms/memory-contexts.md) | direct reference |
| [`tableam-index-fetch`](../idioms/tableam-index-fetch.md) | shares files: `src/backend/access/heap/heapam_handler.c`, `src/include/access/tableam.h` |
| [`tableam-vtable-lifecycle`](../idioms/tableam-vtable-lifecycle.md) | shares files: `src/backend/access/heap/heapam_handler.c`, `src/include/access/tableam.h` |

<!-- /idioms-invoked:auto -->

## Pitfalls

- **`heap_tableam_handler` is the spec.** The TableAmRoutine documentation
  in `tableam.h` is terse; the *real* contract is "what does heap do here"
  [verified-by-code](source/src/backend/access/heap/heapam_handler.c:2665-2722). Read each callback impl
  end-to-end before writing yours — most subtle semantics (CommandId
  handling, ItemPointer reuse, EvalPlanQual interactions in
  `tuple_lock`, HOT-chain-equivalent semantics for `index_delete_tuples`,
  freeze-vs-prune split in `relation_vacuum`) are documented only as
  heap behavior.
- **`tuple_lock` is the EvalPlanQual hot zone.** Returning
  `TM_Updated` / `TM_BeingModified` correctly is mandatory for `SELECT
  ... FOR UPDATE` and for the executor's `EvalPlanQual` retry loop to
  work. The `TM_Result` enum is at [verified-by-code](source/src/include/access/tableam.h:107-126).
- **Required-callback assertion list.** Assertions in `GetTableAmRoutine`
  enumerate the non-NULL contract — `scan_begin/end/rescan/getnextslot`,
  `parallelscan_estimate/initialize/reinitialize`,
  `index_fetch_begin/reset/end/tuple`, `tuple_fetch_row_version`,
  `tuple_tid_valid`, `tuple_get_latest_tid`, `tuple_satisfies_snapshot`,
  `index_delete_tuples`, `tuple_insert`, `tuple_insert_speculative`,
  `tuple_complete_speculative`, `multi_insert`, `tuple_delete`,
  `tuple_update`, `tuple_lock`, `relation_set_new_filelocator`,
  `relation_nontransactional_truncate`, `relation_copy_data`,
  `relation_copy_for_cluster`, `relation_vacuum`,
  `scan_analyze_next_block/tuple`, `index_build_range_scan`,
  `index_validate_scan`, `relation_size`, `relation_needs_toast_table`,
  `relation_estimate_size`, `scan_sample_next_block/tuple`
  [verified-by-code](source/src/backend/access/table/tableamapi.c:44-94).
  Missing any of these is an assertion failure in debug builds and a
  NULL-pointer dereference in release.
- **`scan_set_tidrange` / `scan_getnextslot_tidrange` are NOT in the
  assert list.** They are optional but required for TID-range scan plans
  to consider your AM. If you skip them, EXPLAIN will silently fall back
  to seqscan even when a TID range would have helped [verified-by-code](source/src/backend/access/table/tableamapi.c:44-94)
  (no assert for these two).
- **`relation_toast_am` decides who owns the toast relation.** If you
  return `rel->rd_rel->relam` (your own oid), then the toast relation
  itself uses your AM — which means you must be able to store
  toast-shaped tuples (one row per chunk, with `chunk_id`, `chunk_seq`,
  `chunk_data`). Heap punts and returns its own oid [verified-by-code](source/src/backend/access/heap/heapam_handler.c:2060-2065).
  Most new AMs should also delegate to heap unless the storage model is
  fundamentally chunk-friendly.
- **Visibility map is not part of the AM contract.** Heap maintains a
  `vm` fork via `visibilitymap_set` / `_test`, used by `IndexOnlyScan`
  and `VACUUM`. If your AM doesn't have all-visible / all-frozen page
  semantics, you skip the VM fork entirely — but then
  `IndexOnlyScan` falls back to fetching from your table on every tuple
  [inferred]. The check happens via `VM_ALL_VISIBLE` in
  `nodeIndexonlyscan.c`, which calls `visibilitymap_get_status` only
  if the relation has a VM fork.
- **`ItemPointer` (TID) is 6 bytes — `(uint32 blk, uint16 off)`.** Index
  AMs store TIDs in index tuples; the executor passes TIDs through
  `TupleTableSlot->tts_tid`. If your AM's row identity doesn't fit in a
  block + offset, you must either (a) pack it (e.g. row-group-id ::
  uint32, row-within-group :: uint16), or (b) refuse `CREATE INDEX` on
  yourself by erroring out of `index_build_range_scan`. There is no
  "wide TID" extension point [inferred].
- **`relation_set_new_filelocator` is called for `TRUNCATE`, `CLUSTER`,
  `REINDEX`, and `CREATE TABLE`.** It must initialize the empty
  storage — for heap this means `RelationCreateStorage` and writing the
  init fork for unlogged tables [verified-by-code](source/src/backend/access/heap/heapam_handler.c:625-720).
- **Synchronization traps** (sibling files that must change together):
  - Your handler function declaration in `--1.0.sql` ↔ the C symbol
    name (`AS 'MODULE_PATHNAME', '<myam>_tableam_handler'` must match
    the `PG_FUNCTION_INFO_V1` symbol).
  - Adding a callback in a future PG major version: every existing AM
    breaks at the `GetTableAmRoutine` assert. The
    `last_verified_commit` of this scenario is your tripwire — refresh
    against current `tableam.h` before starting.
  - Built-in path only: `pg_am.dat` ↔ `pg_proc.dat` ↔ `catversion.h`
    (all three must move together, see `add-new-system-catalog-column`).

## Verification (exact test invocations)

```bash
# Build the extension
meson compile -C dev/build-debug install

# Confirm the handler function and AM exist
dev/install-debug/bin/psql -c "CREATE EXTENSION <myam>;"
dev/install-debug/bin/psql -c "SELECT amname, amhandler, amtype FROM pg_am WHERE amtype='t';"

# Functional contrib regression
meson test -C dev/build-debug --suite contrib --test <myam>

# In-core create_am regression (must still pass — your AM extends, not breaks)
meson test -C dev/build-debug --suite regress --test create_am

# Full check-world (catches HOT, EPQ, parallel-scan, vacuum,
# tablesample fallout)
meson test -C dev/build-debug

# Smoke test for ANALYZE + index + bitmap + sample paths
dev/install-debug/bin/psql <<'SQL'
CREATE TABLE t (a int) USING <myam>;
INSERT INTO t SELECT generate_series(1, 100000);
CREATE INDEX ON t (a);
ANALYZE t;
EXPLAIN ANALYZE SELECT * FROM t WHERE a = 42;          -- index_fetch_tuple
EXPLAIN ANALYZE SELECT count(*) FROM t WHERE a < 50;   -- scan_bitmap_next_tuple
EXPLAIN ANALYZE SELECT * FROM t TABLESAMPLE BERNOULLI(1); -- scan_sample_*
UPDATE t SET a = a + 1 WHERE a < 10;                   -- tuple_update path
DELETE FROM t WHERE a > 99990;                         -- tuple_delete + index_delete_tuples
VACUUM t;                                              -- relation_vacuum
CLUSTER t USING t_a_idx;                               -- relation_copy_for_cluster
SQL
```

The new contrib test (`contrib/<myam>/sql/<myam>.sql` + expected) is
the load-bearing test. Mirror `src/test/regress/sql/create_am.sql`
[verified-by-code](source/src/test/regress/sql/create_am.sql:102-145) for the
DML coverage shape.

## Cross-refs

- Companion skills: `.claude/skills/access-method-apis/SKILL.md`,
  `.claude/skills/extension-development/SKILL.md`,
  `.claude/skills/wal-and-xlog/SKILL.md` (for redo of any new WAL your AM
  emits), `.claude/skills/testing/SKILL.md`.
- Related scenarios:
  - `scenarios/add-new-index-am.md` — sibling vtable; same `pg_am` /
    handler / `CREATE ACCESS METHOD` shape but `amtype='i'`.
  - `scenarios/add-new-wal-record.md` — your AM almost certainly needs
    new WAL records; the rmgr + redo + `XLOG_PAGE_MAGIC` plumbing lives
    there.
  - `scenarios/add-new-extension.md` — packaging the AM as a contrib /
    src/test/modules extension.
- Idioms: `knowledge/idioms/catalog-conventions.md` (only if built-in
  path), `knowledge/idioms/fmgr.md` (handler function shape),
  `knowledge/idioms/memory-contexts.md` (TableAmRoutine is static, but
  scan state allocations belong in `CurrentMemoryContext`).
- Subsystems: `knowledge/subsystems/access-heap.md` (the reference impl),
  `knowledge/subsystems/storage-buffer.md` (your AM almost certainly
  uses bufmgr for page reads/writes).
- Issues: `knowledge/issues/access.md`, `knowledge/issues/include-access.md`.
- Reference patch (canonical_commit): `git -C source show 8586bf7ed88`.
