# plproxy — a procedural language whose function bodies contain no code, only a `CLUSTER`/`RUN ON`/`TARGET`/`SELECT` routing DSL that the call handler compiles into a pooled-libpq remote call to horizontally-partitioned databases

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `plproxy/plproxy` @ branch `master`. All `file:line` cites below point
> into that repo (not `source/`), since this doc characterizes an *external*
> extension's divergence from core PG idioms. Cites verified against the files
> fetched on 2026-07-16 (see Sources footer).
>
> **Manifest correction:** the task brief asserted the repo ships NO README.
> That is stale — `README.md` (HTTP 200, 51 lines) exists at repo root and is a
> short feature summary. There is no `README` / `README.rst`. Prose here still
> leans on `[from-comment]` and `[verified-by-code]` because the README is thin;
> the handful of `[from-README]` tags are the few claims it directly supports.

PL/Proxy weaponizes the `LANGUAGE plproxy` call-handler slot — the same
`pg_language` machinery PL/pgSQL, PL/Java and PL/v8 use to run *code* — to build
a database-sharding / RPC router. A PL/Proxy function body executes **zero
computation in the local backend**. It is a four-statement DSL — pick a target
database (`CLUSTER <name>` or `CONNECT <connstr>`), pick an execution mode
(`RUN ON ALL` / `RUN ON ANY` / `RUN ON <hashfunc(args)>` / `RUN ON <N>`), and
optionally override the remote query (`SELECT ...`) (`README.md:9-19`)
`[from-README]`. The handler parses that DSL into a compiled plan, hashes the
`RUN ON` arguments to select one or more partitions, opens (pooled, async) libpq
connections to the remote nodes, runs a query there, and marshals the remote
result rows back as *this* function's return tuples. The control comment names
the whole game outright: `'Database partitioning implemented as procedural
language'` (`plproxy.control:2`) `[verified-by-code]`. This is horizontal
sharding / scatter-gather RPC, shipped years before FDW-based or Citus-based
sharding existed. **Headline divergence:** every other PL in this corpus embeds
a runtime and runs user code in-process; PL/Proxy embeds libpq and runs user
code *on other servers*.

## Domain & purpose

PL/Proxy answers: *how do you transparently split a table across N physical
PostgreSQL databases and call a stored function on the right shard(s) without
the caller knowing where the data lives?* The canonical body is three tokens:

```sql
CREATE FUNCTION get_user_settings(i_username text) RETURNS SETOF user_settings AS $$
    CLUSTER 'userdb'; RUN ON hashtext(i_username);
$$ LANGUAGE plproxy;
```

The function with the *same name and signature* runs on the remote shard picked
by `hashtext(i_username)`, and its `user_settings` rows flow back
(`README.md:22-29`) `[from-README]`. The extension is `superuser = true`,
non-relocatable, default version 2.12.0 (`plproxy.control:3-7`)
`[verified-by-code]`. It requires PostgreSQL 9.3+ (`src/plproxy.h:62-64`)
`[verified-by-code]`. Origin/authorship: idea + language design by Hannu Krosing
& Asko Oja, implementation by Sven Suursoho, long-time maintainer Marko Kreen
(`AUTHORS:2-11`) `[from-comment]`.

## How it hooks into PG

PL/Proxy implements the standard PL call-handler protocol; its "language
runtime" is a fleet of remote databases reached over libpq.

- **Module magic + two entry points**, both `PG_FUNCTION_INFO_V1`:
  `plproxy_call_handler` and `plproxy_validator` (`src/main.c:52-55`)
  `[verified-by-code]`. `libpq-fe.h` is the *first* include of the header, ahead
  of `postgres.h` — a tell that this PL links the client library into the
  backend (`src/plproxy.h:26-28`) `[verified-by-code]`.
- **The call handler** (`plproxy_call_handler`, `src/main.c:239-268`)
  `[verified-by-code]`: rejects trigger use outright (`CALLED_AS_TRIGGER` →
  `elog(ERROR, "PL/Proxy procedures can't be used as triggers")`,
  `src/main.c:245-246`); dispatches set-returning functions to a
  ValuePerCall SRF path (`handle_ret_set`, `src/main.c:206-231`) and scalar
  functions to a single `compile_and_execute` (`src/main.c:258`). For a
  non-`SETOF` function it insists the remote query returned *exactly one row*,
  raising `ERRCODE_NO_DATA_FOUND` or `ERRCODE_TOO_MANY_ROWS` otherwise
  (`src/main.c:259-263`) `[verified-by-code]`.
