# pg_tracing — ideology / divergence notes

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `DataDog/pg_tracing` @ branch `main`. All `file:line` cites below point
> into that repo (not `source/`), since this doc characterizes an *external*
> extension's divergence from core idioms. Cites verified against the files
> fetched on 2026-06-20 (see Sources footer).

pg_tracing turns every PostgreSQL backend into a distributed-tracing emitter: it
generates OpenTelemetry-style spans (start/end/parent) for sampled queries and
makes them readable through SRFs. The control-file comment is just
`'Distributed Tracing for PostgreSQL'` (`pg_tracing.control:2`) `[verified-by-code]`.
**Headline divergence:** it reconstructs a *span tree* by smuggling a W3C
`traceparent` in through a SQL comment / GUC / parallel-worker shmem slot (none
of which is a core trace mechanism), then **monkey-patches every PlanState's
`ExecProcNode` function pointer** to timestamp the first call of each executor
node so it can rebuild the plan into spans after the fact.

## Domain & purpose

pg_tracing answers: *how do you produce a parent-child timing tree for a single
SQL statement — Planner span, ExecutorRun span, one span per plan node, plus
nested-query / trigger / parallel-worker / commit spans — and tie it to a trace
that started in an upstream service?* (`pg_tracing.c:23-43` describes the span
taxonomy) `[from-comment]`. It is the observability sibling of auto_explain and
pg_stat_statements, but where those emit text or aggregate counters, pg_tracing
emits W3C-trace-context-linked spans buffered in shared memory and optionally
pushed to an OTLP collector. The README frames the two propagation mechanisms
(SQLCommenter comment + `pg_tracing.trace_context` GUC) as the core contract
(`README.md:13-17`) `[from-README]`.

## How it hooks into PG

pg_tracing **requires** `shared_preload_libraries`: `_PG_init` returns early if
`!process_shared_preload_libraries_in_progress` (`pg_tracing.c:305-306`)
`[verified-by-code]`, and the SRFs `ereport(ERROR …"must be loaded via
shared_preload_libraries")` if shmem is absent (`pg_tracing_sql_functions.c:325-328`)
`[verified-by-code]`.

- **Nine hooks chained**, prior pointer saved each time
  (`pg_tracing.c:521-544`) `[verified-by-code]`:
  `shmem_request_hook`, `shmem_startup_hook`, `post_parse_analyze_hook`,
  `planner_hook`, `ExecutorStart_hook`, `ExecutorRun_hook`,
  `ExecutorFinish_hook`, `ExecutorEnd_hook`, `ProcessUtility_hook`. The whole
  hook chain exists because a top span can be *started* at any of post-parse /
  planner / ExecutorStart depending on whether the statement skipped parsing
  (cached plan) or planning (`pg_tracing.c:1671-1673`, `1758-1761`) `[from-comment]`.
- **Xact callback** (not a hook): `RegisterXactCallback(pg_tracing_xact_callback)`
  (`pg_tracing.c:546`) drives the `TransactionCommit` span — created on
  `XACT_EVENT_PRE_COMMIT` only if a xid was assigned, ended on
  `XACT_EVENT_COMMIT`/`ABORT` (`pg_tracing.c:2301-2343`) `[verified-by-code]`.
- **Shmem**: `shmem_request_hook` calls `RequestAddinShmemSpace(pg_tracing_memsize())`
  and `RequestNamedLWLockTranche("pg_tracing", 1)` (`pg_tracing.c:646-654`);
  `shmem_startup` carves three `ShmemInitStruct` regions — shared state, the
  `Span` array, and a raw string arena — plus a parallel-workers slot array
  (`pg_tracing.c:606-614`, `pg_tracing_parallel.c:32-34`) `[verified-by-code]`.
  Memsize is `sizeof(pgTracingSharedState) + sizeof(pgTracingSpans) +
  max_span*sizeof(Span) + max_parallel_workers*sizeof(pgTracingParallelContext) +
  shared_str_size` (`pg_tracing.c:558-574`) `[verified-by-code]`.
- **GUCs**: 14 `DefineCustom*Variable` calls (`pg_tracing.c:308-509`)
  `[verified-by-code]`, then `MarkGUCPrefixReserved("pg_tracing")`
  (`pg_tracing.c:518`). Contexts are deliberate: `max_span`/`shared_str_size`
  are `PGC_POSTMASTER` (shmem sizing), the otel-export GUCs are `PGC_SIGHUP`,
  the sampling/track GUCs are `PGC_USERSET` (`pg_tracing.c:315,341,459,483,505`)
  `[verified-by-code]`. `pg_tracing.trace_context` is itself a string GUC with
  check/assign hooks that parse a traceparent (`pg_tracing.c:500-509`,
  `733-782`) `[verified-by-code]`.
