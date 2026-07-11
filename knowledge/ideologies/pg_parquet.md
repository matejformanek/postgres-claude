# pg_parquet — bolting a Parquet-over-object-storage format onto COPY by hijacking `ProcessUtility`, not by extending a format registry

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `CrunchyData/pg_parquet` @ branch `main`. All `file:line` cites below
> point into that repo (not `source/`), since this doc characterizes an
> *external* extension's divergence from core idioms. Cites verified against the
> blobs fetched on 2026-07-11 (see Sources footer). Line numbers are for the
> `main` blobs as fetched.

pg_parquet lets you `COPY (SELECT …) TO 's3://bucket/data.parquet' WITH (format
'parquet')` and `COPY tbl FROM 's3://…' WITH (format 'parquet')`, reading and
writing Apache Parquet files in S3 / Azure Blob / GCS / http(s) / local FS
(`README.md:8-16`) `[from-README]`. **Headline divergence:** core PostgreSQL has
*no pluggable COPY-format registry* — `copy.c` hard-codes `text`/`csv`/`binary`,
and `format` is validated against exactly those. So pg_parquet does not add a
format; it installs a **`ProcessUtility_hook`** that inspects every utility
statement, recognizes a COPY whose `format` option is `parquet` (or whose URI
ends `.parquet`), and *takes the whole command over* — bypassing
`standard_ProcessUtility`'s COPY path entirely and driving its own executor
portal + `DestReceiver` (TO) or core `BeginCopyFrom` data-source callback (FROM)
(`hook.rs:135-167`) `[verified-by-code]`. On top of that it reaches out of the
backend to object storage using a **per-backend single-threaded tokio runtime**
that every network call `block_on`s synchronously (`lib.rs:32-37`)
`[verified-by-code]`. It is written in Rust on pgrx, so nearly all the "backend"
code is `extern "C-unwind"` Rust talking to `pg_sys`.

## Domain & purpose

The extension "allows you to read and write Parquet files, which are located in
`S3`, `Azure Blob Storage`, `Google Cloud Storage`, `http(s) endpoints` or `file
system`, from PostgreSQL via `COPY TO/FROM` commands" and depends on Apache Arrow
for the Parquet codec and pgrx "to extend PostgreSQL's `COPY` command"
(`README.md:8`) `[from-README]`. Three use cases: export tables/queries to
Parquet (files, stdin/stdout, or a program pipe), ingest Parquet back into
tables, and inspect Parquet schema/metadata/statistics via SQL UDFs
(`README.md:69-72`) `[from-README]`. The control file declares it
`superuser = true`, `relocatable = false` (`pg_parquet.control:4-5`)
`[verified-by-code]`, and `_PG_init` hard-refuses to load unless it is in
`shared_preload_libraries` (`lib.rs:41-43`) `[verified-by-code]` — because the
hook must be installed at postmaster start, before any backend forks.

## How it hooks into PG

- **Load-time gate + GUC + hook install.** `_PG_init` panics unless
  `process_shared_preload_libraries_in_progress` (`lib.rs:41-43`); it registers a
  `Userset` bool GUC `pg_parquet.enable_copy_hooks`, calls
  `MarkGUCPrefixReserved("pg_parquet")`, and then `init_parquet_copy_hook()`
  (`lib.rs:45-60`) `[verified-by-code]`. The GUC define runs inside
  `TopMemoryContext.switch_to` so the C-string-backed GUC metadata outlives the
  call (`lib.rs:46-56`) `[verified-by-code]`.
- **The hook itself.** `init_parquet_copy_hook` saves the previous
  `ProcessUtility_hook` into a `static mut PREV_PROCESS_UTILITY_HOOK` and sets
  `ProcessUtility_hook = Some(parquet_copy_hook)` (`hook.rs:38-47`)
  `[verified-by-code]` — the canonical chained-hook idiom (cf.
  `[[knowledge/idioms/process-utility-hook-chain.md]]`).
