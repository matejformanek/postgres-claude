# pg_net — ideology / divergence notes

Extension: **supabase/pg_net** (`master`, control comment "Async HTTP",
`relocatable = false`). A SQL-callable HTTP client whose entire identity is
**asynchrony**: `SELECT net.http_get('http://example.com')` returns a `bigint`
*request id* immediately, and the actual network I/O happens later in a single
shared background worker. The README pitches it as the engine behind Supabase
webhooks. `[from-README]` (README.md ~31).

> This is the deliberate **foil to [[pgsql-http]]**. Same job (outbound HTTP from
> Postgres, same `libcurl` dependency), opposite architecture on every axis:
> foreground vs background, `curl_easy` blocking vs `curl_multi` reactor,
> inline-in-transaction vs fire-at-commit, external-effect-survives-ROLLBACK vs
> effect-cancelled-by-ROLLBACK. Read the two side by side.

---

## Domain & purpose

pg_net lets SQL enqueue outbound HTTP/HTTPS requests **without blocking the
calling backend**. The request functions (`net.http_get`, `net.http_post`,
`net.http_delete`) do nothing but `INSERT` a row into a queue table and return
its id; a long-lived background worker drains the queue, drives the requests
through a non-blocking `libcurl` multi handle wired to an OS event loop
(`epoll`/`kqueue`), and writes results back into a response table the caller
polls or waits on. The design center is "the database proactively notifies
external resources about significant events" — triggers and pg_cron jobs that
fan out webhooks without holding a transaction open for the round trip.
`[from-README]` (README.md ~31, ~89–98).

---

## How it hooks into PG

This is the **`shared_preload_libraries` + background-worker** model, the
opposite end of the spectrum from pgsql-http's plain `LOAD`/`CREATE EXTENSION`:

- **Control file** `pg_net.control.in`: `comment = 'Async HTTP'`,
  `relocatable = false`, `module_pathname = '$libdir/pg_net'`.
  `[verified-by-code]` (pg_net.control.in).
- **`_PG_init` refuses to load outside `shared_preload_libraries`** — it errors
  with a hint to add itself there if `!process_shared_preload_libraries_in_progress`.
  `[verified-by-code]` (worker.c:456–460). It then `RegisterBackgroundWorker`s a
  *static* worker (`BGWORKER_SHMEM_ACCESS | BGWORKER_BACKEND_DATABASE_CONNECTION`,
  `BgWorkerStart_RecoveryFinished`, `bgw_restart_time = 1s`). `[verified-by-code]`
  (worker.c:462–469). See [[bgworker-and-extensions]].
- **Shmem allocation via the hook pair**: `shmem_request_hook` →
  `RequestAddinShmemSpace(sizeof(WorkerState))`, `shmem_startup_hook` →
  `ShmemInitStruct("pg_net worker state", ...)` under `AddinShmemInitLock`.
  `[verified-by-code]` (worker.c:420–449, 471–479). See [[locking]].
- **Four GUCs**, all worker-scoped: `pg_net.ttl` (`PGC_SIGHUP`, default
  `'6 hours'`), `pg_net.batch_size` (`PGC_SIGHUP`, default 200),
  `pg_net.database_name` and `pg_net.username` (both `PGC_SU_BACKEND` — the
  single worker connects to exactly one database). `[verified-by-code]`
  (worker.c:481–494). See [[gucs-config]].
- **SQL surface** is split: the public `http_get/http_post/http_delete` are
  **plpgsql** wrappers that INSERT + `net.wake()`; only `_urlencode_string`,
  `_encode_url_with_params_array`, `worker_restart`, `wait_until_running`,
  `wake` are `language 'c'`. `[verified-by-code]` (sql/pg_net.sql:78–148). The
  C entry points use `PG_FUNCTION_INFO_V1`. See [[fmgr-and-spi]].
- **Two unlogged tables in schema `net`**: `http_request_queue` (the inbox) and
  `_http_response` (the outbox, with a `created` index for TTL expiry).
  `[verified-by-code]` (sql/pg_net.sql:12–46).

---

## Where it diverges from core idioms — THE headline

### 1. Async by queue table + single worker — the whole point