- **`EnableQueryId()`** is called in `_PG_init` (`pg_tracing.c:513`) so jumble
  state and query ids are always available `[verified-by-code]`.
- **Background worker**: if `otel_endpoint` is set, `_PG_init` starts a
  `pg_tracing_otel_exporter` bgworker (`pg_tracing.c:548-552`); it is registered
  statically via `RegisterBackgroundWorker` during preload, else dynamically via
  `RegisterDynamicBackgroundWorker` + `WaitForBackgroundWorkerStartup`
  (`pg_tracing_otel.c:228-260`) `[verified-by-code]`. The worker links **libcurl**
  and POSTs OTLP/JSON (`pg_tracing_otel.c:20,100-118`) `[verified-by-code]`.
- **Output**: SQL SRFs `pg_tracing_spans(consume bool)`, `pg_tracing_json_spans`,
  `pg_tracing_info`, `pg_tracing_reset` (`pg_tracing_sql_functions.c:20-23`)
  read the shmem buffer under the tranche lock `[verified-by-code]`.

## Where it diverges from core idioms — THE headline

### 1. It rewrites executor function pointers to timestamp node entry

The genuinely un-Postgres move: to learn when each plan node first runs,
pg_tracing **walks the live PlanState tree and replaces every node's
`ExecProcNode` method pointer** with its own `ExecProcNodeFirstPgTracing`
(`pg_tracing_planstate.c:236-262`) `[verified-by-code]`. On the first call that
shim records `GetCurrentTimestamp()` into a `traced_planstates` array, then
**restores the original pointer and tail-calls it** so the swap is one-shot per
node (`pg_tracing_planstate.c:226-229`) `[verified-by-code]`. This mirrors
PG core's own `ExecProcNodeFirst` wrapper trick but is applied from *outside* the
executor by an extension. The override is only installed when `instrument` is
set on the node (`pg_tracing_planstate.c:238-240`) and only when planstate spans
are enabled (`pg_tracing.c:1916-1917`) `[verified-by-code]`. Gather /
GatherMerge nodes are special-cased to use the parallel-workers parent id rather
than a fresh random span id (`pg_tracing_planstate.c:203-217`) `[verified-by-code]`.

### 2. Trace context smuggled through a SQL comment, a GUC, or shmem — never a core channel

Core PG has no notion of a propagated trace id. pg_tracing invents three
side-channels:
- **SQLCommenter** comment at the *start or end* of the query text. It
  hand-parses by character offset — checks the query is `>= 72` chars, that the
  first two bytes are `/*` (or the last two before an optional `;` are `*/`),
  `strstr`s for `traceparent='`, and reads fixed byte positions
  (`-` at index 2/35/52, `'` at 55) to extract a 128-bit trace id, 64-bit parent
  id, and sampled flag (`pg_tracing_query_process.c:47-194`) `[verified-by-code]`.
  This is raw offset arithmetic on the source text, *not* the parser.
- **`pg_tracing.trace_context` GUC**, parsed in the GUC check hook into a
  `guc_malloc`'d `Traceparent` (`pg_tracing.c:734-765`) `[verified-by-code]`. Its
  assign hook calls `cleanup_tracing()` so the `SET` itself isn't traced
  (`pg_tracing.c:771-782`) `[verified-by-code]`.
- **Parallel-worker shmem slots**: a leader stuffs its traceparent into a
  spinlock-protected slot keyed by `MyProcNumber`; a worker matches on
  `ParallelLeaderProcNumber` to fetch it (`pg_tracing_parallel.c:46-107`)
  `[verified-by-code]`. This is bespoke propagation because PG's normal parallel
  DSM key/TOC machinery isn't used by the extension.

### 3. Sampling decided once per statement, with a static-variable dedup guard

`is_query_sampled` combines the upstream `sampled` flag (gated by
`caller_sample_rate`) with a local `sample_rate` using a PRNG
(`pg_tracing.c:1155-1185`) `[verified-by-code]`. Because a statement can pass
through `extract_trace_context` up to three times (post-parse, planner,
executor), it guards re-sampling with a **function-static**
`last_statement_check_for_sampling` compared against
`GetCurrentStatementStartTimestamp()` (`pg_tracing.c:1196,1244-1249`)
`[verified-by-code]`. It also ships its own PRNG (`src/pg_tracing_rng.c`,
vendored `src/pg_prng.c`) rather than relying solely on core
(`generate_rnd_double`/`generate_rnd_uint64` used at `pg_tracing.c:1129-1130,1177`)
`[verified-by-code]`.

### 4. A dedicated long-lived MemoryContext under TopMemoryContext, deliberately *not* per-query

