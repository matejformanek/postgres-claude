# pgsql-http — ideology / divergence notes

Extension: **pramsey/pgsql-http** (`master`, default version `1.7`).
A SQL-callable HTTP client for PostgreSQL: `SELECT * FROM http_get('http://example.com')`.

> Citation note: source read via `raw.githubusercontent.com` (the Git Trees API
> host returned HTTP 403, so paths were verified by direct raw fetch). `http.c`
> line numbers are tagged approximate (`~`) where two read passes disagreed; the
> **function name** is the stable anchor. See Sources footer.

---

## Domain & purpose

pgsql-http makes **outbound HTTP requests from inside a backend process**, turning
SQL into a web client. It supports `GET / POST / PUT / PATCH / DELETE / HEAD`,
returns the response (status, content-type, headers, body) as a SQL composite,
and is explicitly pitched for trigger-driven integrations — "write a trigger that
called a web service" `[from-README]`. The transport is **libcurl** linked into
the backend; every request is a synchronous, blocking call executed in the
calling backend's own process. This is the polar opposite of core PG's design
center (durable, transactional, MVCC-versioned local storage): the extension's
entire value is a *non-transactional side effect on the outside world*.

---

## How it hooks into PG

Standard loadable-C-extension model, no exotic machinery:

- **Control file** `http.control`: `default_version = '1.7'`, `module_pathname =
  '$libdir/http'`, comment "HTTP client for PostgreSQL, allows web page
  retrieval inside the database." `[verified-by-code]` (http.control)
- **Module magic**: declared via `PG_MODULE_MAGIC_EXT(.name="http", .version=...)`
  (newer macro form, guarded by `#ifdef PG_MODULE_MAGIC_EXT`). `[verified-by-code]`
  (http.c ~114, PG_MODULE_MAGIC block)
- **`_PG_init`** exists, but only to register GUCs and init curl — *not* to chain
  planner/executor/ProcessUtility hooks. `[verified-by-code]` (http.c `_PG_init`,
  ~line 467–508). This is the **LOAD / CREATE EXTENSION** model, not the
  `shared_preload_libraries` + hook-interception model used by, e.g.,
  pg_stat_statements or [[pg_hint_plan]].
- **SQL-callable C functions** via `PG_FUNCTION_INFO_V1`: the master entry is
  `http_request(http_request)` → `http_response`; plus `urlencode`,
  `urlencode_jsonb`, `bytea_to_text`, `text_to_bytea`, `http_set_curlopt`,
  `http_reset_curlopt`, `http_list_curlopt`. `[verified-by-code]` (http.c, the
  `PG_FUNCTION_INFO_V1(...)` cluster, ~1017–1750). See [[fmgr]].
- **Composite types & SRF-ish returns**: the install SQL defines composite types
  `http_header(field, value)`, `http_request(method, uri, headers,
  content_type, content)`, and `http_response(status, content_type, headers,
  content)`, plus an enum `http_method`. The C side builds a `http_response`
  tuple and returns it as a composite Datum. `[verified-by-code]` (http--1.7.sql
  `CREATE TYPE` block; http.c tuple assembly). The header array
  (`http_header[]`) means a single response Datum carries a nested array of
  composites.
- **GUCs**: registered dynamically. `http_guc_init_opt()` calls
  `DefineCustomStringVariable` per settable curl option, producing GUC names like
  `http.curlopt_timeout_ms`, plus back-compat aliases `http.keepalive` and
  `http.timeout_msec`. `[verified-by-code]` (http.c ~451–503). Scope is
  `PGC_SUSET` for superuser-only options else `PGC_USERSET`, so timeouts/proxies
  can be set per-session with `SET` or pinned with `ALTER ROLE/DATABASE`.
  See [[guc-variables]].

---

## Where it diverges from core idioms — THE headline

**A PostgreSQL backend performs a blocking, synchronous outbound network I/O
(libcurl) in the middle of a transaction.** Core PG backends are built to do
local, transactional, interruptible work; an arbitrary outbound TCP/TLS call to
a third-party server is alien on several axes at once.