A request function never touches the network. `net.http_get` URL-encodes its
params, `INSERT`s a row into `net.http_request_queue`, calls `net.wake()`, and
`RETURN`s the new `id`. `[verified-by-code]` (sql/pg_net.sql:111–148). The
caller later retrieves the result from `net._http_response` (via
`net.http_collect_response`, optionally blocking through `_await_response` which
`pg_sleep(0.05)`-polls until the row appears). `[verified-by-code]`
(sql/pg_net.sql:50–73, 288–337). Core PG has no notion of a deferred,
out-of-band side effect tied to a SQL call returning a *handle* — this is a
job-queue pattern grafted on with two tables and a worker, conceptually closer
to [[pgmq]]/[[pg_cron]] than to a normal function.

### 2. `curl_multi` + epoll/kqueue reactor inside a background worker

Where pgsql-http makes one blocking `curl_easy_perform`, pg_net runs a full
**non-blocking reactor**. The worker creates an event monitor
(`epoll_create1(0)` on Linux, `kqueue()` on BSD/macOS — selected by
`WAIT_USE_EPOLL`) and a `curl_multi` handle, then bridges libcurl's socket and
timer callbacks to the kernel poller:

- `CURLMOPT_SOCKETFUNCTION` → `multi_socket_cb` translates
  `CURL_POLL_IN/OUT/REMOVE` into `epoll_ctl(EPOLL_CTL_ADD/MOD/DEL)` (or
  `EV_SET`/`kevent`). `[verified-by-code]` (event.c:75–113, 177–219).
- `CURLMOPT_TIMERFUNCTION` → `multi_timer_cb` arms a `timerfd`
  (`timerfd_create(CLOCK_MONOTONIC, ...)`) / `EVFILT_TIMER`; libcurl's
  "timeout now" (0 ms) is faked as a 1 ns fire because a zero `itimerspec`
  disarms. `[verified-by-code]` (event.c:30–73, 150–175).

The drain loop calls `wait_event` (= `epoll_wait`/`kevent`) and feeds readiness
back with `curl_multi_socket_action`, reaping finished transfers via
`curl_multi_info_read` → `insert_response`. `[verified-by-code]`
(worker.c:325–370). This is an **entire foreign event loop embedded in a PG
backend process** — far beyond the `WaitEventSet` core would use, and the reason
pg_net needs none of pgsql-http's progress-callback interrupt hack (see §6).

### 3. Wake-at-commit via xact callback + coalescing CAS

