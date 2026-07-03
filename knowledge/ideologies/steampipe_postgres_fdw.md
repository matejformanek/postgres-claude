# steampipe_postgres_fdw — a whole FDW handler written in Go, bridged into PG's C FDW API via cgo `//export`, turning Steampipe's plugin ecosystem into SQL tables

> Headline: where a conformant C FDW like `[[tds_fdw]]` is C all the way down, and
> `[[parquet_s3_fdw]]` is C++ behind a C shim, steampipe_postgres_fdw inverts the
> ratio — the `.so`'s *center of mass is a Go program* compiled `-buildmode=c-archive`,
> and PG's `FdwRoutine` callbacks are Go functions exported to C with `//export`.
> The "remote" is neither a database nor a file but a **Steampipe plugin** — a
> separate Go process speaking gRPC that maps a cloud/SaaS API (AWS, GitHub, …)
> onto rows. It is the "API-as-table", zero-ETL posture: every SELECT is a live
> API call, decoded by a Go runtime living inside a forked PG backend.

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `turbot/steampipe-postgres-fdw` @ branch `develop` (85★, **Go + cgo/C**),
> fetched 2026-07-03. All `file:line` cites point into that repo, **not**
> `source/`. Caveat: fetched via `raw.githubusercontent.com` only (the GitHub
> API tree endpoint + HTML tree view are 403 from this session), so the file
> tree was reconstructed by probing exact paths. The manifest's `fdw/fdw.go` /
> `fdw/init.go` were **404** — the real layout puts Go at the repo *root*
> (`fdw.go`, `errors.go`, `exec.go`, `helpers.go`) and the C side under `fdw/`
> (`fdw.c`, `query.c`, `datum.c`, `logging.c`, `fdw_helpers.h`, `common.h`).
> Files read: `README.md`, `Makefile`, `fdw/Makefile`, `prebuild.tmpl`, `go.mod`,
> `fdw.go`, `errors.go`, `exec.go`, `helpers.go`, `fdw/fdw.c`, `fdw/fdw_helpers.h`,
> `fdw/fdw_handlers.h`, `fdw/common.h`, `fdw/logging.c`. The `hub`, `types`,
> `version` Go packages (the gRPC plugin client) are referenced by import path
> but were not deep-read; claims about them are tagged `[inferred]`.

## Domain & purpose

The FDW "translates APIs to foreign tables. It does not directly interface with
external systems, but instead relies on plugins to implement API- or
provider-specific code that returns data in a standard format via gRPC"
(`README.md:5`) `[from-README]`. It ships two ways: bundled inside the Steampipe
CLI (`make install` drops `steampipe_postgres_fdw.so` into `~/.steampipe`,
`Makefile:9-14`), or as a **standalone extension** built for one plugin
(`make standalone plugin="aws"`, `README.md:53-65`, `Makefile:17-44`)
`[verified-by-code]`. In the standalone path, a code generator
(`go run generate/generator.go`, `Makefile:29`) renders a per-plugin extension
named `steampipe_postgres_<plugin>` (`fdw/Makefile:75-77`) `[verified-by-code]`.
Either way, the relational work — a `SELECT * FROM aws_s3_bucket` — is turned
into a gRPC scan against the plugin, which does the actual API calls; PG runs
joins/aggregates/filters locally over the streamed rows, with limit / sort /
qual pushdown negotiated down to the plugin where the plugin declares support.

## How it hooks into PG

The extension is a **cgo c-archive**: `go build -buildmode=c-archive ../*.go`
compiles all the root Go files (with `netgo` and a `pg14` build tag) into
`steampipe_postgres_fdw.a` plus a generated `.h`, which PGXS then links with the
C objects `datum.o query.o fdw.o logging.o` into the `.so`
(`fdw/Makefile:4-6,50-55`) `[verified-by-code]`. The C includes needed to see
PG's headers are injected at build time by templating `prebuild.tmpl` with
`pg_config` paths (`Makefile:129-142`, `prebuild.tmpl:1-13`) `[verified-by-code]`.

- **Handler / validator (fmgr V1).** `fdw_handler` and `fdw_validator` are
  declared `PG_FUNCTION_INFO_V1` in a cgo-adjacent C header
  (`fdw/fdw_handlers.h:19-20`) `[verified-by-code]` — the `[[fmgr]]` pattern.
  `fdw_handler` does the textbook `makeNode(FdwRoutine)` + field assignment and
  `PG_RETURN_POINTER` (`fdw/fdw_handlers.h:23-38`) `[verified-by-code]`.