pg_tracing creates `pg_tracing_mem_ctx` as an AllocSet child of
**TopMemoryContext** at shmem startup (`pg_tracing.c:617-619`)
`[verified-by-code]`, explicitly because spans must outlive the query's own
contexts: the comment notes that `vacuum analyze` ends and starts its own
transactions while spans are still active, so it "can't rely on memory context
like TopTransactionContext" (`pg_tracing.c:162-169`) `[verified-by-code]`. Spans
accumulate in a `current_trace_spans` buffer that `repalloc`s by doubling
(`pg_tracing.c:957-971`) and is reset via `MemoryContextReset` at end-of-trace
(`pg_tracing.c:1293-1313`) `[verified-by-code]`. This is a leak-scoping strategy
core extensions rarely need because they don't hold state across nested
transactions.

### 5. Span strings live in a raw byte arena indexed by offset, not as palloc'd cstrings

Rather than store operation names / parameters / deparse info as pointers,
pg_tracing copies them into a single `shared_str` arena (`ShmemInitStruct`,
`pg_tracing.c:612-614`) via `append_str_to_shared_str`, which bumps a shared
`extent` and returns the *offset* (`pg_tracing.c:803-820`) `[verified-by-code]`.
Each `Span` carries integer offsets (`operation_name_offset`,
`parameter_offset`, `deparse_info_offset`); at `end_tracing` these are rebased
onto the shared arena (`pg_tracing.c:1336-1354`) and the SRF reads them back as
`shared_str + offset` (`pg_tracing_sql_functions.c:153,235`) `[verified-by-code]`.
When the arena fills it bumps a `dropped_str` stat and returns `-1`
(`pg_tracing.c:808-813`) `[verified-by-code]` — a hand-rolled bump allocator in
shmem, distinct from PG's DSA.

### 6. It re-implements pg_stat_statements' constant-jumbling to normalize query text

To produce `SELECT $1` operation names and capture parameters, it lifts
`fill_in_constant_lengths` and `normalise_query_parameters` — driving the core
flex scanner (`scanner_init`/`core_yylex`) over the query and replacing constants
at `JumbleState->clocations` with `$n` (`pg_tracing_query_process.c:240-458`)
`[verified-by-code]`. This is near-verbatim borrowed pg_stat_statements code
(the comment block at `:213-239` is the upstream one) `[from-comment]`, an idiom
duplication rather than a shared API.

### 7. It forces `INSTRUMENT_ALL` and back-fills `totaltime` instrumentation

In `ExecutorStart` it sets `queryDesc->instrument_options = INSTRUMENT_ALL` when
planstate spans are wanted and we're not in a cursor declaration
(`pg_tracing.c:1826-1827`), and if `totaltime` is still NULL it `InstrAlloc`s it
in the per-query context (`pg_tracing.c:1835-1842`) `[verified-by-code]`. So the
extension changes *what the executor measures*, much like auto_explain, then
harvests `bufusage`/`walusage`/JIT/rows off the QueryDesc
(`pg_tracing.c:1063-1080`) `[verified-by-code]`.

## Notable design decisions (with cites)

- **Buffer-full policy is a GUC**: `keep_on_full` (drop the new trace) vs
  `drop_on_full` (wipe the buffer); checked early under a shared lock that
  escalates to exclusive only to truncate (`pg_tracing.c:73-77,997-1035`)
  `[verified-by-code]`.
- **Lazy set-returning functions are excluded** to avoid span explosion: a
  `T_FunctionScan` with `EXEC_FLAG_SKIP_TRIGGERS` is detected and skipped
  (`pg_tracing.c:1791-1800`) `[verified-by-code]`.
- **Cursors disable planstate spans** because fetches fragment node execution
  across ExecutorRun calls (`pg_tracing.c:1818-1827`) `[from-comment]`.
- **Error path pre-allocates spans** so the `PG_CATCH` handler can record spans
  without allocating during a possible OOM, and disables deparse for the same
  reason (`pg_tracing.c:1920-1924`, `1393-1397`) `[verified-by-code]`.
- **Query-id filtering** via a `GUC_LIST_INPUT` string parsed into a
  `guc_malloc`'d `QueryIdFilter` in the check hook (`pg_tracing.c:441-450,659-719`)
  `[verified-by-code]`.
- **Trace id continuity across a transaction**: a generated trace id is reused
  for later statements in the same `lxid`, and an upstream-provided id can
  retroactively overwrite a generated one on existing spans
  (`pg_tracing.c:1100-1148,1489-1505`) `[verified-by-code]`.
- **otel worker routes libcurl's allocator through MemoryContexts** via curl
  malloc/free/realloc callbacks (`pg_tracing_otel.c:49-84`) `[verified-by-code]`.

