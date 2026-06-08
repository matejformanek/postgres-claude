# Hydra Columnar (hydradatabase/columnar) — a columnar store implemented as a real Table Access Method, with a synthetic TID and a row-mask delete model

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `hydradatabase/columnar` @ branch `main` (the queue named
> `hydradatabase/hydra`, which **301-redirects** to `hydradatabase/columnar`;
> 3026 stars, last pushed 2025-02-10 — alive but slow-moving). All `file:line`
> cites point into that repo (not `source/`), since this characterizes an
> *external* extension's divergence from core idioms. Cites verified against the
> files fetched on 2026-06-08 (see Sources footer). This is the Citus-columnar
> lineage and the **table-AM successor to `[[knowledge/ideologies/cstore_fdw]]`**:
> the same authors' columnar storage moved from the FDW API to the Table AM API.

## Domain & purpose

Hydra Columnar is "open source, column-oriented Postgres" — a drop-in columnar
storage extension positioned as a data warehouse, benchmarked on ClickBench
(`README.md:5`, `:20-28`) `[from-README]`. Where a normal table stores rows in
heap pages, a columnar table stores values grouped by column into compressed
*stripes* and *chunk groups*, so analytic scans read only the needed columns and
skip irrelevant chunks. The whole thing is delivered as a single C extension
(`columnar`, `default_version = '11.1-12'`, `columnar.control:2`)
`[verified-by-code]` built around two pluggable PG APIs: the **Table Access
Method** (for storage + DML) and a **CustomScan** (for column projection +
chunk pruning). It is the storage-engine counterpart to the "host a foreign
engine through a pluggable API" family (`[[knowledge/ideologies/cstore_fdw]]`,
`[[knowledge/ideologies/pg_duckdb]]`, `[[knowledge/ideologies/zombodb]]`), except
the engine here is *native* — it writes to the relation's own file via PG's smgr
and buffer manager, not to an external system.

## How it hooks into PG

The extension registers a table AM. `columnar_handler` is the `amhandler`
returning `&columnar_am_methods` (`columnar_tableam.c:3032-3037`)
`[verified-by-code]`, wired up by `CREATE ACCESS METHOD columnar TYPE TABLE
HANDLER columnar_handler`; users then write `CREATE TABLE ... USING columnar`.
The `TableAmRoutine` is fully populated (`columnar_tableam.c:2961-3022`)
`[verified-by-code]`: `slot_callbacks`, `scan_begin/end/rescan/getnextslot`,
`tuple_insert`/`multi_insert`/`tuple_delete`/`tuple_update`/`tuple_lock`,
`index_fetch_*`, `index_build_range_scan`, `relation_set_new_filelocator`,
`relation_vacuum`, `scan_analyze_*`, `relation_estimate_size`, and sampling —
see the `access-method-apis` skill for the contract.

Beyond the AM, `columnar_tableam_init()` chains **four hooks**
(`columnar_tableam.c:2695-2711`, `columnar_customscan.c:256-322`,
`columnar_planner_hook.c:451-452`) `[verified-by-code]`:

- `object_access_hook` → `ColumnarTableAMObjectAccessHook` (clean up columnar
  metadata when a columnar table is dropped).
- `ProcessUtility_hook` → `ColumnarProcessUtility` (intercept DDL like
  TRUNCATE/VACUUM on columnar tables).
- `set_rel_pathlist_hook` → `ColumnarSetRelPathlistHook` + `RegisterCustomScanMethods`
  (inject the columnar CustomScan path).
- `planner_hook` → `ColumnarPlannerHook`.

Cross-ref `[[knowledge/architecture/access-methods]]`,
`[[knowledge/subsystems/access-heap]]` (the heap AM it parallels),
`[[knowledge/subsystems/storage-buffer]]` + `[[knowledge/architecture/wal]]`
(the buffer/WAL layer it deliberately reuses, unlike cstore_fdw).

## Where it diverges from core idioms

### 1. The TID is synthetic: a `row_number` packed into `ItemPointerData`, because there are no heap line pointers

