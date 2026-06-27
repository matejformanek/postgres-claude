# parquet_s3_fdw — ideology / divergence notes

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `pgspider/parquet_s3_fdw` @ branch `main`. ~241★, language **C++**. All
> `file:line` cites below point into that repo (cited as `src/parquet_impl.cpp:NN`,
> `parquet_s3_fdw_connection.cpp:NN`, etc.), **not** `source/`, since this doc
> characterizes an *external* extension's divergence from core idioms. Cites
> verified against the files fetched on 2026-06-27 (see Sources footer).

parquet_s3_fdw makes a set of **Apache Parquet files on Amazon S3 (or a local
directory, or MinIO)** appear as PostgreSQL foreign tables. Its headline
divergence is **dimensional**: where a conformant C FDW like `[[tds_fdw]]`
marshals a remote row stream one tuple at a time, this extension is a
**columnar reader written in C++** that pulls whole Parquet *row groups* into
in-memory Apache Arrow tables, prunes them at *planning time* using Parquet
column-chunk min/max statistics, and reaches storage by implementing Arrow's
`RandomAccessFile` interface directly on top of the **AWS C++ SDK** — three
foreign C++ libraries (Arrow, Parquet, `libaws-cpp-sdk`) linked into the
backend, fenced off from PG's `longjmp`-based error machinery by a
hand-rolled `try { … } catch (std::exception&) { elog(ERROR, …) }` firewall at
every `extern "C"` callback boundary.

## Domain & purpose

