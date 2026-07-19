# pg_later — a background worker that runs a Tokio async runtime and executes deferred queries by opening a sqlx client connection *back to its own database*, not through SPI

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `tembo-io/pg_later` @ branch `main`. All `file:line` cites below point
> into that repo (not `source/`), since this doc characterizes an *external*
> extension's divergence from core idioms. Cites verified against the files
> fetched on 2026-07-18 (see Sources footer). Built on `[[pgmq]]` and the
> `[[pgrx]]` framework; a distinct async-execution shape versus `[[pg_cron]]`
> (scheduler) and `[[pg_net]]` (async outbound HTTP).

## Domain & purpose

pg_later gives Postgres "fire-and-forget" SQL: `select pg_later.exec('<query>')`
returns a job id immediately; a background worker runs the query later and
stashes the result; `select pg_later.fetch_results(job_id)` retrieves it as
JSON (`README.md`; `src/api.rs:26-76`) `[verified-by-code]`. It is a pgrx/Rust
extension by Tembo, using `[[pgmq]]` (Postgres Message Queue, same authors) as
its durable job/result transport.

**The one thing that makes pg_later structurally distinct.** The natural way for
a background worker to run a query is `SPI` — the in-process server-programming
interface, executing in the worker's own backend under its transaction. pg_later
does **not** do that for the deferred query. Its worker spins up a **Tokio
current-thread async runtime** and connects to the *same database* through
**`sqlx`** — an ordinary async Postgres *client* driver speaking the wire
protocol over TCP or a unix socket (`src/bgw.rs:33-45`, `src/util.rs:63-70`)
`[verified-by-code]`. The worker becomes a **client of its own server**: the
deferred query runs in a separate session, under whatever role the connection
string names, on its own transaction — not in the worker's backend, not via SPI.
That round-trip-out-and-back-in is the signature divergence. (SPI is still used,
but only by the *user-facing* functions to enqueue/dequeue pgmq messages —
`src/api.rs:15-63` — never to run the payload query.)

## How it hooks into PG

- **`_PG_init` requires `shared_preload_libraries`** (`src/bgw.rs:16-19`): it
  errors out if `process_shared_preload_libraries_in_progress` is false, then
  registers GUCs and a static background worker
  (`BackgroundWorkerBuilder::new("PG Later Background Worker")
  .set_function("background_worker_main").set_library("pg_later")
  .enable_spi_access().load()`, `src/bgw.rs:20-25`) `[verified-by-code]`.
- **User-facing `#[pg_extern]` functions** (`src/api.rs`): `init()` creates two
  pgmq queues (`pgmq.create_non_partitioned('pg_later_jobs' / '_results')`,
  `:9-23`); `exec(query, delay, validate)` (`:26-46`); `fetch_results(job_id)`
  (`:49-76`) `[verified-by-code]`.