## Links into corpus

- [[process-utility-hook-chain]] — pg_tracing is one more `ProcessUtility_hook`
  link; the chain-saving idiom is shared.
- [[background-worker-startup]] — the otel exporter's static/dynamic bgworker
  registration follows this idiom (`RegisterBackgroundWorker` vs
  `RegisterDynamicBackgroundWorker` + `WaitForBackgroundWorkerStartup`).
- [[guc-variables]] — the 14 `DefineCustom*Variable` calls + check/assign hooks +
  `MarkGUCPrefixReserved`.
- [[memory-contexts]] — the deliberate TopMemoryContext-child arena vs per-query
  contexts.
- [[locking-overview]] — single named LWLock tranche guarding the span buffer,
  shared/exclusive escalation; spinlock on the parallel slot array.
- [[parallel-state-propagation]] / [[parallel-context-and-dsm]] — contrast: PG's
  DSM/TOC parallel-state propagation vs pg_tracing's bespoke shmem-slot
  traceparent handoff.
- [[expression-evaluator-flow]] / executor [[executor]] — the `ExecProcNode`
  pointer-swap is the load-bearing divergence; core's own `ExecProcNodeFirst`
  is the model it imitates.
- [[fmgr]] / [[spi]] — SRF output via `InitMaterializedSRF` + `tuplestore_putvalues`.
- [[error-handling]] — `PG_TRY`/`PG_CATCH`/`PG_FINALLY` around each executor
  hook to flush spans on error.
- Sibling ideologies: [[pgaudit]] (closest sibling — also a hook-chain observer
  layered on ExecutorStart/ProcessUtility, but logs text instead of building a
  span tree), [[pg_net]] / [[pgsql-http]] (bgworker + shmem + libcurl HTTP
  egress, same shape as the otel exporter).
- Subsystem refs: `subsystems/contrib-pg_stat_statements.md` (the jumbling /
  constant-normalization code pg_tracing copies), `subsystems/contrib-auto_explain.md`
  (the closest in-tree analogue: hooks + `INSTRUMENT_ALL` forcing).

> Corpus gap: there is no idiom doc for the **`ExecProcNode` per-node
> pointer-swap instrumentation pattern** (core's `ExecProcNodeFirst` plus the
> extension-side override). Both auto_explain-style timing and pg_tracing rely
> on it; worth a dedicated `idioms/execprocnode-instrumentation.md`.
> Corpus gap: no idiom doc for the **offset-indexed shmem string arena / bump
> allocator** pattern (pg_stat_statements' external query-text file is a cousin).

## Sources

All fetched 2026-06-20.

- Tree listing: `https://api.github.com/repos/DataDog/pg_tracing/git/trees/main?recursive=1` — 200
- `https://raw.githubusercontent.com/DataDog/pg_tracing/main/README.md` — 200
- `https://raw.githubusercontent.com/DataDog/pg_tracing/main/pg_tracing.control` — 200
- `https://raw.githubusercontent.com/DataDog/pg_tracing/main/src/pg_tracing.c` — 200 (2352 lines)
- `https://raw.githubusercontent.com/DataDog/pg_tracing/main/src/pg_tracing.h` — 200 (fetched; struct/enum reference, not deeply cited here)
- `https://raw.githubusercontent.com/DataDog/pg_tracing/main/src/pg_tracing_query_process.c` — 200
- `https://raw.githubusercontent.com/DataDog/pg_tracing/main/src/pg_tracing_planstate.c` — 200
- `https://raw.githubusercontent.com/DataDog/pg_tracing/main/src/pg_tracing_sql_functions.c` — 200
- `https://raw.githubusercontent.com/DataDog/pg_tracing/main/src/pg_tracing_active_spans.c` — 200 (fetched; not directly cited)
- `https://raw.githubusercontent.com/DataDog/pg_tracing/main/src/pg_tracing_otel.c` — 200
- `https://raw.githubusercontent.com/DataDog/pg_tracing/main/src/pg_tracing_parallel.c` — 200
- `https://raw.githubusercontent.com/DataDog/pg_tracing/main/src/pg_tracing--0.1.0.sql` — 200 (status-checked only, not fetched into analysis)

Skimmed-but-not-fetched: `src/pg_tracing_span.c`, `src/pg_tracing_json.c`,
`src/pg_tracing_explain.c`, `src/pg_tracing_operation_hash.c`,
`src/pg_tracing_rng.c`, `src/pg_tracing_strinfo.c`, `src/version_compat.c`
(referenced via callers in the cited files; behavior inferred from call sites).
No 404s encountered — all guessed paths resolved against the tree listing.