The `.control` comment is `'foreign-data wrapper for parquet on S3'`, default
version `0.3`, `relocatable = true` (`parquet_s3_fdw.control:2-5`)
`[verified-by-code]`. It is a **fork of the original `adjust/parquet_fdw`**
(Apache-Arrow-based local Parquet FDW; copyright lines name both "TOSHIBA
CORPORATION" and "adjust GmbH", `src/parquet_fdw.c:6-7`) `[from-comment]`,
extended by TOSHIBA to add an S3 storage backend and full write support. A
foreign server / table carries S3 connection options (`user`, `password`,
`region`, `endpoint`, `parquet_s3_fdw_connection.cpp:370-381`), a `filename`
or `dirname`, plus reader knobs (`use_threads`, `use_mmap`, `max_open_files`,
`schemaless`, `sorted`, `key`, `insert_file_selector`)
`[verified-by-code]`. Unlike a network FDW there is no remote query engine —
the "remote" is an object store, and *all* relational work (filtering beyond
row-group pruning, joins, aggregates) happens locally in PG over the
materialized Arrow data.

## How it hooks into PG

The `FdwRoutine` is assembled in a **plain `.c` file** (`src/parquet_fdw.c`),
deliberately separate from the C++ implementation, so the handler itself
compiles as C and the C++ TU exports each callback as `extern "C"`:

- **Handler / validator / version:** `parquet_s3_fdw_handler` does the textbook
  `makeNode(FdwRoutine)` + field assignment (`src/parquet_fdw.c:175-204`)
  `[verified-by-code]`; `parquet_s3_fdw_validator` delegates to
  `parquet_fdw_validator_impl` (`src/parquet_fdw.c:166-170`); all are
  `PG_FUNCTION_INFO_V1` (`src/parquet_fdw.c:157-158,172`) — the
  `[[fmgr-and-spi]]` handler pattern.
- **Scan lifecycle:** `GetForeignRelSize`/`GetForeignPaths`/`GetForeignPlan`,
  `BeginForeignScan`/`IterateForeignScan`/`ReScanForeignScan`/`EndForeignScan`,
  `ExplainForeignScan` → the `parquet*ForeignScan` functions
  (`src/parquet_fdw.c:179-187`) `[verified-by-code]`.
- **Parallel scan:** the full DSM set —
  `IsForeignScanParallelSafe`, `EstimateDSMForeignScan`,
  `InitializeDSMForeignScan`, `ReInitializeDSMForeignScan`,
  `InitializeWorkerForeignScan`, `ShutdownForeignScan`
  (`src/parquet_fdw.c:188-193`) `[verified-by-code]` — see
  `[[parallel-query]]`.
- **Modify:** `AddForeignUpdateTargets`, `PlanForeignModify`,
  `BeginForeignModify`, `ExecForeignInsert`/`Update`/`Delete`,
  `EndForeignModify` (`src/parquet_fdw.c:195-201`) `[verified-by-code]`. No
  direct-modify, batch-insert, or join/upper push-down callbacks are set.
- **ANALYZE / IMPORT:** `AnalyzeForeignTable` (`src/parquet_fdw.c:186`)
  returns `parquetAcquireSampleRowsFunc` (`src/parquet_impl.cpp:2876-2883`);
  `ImportForeignSchema` (`src/parquet_fdw.c:194`) plus two SRFs
  `import_parquet_s3` / `import_parquet_s3_with_attrs`
  (`src/parquet_impl.cpp:3530,3554`) `[verified-by-code]`.
- **`_PG_init`** registers three GUCs (`parquet_s3_fdw.use_threads`,
  `parquet_fdw.enable_multifile`, `parquet_fdw.enable_multifile_merge`,
  `src/parquet_fdw.c:120-154`), calls `parquet_s3_init()` (which runs
  `Aws::InitAPI`), and registers `on_proc_exit(&parquet_s3_shutdown)` (which
  runs `Aws::ShutdownAPI`) (`src/parquet_fdw.c:131-133`,
  `parquet_s3_fdw_connection.cpp:131-143`) `[verified-by-code]`.
- **Library boundary:** the AWS SDK (`<aws/s3/...>`), Apache Arrow
  (`arrow::`), and Parquet (`parquet::`) are all linked into the backend
  address space (`parquet_s3_fdw.cpp:15-16`, `src/reader.cpp` `parquet::`/
  `arrow::` throughout) `[verified-by-code]`.

## Where it diverges from core idioms

### 1. C++ ⟷ C extern boundary with a per-callback exception firewall

Every FDW callback is defined `extern "C"` in a `.cpp` TU
(`src/parquet_impl.cpp:2406,2630,2652,…`) `[verified-by-code]`, and the ones
that call into Arrow/AWS wrap the C++ body in a `try`/`catch` that converts a
thrown `std::exception` into `elog(ERROR, "parquet_s3_fdw: %s", e.what())`.
`parquetIterateForeignScan` is the canonical shape:
`try { festate->next(slot); } catch (std::exception &e) { error = e.what(); }`
then `elog(ERROR, …)` (`src/parquet_impl.cpp:2638-2647`) `[verified-by-code]`;
`parquetBeginForeignScan` does the same around state creation
(`src/parquet_impl.cpp:2575-2596`). This **is** an exception firewall — unlike
`[[pgrouting]]` historically (C++ Boost code that could let exceptions reach
PG) or the `[[pgrx]]` Rust panic-to-ereport bridge, here it is hand-written at
each seam. It is necessary because a C++ exception unwinding *through* a PG C
stack frame (or a PG `ereport` `longjmp` unwinding *through* a C++ frame that
owns Arrow objects) is undefined behavior. Conversely, the C-side
`create_s3_connection` uses `PG_TRY`/`PG_CATCH` to `delete` a half-built
`S3Client` on `ereport` (`parquet_s3_fdw_connection.cpp:340-400`)
`[verified-by-code]` — the mirror-image firewall, catching the *PG* error so
the C++ heap object is freed.

### 2. Columnar row-group reads, not row-at-a-time IterateForeignScan

The execution state pulls one Parquet **row group** at a time into an Arrow
`Table` via `reader->RowGroup(rg)->ReadTable(this->indices, &this->table)`
(`src/reader.cpp:1234-1236`) `[verified-by-code]`, caches the per-column
`arrow::Array` chunks (`src/reader.cpp:1249-1274`), and then
`IterateForeignScan` hands out one PG tuple per `next()` call by indexing into
those in-memory columnar chunks (`src/reader.cpp:1271-1277`,
`src/parquet_impl.cpp:2640`) `[verified-by-code]`. So the *storage* read is
columnar and bulk; the *FDW contract* (one `TupleTableSlot` per
`IterateForeignScan`) is satisfied by re-rowifying the Arrow batch in memory.
`read_next_rowgroup` advances to the next row group (or asks the parallel
coordinator for one, see §6) when the current Arrow table is exhausted
(`src/reader.cpp:1200-1280`).

### 3. Predicate pushdown into Parquet row-group min/max statistics — at plan time

This is the deepest planner divergence. `extract_rowgroups_list` opens each
Parquet file *during planning* and, for every row group, reads each referenced
column chunk's `statistics()` and calls `row_group_matches_filter`
(`src/parquet_impl.cpp:798-808,854-976`) `[verified-by-code]`.
`row_group_matches_filter` decodes the chunk's `EncodeMin()`/`EncodeMax()`,
converts the bytes to the PG type, and compares against the qual constant with
the operator's btree strategy number — pruning any row group whose `[min,max]`
range cannot satisfy a `<`/`<=`/`>`/`>=`/`=` predicate
(`src/parquet_impl.cpp:585-661`) `[verified-by-code]`. Surviving row-group
indices are pinned into `fdw_private` (`FdwScanPrivateRowGroups`) and re-read at
`BeginForeignScan` (`src/parquet_impl.cpp:2462-2463,2583-2589`). The matched
row count is also computed during planning and fed straight into the planner:
`baserel->tuples = total_rows; baserel->rows = matched_rows`
(`src/parquet_impl.cpp:1711-1712`) `[verified-by-code]`. There is even a
special case for the jsonb `?` (exists) operator against a Parquet `MAP` column
(`src/parquet_impl.cpp:595-614`). **Projection pushdown** is the `this->indices`
vector — only the columns the query references are passed to `ReadTable`
(`src/reader.cpp:266,308-316,489,531-541`; consumed at
`src/reader.cpp:1236`) `[verified-by-code]`.

### 4. S3 access via Arrow's RandomAccessFile implemented on the AWS C++ SDK

`S3RandomAccessFile` subclasses `arrow::io::RandomAccessFile` and implements
`Read`/`Seek`/`Tell`/`GetSize` by issuing AWS S3 `GetObjectRequest` with an
HTTP byte-`Range` header (`bytes=<off>-<off+n-1>`) and `HeadObjectRequest` for
size (`parquet_s3_fdw.cpp:23-121`) `[verified-by-code]`. So Arrow's Parquet
reader believes it is reading a seekable local file, while each "seek+read"
becomes a ranged S3 GET against the backend's linked-in AWS SDK. The S3 client
config picks `HTTP` + `endpointOverride` for MinIO vs `HTTPS` + `region` for
real S3 (`parquet_s3_fdw_connection.cpp:508-523`), signs with
`AWSAuthV4Signer` (`:514,522`), and credentials come from the user mapping's
`user`/`password` options (`:499-501`) `[verified-by-code]`. `Read(nbytes)`
even does a bare `malloc(nbytes)` (`parquet_s3_fdw.cpp:100`) — raw C++ heap,
not `palloc`.

### 5. Memory & handles live in Arrow/AWS allocators OUTSIDE MemoryContexts

The C++ execution-state object, the Arrow tables, and the AWS `S3Client` are
all heap-allocated by their own libraries (`new`/`delete`,
`arrow::default_memory_pool()`, `Aws::MakeShared`), *not* `palloc`. The FDW
bridges them back to `[[memory-contexts]]` discipline two ways:
- **Scan state** is tied to a per-scan `AllocSetContextCreate` child of
  `es_query_cxt` (`src/parquet_impl.cpp:2517-2519`), and a
  `MemoryContextRegisterResetCallback` invoking `destroy_parquet_state` runs
  the C++ destructor when that context is reset
  (`src/parquet_impl.cpp:2602-2607`) `[verified-by-code]`. So PG context
  teardown drives C++ `delete` — `EndForeignScan` itself does no freeing and
  says so (`src/parquet_impl.cpp:2652-2658`) `[from-comment]`.
- **Write buffers** are an Arrow `Table` materialized in memory then written to
  a *local temp file* with `parquet::arrow::WriteTable`
  (`src/modify_reader.cpp:1259-1263`) before upload.
- The AWS `S3Client` is freed by an explicit `delete` in `s3_client_close`
  (`parquet_s3_fdw_connection.cpp:530-534`), invoked from the cache-invalidation
  path — never via a MemoryContext. A `pthread_mutex` (`cred_mtx`) guards
  `ClientConfiguration` construction (`parquet_s3_fdw_connection.cpp:504-506`)
  `[verified-by-code]` — an OS thread primitive inside a PG backend, because
  the AWS SDK and Arrow `use_threads` path are genuinely multi-threaded.

### 6. Parallel scan distributes row groups via a coordinator in DSM

Rather than partition by block, the parallel path hands out row groups: a
worker calls `coordinator->next_rowgroup(reader_id)` under a lock to claim the
next row-group index (`src/reader.cpp:1208-1216`) `[verified-by-code]`,
plumbed through `EstimateDSMForeignScan`/`InitializeDSMForeignScan`/
`InitializeWorkerForeignScan` (`src/parquet_fdw.c:188-193`). The unit of
parallel work is therefore the Parquet row group, not the PG page —
`[[parallel-query]]` adapted to a columnar file layout.

### 7. Connection cache is postgres_fdw-shaped, but caches an S3Client

The cache keeps postgres_fdw's exact skeleton — a backend-local `HTAB` keyed by
**user-mapping OID** (`key = user->umid`), created in `CacheMemoryContext`,
with `CacheRegisterSyscacheCallback(FOREIGNSERVEROID/USERMAPPINGOID, …)`
registered once (`parquet_s3_fdw_connection.cpp:157-220`) `[verified-by-code]`
— but the cached payload is an `Aws::S3::S3Client *`, and the
`parquet_s3_fdw_get_connections`/`disconnect`/`disconnect_all` SRFs mirror
postgres_fdw's same-named functions (`:116-118`) `[verified-by-code]`. There is
no xact/subxact callback registration (an object store has no transactions to
join), which is the visible gap versus `[[sqlite_fdw]]`/postgres_fdw.

### 8. Schema import drives the Parquet footer, not a remote catalog

`ImportForeignSchema` (and the `import_parquet_s3*` SRFs) reads the Parquet
file's own schema metadata (`meta->num_row_groups()`, the Arrow schema) to
synthesize `CREATE FOREIGN TABLE` DDL (`src/parquet_impl.cpp:2803,3038-3047`)
`[verified-by-code]` — the catalog is the file footer, with no server round-trip.

## Notable design decisions (with cites)

- **Write = read-modify-rewrite of the whole file.** INSERT/UPDATE/DELETE
  mutate an in-memory Arrow table; `EndForeignModify` calls `fmstate->upload()`
  (`src/parquet_impl.cpp:4279-4287`), which for each modified reader writes a
  fresh Parquet file locally (`parquet::arrow::WriteTable`,
  `src/modify_reader.cpp:1594-1599,1259-1263`) and `PutObject`s the entire
  object back to S3 (`parquet_s3_fdw_connection.cpp:1141-1172`)
  `[verified-by-code]`. No in-place row mutation exists — every modify rewrites
  the whole Parquet file. `upload()` short-circuits if `modified == false`
  (`src/modify_reader.cpp:1591-1592`).
- **`key` column option drives UPDATE/DELETE matching.**
  `set_keycol_names`/`keycol_names` identify which columns locate the target row
  to rewrite (`src/modify_reader.cpp:298-305`,
  `src/modify_state.cpp:152`) `[verified-by-code]`.
- **`insert_file_selector` lets a user function choose the target file** for an
  INSERT across a directory of Parquet files
  (`get_selected_file_from_userfunc`, `src/parquet_impl.cpp:4304-4316`,
  uses `OidFunctionCall1NullableArg`) `[verified-by-code]`.
- **Four reader strategies, EXPLAIN-visible.** `RT_TRIVIAL`, `RT_SINGLE`
  (single file), `RT_MULTI` (multifile), `RT_MULTI_MERGE` /
  caching-merge — selected by file count and `sorted`/ORDER-BY pushdown, with
  dedicated C++ classes (`SingleFileExecutionStateS3`,
  `MultifileExecutionStateS3`, `MultifileMergeExecutionStateS3`,
  `CachingMultifileMergeExecutionStateS3`, `src/exec_state.cpp:45-765`) and
  reported in EXPLAIN (`src/parquet_impl.cpp:2906-2915`) `[verified-by-code]`.
  The merge readers provide **ORDER BY push-down** by k-way-merging sorted
  files, costed by `cost_merge` (`src/parquet_impl.cpp:1775-1800`).
- **"schemaless" mode** maps an entire Parquet file into a single `jsonb`
  column — `read_schemaless_column` builds a jsonb object per row
  (`src/reader.cpp:1285-1309`) and the planner builds jsonb-aware row-group
  filters (`src/parquet_impl.cpp:234`) `[verified-by-code]`.
- **MinIO as a first-class S3 target** (`use_minio`, HTTP + endpoint override,
  payload-signing `Never`, `parquet_s3_fdw_connection.cpp:508-515`)
  `[verified-by-code]`.
- **ANALYZE is real** — `AnalyzeForeignTable` returns
  `parquetAcquireSampleRowsFunc` (`src/parquet_impl.cpp:2876-2883`), which
  samples rows across files' row groups, unlike `[[sqlite_fdw]]` (whose ANALYZE
  is a no-op).