- **Dispatch.** `parquet_copy_hook` re-boxes the raw C args as `PgBox`, tests
  `is_copy_to_parquet_stmt` / `is_copy_from_parquet_stmt`, and on a match runs its
  own processing and `return`s (never calling downstream); otherwise it forwards
  to `PREV_PROCESS_UTILITY_HOOK` or `standard_ProcessUtility`
  (`hook.rs:135-193`) `[verified-by-code]`. It sets the `QueryCompletion`
  `nprocessed` + `CMDTAG_COPY` itself so the client still sees a normal `COPY N`
  tag (`hook.rs:151-166`) `[verified-by-code]`.
- **Recognition.** A statement is "ours" when `copy_from` matches, the URI parses
  to a supported scheme, and either `format 'parquet'` is set or the URI has a
  parquet extension (`copy_utils.rs:444-483`, `is_parquet_format_option`
  `:495-511`) `[verified-by-code]`. It also declines if `crunchy_query_engine`
  exists, and warns (but declines) if `pg_parquet` itself is not `CREATE
  EXTENSION`-ed (`copy_utils.rs:465-480`) `[verified-by-code]`.
- **Object-store IO crosses into the backend via a current-thread tokio
  runtime.** `PG_BACKEND_TOKIO_RUNTIME` is a `LazyLock<Runtime>` built with
  `new_current_thread()` — "uses the same thread that is running the Postgres
  backend" (`lib.rs:30-37`) `[verified-by-code]` `[from-comment]`. Every network
  round-trip is a synchronous `.block_on(async { … })` on that runtime
  (`parquet_writer.rs:122-124,129-131,137-139`, `uri_utils.rs:239-259,270-294`,
  `aws.rs:127-128,136-137`) `[verified-by-code]`.

## Where it diverges from core idioms

### 1. COPY-format extension without a format-extension point

Core's `copy.c` does not expose a way to register a new COPY format; the format
name is closed. pg_parquet's answer is to **not touch the COPY grammar or format
dispatch at all** and instead intercept the entire `T_CopyStmt` above
`standard_ProcessUtility` (`hook.rs:135-167`) `[verified-by-code]`. The cost of
this "intercept the whole command" strategy is that the extension must
**re-implement the parts of core's COPY driver it needs**:

- COPY TO rebuilds the statement as a `SELECT`: if the COPY names a relation it
  synthesizes a `SelectStmt` (`SELECT * FROM rel` or the explicit attlist),
  otherwise it uses the COPY's own query; then `pg_analyze_and_rewrite` →
  `pg_plan_query` → `CreateNewPortal` → `PortalRun` with its custom
  `DestReceiver` (`copy_to.rs:29-109`, `convert_copy_to_relation_to_select_stmt`
  `:133-198`) `[verified-by-code]`. This mirrors, in Rust, what core's
  `DoCopyTo` does internally.
- It re-derives COPY's own guards from the core source: the table-kind check
  ("cannot copy from view … Try the COPY (SELECT …) TO variant.") is copied from
  the PG COPY path (`copy_to.rs:200-270`, comment `:201`) `[verified-by-code]`
  `[from-comment]`; likewise COPY FROM's RLS refusal (`copy_from.rs:224-238`) and
  a vendored `check_copy_table_permission` (`pg_compat.rs:80-179`)
  `[verified-by-code]`. Cross-ref `[[knowledge/idioms/row-security-policy-application.md]]`.

### 2. COPY FROM reuses core's parser by faking the *binary* wire format