`net.wake()` doesn't signal the worker directly. It `RegisterXactCallback(
wake_at_commit, ...)` once per transaction (guarded by `wake_commit_cb_active`).
`[verified-by-code]` (worker.c:124–132). Only on `XACT_EVENT_COMMIT` does it
`pg_atomic_compare_exchange_u32(&worker_state->should_wake, 0→1)` and `SetLatch`
the worker's shared latch — and **only the first committer wins the CAS**, so a
thundering herd of concurrent commits collapses into a single wake.
`[verified-by-code]` (worker.c:94–122). `XACT_EVENT_ABORT` just clears the flag,
so a **`ROLLBACK` means the request is never sent** — the exact inverse of
pgsql-http, where the POST has already hit the wire by the time you roll back.
This makes enqueue genuinely transactional with respect to the local database.

### 4. Durability traded away on purpose — unlogged queue, at-most-once

Both `http_request_queue` and `_http_response` are **`UNLOGGED`**
`[verified-by-code]` (sql/pg_net.sql:12, 35); the README is explicit that this
buys performance "at the expense of durability." `[from-README]` (README.md ~53).
Combined with §3, the delivery contract is subtle: the enqueue is transactional
(survives commit, vanishes on rollback) but a **crash before the worker drains
the queue silently loses the requests** — unlogged tables are truncated on crash
recovery. There is no WAL, no replication of in-flight requests, no retry beyond
the worker re-reading whatever rows survive. This is a deliberate "fire-and-
mostly-forget" stance utterly unlike core PG's durability guarantees, and unlike
[[pgmq]] which keeps its queue in *logged* tables.

### 5. The worker runs its own transactions over SPI with saved plans

The bgworker is a full backend (`BackgroundWorkerInitializeConnection(
guc_database_name, guc_username, 0)`), and each drain iteration is its own
transaction: `SetCurrentStatementStartTimestamp` → `StartTransactionCommand` →
`PushActiveSnapshot` → `SPI_connect` → ... → `CommitTransactionCommand`.
`[verified-by-code]` (worker.c:285–389). It drains the queue with a single
`DELETE ... LIMIT $1 ... RETURNING` (claim-and-remove in one statement) and
expires old responses with `DELETE ... WHERE created < now() - $1`, both via
`SPI_prepare` + **`SPI_saveplan`** cached in file-static pointers so the plans
survive across the worker's many transactions. `[verified-by-code]`
(core.c:122–190). See [[fmgr-and-spi]]. Note the candid comment that
`get_request_queue_row` has an *implicit* dependency on the queue-drain having
run, "unfortunately we're not able to make this dependency explicit due to the
design of SPI (which uses global variables)." `[from-comment]` (core.c:192–194).

### 6. Interrupt model — the clean way, because curl never blocks

pgsql-http had to read `QueryCancelPending`/`ProcDiePending` from a curl progress
callback because control was stuck inside `curl_easy_perform`. pg_net has **no
such hack**: because the multi interface returns control to PG between socket
events, the worker reaches `CHECK_FOR_INTERRUPTS()` normally in
`wait_while_processing_interrupts` after every `WaitLatch`. `[verified-by-code]`
(worker.c:182–206). It does still rebuild signal handling: a custom `SIGUSR1`
handler that `SetLatch`es **and** chains `procsignal_sigusr1_handler`, with a
pointed comment that without the extra `SetLatch`, `DROP DATABASE` would hang
because the sleeping worker would never reach `CHECK_FOR_INTERRUPTS`.
`[verified-by-code]` (worker.c:149–160). `SIGTERM`/`SIGHUP` set a restart flag +
latch. `[verified-by-code]` (worker.c:134–147).

### 7. Liveness coordination via shmem atomics + ConditionVariable

`WorkerState` is `pg_atomic_uint32 got_restart/should_wake/status`, a `Latch *`,
a `ConditionVariable`, the epoll fd, and the `CURLM *`. `[verified-by-code]`
(core.h:11–19). The worker publishes its state (`WS_NOT_YET` → `WS_RUNNING` →
`WS_EXITED`) by writing the atomic and `ConditionVariableBroadcast`-ing; the
SQL-callable `wait_until_running()` sleeps on that CV until the worker is up.
`[verified-by-code]` (worker.c:72–89, 162–166). This is core's own shmem-atomics
+ CV toolkit (see [[locking]]) used exactly as intended — the disciplined
counterpart to the wilder event-loop divergence.

### 8. Existence guard via ConditionalLockRelationOid

Before each drain the worker checks the extension still exists by resolving the
`net` schema + the two table OIDs and taking **conditional** `AccessShareLock`s
(`ConditionalLockRelationOid`); if it can't, it aborts the iteration and breaks.
`[verified-by-code]` (worker.c:208–227, 292–297). Using the *conditional* lock
variant means a concurrent `DROP EXTENSION` (holding `AccessExclusiveLock`) is
never blocked by the worker — the worker simply backs off. A small but real
divergence: core code rarely uses `ConditionalLockRelationOid` as a polled
"does this object still exist and is it free?" probe.

### 9. Manual pgstat flush — the bgworker footgun

After each committed iteration the worker calls `pgstat_report_stat(false)`,
with a comment explaining that background workers that modify tables must flush
their pending pgstat counters themselves, since (unlike regular backends) they
have no `tcop/postgres.c` main loop to do it. `[verified-by-code]`
(worker.c:391–398). Without it, the worker's `n_tup_ins`/`n_tup_del` never reach
shared stats — a genuine gotcha for any table-writing bgworker.

### Contrast table

| axis | [[pgsql-http]] | pg_net |
|---|---|---|
| placement | foreground backend, in user txn | dedicated bgworker |
| curl mode | `curl_easy` blocking | `curl_multi` + epoll/kqueue reactor |
| caller blocks? | yes, for the round trip | no — returns request id |
| ROLLBACK | request already sent (irreversible) | request never sent (xact callback) |
| durability | n/a (synchronous) | unlogged tables, lost on crash |
| interrupts | progress-callback reads PG globals | normal `CHECK_FOR_INTERRUPTS` |
| load model | `LOAD` / `CREATE EXTENSION` | `shared_preload_libraries` |

---

## Notable design decisions (with cites)

- **Request functions enqueue + `wake()`, never do I/O** — the asynchronous
  contract lives entirely in plpgsql + two tables. `[verified-by-code]`
  (sql/pg_net.sql:111–148).
- **`curl_multi` driven by `epoll`/`kqueue`** with `timerfd`/`EVFILT_TIMER` for
  libcurl's timer callback — a reactor inside a bgworker. `[verified-by-code]`
  (event.c, worker.c:320–370).
- **Wake only at commit, coalesced by CAS** so 100k inserts in one statement wake
  the worker once. `[verified-by-code]` (worker.c:94–122; comment ~91–93).
- **Unlogged queue/response tables** — durability deliberately traded for speed;
  rollback cancels, crash drops. `[verified-by-code]` (sql/pg_net.sql:12,35) +
  `[from-README]` (README.md ~53).
- **SPI saved plans** for claim-by-`DELETE...RETURNING` and TTL expiry, reused
  across the worker's per-iteration transactions. `[verified-by-code]`
  (core.c:122–190).
- **Custom SIGUSR1 that SetLatch + chains the default handler** to keep
  `DROP DATABASE` from hanging. `[verified-by-code]` (worker.c:149–160).
- **`proc_exit(EXIT_FAILURE)` on drain to trigger postmaster restart**, paired
  with `bgw_restart_time = 1s`. `[verified-by-code]` (worker.c:413, 468).
- **Static `_Static_assert` on `LIBCURL_VERSION_NUM >= 7.83.0`** because it relies
  on `curl_easy_nextheader()`. `[verified-by-code]` (worker.c:16–24).
- **Response body accumulated in palloc'd StringInfo** (`body_cb` →
  `appendBinaryStringInfo`), freed via `pfree_handle`/`destroyStringInfo` — same
  curl↔palloc bridge as pgsql-http. `[verified-by-code]` (core.c:18–23, 319–329).
  See [[memory-contexts]].

---

## Links into corpus

- [[pgsql-http]] — the synchronous-foreground foil; read together.
- [[bgworker-and-extensions]] — `RegisterBackgroundWorker`, `bgw_*`,
  `BackgroundWorkerInitializeConnection`, the `WaitLatch` + `WL_EXIT_ON_PM_DEATH`
  idiom, signal-handler skeleton.
- [[fmgr-and-spi]] — `PG_FUNCTION_INFO_V1`, SPI prepared/saved plans, the worker
  running its own `StartTransactionCommand`/`CommitTransactionCommand`.
- [[locking]] — shmem atomics + `ConditionVariable`, `AddinShmemInitLock`,
  `ConditionalLockRelationOid` as an existence probe.
- [[gucs-config]] — `PGC_SIGHUP`/`PGC_SU_BACKEND` worker GUCs.
- [[memory-contexts]] — curl write buffer bridged to palloc/StringInfo.
- Sibling ideologies: [[pg_auto_failover]] (bgworker + libpq outbound I/O via a
  `poll(2)` loop — the other "network from a worker" case), [[pgmq]] (logged
  queue-as-tables, the durable contrast to §4), [[pg_cron]]
  (bgworker + SPI + own transactions), [[pglogical]] (worker tree).

> Corpus gap: no dedicated `idioms/job-queue-tables.md`. The enqueue/claim-by-
> `DELETE...RETURNING`/poll-response pattern here, in [[pgmq]], and in [[pg_cron]]
> would anchor a future idioms note on queue-table extensions. `[inferred]`

---

## Sources

- `https://raw.githubusercontent.com/supabase/pg_net/master/README.md`
  — HTTP 200 — fetched 2026-06-19.
- `https://raw.githubusercontent.com/supabase/pg_net/master/pg_net.control.in`
  — HTTP 200 — fetched 2026-06-19.
- `https://raw.githubusercontent.com/supabase/pg_net/master/sql/pg_net.sql`
  — HTTP 200 — fetched 2026-06-19.
- `https://raw.githubusercontent.com/supabase/pg_net/master/src/core.h`
  — HTTP 200 — fetched 2026-06-19.
- `https://raw.githubusercontent.com/supabase/pg_net/master/src/core.c`
  — HTTP 200 — fetched 2026-06-19.
- `https://raw.githubusercontent.com/supabase/pg_net/master/src/worker.c`
  — HTTP 200 — fetched 2026-06-19.
- `https://raw.githubusercontent.com/supabase/pg_net/master/src/event.c`
  — HTTP 200 — fetched 2026-06-19.
- `https://api.github.com/repos/supabase/pg_net/git/trees/master?recursive=1`
  — HTTP 200 — fetched 2026-06-19 (used for file discovery; `event.h`, `util.c`,
  `errors.c` skimmed-not-fetched).
</content>
</invoke>