- **The FdwRoutine vtable is half C, half Go.** The *planning* callbacks are C
  functions (`fdwGetForeignRelSize`, `fdwGetForeignPaths`, `fdwGetForeignPlan`,
  `fdwIsForeignScanParallelSafe`) defined in `fdw/fdw.c`; each C planner wrapper
  in turn calls a Go `//export` function (`goFdwGetRelSize`, `goFdwGetPathKeys`)
  to reach the plugin (`fdw/fdw_handlers.h:24-28`, `fdw/fdw.c:262-341,397-412`)
  `[verified-by-code]`. The *execution* callbacks are wired **directly** to Go
  functions — `BeginForeignScan = goFdwBeginForeignScan`,
  `IterateForeignScan = goFdwIterateForeignScan`, `EndForeignScan`,
  `ReScanForeignScan`, `ExplainForeignScan`, `ImportForeignSchema`,
  `ExecForeignInsert` are Go `//export` symbols installed straight into the
  `FdwRoutine` struct as C function pointers (`fdw/fdw_handlers.h:29-35`,
  `fdw.go:301,418,492,508,279,541,592`) `[verified-by-code]`. So PG's executor
  calls a Go function on every tuple with no intervening C trampoline — cgo
  generates the ABI glue.
- **`_PG_init` is C.** `PG_MODULE_MAGIC` and `_PG_init` live in `fdw/fdw.c:29,41`;
  `_PG_init` registers `on_proc_exit(&exitHook, …)` (which calls Go
  `goFdwShutdown` → `hub.Close()`) and `RegisterXactCallback(pgfdw_xact_callback,
  …)` (which on `XACT_EVENT_ABORT` calls Go `goFdwAbortCallback` → `hub.Abort()`)
  (`fdw/fdw.c:70-97`) `[verified-by-code]`. The Go runtime itself is booted lazily
  by `goInit()` on the first `GetForeignRelSize` (`fdw/fdw.c:272`), whose Go
  `init()` builds the plugin hub (`fdw.go:41-95`) `[verified-by-code]`.
- **IMPORT FOREIGN SCHEMA drives the plugin's schema.** `goFdwImportForeignSchema`
  asks the hub for the plugin's table/column schema and synthesizes
  `CREATE FOREIGN TABLE` DDL (`fdw.go:541-590`) `[verified-by-code]` — the
  "catalog" is the plugin's gRPC-reported schema, plus special internal schemas
  for settings/command tables (`fdw.go:558-569`).
- **One Go runtime per backend.** Because PG forks a fresh backend per connection,
  each backend that touches a steampipe table boots its *own* embedded Go runtime
  (its own goroutine scheduler, GC, gRPC client pool) inside that forked process
  `[inferred]`. There is no shared Go runtime across backends; the plugin
  processes are the shared, long-lived component, reached over gRPC.

## Where it diverges from core idioms

### 1. Two memory managers coexist: Go's GC heap and PG's MemoryContext/palloc

The scan produces rows as Go values (`row` is a `map[string]interface{}` from the
plugin, `fdw.go:445-468`), which are then converted **into PG Datums** column by
column through `ValToDatum`, writing into a PG `StringInfo` buffer and calling
`InputFunctionCall` / `cstring_to_text_with_len` (`helpers.go:150-182`)
`[verified-by-code]`. The tuple is materialized with PG's own `heap_form_tuple` +
`ExecStoreHeapTuple` via the `fdw_saveTuple` inline helper (`fdw/fdw_helpers.h:65-69`,
called at `fdw.go:486`) `[verified-by-code]`. So the row *arrives* on the Go GC
heap and *lands* in PG-managed memory — two allocators back-to-back. The code is
visibly careful at the seam: `ValToDatum`/`valToBuffer` allocate C strings with
`C.CString` and immediately `C.free` them "to avoid memory leak … this is a hot
path" (`helpers.go:157-161,204-209`) `[verified-by-code]`, because a `C.CString`
is malloc'd outside any MemoryContext and PG's context reset will never reclaim it.

### 2. A cgo handle table, because a Go pointer cannot live in `node->fdw_state`