- **The validator** (`plproxy_validator`, `src/main.c:274-292`)
  `[verified-by-code]`: gates on `CheckFunctionValidatorAccess`
  (`src/main.c:280`), then calls `plproxy_compile(NULL, proc_tuple, true)` — it
  parses and type-checks the DSL body at `CREATE FUNCTION` time but cannot
  resolve the polymorphic return type without call info, so return-type checking
  is skipped in validate-only mode (`src/function.c:508-518`)
  `[verified-by-code]`.
- **Execution runs under SPI.** `compile_and_execute` wraps the whole thing in
  `SPI_connect()` / `SPI_finish()` (`src/main.c:163-198`) `[verified-by-code]` —
  SPI is used for *local* helper queries (cluster resolution, hash evaluation),
  not for the remote call. Lazy startup init (function cache, cluster cache,
  syscache callbacks) is run inside SPI on first call (`src/main.c:125-136`,
  `176`) `[verified-by-code]`.
- **Per-function compiled-state cache keyed on OID + a pg_proc row stamp.** The
  function cache is an `HTAB` keyed on `Oid` alone — "As PL/Proxy does not do
  trigger functions, its enough to index just on OID" (`src/function.c:37-46`,
  `152-169`) `[from-comment]` `[verified-by-code]`. Each entry carries a
  `RowStamp` set from the proc tuple (`plproxy_set_stamp`, `src/function.c:255`)
  and validated on every lookup (`plproxy_check_stamp`, `src/function.c:565`); a
  stale entry is deleted and recompiled (`src/function.c:562-591`)
  `[verified-by-code]`. This is the same fn_oid/fn_xmin invalidation shape the
  core PL compile caches use, done by hand.
- **Each function gets its own `MemoryContext`** carved off `TopMemoryContext`
  (`fn_new`, `src/function.c:239-263`) `[verified-by-code]`, freed as a unit by
  `MemoryContextDelete` on recompile/eviction, after explicitly
  `SPI_freeplan`-ing the cached local plans (`fn_delete`,
  `src/function.c:271-284`) `[verified-by-code]`.

## Where it diverges from core idioms

A normal PL (plpgsql, plv8, pljava) runs the function body's code inside the
backend process. PL/Proxy runs *no* body code locally: it compiles a routing
directive and dispatches an RPC. The divergences worth naming:

**1. The body is a mini-DSL, not a program.** `fn_parse` detoasts
`pg_proc.prosrc` and hands it to a bison/flex parser (`plproxy_run_parser`),
which fills structured fields on the `ProxyFunction` — `run_type`,
`cluster_name`, `hash_sql`, `connect_str`, `target_name` — rather than producing
any executable (`src/function.c:321-342`, `src/plproxy.h:344-360`)
`[verified-by-code]`. `run_type` is a 4-value enum: `R_HASH`, `R_ALL`, `R_ANY`,
`R_EXACT` (`src/plproxy.h:106-112`) `[verified-by-code]`. A sanity rule: PL/Proxy
functions **must be VOLATILE** (`src/function.c:502-503`), and `RUN ON ALL`
requires a set-returning function (`src/function.c:528-531`) `[verified-by-code]`.

**2. The "remote query" is synthesized from the function's own signature.** If
the body has no explicit `SELECT`, `plproxy_standard_query` builds
`select <cols>::<types> from <target>(<$1..$n>)` — i.e. it calls a same-named
function on the remote side, coercing each result column to the expected type
(`src/query.c:160-238`) `[verified-by-code]`. `TARGET <name>` overrides the
remote function name (`src/query.c:198`) `[verified-by-code]`. Argument
references in the DSL/query are rewritten to positional `$N::type` placeholders
via `plproxy_query_add_ident` / `add_ref` (`src/query.c:68-119`)
`[verified-by-code]`, matched to function args by name or `$N` index
(`plproxy_get_parameter_index`, `src/function.c:75-101`) `[verified-by-code]`.