## Links into corpus

- [[tds_fdw]] — the "conformant single-source C FDW" foil: row-at-a-time
  IterateForeignScan over a network client. parquet_s3_fdw is the columnar,
  C++, object-store antithesis (bulk Arrow row groups; storage is S3, not a
  query engine).
- [[sqlite_fdw]] — sibling pgspider FDW over an *embedded engine*; compare its
  in-process `sqlite3*`-on-a-file model (with xact emulation + affinity
  normalization) against parquet_s3_fdw's *no-engine* object-store model (no
  transactions, statistics-based pruning instead of SQL pushdown).
- [[pg_duckdb]] / [[cstore_fdw]] — the closest contrast: pg_duckdb also reads
  Parquet/columnar through an *embedded vectorized engine* (DuckDB does the
  filtering), whereas parquet_s3_fdw reads Parquet directly via Arrow and pushes
  only row-group min/max pruning, doing the rest in PG; cstore_fdw is the
  columnar-storage-as-FDW cousin.
- [[wrappers]] / [[wasmer-postgres]] — high-divergence FDW/runtime frameworks;
  parquet_s3_fdw is hand-written C++ rather than a Rust-trait or WASM-loader
  abstraction.
- [[pgrouting]] / [[pgrx]] — the C++-exception / Rust-panic firewall contrast
  for §1: parquet_s3_fdw hand-writes the `catch(std::exception&) → elog(ERROR)`
  bridge at each callback rather than relying on a framework.