The per-scan execution state is a Go struct (`ExecState`, holding a Go
`hub.Iterator` interface, `exec.go:29-34`). cgo forbids storing a Go pointer in C
memory across calls (the GC may move or collect it), so `fdw_state` cannot hold
the Go object directly. Instead `SaveExecState` inserts the state into a global
`map[uint64]*ExecState` under a `sync.RWMutex`, mints an integer token, and stores
only that token in a `malloc`'d C `GoFdwExecutionState{ uint tok; }`
(`exec.go:36-51`) `[verified-by-code]`; `GetExecState`/`ClearExecState` look the
Go object back up by token and `free` the C cell (`exec.go:53-75`). This is the
canonical `runtime/cgo.Handle` pattern, hand-rolled — the divergence from a C
FDW that would just `palloc` a state struct and stash the pointer in `fdw_state`.

### 3. Error handling: Go `panic`/`recover` on one side, `ereport(ERROR)` longjmp on the other, bridged at every seam

PG signals errors by `ereport(ERROR)` which `longjmp`s up the C stack — and a
`longjmp` **over live Go stack frames** would corrupt the Go runtime, just as a Go
`panic` unwinding *into* C is undefined. steampipe bridges both directions
explicitly. Go→PG: `FdwError(err)` converts a Go `error` into
`C.fdw_errorReport(C.ERROR, C.ERRCODE_FDW_ERROR, cmsg)` → `ereport`
(`errors.go:11-15`, helper at `fdw/fdw_helpers.h:41`) `[verified-by-code]`. To keep
Go panics from ever reaching the C boundary, **every** `//export` callback opens
with a `defer func(){ if r := recover(); … FdwError(fmt.Errorf("%v", r)) }()`
(`fdw.go:228-234,281-286,305-310,323-328,420-425,494-499,510-515,543-548,594-599`)
`[verified-by-code]` — the panic is caught in Go and re-raised as a PG error at the
boundary rather than being allowed to unwind through cgo. `goFdwBeginForeignScan`
even installs a *double* recover (outer + inner) for defense-in-depth against a
panic during early init (`fdw.go:303-328`) `[from-comment]`. Note the asymmetry:
`FdwError` itself calls `ereport(ERROR)` which `longjmp`s — so the two
abort-path callbacks that must *not* re-raise (`goFdwAbortCallback`,
`goFdwShutdown`) deliberately recover **without** calling `FdwError` ("DO NOT call
FdwError or we will recurse", `fdw.go:532-534,690-692`) `[from-comment]`.

### 4. Query cancellation has to be polled across the cgo boundary

PG's `statement_timeout` / cancel sets `QueryCancelPending`, normally noticed by
`CHECK_FOR_INTERRUPTS()` in C. But while control is down inside a Go goroutine
blocked on a plugin gRPC stream, no C interrupt check runs. The fix is a polling
bridge: `init()` installs `hub.SetQueryCancelChecker(func() bool { return
C.fdw_query_cancel_pending() != 0 })` (`fdw.go:76-78`), and the C inline reads the
`volatile sig_atomic_t` flags `QueryCancelPending || ProcDiePending`
(`fdw/fdw_helpers.h:32-34`) `[verified-by-code]` — a Go goroutine polling PG's
signal flags to abort a hung API call (motivated by issue #671, `fdw.go:73-75`)
`[from-comment]`.

### 5. Planning + qual/sort/limit pushdown is split C↔Go

Cost estimation lands in `baserel->rows`/`width` from the plugin via
`goFdwGetRelSize` (`fdw.go:152-224`, injected at `fdw/fdw.c:341`). Path keys for
sort pushdown are computed by asking the plugin which columns it can sort on
(`goFdwGetPathKeys` → `hub.GetPathKeys`, `fdw.go:226-277`) and matched against the
query's sort groups; `goFdwCanSort` walks the deparsed sort groups and stops at the
first column the plugin can't satisfy (`fdw.go:100-138`) `[verified-by-code]`.
LIMIT+OFFSET is deparsed in C (`deparseLimit`, refusing pushdown under GROUP BY /
DISTINCT / aggregates / multi-rel, `fdw/fdw.c:350-388`) but only *applied* if all
sort fields could be pushed down (`fdw.go:376-381`) `[verified-by-code]`. Quals are
turned into plugin filters by `restrictionsToQuals` at `BeginForeignScan`
(`fdw.go:361`, in `quals.go`) `[verified-by-code]`. The plan state crosses the
plan→exec boundary by being **serialized into a PG `List` of `Const` nodes**
(`serializePlanState`/`initializeExecState`, `fdw/fdw.c:517-569`) rather than kept
as a Go object — because the executor may run in a different context than the
planner.

## Notable design decisions

- **`-buildmode=c-archive` with `netgo`.** The whole extension is a Go static
  archive linked into the backend; `netgo` forces Go's pure-Go DNS resolver "since
  we are not binding to lresolv, DNS resolution may have some subtle differences
  from system DNS" (`fdw/Makefile:38-55`) `[from-comment]` — a real consequence of
  running Go's net stack inside PG rather than glibc's.
- **`main()` and a no-op `goInit` export are required.** `func main() {}` exists
  only because c-archive demands it (`fdw.go:706-707`), and `//export goInit`
  is an empty function that forces module loading / the Go `init()` to run
  (`fdw.go:39-42`) `[verified-by-code]`.
- **Env vars are hand-copied C→Go.** "env vars do not all get copied into the Go
  env vars so explicitly copy them" — `SetEnvVars` walks the C `environ` array and
  `os.Setenv`s each (`fdw.go:50`, `helpers.go:41-54`) `[from-comment]` — a
  fork-model quirk: the Go runtime doesn't see everything the postmaster set.
- **A signal-16 handler is installed to paper over a Go/PG stack clash.** `_PG_init`
  `sigaction`s SIGURG (16) with `SA_ONSTACK` and swallows it, because "certain
  postgres errors … cause a crash as the signal handler is not set up correctly
  for Go (SA_ONSTACK is not set)" (`fdw/fdw.c:43-67`) `[from-comment]` — Go's
  runtime uses SIGURG for async preemption and the two signal regimes collide.
- **Abort/shutdown wired through PG lifecycle hooks, not Go.** Transaction abort
  (`RegisterXactCallback`) and process exit (`on_proc_exit`) are the C anchors that
  reach into Go to tear down plugin connections (`fdw/fdw.c:70-97`)
  `[verified-by-code]` — the plugin hub's lifecycle is pinned to PG's, not Go's GC.
- **INSERT is only for "command"/settings tables.** `goFdwExecForeignInsert` returns
  `nil` for normal tables and only handles inserts into internal command/settings
  schemas (cache control, per-table settings) (`fdw.go:592-683`)
  `[verified-by-code]` — this is a read-oriented, API-as-table FDW, not a writable one.
- **OpenTelemetry trace context threaded from SQL into the plugin.** `fdw/fdw.c`
  extracts `traceparent`/`tracestate` from session GUCs or SQLcommenter query
  comments (`fdw/fdw.c:107-260`) and Go forwards it to the plugin in scan options
  (`fdw.go:183-205,334-347`) `[verified-by-code]` — distributed tracing across the
  PG→plugin gRPC hop.

## Links into corpus

- `[[parquet_s3_fdw]]` — the closest structural sibling: a non-C FDW behind a C
  shim, with the same "foreign language ⟷ C exception firewall" problem.
  parquet_s3_fdw's is C++ `try/catch`→`elog`; steampipe's is Go `recover`→`FdwError`.
  Both hand-roll the bridge at every callback seam.
- `[[wrappers]]` — the Rust-trait FDW framework; the other "FDW in a non-C
  language" answer. wrappers abstracts the `FdwRoutine` behind a Rust trait via
  pgrx; steampipe exposes raw Go `//export` functions as the vtable and reaches an
  *external gRPC plugin* rather than in-process Rust.
- `[[pg_duckdb]]` / `[[cstore_fdw]]` — analytics/columnar FDW cousins; contrast the
  *embedded engine* posture (DuckDB / columnar storage in-process) with steampipe's
  *external API* posture (no engine, no storage — every scan is a live gRPC call).
- `[[sqlite_fdw]]` / `[[tds_fdw]]` — conformant single-source C FDWs; the C
  baseline steampipe diverges from (their handler, state, and error paths are all C).
- `[[foreign]]` — the FDW subsystem doc: the `FdwRoutine` scan/modify lifecycle and
  plan-time `baserel->rows`/`width` costing that steampipe fills from the plugin.
- `[[fdw-routine-callbacks]]` / `[[fdw-iterate-scan]]` — the callback vtable and the
  one-tuple-per-`IterateForeignScan` contract, here satisfied by a Go function.
- `[[fmgr]]` — `PG_FUNCTION_INFO_V1(fdw_handler)` + `makeNode(FdwRoutine)`.
- `[[memory-contexts]]` — the palloc/StringInfo side of the two-allocator seam and
  the `C.CString`+`C.free` discipline for memory outside any context.
- `[[error-handling]]` — `ereport(ERROR)` longjmp vs Go `panic`/`recover`; the
  `ERRCODE_FDW_ERROR` bridge and the "don't recurse in abort paths" rule.

> Corpus gap: no idiom doc for the **cgo/foreign-runtime ⟷ C FDW boundary** — the
> `//export` callbacks-as-vtable pattern, the cgo *handle table* substituting for a
> Go pointer in `fdw_state`, the `recover()`→`ereport` firewall at every seam, and
> the poll-PG-cancel-flags-from-a-goroutine bridge. Shared in spirit with
> `[[parquet_s3_fdw]]` (C++) and `[[wrappers]]`/`[[pgrx]]` (Rust); worth an
> `idioms/foreign-runtime-fdw-boundary.md`.

## Sources

All fetched 2026-07-03 (branch `develop`) via
`https://raw.githubusercontent.com/turbot/steampipe-postgres-fdw/develop/<path>`.
GitHub API tree endpoint + HTML tree view were not used (403 from this session);
paths were probed directly.

- `README.md` → HTTP 200 (103 lines; scope, build modes, install).
- `Makefile` → HTTP 200 (155 lines; c-archive build, standalone/render/generator,
  `prebuild.go` C-include templating).
- `fdw/Makefile` → HTTP 200 (84 lines; `MODULE_big`, `OBJS`, `go build
  -buildmode=c-archive`, `netgo`, install/standalone).
- `prebuild.tmpl` → HTTP 200 (13 lines; the templated cgo CFLAGS + PG includes).
- `go.mod` → HTTP 200 (232 lines; module `.../v2`, go 1.26.1, steampipe-plugin-sdk/v6,
  gRPC/protobuf, OpenTelemetry).
- `fdw.go` → HTTP 200 (707 lines; **all `//export goFdw*` callbacks**, `init()`/hub
  creation, per-callback `recover`, query-cancel bridge, import, command-insert).
- `errors.go` → HTTP 200 (23 lines; `FdwError` → `fdw_errorReport(ERROR)`).
- `exec.go` → HTTP 200 (75 lines; the cgo handle table for `fdw_state`).
- `helpers.go` → HTTP 200 (248 lines; `ValToDatum`, `SetEnvVars`, relation/tupdesc
  builders, C↔Go string/datum conversion).
- `fdw/fdw.c` → HTTP 200 (683 lines; `_PG_init`, `PG_MODULE_MAGIC`, C planner
  wrappers, LIMIT deparse, plan-state serialize, signal-16 hack, trace context).
- `fdw/fdw_handlers.h` → HTTP 200 (46 lines; `PG_FUNCTION_INFO_V1(fdw_handler)`,
  `makeNode(FdwRoutine)` assembly wiring C + Go callbacks).
- `fdw/fdw_helpers.h` → HTTP 200 (122 lines; inline PG-helper shims,
  `fdw_query_cancel_pending`, `fdw_saveTuple`, `fdw_errorReport`).
- `fdw/common.h` → HTTP 200 (138 lines; `FdwPlanState`/`FdwExecState`/`ConversionInfo`
  struct defs).
- `fdw/logging.c` → HTTP 200 (67 lines; `NodeTag`→string for logging).
- `fdw/query.c` → HTTP 200 (718 lines; qual/path deparse; skimmed, not deep-cited).
- `fdw/datum.c` → HTTP 200 (56 lines; datum→Go conversion; skimmed).
- `quals.go` → HTTP 200 (600 lines; `restrictionsToQuals`; skimmed).
- `schema.go` → HTTP 200 (79 lines; `SchemaToSql`; skimmed).

> Sources gap — 404s (manifest/probe misses): `fdw/fdw.go`, `fdw/init.go` (the
> manifest paths — Go lives at repo root, not `fdw/`); `fdw/steampipe_postgres_fdw.h`
> and the generated `steampipe_postgres_fdw.h` (cgo-generated at build time, not
> committed); `init.go`/`logging.go`/`hub.go`/`datum.go` at root (no such files —
> `init()` is in `fdw.go`, logging is C). The `hub/`, `types/`, `version/` Go
> subpackages (gRPC plugin client, the actual API-scan engine) were referenced by
> import path (`fdw.go:30-32`) but not fetched; iterator/gRPC-stream claims are
> `[inferred]`.