**3. Partition selection is hash-modulo-over-a-power-of-two connection array.**
The cluster holds `part_count` (a power of 2) connections in `part_map`, plus a
`part_mask = part_count - 1` (`src/plproxy.h:204-206`, `src/cluster.c:392-393`)
`[verified-by-code]`. `tag_part` maps a hash to a partition index with a bitmask
`hash & part_mask` — or a true modulus `hash % part_count` when
`modular_mapping` is set (which relaxes the power-of-2 requirement)
(`src/execute.c:803-823`, `src/cluster.c:87-93`) `[verified-by-code]`. For
`R_HASH`, the hash function named in `RUN ON` is executed *locally via SPI*
(`hash_sql`), and its int2/int4/int8 result tags the target connection
(`tag_hash_partitions`, `src/execute.c:830-874`) `[verified-by-code]`. `R_ALL`
tags every partition, `R_ANY` picks a random one, `R_EXACT` a fixed number
(`tag_run_on_partitions`, `src/execute.c:903-931`) `[verified-by-code]`.

**4. Its own connection pool, keyed on connect-string and DB user.** Clusters
and their connections live in a dedicated long-lived context `cluster_mem` off
`TopMemoryContext` (`src/cluster.c:32-33`, `162-174`) `[verified-by-code]`.
Connections are deduplicated in an AA-tree keyed on connstr — a repeated connstr
reuses the existing `ProxyConnection` (`add_connection`, `src/cluster.c:237-266`)
`[verified-by-code]`. Each connection further keeps a per-user
`ProxyConnectionState` sub-tree (`userstate_tree`), so a physical libpq handle is
scoped to (connstr, DB user) (`src/plproxy.h:163-193`,
`plproxy_activate_connection`, `src/cluster.c:1248-1271`) `[verified-by-code]`.
libpq uses `malloc`, so handles are freed explicitly with `PQfinish`
(`plproxy_disconnect`, `src/execute.c:1152-1164`; noted in the context inventory
`src/main.c:39`) `[verified-by-code]` `[from-comment]`.

**5. A hand-rolled async libpq state machine driven by `poll()`.** PL/Proxy
`#error`s at compile time if `poll()` is unavailable (`src/execute.c:31-38`)
`[verified-by-code]`. Connections advance through a 7-state enum
(`C_NONE`, `C_CONNECT_WRITE`, `C_CONNECT_READ`, `C_READY`, `C_QUERY_WRITE`,
`C_QUERY_READ`, `C_DONE`; `src/plproxy.h:115-124`) `[verified-by-code]`.
`prepare_conn` starts a non-blocking connect with `PQconnectStart`
(`src/execute.c:300-352`); `handle_conn` pumps `PQconnectPoll` and, in the read
phase, `PQconsumeInput` + `PQisBusy` + `PQgetResult` (`src/execute.c:420-471`)
`[verified-by-code]`. Queries are sent with `PQsendQueryParams` and flushed with
`PQflush` (`send_query`/`flush_connection`, `src/execute.c:95-110`, `174-220`)
`[verified-by-code]`. The driver loop `remote_execute` fans the query out to all
tagged partitions, then spins on `poll_conns` — which builds a `pollfd` array
and `poll()`s with a 1s tick — until every connection reaches `C_DONE`, calling
`CHECK_FOR_INTERRUPTS()` each iteration (`src/execute.c:479-584`, `617-697`)
`[verified-by-code]`. This is genuinely parallel scatter-gather: all shards run
concurrently.

**6. Cancel propagation to remote shards.** `plproxy_exec` wraps execution in
`PG_TRY`/`PG_CATCH`; if the local statement is cancelled
(`geterrcode() == ERRCODE_QUERY_CANCELED`), it forwards `PQcancel` to every
in-flight partition via `PQgetCancel` and then drains them
(`remote_cancel` / `remote_wait_for_cancel`, `src/execute.c:699-797`,
`1166-1205`) `[verified-by-code]`. A vanilla PL has nothing analogous — there is
no remote work to cancel.