- [[executor-and-planner]] — the FdwRoutine scan/modify lifecycle and the
  plan-time `baserel->rows`/`baserel->tuples` costing the row-group pruner
  feeds.
- [[parallel-query]] — the DSM scan callbacks and the row-group coordinator.
- [[fmgr-and-spi]] — `PG_FUNCTION_INFO_V1` handler/validator + the import SRFs
  and `OidFunctionCall1NullableArg`.
- [[memory-contexts]] — `MemoryContextRegisterResetCallback` driving the C++
  destructor; Arrow/AWS allocations living outside contexts.
- [[gucs-config]] — the three `DefineCustomBoolVariable` knobs in `_PG_init`.
- [[error-handling]] — `ERRCODE_SQLCLIENT_UNABLE_TO_ESTABLISH_SQLCONNECTION`
  for S3 connect failures; the `PG_TRY`/`PG_CATCH` + `try`/`catch` mirror pair.

> Corpus gap: no idiom doc for the **C++/Arrow ⟷ C exception firewall** — the
> `extern "C"` callback + `try{}catch(std::exception&){elog(ERROR)}` pattern
> (and its `PG_TRY`/`PG_CATCH` mirror for freeing C++ heap objects on PG
> error). Shared by parquet_s3_fdw, pg_duckdb, and historically pgrouting;
> worth an `idioms/cxx-exception-firewall.md`.
> Corpus gap: no idiom doc for **statistics-based partition/row-group pruning at
> plan time** — reading external file metadata during `GetForeignRelSize` to set
> `baserel->rows` and pin a surviving-chunk list into `fdw_private`. Distinct
> from postgres_fdw's `use_remote_estimate` (which round-trips SQL); here the
> "statistics" are the Parquet footer's column-chunk min/max.