### 1. Interruptibility — solved via a curl progress callback, not CHECK_FOR_INTERRUPTS

A normal long-running backend loop sprinkles `CHECK_FOR_INTERRUPTS()` so query
cancel (Ctrl-C / `pg_cancel_backend`) and termination land promptly. But while
control is *inside libcurl* blocked on a socket, the backend can't reach a
`CHECK_FOR_INTERRUPTS()`. There are **no `CHECK_FOR_INTERRUPTS()` calls in
http.c** `[verified-by-code]` (grep of http.c). Instead the extension wires a
curl progress callback that libcurl invokes periodically during transfer:

```c
static int
http_progress_callback(void *clientp, curl_off_t dltotal, curl_off_t dlnow,
                       curl_off_t ultotal, curl_off_t ulnow)
{
#ifdef WIN32
	if (UNBLOCKED_SIGNAL_QUEUE())
		pgwin32_dispatch_queued_signals();
#endif
	/* Check the PgSQL global flags */
	return QueryCancelPending || ProcDiePending;
}
```
`[verified-by-code]` (http.c `http_progress_callback`, ~line 233–245 in one pass /
~413–425 in another — function name is the stable anchor). Returning non-zero
from a curl progress callback aborts the transfer, so a pending cancel/die flag
makes curl bail out of the blocking call. Wired with:

```c
CURL_SETOPT(g_http_handle, CURLOPT_XFERINFOFUNCTION, http_progress_callback);
CURL_SETOPT(g_http_handle, CURLOPT_NOPROGRESS, 0);
```
`[verified-by-code]` (http.c, CURL_SETOPT block ~877). This is a **reimplementation
of PG's interrupt contract in libcurl's vocabulary** — reading PG's global
`QueryCancelPending`/`ProcDiePending` directly rather than calling the macro that
would consume them. It is the single most idiom-violating line in the codebase,
and the cleanest illustration of "embedded foreign event loop inside a backend."

### 2. statement_timeout interaction — no integration; libcurl owns the clock