A heap TID is `(block, offset)` pointing at a real line pointer on a page.
Columnar has stripes, not line pointers, so it manufactures TIDs:
`row_number_to_tid` packs a monotonically increasing row number into a
`(BlockNumber, OffsetNumber)` using `VALID_ITEMPOINTER_OFFSETS` as the radix
(`columnar_tableam.c:420-442`) `[verified-by-code]`, and `tid_to_row_number`
inverts it. So `ctid` is a fiction the AM maintains to satisfy the executor and
indexes; index entries store these synthetic TIDs, and `index_fetch_tuple`
binary-searches a stripe metadata list to map a row number back to its stripe
(`columnar_tableam.c:586-609`, `FindStripeMetadataFromListBinarySearch`)
`[verified-by-code]`. Cross-ref
`[[knowledge/data-structures/heap-tuple-layout]]` (the `ItemPointer` contract it
reinterprets), `[[knowledge/ideologies/zombodb]]` (which also writes a synthetic
`xs_heaptid`).

### 2. Storage rides PG's smgr/buffer/WAL by faking a contiguous byte stream over formatted pages

cstore_fdw wrote raw files with `fwrite` and got no WAL. Hydra Columnar instead
keeps the data **inside the relation's main fork**: `columnar_storage.c`
"translates columnar read/write operations on logical offsets into operations on
pages/blocks" because "the buffer cache and WAL depend on formatted pages with
headers, so these large buffers need to be written across many pages"
(`columnar_storage.c:8-21`) `[verified-by-code]`. Block 0 holds a
`ColumnarMetapage` (magic/version + `reservedStripeId`, `reservedRowNumber`,
`reservedOffset` allocators), block 1 is reserved empty, and logical data starts
after (`columnar_storage.c:21-23`, `:56-88`) `[verified-by-code]`. This is the
load-bearing improvement over the FDW design: by formatting pages, columnar gets
crash safety and replication from core's WAL for free, at the cost of a logical-
to-physical offset mapping layer. Cross-ref
`[[knowledge/subsystems/storage-buffer]]`, `[[knowledge/architecture/wal]]`,
`[[knowledge/ideologies/cstore_fdw]]` (the WAL-less predecessor).

### 3. There is no in-place UPDATE; UPDATE is "mark deleted in a row-mask + re-insert", and DELETE never touches a heap xmax

Columnar stripes are write-once/compressed, so a row cannot be updated in place.
`columnar_tuple_delete` flips a bit in a **row-mask** bitmap stored in the
`columnar.row_mask` catalog (`UpdateRowMask(... rowNumber)`,
`columnar_tableam.c:1090-1112`) `[verified-by-code]`; visibility of a deleted
row is therefore a metadata bitmap lookup, not heap `xmax`/MVCC on the tuple.
`columnar_tuple_update` does the same row-mask delete and then calls
`columnar_tuple_insert` for the new version, setting `*update_indexes = true`
(`columnar_tableam.c:1119-1160`) `[verified-by-code]` — every UPDATE is a
logical delete + append. The `columnar.row_mask` catalog has columns
`storage_id, stripe_id, chunk_id, start_row_number, end_row_number,
deleted_rows, mask` (`columnar_metadata.c:216-225`) `[verified-by-code]`.
Re-implementing delete/visibility as a sidecar bitmap is a complete departure
from heap MVCC. Cross-ref `[[knowledge/architecture/mvcc]]`,
`[[knowledge/subsystems/access-heap]]`.

### 4. Writes serialize on a per-relation advisory transaction lock, not row locks

Because deletes/updates mutate shared row-mask + stripe metadata, both
`columnar_tuple_delete` and `columnar_tuple_update` first take a relation-wide
lock: `DirectFunctionCall1(pg_advisory_xact_lock_int8,
Int64GetDatum(storageId))` held to transaction end
(`columnar_tableam.c:1098-1103`, `:1130-1135`) `[verified-by-code]`. If the
row-mask update finds the row already gone, it returns `TM_Deleted`
(`:1109`). So concurrent writers to one columnar table serialize at table
granularity via an advisory lock keyed on the storage id — coarse compared to
heap's per-tuple locking, a deliberate trade for the append-only stripe model.
Cross-ref `[[knowledge/idioms/locking-overview]]` (advisory + heavyweight locks).

### 5. MVCC visibility lives in stripe write-state, tracked in metadata, not in tuple headers