**7. Remote errors, notices and warnings are re-mapped into local ereports.**
`plproxy_remote_error` pulls every diagnostic field off the remote `PGresult`
(SQLSTATE, severity, primary/detail/hint, statement position, internal query,
context) and re-`ereport`s them locally, deliberately clamping a remote
FATAL/PANIC down to a local `ERROR` and choosing NOTICE vs WARNING from the
SQLSTATE class rather than the (possibly localized) severity string
(`src/main.c:84-117`) `[verified-by-code]`. A `PQsetNoticeReceiver` hook routes
async remote notices through the same path (`handle_notice`,
`src/execute.c:274-280`, `prepare_conn` `src/execute.c:351`)
`[verified-by-code]`. Its own errors go through `plproxy_error_with_state`, which
*also frees pending results* before throwing (`src/main.c:62-78`), with a
convenience macro defaulting to `ERRCODE_INTERNAL_ERROR` (`src/plproxy.h:385`)
`[verified-by-code]`.

**8. Result rows are re-assembled by column *name*, not position.** After the
remote query returns, `map_results` builds a `result_map` matching each expected
tuple attribute to a remote result column by name (fast 1:1 path, then an O(n²)
fallback for reordered columns), erroring on missing/extra fields
(`src/result.c:28-104`) `[verified-by-code]`. `walk_results` then iterates the
active connections and their rows as one logical result set — the scatter-gather
merge (`src/result.c:107-130`) `[verified-by-code]`. Rows are rebuilt into local
composites via `plproxy_recv_composite` or scalars via `plproxy_recv_type`,
using binary I/O when both sides are the same major.minor server version and the
types support send/recv (`return_composite`/`return_scalar`,
`src/result.c:133-201`; binary decision in `send_query`,
`src/execute.c:191-205`) `[verified-by-code]`. Conversion runs in the query
context so palloc'd Datums survive the return (`src/result.c:19-24`)
`[from-comment]`.

**9. Cluster config has two provenance modes — SQL/MED or "compat" schema
functions.** Modern clusters are defined as SQL/MED foreign servers under the
`plproxy` FDW; `plproxy_fdw_validator` validates server/user-mapping/FDW options,
extracting partition numbers from `p<N>` / `partition_<N>` option names and
enforcing the power-of-2 partition count (`src/cluster.c:81-82`, `443-605`)
`[verified-by-code]`. Legacy "compat" clusters are read from three SQL functions
— `plproxy.get_cluster_version($1)`, `plproxy.get_cluster_partitions($1)`,
`plproxy.get_cluster_config($1)` — prepared as SPI plans and re-run to fetch a
version serial, the connstr list, and the key/value config
(`src/cluster.c:59-65`, `177-214`, `936-954`) `[verified-by-code]`.
`refresh_cluster` picks the mode: if a foreign server of that name exists it is
SQL/MED, else it falls back to compat and errors if the `plproxy` schema
functions are absent (`refresh_cluster` `src/cluster.c:1049-1122`,
`determine_compat_mode` `src/cluster.c:810-855`) `[verified-by-code]`.

**10. `CONNECT` builds a private single-partition "fake cluster".** A direct
`CONNECT '<connstr>'` (or `CONNECT` resolved by a query) bypasses cluster config
entirely: `fake_cluster` fabricates a one-partition cluster whose name *is* the
connect string, cached in a separate `fake_cluster_tree`
(`src/cluster.c:1127-1163`, `plproxy_find_cluster` `src/cluster.c:1199-1242`)
`[verified-by-code]`. This is the RPC-to-an-arbitrary-DSN escape hatch.

## Notable design decisions

- **Nested calls to the same cluster are forbidden.** The cluster carries a
  `busy` flag; a re-entrant PL/Proxy call on an in-flight cluster errors
  ("Nested PL/Proxy calls to the same cluster are not supported"), because the
  connection/result state is global per-cluster and would corrupt
  (`src/main.c:184-186`, flag set/cleared in `plproxy_exec`
  `src/execute.c:1176-1194`, comment `src/execute.c:896-902`)
  `[verified-by-code]` `[from-comment]`.
- **Two-minute lazy maintenance sweep instead of a background worker.** On call
  entry `run_maint` fires at most once per `2*60` seconds, walking all clusters
  to drop over-lifetime / dead connections and clear stale results — no bgworker,
  no timer, just piggy-backed on foreground calls (`src/main.c:141-156`,
  `PLPROXY_MAINT_PERIOD`/`PLPROXY_IDLE_CONN_CHECK` `src/plproxy.h:97-103`,
  `plproxy_cluster_maint` `src/cluster.c:1344-1349`) `[verified-by-code]`.