Rather than re-implement tuple construction, COPY FROM leans on core: it calls
`BeginCopyFrom(… Some(copy_parquet_data_to_buffer) …)` / `CopyFrom` /
`EndCopyFrom` (`copy_from.rs:167-181`) `[verified-by-code]`, registering a
**data-source callback** (`copy_parquet_data_to_buffer`, `copy_from.rs:75-104`)
`[verified-by-code]` that hands core bytes in PG's *binary* COPY format. The
Parquet→binary translation happens in a `ParquetReaderContext` whose output the
callback drains buffer-by-buffer (`copy_from.rs:88-101`) `[verified-by-code]`;
`copy_options` force binary format (`copy_from.rs:164-165`) `[verified-by-code]`.
So core's `copyfromparse.c` still does partition routing, defaults, constraints —
pg_parquet only substitutes the *bytes*. The reader contexts live on a
`static mut Vec` **stack** because COPY can nest (`copy_from.rs:34-71`)
`[verified-by-code]`. Cross-ref `[[knowledge/idioms/tablesync-initial-copy.md]]`
(core's other "COPY as a library" client) and the `[[.claude/skills/copy-family]]`
skill.

### 3. A custom `#[repr(C)] DestReceiver` that buffers PG tuples into Arrow

COPY TO plugs a hand-rolled `CopyToParquetDestReceiver` — a `#[repr(C)]` struct
whose first field is a real `DestReceiver`, with `rStartup`/`receiveSlot`/
`rShutdown`/`rDestroy` wired to `extern "C-unwind"` Rust fns
(`copy_to_dest_receiver.rs:28-45,376-425`) `[verified-by-code]`. `copy_receive`
pulls all attrs from the `TupleTableSlot`, snapshots the datums into a
`PgHeapTuple`, and accumulates them into a batch; when the batch hits
`target_batch_size` (or would overflow arrow's `i32::MAX` per-column array cap)
it flushes to Parquet (`copy_to_dest_receiver.rs:259-311,83-94`)
`[verified-by-code]`. This is the classic custom-DestReceiver idiom (same shape
`SPI`, `EXPLAIN`, and `printtup` use) turned into a Parquet encoder.

### 4. Arrow/Parquet buffers live *outside* palloc; two hand-managed MemoryContexts bound them

The row batches accumulate as Rust/Arrow structures owned by a `Box`-leaked
`ParquetWriterContext` (`copy_to_dest_receiver.rs:242-254`) `[verified-by-code]`,
i.e. arrow columnar buffers are **heap allocations the memory-context machinery
cannot see**. To keep the PG side bounded, the receiver creates two explicit
`AllocSetContextCreateExtended` contexts — a per-row-group context reset after
every flush (`MemoryContextReset`) and a copy-lifetime context — and tears them
down in `cleanup` via `MemoryContextDelete` plus `Box::from_raw`/`drop` of the
writer (`copy_to_dest_receiver.rs:69-81,172-192,383-401`) `[verified-by-code]`.
This is the recurring "Rust-owned bytes shadow-managed alongside palloc" tax the
corpus sees in every pgrx extension; cross-ref
`[[knowledge/idioms/memory-contexts.md]]`,
`[[knowledge/idioms/memory-context-api-and-dispatch.md]]`, and the
`[[knowledge/ideologies/pgrx.md]]` note.

### 5. Object-store networking from inside a backend, via a blocking single-thread runtime

Core backends never open outbound network sockets in the executor. pg_parquet
does: it builds `object_store::ObjectStore` handles (`aws`/`azure`/`gcs`/`http`/
`fs`) and drives them through the current-thread tokio runtime, `block_on`-ing
every `head`/`write`/`flush`/`finish` (`uri_utils.rs:220-334`,
`parquet_writer.rs:116-140`) `[verified-by-code]`. Because the runtime is
`new_current_thread` it multiplexes on the backend's own thread — so signals /
`CHECK_FOR_INTERRUPTS` are only serviced between `block_on`s, not during them
`[inferred]`. Stores are cached per session keyed on `(scheme, bucket)` in a
`static mut OBJECT_STORE_CACHE`, with credential-expiry-based eviction
(`object_store_cache.rs:20-129`) `[verified-by-code]`. AWS credentials are loaded
by *actually running the aws-sdk* default provider chain under the same runtime
(`block_on(aws_config::defaults(…).load())`, then `provide_credentials`) because
`object_store` alone won't read `~/.aws/config` (`aws.rs:26-165`, esp.
`:127-128,135-143`) `[verified-by-code]` `[from-comment]`. Cross-ref
`[[knowledge/ideologies/postgres-aws-s3.md]]`, `[[knowledge/ideologies/pg_lake.md]]`.

### 6. Type mapping is PG tupdesc ↔ Arrow schema, gated by PG's own coercion rules

Instead of a fixed on-disk layout, the write path derives an **Arrow schema from
the tuple descriptor** (`parse_arrow_schema_from_attributes`,
`parquet_writer.rs:61-79`) and converts it to a Parquet schema via arrow's
`ArrowSchemaConverter` (`schema_parser.rs:36-49`) `[verified-by-code]`. The
mapping is explicit per PG type OID (`BOOLOID`, `NUMERICOID`, `JSONBOID`,
`UUIDOID`, timestamps, …) with array/composite/domain recursion, and read-side
compatibility is checked with core's own `can_coerce_type` / `can_cast_types`
(`schema_parser.rs:11-34`) `[verified-by-code]`. Composite types map to Arrow
structs, arrays to Arrow lists, and PostGIS geometry gets GeoParquet `geo`
key-value metadata written into the file footer (`parquet_writer.rs:102-109`)
`[verified-by-code]`. This is a far larger type-bridge surface than core COPY,
which only ever emits/parses text or PG's binary send/recv.

## Notable design decisions (cited)

- **Must be in `shared_preload_libraries`; hard panic otherwise**
  (`lib.rs:41-43`) `[verified-by-code]` — the hook has to exist before any
  backend runs COPY.
- **`ProcessUtility_hook` chaining preserves any prior hook** (e.g. pgaudit) and
  restores `nprocessed`/`CMDTAG_COPY` on the completion tag so clients are
  none the wiser (`hook.rs:38-47,151-166`) `[verified-by-code]`. The test config
  even co-loads `pgaudit` to prove coexistence (`lib.rs:74`) `[verified-by-code]`.
- **Object-storage authorization uses purpose-built roles, not superuser-only.**
  `_PG_init`/bootstrap creates `parquet_object_store_read` /
  `parquet_object_store_write` roles (`sql/bootstrap.sql:1-10`)
  `[verified-by-code]`; `ensure_access_privilege_to_uri` short-circuits for
  superusers and stdin/out, else requires the matching role — reusing core's
  `pg_read_server_files`/`pg_write_server_files`/`pg_execute_server_program` for
  file/program targets and the two custom roles for remote URIs
  (`uri_utils.rs:336-391`) `[verified-by-code]`.
- **stdin/stdout and `PROGRAM` are bridged through a Postgres temp file.** For
  `COPY … TO STDOUT (format parquet)` and program pipes it writes the Parquet to
  an `OpenTemporaryFile` (auto-removed at xact end) and then streams it out
  (`uri_utils.rs:82-112,178-190`, `copy_to_dest_receiver.rs:148-170,313-330`)
  `[verified-by-code]` — Parquet's footer-at-end format can't be written to a
  forward-only pipe incrementally.
- **Batch flush respects both a row-count and a byte budget**, and pre-emptively
  flushes to dodge arrow's per-column `i32::MAX` array-size limit
  (`copy_to_dest_receiver.rs:83-94,304-306`, `parquet_writer.rs:126-132`)
  `[verified-by-code]`. Reader side symmetrically drops to batch-size 1 when a
  column would exceed that cap (`uri_utils.rs:296-315`) `[verified-by-code]`.
- **Per-session object-store cache with credential expiry** avoids re-auth on
  every COPY but honors token TTLs (`object_store_cache.rs:46-99,111-129`)
  `[verified-by-code]`.
- **pgrx `panic = "unwind"` in both dev and release profiles** (`Cargo.toml`
  `[profile.dev]`/`[profile.release]`) `[verified-by-code]` — required so Rust
  panics can be caught by `#[pg_guard]`/`PgTryBuilder` and turned into `ereport`
  rather than aborting the backend; the COPY paths wrap execution in
  `PgTryBuilder(...).finally(...)` to free the dest receiver / pop the reader
  context on error (`hook.rs:93-106,121-130`) `[verified-by-code]`.
- **A small `pg_compat` shim vendors core statics and papers over PG 14→18 API
  drift** (`pg_analyze_and_rewrite`, `strVal`, `MarkGUCPrefixReserved`, two
  `check_copy_table_permission` variants behind `#[cfg]`) (`pg_compat.rs:13-179`)
  `[verified-by-code]` — the same "copy an awkward-to-call core routine" tax seen
  in `[[knowledge/ideologies/pg_dirtyread.md]]` and `[[knowledge/ideologies/pg_squeeze.md]]`.

## Links into corpus

- `[[knowledge/idioms/process-utility-hook-chain.md]]` — the exact chaining
  idiom `init_parquet_copy_hook` implements (save prev, install, forward on
  non-match).
- `[[knowledge/idioms/tablesync-initial-copy.md]]` — core's other in-backend
  client of the COPY machinery; pg_parquet is a second "COPY as a library" user,
  but from the format side.
- `[[knowledge/idioms/memory-contexts.md]]` /
  `[[knowledge/idioms/memory-context-api-and-dispatch.md]]` — the two
  `AllocSet` contexts the dest receiver hand-manages around off-heap Arrow buffers.
- `[[knowledge/idioms/row-security-policy-application.md]]` — COPY FROM's RLS
  refusal, re-derived from core.
- `[[knowledge/idioms/guc-variables.md]]` — the `pg_parquet.enable_copy_hooks`
  GUC + `MarkGUCPrefixReserved`.
- `[[knowledge/subsystems/tcop.md]]` — where `ProcessUtility` /
  `standard_ProcessUtility` / `PortalRun` live in core.
- `[[knowledge/ideologies/pgrx.md]]` — the Rust/pgrx substrate (`#[pg_guard]`,
  `PgBox`, `extern "C-unwind"`, `panic = "unwind"`).
- `[[knowledge/ideologies/pg_lake.md]]` / `[[knowledge/ideologies/pg_ducklake.md]]`
  / `[[knowledge/ideologies/pg_duckdb.md]]` — sibling "PG ↔ lakehouse/Parquet"
  extensions; contrast their FDW/custom-scan integration with pg_parquet's
  COPY-hook one.
- `[[knowledge/ideologies/parquet_s3_fdw.md]]` — Parquet-over-S3 via the FDW
  interface instead of COPY; the closest functional sibling with a different hook.
- `[[knowledge/ideologies/postgres-aws-s3.md]]` — the other "reach S3 from a
  backend" extension; contrast credential handling.
- `[[knowledge/ideologies/pg_bulkload.md]]` — another bulk-load path that
  side-steps parts of the normal COPY/INSERT machinery.
- `.claude/skills/copy-family/SKILL.md` — core `copy*.c` internals pg_parquet
  intercepts and partially re-implements.
- `.claude/skills/extension-development/SKILL.md` /
  `.claude/skills/bgworker-and-extensions/SKILL.md` — `_PG_init`,
  `shared_preload_libraries` timing, hook installation.

## Anthropology takeaway

pg_parquet is the corpus's cleanest case of an extension **routing around a
missing extension point**. Core never designed COPY formats to be pluggable, so
rather than patch `copy.c`, pg_parquet climbs one level up to
`ProcessUtility_hook` and swallows the whole COPY command — then rebuilds just
enough of core's TO path (SELECT-ify → plan → portal → custom `DestReceiver`) and
reuses core's FROM path wholesale by feeding it synthesized *binary* COPY bytes.
That split is the reusable lesson: when you can't extend the middle, intercept
the top and re-enter core at whatever seam it *does* expose (`BeginCopyFrom`'s
data-source callback, the `DestReceiver` vtable). The second reusable pattern is
the object-storage bridge: a per-backend `new_current_thread` tokio runtime that
`block_on`s every request, an off-heap Arrow buffer pool shadow-managed by two
explicit `AllocSet` contexts, and purpose-built `parquet_object_store_{read,write}`
roles layered on core's `pg_{read,write}_server_files` — a compact template any
"PostgreSQL talks to S3" extension can copy. Both patterns show the pgrx tax
plainly: almost every divergence here is really "Rust-owned state living next to,
but invisible to, palloc, and made safe only by `panic = "unwind"` + `#[pg_guard]`."

## Sources

All fetched 2026-07-11, branch `main`, via
`https://raw.githubusercontent.com/CrunchyData/pg_parquet/main/<path>`:

- `README.md` — 200 (440 lines; domain, usage, roles, copy options — README-cited).
- `Cargo.toml` — 200 (67 lines; arrow/parquet/object_store/tokio/pgrx deps, unwind profiles).
- `pg_parquet.control` — 200 (5 lines; `superuser=true`, `relocatable=false`).
- `src/lib.rs` — 200 (78 lines; `_PG_init`, GUC, tokio runtime, module tree — deep-read).
- `src/parquet_copy_hook.rs` — 200 (11 lines; module root).
- `src/parquet_copy_hook/hook.rs` — 200 (194 lines; ProcessUtility_hook install + dispatch — deep-read).
- `src/parquet_copy_hook/copy_to.rs` — 200 (270 lines; SELECT-ify + portal + table-kind guard — deep-read).
- `src/parquet_copy_hook/copy_from.rs` — 200 (238 lines; BeginCopyFrom callback + reader-context stack + RLS — deep-read).
- `src/parquet_copy_hook/copy_utils.rs` — 200 (733 lines; format/URI recognition, options — partial deep-read).
- `src/parquet_copy_hook/copy_to_dest_receiver.rs` — 200 (426 lines; custom DestReceiver, batch collection, MemoryContexts — deep-read).
- `src/parquet_copy_hook/pg_compat.rs` — 200 (200 lines; vendored core statics + PG14→18 shims — skimmed).
- `src/arrow_parquet.rs` — 200 (11 lines; module root).
- `src/arrow_parquet/uri_utils.rs` — 200 (392 lines; URI parse, object-store readers/writers, tokio block_on, privilege check, temp-file bridge — deep-read).
- `src/arrow_parquet/parquet_writer.rs` — 200 (161 lines; ParquetWriterContext, block_on write/flush/finish, GeoParquet metadata — deep-read).
- `src/arrow_parquet/parquet_reader.rs` — 200 (417 lines; fetched, reader context — referenced).
- `src/arrow_parquet/schema_parser.rs` — 200 (715 lines; PG-OID→Arrow schema, can_coerce_type gating — head deep-read).
- `src/object_store.rs` — 200 (6 lines; module root).
- `src/object_store/object_store_cache.rs` — 200 (201 lines; per-session (scheme,bucket) cache + expiry — deep-read).
- `src/object_store/aws.rs` — 200 (166 lines; aws-sdk credential chain via tokio block_on — deep-read).
- `sql/bootstrap.sql` — 200 (16 lines; parquet_object_store_{read,write} roles + parquet schema).

Probed-but-404 (module roots use `foo.rs` not `foo/mod.rs`, resolved by fetching
the `.rs` sibling): `src/parquet_copy_hook/mod.rs`, `src/object_store/mod.rs`,
`src/arrow_parquet/mod.rs`, `src/type_compat/mod.rs`. No content gaps resulted.
GitHub API / trees endpoint was blocked this run; all paths fetched directly by
following `mod` declarations from `lib.rs`. All cites are `[verified-by-code]`
against the fetched `.rs`/`.toml`/`.control`/`.sql` blobs except the
domain/purpose/usage narrative (`[from-README]`), the tokio-runtime and
aws-config rationale comments (`[from-comment]`), and the
interrupt-servicing/current-thread inference (§5, `[inferred]`).