There is **no `statement_timeout` integration**. The backend's
`statement_timeout` fires via a SIGALRM-driven timer that can only act at the next
interrupt point; while blocked in libcurl, that point may not arrive until the
progress callback runs. The extension instead imposes **its own** default
timeouts: `CURLOPT_CONNECTTIMEOUT_MS = 1000` (1s connect) and
`CURLOPT_TIMEOUT_MS = 5000` (5s total), overridable via the curl GUCs.
`[verified-by-code]` (http.c ~700–701; comment "Always want a default fast
(1 second) connection timeout"). So a query's effective wall-clock bound for an
HTTP call is governed by libcurl, not by core PG's `statement_timeout` —
two independent timeout regimes the operator must reason about separately.
`[inferred]` (from the absence of statement_timeout plumbing + presence of curl
timeouts).

### 3. No MVCC, no WAL, no snapshot — the request is invisible to the storage engine

An HTTP call writes nothing to a relation, emits no WAL, takes no snapshot, and
is not rolled back if the surrounding transaction aborts. Core PG's safety net
(atomic, durable, recoverable) simply does not extend across the network
boundary. If the transaction `ROLLBACK`s after a `http_post`, the POST already
happened on the remote server. `[inferred]` (no WAL/heap/xact API appears in
http.c; the side effect is external). This is the FDW-class hazard — external
effects that PG's transaction manager cannot undo — but unlike a well-behaved FDW
there is no transaction-callback hook attempting any compensation.

### 4. Volatility labeling — the function is a network side-effect masquerading in the type system

`http_request`/`http_get` etc. perform non-deterministic, side-effecting I/O, so
they MUST be (and are, by their nature) treated as **VOLATILE**: the planner must
not fold, cache, or reorder them. By contrast the pure helpers — `urlencode`,
`urlencode_jsonb`, `bytea_to_text`, `text_to_bytea`, `http_header(s)` — are
correctly labeled `IMMUTABLE STRICT` because they are deterministic pure
transforms. `[verified-by-code]` (http--1.7.sql: the `urlencode`/`*_to_*`/
`http_headers` functions carry `IMMUTABLE STRICT`). The divergence: PG's
volatility classification was designed to describe *purity with respect to the
database* (does it read tables? does it change between calls?); here it is being
stretched to police a function whose impurity is *the outside world*. Marking an
HTTP function IMMUTABLE would be catastrophic (the planner could evaluate it once
at plan time, or constant-fold it), so the labeling discipline matters more here
than for most extensions. `[inferred]` from PG volatility semantics + the README
caveats about side effects.

### 5. Memory: curl buffers funnel into StringInfo / palloc, with explicit pfree

libcurl wants a write callback to accumulate the response body. The extension
points curl at a PG `StringInfo` and appends with `appendBinaryStringInfo`, so the
curl-driven growth lands in palloc'd memory under the current MemoryContext rather
than raw `malloc`/`realloc`:

```c
static size_t
http_writeback(void *contents, size_t size, size_t nmemb, void *userp)
{
	size_t realsize = size * nmemb;
	StringInfo si = (StringInfo)userp;
	appendBinaryStringInfo(si, (const char*)contents, (int)realsize);
	return realsize;
}
```
`[verified-by-code]` (http.c `http_writeback`, ~617–623). Buffers are
`initStringInfo`'d before the call and explicitly `pfree`'d afterward
(`pfree(si_headers.data); pfree(si_data.data); ...`). `[verified-by-code]`
(http.c cleanup block ~1633). This is the right bridge: curl's allocator
boundary is reconciled with PG's [[memory-contexts]] so a long-lived backend
issuing many requests doesn't leak — though note curl's *own* internal
allocations (the easy handle, slist) are managed via `curl_easy_cleanup` /
`curl_slist_free_all`, outside palloc. The easy handle is even **cached across
calls** when `CURLOPT_TCP_KEEPALIVE` is set (`g_http_handle` kept non-NULL),
a static-global lifetime that core PG code would normally route through a
MemoryContext. `[verified-by-code]` (http.c ~1633 conditional cleanup).

### 6. Error handling — libcurl errors funneled into ereport(ERROR)

curl failures are translated into PG errors via a small adapter that prefers
curl's error buffer, falling back to `curl_easy_strerror`:

```c
static void
http_error(CURLcode err, const char *error_buffer)
{
	if ( strlen(error_buffer) > 0 )
		ereport(ERROR, (errmsg("%s", error_buffer)));
	else
		ereport(ERROR, (errmsg("%s", curl_easy_strerror(err))));
}
```
`[verified-by-code]` (http.c `http_error`, ~626–632). A failed network call thus
*aborts the transaction* via the standard longjmp `ereport(ERROR)` path —
consistent with PG's [[error-handling]] contract, even though the failure
originates outside the database. Specific SQLSTATEs appear for the structured
cases (`ERRCODE_FEATURE_NOT_SUPPORTED`, `ERRCODE_OUT_OF_MEMORY`).
`[verified-by-code]` (http.c ~1602–1605).

### Contrast with [[pg_auto_failover]]

Both extensions do outbound network I/O from a PG process, but the *placement*
inverts the risk model:

- **pg_auto_failover** does its network I/O from a **background worker** using
  **libpq**, off the query path. A monitor/keeper bgworker has its own loop with
  `WaitLatch` + `CHECK_FOR_INTERRUPTS`, no user transaction is held hostage, and
  the I/O is to other Postgres nodes it controls. `[inferred]` (see
  [[pg_auto_failover]]).
- **pgsql-http** does its network I/O **inline in the foreground backend**,
  inside the user's transaction, to **arbitrary** third-party servers over
  libcurl. The transaction (and its locks, snapshot, and `statement_timeout`
  budget) is held for the full duration of a remote call the DB does not control.

That difference — bgworker/libpq/controlled-peer vs foreground/libcurl/arbitrary-peer —
is why pgsql-http needs the progress-callback interrupt hack and its own timeout
defaults, while pg_auto_failover leans on the normal bgworker idioms.

---

## Notable design decisions (with cites)

- **Interrupt via curl progress callback reading PG globals directly.** Chooses
  `QueryCancelPending || ProcDiePending` over `CHECK_FOR_INTERRUPTS()` because
  the latter is unreachable while blocked in curl. `[verified-by-code]` (http.c
  `http_progress_callback` + CURLOPT_XFERINFOFUNCTION wiring ~877).
- **Aggressive default timeouts** (1s connect / 5s total) so a hung remote host
  doesn't pin a backend indefinitely; overridable per-session. `[verified-by-code]`
  (http.c ~700–701).
- **Response body accumulated in palloc'd StringInfo**, not malloc, with explicit
  `pfree` — bounds memory growth in long-lived backends. `[verified-by-code]`
  (http.c `http_writeback` ~617; cleanup ~1633).
- **Optional easy-handle reuse** keyed on `CURLOPT_TCP_KEEPALIVE` via a static
  global `g_http_handle` to amortize connection setup. `[verified-by-code]`
  (http.c ~1633 conditional `curl_easy_cleanup`).
- **Dynamic GUC registration** — one `DefineCustomStringVariable` per settable
  curl option, plus deprecated-name aliases for back-compat. `[verified-by-code]`
  (http.c `http_guc_init_opt` ~451–503).
- **Pure helpers marked IMMUTABLE STRICT, request functions left VOLATILE** — the
  volatility split is load-bearing for planner correctness. `[verified-by-code]`
  (http--1.7.sql).
- **README ships explicit operational warnings** (slow responses block queries,
  unvalidated remote data, restrict via function privileges). `[from-README]`.

---

## Links into corpus

- [[fmgr]] — `PG_FUNCTION_INFO_V1`, composite/array Datum return assembly.
- [[memory-contexts]] — curl write buffers bridged to palloc/StringInfo; pfree
  discipline; static-global handle lifetime.
- [[error-handling]] — libcurl `CURLcode` translated into `ereport(ERROR)`.
- [[guc-variables]] — dynamic `DefineCustomStringVariable` per curl option,
  PGC_SUSET vs PGC_USERSET.
- [[storage-ipc]] — `QueryCancelPending` / `ProcDiePending` are the interrupt
  globals the progress callback reads.
- Sibling ideologies: [[pg_auto_failover]] (bgworker + libpq outbound I/O — the
  contrast case), [[wrappers]] / [[cstore_fdw]] (external-resource access with
  non-transactional effects), [[pg_cron]] (another background-vs-foreground
  placement decision).

> Corpus gap: there is no dedicated `idioms/sql-function-volatility.md`. The
> VOLATILE/STABLE/IMMUTABLE discussion above is anchored to the install SQL and
> PG volatility semantics; a future idioms doc on function purity/volatility
> would be the proper wikilink target. `[inferred]`

---

## Sources

- `https://raw.githubusercontent.com/pramsey/pgsql-http/master/README.md`
  — HTTP 200 — fetched 2026-06-14T00:00:00Z.
- `https://raw.githubusercontent.com/pramsey/pgsql-http/master/http.control`
  — HTTP 200 — fetched 2026-06-14T00:00:00Z (confirmed default_version 1.7).
- `https://raw.githubusercontent.com/pramsey/pgsql-http/master/http--1.7.sql`
  — HTTP 200 — fetched 2026-06-14T00:00:00Z.
- `https://raw.githubusercontent.com/pramsey/pgsql-http/master/http.c`
  — HTTP 200 — fetched 2026-06-14T00:00:00Z (read twice; line numbers for the
  progress callback differed between passes, hence the `~` tags).
- `https://api.github.com/repos/pramsey/pgsql-http/git/trees/master?recursive=1`
  — **HTTP 403 Forbidden** to the fetch tool — tree could not be enumerated;
  paths instead verified by direct raw fetches. The manifest hint
  `http--1.6.sql` was **substituted with `http--1.7.sql`** (the control file's
  default_version), which fetched 200.