- **Idle pooled connections are probed before reuse.** `check_old_conn`
  `poll()`s a would-be-reused socket for unexpected readable data and drops it as
  "unstable" if any is pending, in addition to enforcing `connection_lifetime`
  (`src/execute.c:222-272`) `[verified-by-code]`.
- **Remote I/O is pinned to the local `server_encoding`.** On each new
  connection `tune_connection` compares the remote `client_encoding` and, if it
  differs, sends a `set client_encoding` tuning query first — so no silent
  encoding conversion happens on the wire (`src/execute.c:118-171`)
  `[verified-by-code]`.
- **`SPLIT` fans a single array argument out to per-partition sub-arrays.** An
  array marked `SPLIT` is deconstructed and each element routed to the partition
  its `RUN ON` hash picks, then re-accumulated into per-connection array params —
  turning one call into a batched multi-shard write
  (`prepare_and_tag_partitions` `src/execute.c:941-1053`, `IS_SPLIT_ARG`
  `src/plproxy.h:91`, `plproxy_split_add_ident` requires an array arg
  `src/function.c:119-138`) `[verified-by-code]`.
- **SQL/MED cluster + user-mapping invalidation via syscache callbacks.** It
  registers `CacheRegisterSyscacheCallback` on `FOREIGNSERVEROID` and
  `USERMAPPINGOID` and stamps foreign-server/user-mapping TIDs so config edits
  flip a `needs_reload` flag on the affected clusters/users
  (`plproxy_syscache_callback_init` / `ClusterSyscacheCallback`
  `src/cluster.c:857-929`) `[verified-by-code]`.
- **Connection identity is (connstr, DB user); `default_user` chooses whose
  credentials.** `refresh_cluster` resolves the connection user from a
  `default_user` config of `current_user` or `session_user` (custom users are
  deliberately unsupported) (`src/cluster.c:1049-1077`) `[verified-by-code]`;
  user-mapping options build the `user=`/`password=` connstr tail
  (`reload_sqlmed_user` `src/cluster.c:620-697`, `get_connstr`
  `src/execute.c:282-298`) `[verified-by-code]`.
- **Untyped-RECORD returns are revalidated per call.** Functions returning bare
  `RECORD` need an `AS (...)` column list; the cached tuple descriptor is
  compared against the call's expected descriptor and rebuilt on mismatch
  (`dynamic_record` handling, `fn_refresh_record` `src/function.c:445-483`,
  `fn_returns_dynamic_record` `src/function.c:213-231`) `[verified-by-code]`.

## Links into corpus

- [[citus]] — the modern distributed-execution successor to hand-rolled
  PL/Proxy sharding.
- [[wrappers]] — the FDW-framework path to remote data.
- [[oracle_fdw]] — remote data via an FDW instead of a PL handler.
- [[pljava]] — a PL handler that actually runs code (embeds a JVM).
- [[plv8]] — a PL handler that actually runs code (embeds V8).
- [[pg_background]] — asynchronous in-cluster query execution.

## Sources

All fetched from `https://raw.githubusercontent.com/plproxy/plproxy/master/`
@ 2026-07-16:

- `AUTHORS` → HTTP 200 (40 lines)
- `plproxy.control` → HTTP 200 (7 lines)
- `src/plproxy.h` → HTTP 200 (447 lines)
- `src/function.c` → HTTP 200 (606 lines)
- `src/execute.c` → HTTP 200 (1206 lines)
- `src/cluster.c` → HTTP 200 (1350 lines)
- `src/query.c` → HTTP 200 (323 lines)
- `src/result.c` → HTTP 200 (222 lines)
- `src/main.c` → HTTP 200 (292 lines)
- `README.md` → HTTP 200 (51 lines) — **exists**, contra the task manifest's
  "no README" claim; used sparingly for `[from-README]` tags.
- `README` → HTTP 404 (no extensionless README)
- `README.rst` → HTTP 404 (no reStructuredText README)

Files not fetched (referenced by the corpus above but out of the confirmed
manifest): `src/scanner.l`, `src/parser.y` (the DSL lexer/grammar behind
`plproxy_run_parser`), `src/type.c` (the `ProxyType`/`plproxy_recv_*` I/O
cache), and the `aatree.[ch]` / `rowstamp.h` helpers. Claims about the parser
and type-conversion internals are `[inferred]` from their headers
(`src/plproxy.h:402-423`) and call sites, not from those source files directly.