- **One GUC** `pglater.host` (`PGC_SUSET` string, "unix socket url for
  Postgres", `src/guc.rs:9-16`), plus env vars `PGLATER_SOCKET_URL` and
  `DATABASE_URL` (`src/util.rs:20-25`) `[verified-by-code]`.
- **Transport is entirely `[[pgmq]]`** — jobs and results are pgmq messages;
  the worker `read`/`send`/`archive`s via `PGMQueueExt` (`src/bgw.rs:61-79`)
  `[verified-by-code]`.

## Where it diverges from core idioms

### 1. A Tokio async runtime inside a Postgres background worker

`background_worker_main` builds a single-threaded Tokio runtime with IO+time
drivers enabled and `block_on`s async closures for every unit of work:

```
let runtime = tokio::runtime::Builder::new_current_thread()
    .enable_io().enable_time().build().unwrap();
let (conn, queue) = runtime.block_on(async { … util::get_pg_conn() … });
…
while BackgroundWorker::wait_latch(Some(wait_duration)) { … runtime.block_on(async { … }) … }
```
(`src/bgw.rs:33-92`) `[verified-by-code]`. So a PG aux process — normally a
straight-line C loop around `WaitLatch`/`CHECK_FOR_INTERRUPTS` — hosts a
full async executor. The PG side is preserved at the seams
(`BackgroundWorker::attach_signal_handlers(SIGHUP|SIGTERM)`, `:31`;
`wait_latch`, `:50`), but all real work happens on the Tokio reactor. This is
the same "embed a foreign runtime/event-loop in a PG process" pattern seen in
`[[pg_net]]` (libcurl `curl_multi` + epoll) — here it is Tokio + sqlx.

### 2. Executing the deferred query as a *client of its own database* (sqlx, not SPI)

`get_pg_conn` builds a `sqlx` `PgPool` (max 4 connections, 10s acquire timeout)
and the worker runs every job through it:

```
let conn = util::get_pg_conn().await…;              // sqlx::PgPool to this same DB
…
let job = msg.message;                               // { query: String }
let result_message = exec_job(msg.msg_id, &job.query, &conn).await…;
```
(`src/bgw.rs:40-65`, `src/util.rs:63-70`) `[verified-by-code]`. The query text is
executed by `query_to_json`, which wraps row-returning queries as
`select to_jsonb(t) as results from ({query}) t` and collects the JSON
(`src/executor.rs:14-22`), or runs utility statements via `sqlx::query(...).execute`
and reports `rows_affected` (`src/executor.rs:25-31`) `[verified-by-code]`. Three
consequences of "client, not SPI":
- **Separate session & transaction.** The deferred query is not in the worker's
  backend transaction; it commits on its own connection. Fire-and-forget is real
  fire-and-forget.
- **Role divergence.** The connection identity is resolved from
  `pglater.host` → `PGLATER_SOCKET_URL` → `DATABASE_URL`
  (default `postgresql://postgres:postgres@0.0.0.0:5432/postgres`)
  (`src/util.rs:20-24`, `110-136`) `[verified-by-code]`. The deferred query runs
  as **that** role — typically a superuser-ish `postgres` — **not** as the role
  that called `pg_later.exec`. A caller with limited privileges can enqueue a
  query that runs with the worker connection's privileges. This is a genuine
  privilege-escalation surface, and the inverse of SPI, which would run under the
  worker's own (controlled) identity.
- **Connection bootstrapping fragility.** If `DATABASE_URL`/socket resolution is
  wrong, the worker `expect("failed to connect to database")` panics
  (`src/bgw.rs:41-42`) `[verified-by-code]`.

### 3. Query "validation" via an external Rust SQL parser, and string-hygiene sanitization

`exec` sanitizes the query by **doubling single quotes and stripping every
semicolon**, then optionally validates it with the Rust `sqlparser` crate's
`PostgreSqlDialect` — *not* PG's own parser:

```
let prepared_query = query.replace('\'', "''").replace(';', "");
if validate {
    let parse_result = Parser::parse_sql(&PostgreSqlDialect{}, &prepared_query);
    parse_result.expect("Query parsing failed, please submit a valid query");
}
let enqueue = format!("select pgmq.send('pg_later_jobs', '{msg}'::jsonb, {delay})");
```
(`src/api.rs:32-44`) `[verified-by-code]`. Two divergences: (a) validation uses a
*second, independent* SQL grammar (sqlparser) that can accept/reject differently
from the server that will actually run the query — a semantic gap; and (b) the
`;`-strip + quote-double is hand-rolled SQL-string hygiene feeding a
`format!`-built `pgmq.send('…'::jsonb, …)` — the standard "build SQL by string
interpolation" anti-pattern core avoids with parameterized plans. A failed parse
`.expect()`-panics rather than `ereport`-ing a clean error `[verified-by-code]`.

### 4. Results marshalled to JSON through the queue; naive row/utility classifier

Because results travel back as a pgmq message, they are serialized to JSON:
`exec_job` builds `{ status, job_id, query, result }` (`src/bgw.rs:112-132`) and
`send`s it to `pg_later_results` (`src/bgw.rs:68-71`) `[verified-by-code]`.
Whether to expect rows is decided by `clf::returns_rows`, whose entire body is:

```
sql.trim().to_uppercase().starts_with("SELECT")
```
(`src/clf.rs:9-12`, explicitly `// TODO - build a more complex statement
classifier`) `[verified-by-code]`. So `WITH … SELECT`, `VALUES`, `TABLE t`,
`INSERT … RETURNING`, `EXPLAIN`, and lowercase-after-comment queries are
misclassified as utility statements and lose their result set — a documented-in-
code sharp edge. Jobs are **always archived whether they succeed or fail**
(`src/bgw.rs:74-79`), with no retry ("in future, support some sort of retry")
`[verified-by-code]`.

### 5. Readiness gate and poll loop

The worker will not process until pgmq's job table exists, checked each tick with
a `sqlx` `SELECT EXISTS(… pg_tables … 'q_pg_later_jobs')` (`src/bgw.rs:97-109`),
and backs off with a variable `wait_duration` (0s when it just processed a job,
5s when idle, 10s on error) driving `wait_latch` (`src/bgw.rs:49-92`)
`[verified-by-code]` — a hand-rolled adaptive poll rather than a
notify/latch-driven wakeup.

## Notable design decisions

- **pgmq as the durable substrate** — no bespoke job table; jobs/results are
  pgmq queues, inheriting pgmq's visibility-timeout + archive semantics
  (`src/api.rs:11-12`, `src/bgw.rs:13,68-79`) `[verified-by-code]`. See
  `[[pgmq]]`.
- **`.enable_spi_access()` on the worker** (`src/bgw.rs:24`) — SPI *is* wired
  up, but used only via the pgrx user functions for pgmq bookkeeping; the payload
  query pointedly does not use it `[verified-by-code]`.
- **`extern "C-unwind"` entry points** (`src/bgw.rs:16,30`) — pgrx's unwinding
  ABI so Rust panics can cross the C boundary as controlled aborts
  `[verified-by-code]`; cf. `[[pgrx]]` `pg_guard_ffi_boundary`.
- **`Job` is a `PostgresType`** (`src/executor.rs:9-11`) — the job payload is a
  serde-(de)serializable pgrx composite carried as jsonb in the queue
  `[verified-by-code]`.

## Links into corpus

- Built directly on `[[pgmq]]` (queue transport) and `[[pgrx]]` (Rust/pgrx
  substrate, `extern "C-unwind"`, `#[pg_extern]`, GUC macros).
- Async-runtime-in-a-bgworker mirrors `[[pg_net]]` (libcurl multi + epoll in a
  shared_preload worker) and contrasts `[[pg_cron]]` (a scheduler that uses SPI /
  background sessions). The "connect back to your own DB as a client" move also
  appears in `[[pg_auto_failover]]` (outbound libpq to peers) — but pg_later
  points the client connection at *itself*.
- The role/identity divergence and string-built SQL connect to the security
  observations in `[[index_advisor]]` ("no C therefore safe" inverted) and the
  privilege notes in `knowledge/idioms/` security-definer / current_role docs.
- Foreign-runtime memory (Tokio/sqlx buffers, the PgPool) lives outside PG
  MemoryContexts — same off-heap theme as `[[pglite-fusion]]`, `[[onesparse]]`,
  `[[vault]]`. See `knowledge/idioms/memory-contexts.md`.

## Sources

- `src/bgw.rs` → HTTP 200 (133 lines; `_PG_init`, `background_worker_main`
  Tokio loop, `ready`, `exec_job` — deep-read; the load-bearing file).
- `src/util.rs` → HTTP 200 (157 lines; `Config`/env defaults, socket-vs-TCP
  `PgConnectOptions` resolution, `get_pg_conn` PgPool — deep-read).
- `src/api.rs` → HTTP 200 (76 lines; `init`, `exec` sanitize/validate/enqueue,
  `fetch_results` — deep-read).
- `src/executor.rs` → HTTP 200 (44 lines; `query_to_json`, `exec_row_query`
  to_jsonb wrap, `exec_utility` — deep-read).
- `src/clf.rs` → HTTP 200 (26 lines; the `starts_with("SELECT")` classifier +
  its own TODO).
- `src/guc.rs` → HTTP 200 (48 lines; `pglater.host` PGC_SUSET string GUC).
- `src/lib.rs` → HTTP 200 (22 lines; module wiring, `pg_module_magic!`).
- `Cargo.toml`, `README.md` → HTTP 200 (dependency set incl. `sqlx`, `tokio`,
  `sqlparser`, `pgmq`; user-facing exec/fetch workflow).

All cites `[verified-by-code]` against the fetched `.rs` files except the
end-user fire-and-forget workflow (`[from-README]`) and the privilege-escalation
*consequence* of the connection-string role (which is `[inferred]` from the role
resolution in `src/util.rs:20-24,110-136` — the repo does not narrate it as a
risk). `src/worker.rs`/`src/query.rs` were probed and are **404**; the worker
logic lives in `src/bgw.rs` and the classifier in `src/clf.rs`.