A stripe is `STRIPE_WRITE_FLUSHED`, `STRIPE_WRITE_IN_PROGRESS`, or
`STRIPE_WRITE_ABORTED`, plus an `insertedByCurrentXact` flag, and the AM
consults these to decide whether a row number is visible
(`columnar_tableam.c:696-784`) `[verified-by-code]`: an in-progress stripe is
visible only to the inserting xact, an aborted stripe's rows are skipped. This
re-hosts the "is this tuple visible to my snapshot" decision into the columnar
metadata catalog (`columnar.stripe`, `columnar.chunk`, `columnar.chunk_group`,
`columnar.row_mask` — `columnar_metadata.c:179-225`) rather than reading
xmin/xmax off each tuple. Cross-ref `[[knowledge/architecture/mvcc]]`,
`[[knowledge/idioms/catalog-conventions]]`.

### 6. A CustomScan pushes column projection and quals into the AM — core's SeqScan can't do columnar projection

The whole point of columnar is to read only referenced columns and skip chunk
groups by min/max stats; a plain `SeqScan` would materialize every column.
Hydra adds a CustomScan (`ColumnarScanState` embeds `CustomScanState` as its
first field, `columnar_customscan.c:69-100`) whose comment states it exists to
"push down the projections into the table access methods"
(`columnar_customscan.c:6`) `[verified-by-code]`. `ColumnarSetRelPathlistHook`
adds columnar scan paths with a custom cost model (`CostColumnarScan`,
`AddColumnarScanPaths`, `columnar_customscan.c:111-173`), it supports
parallel scan via DSM (`Columnar_EstimateDSMCustomScan` /
`InitializeDSM` / `InitializeWorker`, `:165-176`), and provides
`ColumnarScan_ExplainCustomScan` for EXPLAIN. Driving column projection +
chunk-group pruning through a CustomScan + path-list hook is the planner-side
half of the design that the table-AM API alone cannot express. Cross-ref
`[[knowledge/subsystems/executor]]`, `[[knowledge/subsystems/optimizer]]`,
`[[knowledge/architecture/planner]]`, the `executor-and-planner` skill.

### 7. Several AM callbacks are deliberately stubbed-out `elog(ERROR)` or NULL

The AM surface is intentionally partial: `parallelscan_estimate/initialize/
reinitialize` all `elog(ERROR, "... not implemented")`
(`columnar_tableam.c:476-490`) — table-AM parallel *seq* scan is unsupported
(parallelism comes via the CustomScan instead); `scan_bitmap_next_block/tuple`
are `NULL` so bitmap heap scans don't apply
(`columnar_tableam.c:3018-3019`); `columnar_get_latest_tid`,
`columnar_tuple_tid_valid`, `columnar_relation_copy_data` are unimplemented
(`:843-852`, `:1304`) `[verified-by-code]`. Index scans also refuse to run when
there is unflushed data: "cannot read from index when there is unflushed data"
(`:505`, `:535`). Shipping a Table AM that fills only the callbacks columnar can
honor — and hard-erroring the rest — is a pragmatic divergence from the heap AM's
full coverage. Cross-ref the `access-method-apis` skill.

## Notable design decisions (cited)

- **Per-table settings via SQL functions, not GUCs**: `alter_columnar_table_set`
  / `alter_columnar_table_reset` (`columnar_tableam.c:3141`, `:3266`)
  `[verified-by-code]` adjust compression, stripe row limit, and chunk group
  size per relation — storage tuning exposed as functions over the
  `columnar.options` catalog (`columnar_metadata.c:153-179`).
- **Its own VACUUM entry point**: `vacuum_columnar_table`
  (`columnar_tableam.c:3496`) plus the AM's `relation_vacuum = columnar_vacuum_rel`
  (`:3007`) — vacuum compacts stripes / reclaims row-mask-deleted rows rather
  than running heap's lazy vacuum.
- **Storage-format versioning with online upgrade/downgrade**:
  `upgrade_columnar_storage` / `downgrade_columnar_storage`
  (`columnar_tableam.c:3351`, `:3387`) and `ColumnarMetapageIsCurrent/Older/Newer`
  (`columnar_storage.c:146-148`) `[verified-by-code]` — the on-disk metapage
  format is explicitly versioned, a maturity cstore_fdw lacked.