## Sources

All fetched 2026-06-27 (branch `main`) via
`https://raw.githubusercontent.com/pgspider/parquet_s3_fdw/main/<path>`, tree
listing via `https://api.github.com/repos/pgspider/parquet_s3_fdw/git/trees/main?recursive=1` (HTTP 200):

- `parquet_s3_fdw.control` → HTTP 200 (5 lines).
- `parquet_s3_fdw.cpp` → HTTP 200 (121 lines; `S3RandomAccessFile` Arrow-over-AWS shim).
- `src/parquet_fdw.c` → HTTP 200 (204 lines; the C `FdwRoutine` handler, `_PG_init`, GUCs).
- `src/parquet_impl.cpp` → HTTP 200 (4671 lines; scan/modify callbacks, row-group
  pruning, costing, import — only the cited functions read in depth).
- `src/reader.cpp` → HTTP 200 (2106 lines; columnar `ReadTable`/row-group/projection,
  parallel coordinator, schemaless jsonb).
- `src/exec_state.cpp` → HTTP 200 (901 lines; the four execution-state classes).
- `src/modify_state.cpp` → HTTP 200 (811 lines; modify orchestration, `upload()`).
- `src/modify_reader.cpp` → HTTP 200 (2732 lines; write-path `WriteTable`, key columns,
  per-reader `upload`; only cited sections read in depth).
- `parquet_s3_fdw_connection.cpp` → HTTP 200 (1226 lines; connection cache,
  `s3_client_open`, `Aws::InitAPI`/`ShutdownAPI`, `PutObject` upload).
- `parquet_s3_fdw.h` → HTTP 200 (skimmed; the `parquet* → parquetS3*` rename macros
  confirming the `adjust/parquet_fdw` fork lineage).
- `src/common.cpp` → HTTP 200 (skimmed; helper utilities, no routine wiring).

> Sources gap: `README.md` on `main` returned HTTP 200 but is the **wrong file**
> — it is a PL/.NET (`pl/dotnet`) README with zero "parquet" mentions (a repo
> packaging mishap on this branch). No README-level scope claims were taken
> from it; all `[from-README]`-class facts were instead sourced from the
> `.control` comment and code. The extension's actual usage docs live elsewhere
> (e.g. a `doc/` tree or upstream wiki) and were not fetched.

Skimmed-but-not-fetched: `src/slvars.cpp` (schemaless-var support),
`parquet_s3_fdw_server_option.c` (server option validation),
the `*.hpp`/`heap.hpp` headers (struct decls), and the test corpora.