- **A vendored `safeclib`** (≈40 `mem*_s`/`str*_s` files under
  `columnar/src/backend/columnar/safeclib/`) for bounds-checked memory/string ops
  in the compression/IO paths — an unusual choice for a PG extension, which
  normally leans on `palloc`/`StringInfo`. Cross-ref
  `[[knowledge/idioms/memory-contexts]]`.
- **`relocatable = false`, `module_pathname = '$libdir/columnar'`**
  (`columnar.control:3-4`) — standard for a `.so` that must be preloaded to
  install hooks + the AM. Cross-ref `extension-development` skill §3.

## Links into corpus

- `access-method-apis` skill + `[[knowledge/architecture/access-methods]]` —
  the `TableAmRoutine` Hydra fills, with synthetic TIDs and stubbed parallel/
  bitmap callbacks; the single most important cross-reference.
- `[[knowledge/subsystems/access-heap]]` — the row-store AM Hydra parallels and
  diverges from (no line pointers, no in-place update, no heap-xmax delete).
- `[[knowledge/subsystems/storage-buffer]]` + `[[knowledge/subsystems/storage-buffer]]`
  + `[[knowledge/architecture/wal]]` — the smgr/buffer/WAL layer Hydra reuses
  by formatting pages (the key improvement over cstore_fdw's raw-file IO).
- `[[knowledge/architecture/mvcc]]` — visibility re-hosted into stripe
  write-state + a row-mask bitmap catalog instead of tuple xmin/xmax.
- `[[knowledge/idioms/locking-overview]]` — per-relation `pg_advisory_xact_lock` over the
  storage id serializing writers.
- `[[knowledge/subsystems/optimizer]]` + `[[knowledge/subsystems/executor]]` +
  `[[knowledge/architecture/planner]]` + `executor-and-planner` skill — the
  CustomScan + `set_rel_pathlist_hook` doing column projection / chunk pruning.
- `[[knowledge/idioms/catalog-conventions]]` — the `columnar.{options,stripe,chunk,
  chunk_group,row_mask}` metadata catalog.
- `[[knowledge/ideologies/cstore_fdw]]` — the FDW-based predecessor by the same
  lineage; Hydra is the same idea re-expressed through the Table AM API with
  real WAL. `[[knowledge/ideologies/pg_duckdb]]` — the *other* columnar approach
  (embed DuckDB via a stub table AM + planner swap) for contrast.

## Sources

Fetched 2026-06-08 (branch `main`):

- `https://api.github.com/repos/hydradatabase/hydra`
  @ 2026-06-08 → HTTP 301 → resolves to `hydradatabase/columnar` (3026 stars,
  not archived, default branch `main`, last push 2025-02-10).
- `https://api.github.com/repos/hydradatabase/columnar/git/trees/main?recursive=1`
  @ 2026-06-08 → HTTP 200 (tree listing).
- `https://raw.githubusercontent.com/hydradatabase/columnar/main/README.md`
  @ 2026-06-08 → HTTP 200 (96 lines).
- `https://raw.githubusercontent.com/hydradatabase/columnar/main/columnar/src/backend/columnar/columnar.control`
  @ 2026-06-08 → HTTP 200 (4 lines).
- `.../columnar/columnar_tableam.c` @ 2026-06-08 → HTTP 200 (4030 lines).
- `.../columnar/columnar_customscan.c` @ 2026-06-08 → HTTP 200 (2851 lines).
- `.../columnar/columnar_planner_hook.c` @ 2026-06-08 → HTTP 200 (457 lines).
- `.../columnar/columnar_storage.c` @ 2026-06-08 → HTTP 200 (913 lines).
- `.../columnar/columnar_metadata.c` @ 2026-06-08 → HTTP 200 (2642 lines).

All cites are `[verified-by-code]` against the fetched `.c`/`.control`
(`TableAmRoutine` population, `columnar_handler`, synthetic TID mapping, storage
metapage layout, row-mask delete/update, advisory-lock serialization, stripe
write-state visibility, CustomScan + hooks, stubbed callbacks, metadata catalog
attnums) except the "column-oriented Postgres / data warehouse" framing and
benchmark claims, which are `[from-README]`. The `columnar_reader.c`/
`columnar_writer.c`/`columnar_compression.c` bodies, the `safeclib` internals,
the full `columnar_customscan.c` chunk-pruning logic, and the SQL install/
upgrade scripts were not deep-read.
