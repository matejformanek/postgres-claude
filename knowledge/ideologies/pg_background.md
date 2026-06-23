# pg_background — ideology / divergence-from-core notes

> Extension: `vibhorkum/pg_background` @ `master` (control reports
> `comment = 'Run SQL queries in the background'`,
> `default_version = '2.0'`, `module_pathname = '$libdir/pg_background'`,
> `relocatable = true`)
> `[verified-by-code: pg_background.control:1-4]`. 251★, C + PL/pgSQL.
> One durable "how this diverges from core PG design" doc. All `file:line`
> cites point into the **pg_background** tree (`src/pg_background.c`,
> `src/pg_background_worker.c`, `src/pg_background_internal.h`,
> `src/pg_background.h`, `pg_background.control`, `README.md`,
> `docs/ARCHITECTURE.md`), **NOT** into PG `source/`.
> Confidence tags: `[verified-by-code]` `[from-README]` `[from-comment]`
> `[inferred]` `[unverified]`.
> **Sibling note:** read this against
> [[knowledge/ideologies/pg_cron]] — the other corpus extension that drives
> the **dynamic bgworker** lifecycle as its core mechanism. They diverge sharply
> on *why* the worker exists: pg_cron launches a worker on a *schedule* and runs
> the job over a fresh **libpq** connection to its own postmaster (so the job is
> a normal client session); pg_background launches a worker *on demand* per call
> and streams results back through a **DSM/shm_mq** channel inside shared memory,
> never opening a socket. The other queue/worker siblings
> [[knowledge/ideologies/pgmq]] (pure-SQL queue, *no* C, *no* worker) and
> [[knowledge/ideologies/pgque]] (pure-SQL, ticked by an *external* scheduler)
> are the foil: pg_background is the one that reaches all the way down to the
> raw `RegisterDynamicBackgroundWorker` + `shm_mq` machinery PG normally reserves
> for parallel query. **The autonomous-transaction angle core lacks:** PostgreSQL
> has deliberately never shipped Oracle-style autonomous transactions
> (a nested block that commits independently of its caller); pg_background
> *emulates* them by running the SQL in a **separate process with its own
> transaction**, so a worker can COMMIT audit/log rows even if the launching
> transaction later rolls back `[from-README: README.md:8, 75-79, 96]`.

## Domain & purpose

pg_background runs an arbitrary SQL string in a freshly-launched **background
worker process**, hands the caller a `(pid, cookie)` handle, and lets the caller
pull the result set (or just the outcome/SQLSTATE) back later via that handle
`[from-README: README.md:8-15]`. Because the worker is a *separate backend* with
its *own* transaction, the pattern delivers what PostgreSQL core refuses to ship
natively: **autonomous-transaction semantics** — "commit/rollback independently
of the caller's transaction" `[from-README: README.md:79, 159]`. Headline uses:
audit logging that must persist even if the parent rolls back; fire-and-forget
side-effect queries; long-running maintenance that should not block the client
session; and synchronous launch-and-wait fan-out `[from-README:
README.md:96, 131-134]`.

The original upstream pg_background (the ~2014 Robert Haas demo of the dynamic
bgworker + shm_mq APIs) was three SQL-callable functions. This fork has grown
into a "production-grade" surface (v2.0): a cookie-validated v2 API, a
session-local worker hash table, `pg_background_list` / `_stats` / `_cancel` /
`_progress` observability, structured error propagation, per-worker labels, and
a 14-19 multi-version compatibility shim `[verified-by-code:
pg_background.c:243-277; pg_background.h:1-60]`. The two-file split is the spine:
`pg_background.c` is the **launcher** (runs in the user's backend);
`pg_background_worker.c` is the **worker body** (runs in the bgworker). They
communicate *only* through the DSM structs and the response shm_mq, never by
direct call `[from-comment: pg_background_worker.c:6-12]`.

## How it hooks into PG

- **`_PG_init` registers only GUCs — no static worker, no hook chain.** Three
  `DefineCustomIntVariable` calls (`pg_background.max_workers`,
  `default_queue_size`, `worker_timeout`, all `PGC_USERSET`) plus
  `MarkGUCPrefixReserved("pg_background")` on PG ≥ 15 `[verified-by-code:
  pg_background.c:291-343]`. There is **no `RegisterBackgroundWorker`** at load
  time — the worker is created at *runtime*, per call (see divergence #1).
- **Load model: plain `CREATE EXTENSION`, no `shared_preload_libraries`.**
  Because every worker is dynamic, the library only needs to be resolvable as
  `$libdir/pg_background` when `RegisterDynamicBackgroundWorker` names it via
  `bgw_library_name` `[verified-by-code: pg_background.c:754]`. `PG_MODULE_MAGIC`
  is unconditional `[verified-by-code: pg_background.c:234]`. See
  [[knowledge/idioms/catalog-conventions]].
- **`pg_background_launch(sql, queue_size, label)` → `(pid, cookie)`.** The v2
  entry point; `pg_background_submit` is the fire-and-forget twin (results
  disabled). Both call `launch_internal`, then `build_handle_tuple`
  `[verified-by-code: pg_background.c:879-909, 939-959]`. `launch_internal` is
  where the dynamic worker is born (#1).
- **SQL-callable C functions** are the standard `PG_FUNCTION_INFO_V1` fmgr
  surface — `launch`, `submit`, `result`, `detach`, `cancel`, `wait`, `list`,
  `stats`, `report_progress`, `get_progress`, `result_info`, `error_info`,
  `detach_all`, `cancel_all`, `full_sql`, `record_timeout`
  `[verified-by-code: pg_background.c:243-277]`. See [[knowledge/idioms/fmgr]].
- **DSM + shm_toc result channel.** `launch_internal` builds one DSM segment via
  `dsm_create`, lays it out with a `shm_toc` table-of-contents holding five
  keyed chunks — `INPUT`, `SQL`, `GUC`, `QUEUE`, `OUTPUT` — and a `shm_mq`
  response queue inside the `QUEUE` chunk `[verified-by-code:
  pg_background.c:677-746; pg_background_internal.h:55-61]`. The launcher is the
  queue *receiver*; the worker is the *sender* (#2).
- **Worker entry point.** `bgw_function_name = "pg_background_worker_main"` and
  `bgw_main_arg = UInt32GetDatum(dsm_segment_handle(seg))` pass the DSM handle to
  the worker, which `dsm_attach`es it and reads the toc back
  `[verified-by-code: pg_background.c:755-759; pg_background_worker.c:271-312]`.
  Inside, `BackgroundWorkerInitializeConnection(db, user,
  BGWORKER_BYPASS_ALLOWCONN)` opens the database, `RestoreGUCState` replays the
  launcher's GUCs, and `SetUserIdAndSecContext` adopts the launcher's user
  identity before running the SQL `[verified-by-code:
  pg_background_worker.c:344-418]`.
- **The handle type is a composite `(pid int4, cookie int8)`** built by
  `build_handle_tuple` `[verified-by-code: pg_background.c:565-580]`; the cookie
  is a `pg_strong_random` 64-bit value forced non-zero (#7).

## Where it diverges from core idioms

### 1. The dynamic background worker is the user-facing primitive — not infrastructure

Core PG uses `RegisterDynamicBackgroundWorker` internally for **parallel query**
(one leader spinning up transient workers it fully controls) and exposes
`RegisterBackgroundWorker` to extensions as a *boot-time* facility you wire in
`shared_preload_libraries`. pg_background instead makes the **runtime** dynamic
worker a *SQL-callable primitive*: every `pg_background_launch(...)` call fills
in a `BackgroundWorker` struct on the stack and calls
`RegisterDynamicBackgroundWorker(&worker, &worker_handle)` `[verified-by-code:
pg_background.c:748-792]`. The struct is configured with
`BGWORKER_SHMEM_ACCESS | BGWORKER_BACKEND_DATABASE_CONNECTION`,
`bgw_start_time = BgWorkerStart_ConsistentState`,
`bgw_restart_time = BGW_NEVER_RESTART` (a per-call worker must never auto-respawn
after it exits), and `bgw_notify_pid = MyProcPid` so the launcher is signalled on
startup `[verified-by-code: pg_background.c:749-760]`. The launcher then blocks in
`WaitForBackgroundWorkerStartup(worker_handle, &pid)` to learn the worker PID,
and — critically — `shm_mq_wait_for_attach(responseq)` to close the
NOTIFY-vs-DSM startup race before returning the handle to SQL `[verified-by-code:
pg_background.c:798-818]`. This is the entire reason the extension exists: it
turns a backend-internal worker-spawn API into a database feature. See
[[knowledge/idioms/parallel-state-propagation]] and core's own use in prose at
`src/backend/access/transam/parallel.c` and the registration machinery in
`src/backend/postmaster/bgworker.c`.

### 2. Results stream back through a shm_mq carrying the raw libpq wire protocol

A worker has no client socket. pg_background reuses PG's own
**`pq_redirect_to_shm_mq`** so the worker's `DestRemote` destination writes the
*libpq frontend/backend protocol* into the response shm_mq instead of a network
connection `[verified-by-code: pg_background_worker.c:320]`. The worker runs the
query through a real `Portal` with a `DestRemote` receiver, so it emits genuine
`T` (RowDescription), `D` (DataRow), `C` (CommandComplete), `E`/`N`
(Error/Notice), `A` (NotifyResponse), and `Z` (ReadyForQuery) frames
`[verified-by-code: pg_background_worker.c:613-655]`. The launcher's
`pg_background_result` SRF is then a hand-rolled **protocol state machine** that
`shm_mq_receive`s those frames and reconstructs tuples: `T` validates the
rowtype against the caller's `FROM`-clause column list, `D` is fed to
`form_result_tuple` and `SRF_RETURN_NEXT`'d, `C` collects command tags, `Z`
marks completion, `E`/`N` re-throw `[verified-by-code:
pg_background.c:1166-1399, 1277-1363]`. This is a deliberate, unusual choice:
rather than invent a private serialization, the extension **smuggles the entire
libpq protocol through shared memory** — the same trick PG's parallel executor
uses (`pqmq.c`), here surfaced as a user feature. The `T` handler even bounds
`natts` against `MaxTupleAttributeNumber` to defend against a corrupted/malicious
worker `[verified-by-code: pg_background.c:1294-1298]`. See
[[knowledge/idioms/fmgr]] (the SRF) and core `src/backend/storage/ipc/shm_mq.c`.

### 3. Autonomous transactions by process separation — the thing core refuses to ship

PostgreSQL has repeatedly declined Oracle-style autonomous transactions (a
sub-block that commits independently within the *same* backend) because the
backend is single-threaded around one transaction stack. pg_background sidesteps
the entire objection by putting the autonomous work **in a different process**:
the worker calls `StartTransactionCommand` / runs the SQL / `CommitTransactionCommand`
on its own, with no link to the launcher's transaction state
`[verified-by-code: pg_background_worker.c:394, 444; README.md:876]`. So a worker
COMMIT survives a launcher ROLLBACK — exactly the audit-logging use case
`[from-README: README.md:96, 159]`. The cost surfaces in the README's own
caveats: the worker is a *separate* transaction, so it cannot see the launcher's
uncommitted rows, and `TransactionStmt`s (`BEGIN`/`COMMIT`/`SAVEPOINT`) are
explicitly rejected inside the worker SQL `[verified-by-code:
pg_background_worker.c:587-590]`. This is the load-bearing divergence: the
feature is "autonomous transactions" spelled "separate backend", and every other
mechanism here (DSM, shm_mq, cookies, GUC copy) exists to make that one process
behave enough like the caller.

### 4. Full GUC state and security context are copied to the worker — the parallel-worker propagation contract, by hand

A fresh bgworker boots with default GUCs and no user identity. To make the
worker's SQL behave like the caller's, `launch_internal` serializes the
launcher's **entire** GUC state with `EstimateGUCStateSpace` /
`SerializeGUCState` into a DSM chunk, and the worker replays it with
`RestoreGUCState` inside a throwaway transaction at startup `[verified-by-code:
pg_background.c:681-682, 738-739; pg_background_worker.c:353-355]`. The code
comment is explicit that this mirrors how PG parallel workers propagate GUCs, and
that it copies *everything* — `search_path`, `lock_timeout`,
role-based settings — by design `[from-comment: pg_background.c:728-737]`.
Identity is propagated separately: the launcher captures
`GetUserIdAndSecContext` and `GetAuthenticatedUserId` into the input struct, and
the worker re-establishes both via `BackgroundWorkerInitializeConnection(...,
authenticated_user, ...)` and `SetUserIdAndSecContext(input->current_user_id,
input->sec_context)` `[verified-by-code: pg_background.c:699-703;
pg_background_worker.c:344-416]`. The worker even re-checks that the db/user were
not renamed during startup and ERRORs if so `[verified-by-code:
pg_background_worker.c:348-351]`. This is far more plumbing than a normal SQL
function needs — it is the parallel-query state-propagation contract reimplemented
for a general-purpose worker. See [[knowledge/idioms/guc-variables]] and
[[knowledge/idioms/parallel-state-propagation]].

### 5. Error propagation re-throws the worker's real ErrorData across the process boundary

When the worker's SQL fails, a naive shm_mq teardown would surface a generic
`08006 connection failure` to the launcher. pg_background instead reconstructs
the *original* error. In the worker, `pg_background_worker_error_exit`
`CopyErrorData`s the live error, strlcpy's its `message`/`detail`/`hint`/`context`
plus B5c source identifiers (schema/table/column/constraint name) and the
SQLSTATE into the DSM `OUTPUT` struct, then calls `EmitErrorReport` so a real
`E` frame *also* goes over the shm_mq, then `proc_exit(1)` `[verified-by-code:
pg_background_worker.c:136-255]`. On the launcher side, the `E`/`N` handler
parses the frame with `pq_parse_errornotice` and re-raises it via
`throw_untranslated_error`, which runs each field through `pg_client_to_server`
before `ThrowErrorData` — so the launcher session raises the worker's actual
SQLSTATE and message, not a synthesized one `[verified-by-code:
pg_background.c:976-994, 1240-1259]`. The worker takes pains to make this
longjmp-safe: a nested `PG_TRY` swallows OOM raised *inside* `EmitErrorReport`
(mirroring `ParallelWorkerMain`), and the SIGTERM handler deliberately sets
`QueryCancelPending` (catchable ERROR) rather than `ProcDiePending` (FATAL that
bypasses `PG_CATCH` and looks like a crash to the postmaster) `[from-comment:
pg_background_worker.c:205-213, 686-708]`. See [[knowledge/idioms/error-handling]].

### 6. Two-process IPC built on publish-flag memory barriers, not locks

The `OUTPUT` struct is written by the worker and read by the launcher with **no
lock** — coordination is by hand-rolled publish flags + memory barriers. The
worker writes the error block, issues `pg_write_barrier()`, then strlcpy's
`error_sqlstate` *last* as the publish flag; the launcher tests `error_sqlstate`
first and only issues `pg_read_barrier()` + reads the rest if it is non-empty
`[verified-by-code: pg_background_worker.c:189-196;
pg_background_internal.h:158-170]`. The same idiom guards the
`result_row_count`+`command_tag` pair via `result_published`, so a reader can
never pair a fresh row count with a stale tag `[verified-by-code:
pg_background_worker.c:646-653; pg_background_internal.h:172-181]`. v2.0 split the
old single fixed-data chunk into separate `INPUT` (launcher→worker) and `OUTPUT`
(worker→launcher) toc keys specifically to clarify barrier ordering and avoid
cache-line bouncing `[from-comment: pg_background_internal.h:42-54]`. This is
lock-free shared-memory discipline an ordinary extension never has to reason
about. See [[knowledge/idioms/memory-contexts]] (the DSM/context boundary).

### 7. A cryptographic cookie defends a PID-keyed handle against reuse

The handle is `(pid, cookie)`, where `cookie` is a `pg_strong_random` 64-bit
value forced non-zero (so a zero-initialized stale handle can never accidentally
match) `[verified-by-code: pg_background.c:401-419]`. Every result/detach/cancel
entry point validates `info->cookie == cookie_in` before acting, raising a
"cookie mismatch" ERROR on a stale handle `[verified-by-code:
pg_background.c:1101-1105, 1494-1497, 2440-2442]`. The threat model is **PID
reuse**: a session can outlive a worker, the OS can recycle the PID, and a bare
PID handle would then address the wrong worker. `save_worker_info` adds belt-and-
braces: if a hash entry for a just-reused PID exists under a *different* user, it
`TerminateBackgroundWorker` + `dsm_detach`es the worker it just launched and
ERRORs rather than risk cross-user confusion `[from-comment + verified-by-code:
pg_background.c:2101-2150]`. Core composite handle types (e.g. a plain
`pg_cancel_backend(pid)`) carry no such anti-reuse token — this is a security
hardening the simple original never had.

### 8. Cancellation is cooperative-only because SIGKILL would crash the cluster

There is no force-stop. `pgbg_request_cancel` sets the mutable
`input->cancel_requested` flag in the DSM, and `pgbg_send_cancel_signals` sends a
single `SIGTERM` (`kill(info->pid, SIGTERM)`) `[verified-by-code:
pg_background.c:1811-1828, 1885-1886]`. The worker's SIGTERM handler converts it
to a catchable `QueryCancelPending` that surfaces at the next
`CHECK_FOR_INTERRUPTS` and exits via `proc_exit(1)` `[verified-by-code:
pg_background_worker.c:696-708]`. The code header spells out *why* it never
escalates to SIGKILL: the postmaster treats any child killed by an uncaught
signal as a crash and triggers cluster-wide crash recovery — so a force-kill of
one worker would drop every session `[from-comment: pg_background.c:1839-1850]`.
On Windows, signal cancel is unavailable entirely, so only the pre-execution
flag check works `[from-comment: pg_background.c:1858-1887]`. This constraint —
"you cannot reliably kill a bgworker without crashing the server" — is a real
core limitation the extension has to design *around*, not a choice.

### 9. Resource lifecycle pinned to DSM detach callbacks, with launcher-owned tracking

The launcher pins the DSM mapping (`dsm_pin_mapping`) so transaction cleanup
won't yank it from under a still-running worker, and registers
`on_dsm_detach(seg, cleanup_worker_info, pid)` so the session-local hash entry is
reaped when the segment finally detaches `[verified-by-code:
pg_background.c:844-852, 2152]`. The `BackgroundWorkerHandle` is explicitly
**PostgreSQL-owned**: a prominent comment forbids `pfree`ing it (PG frees it when
the worker exits or the session ends), a footgun that the original demo did not
have to warn about `[from-comment: pg_background.c:762-774;
pg_background_internal.h:198]`. The launcher keeps a rich per-worker
`pg_background_worker_info` (cookie, seg, handle, responseq, label, full SQL
text, timestamps) in a dedicated `WorkerInfoMemoryContext` child of
`TopMemoryContext` so it survives statement boundaries `[verified-by-code:
pg_background_internal.h:200-260; pg_background.c:363-372]`. This launcher-side
bookkeeping is the production-grade layer the upstream 3-function demo lacked.

## Notable design decisions (with cites)

- **The worker SQL runs in two PG_TRY phases: pre-commit and commit.** Deferred
  constraint triggers and AFTER triggers fire during
  `CommitTransactionCommand`, so commit-time errors (deferred FK 23503, deferred
  unique 23505, cancel 57014) are caught by a *separate sequential* PG_TRY after
  the execution PG_TRY's `PG_END_TRY`, preserving the "exactly one
  EmitErrorReport per error" invariant `[from-comment + verified-by-code:
  pg_background_worker.c:432-460]`.
- **Multi-statement SQL, last-command result wins.** The worker
  `pg_parse_query`s the whole string and runs each statement through its own
  portal; only the final command gets a `DestRemote` receiver (earlier ones get
  `DestNone`), and `output->result_row_count`/`command_tag` reflect the last
  command `[verified-by-code: pg_background_worker.c:575-656]`.
- **COPY is rejected.** `G`/`H`/`W` frames (COPY-in/out/both) raise
  `ERRCODE_FEATURE_NOT_SUPPORTED` in the launcher's protocol reader — the shm_mq
  channel does not model COPY streaming `[verified-by-code:
  pg_background.c:1353-1359]`.
- **Binary result format, with a text fallback per column.** The worker requests
  binary output format (`format = 1`), and the launcher's `T` handler accepts a
  column only if the type has a binary receive function (`exists_binary_recv_fn`)
  matching the requested type, else it must be declared `text` `[verified-by-code:
  pg_background_worker.c:585, 618; pg_background.c:1305-1331]`.
- **`pg_background_submit` is fire-and-forget.** It sets `result_disabled`, so
  `pg_background_result` refuses to read it; any NOTIFY a submit-worker raises is
  written to the shm_mq but never consumed and so effectively dropped
  `[from-comment: pg_background.c:1107-1110, 1261-1274]`.
- **Non-blocking receive + WaitLatch, not a blocking shm_mq_receive.** v2.0 (C3)
  switched the result loop to a non-blocking `shm_mq_receive(..., true)` plus a
  250 ms `WaitLatch` that re-checks worker liveness, so a worker that attaches
  but never sends and never exits cannot hang the launcher forever
  `[from-comment + verified-by-code: pg_background.c:1182-1204]`.
- **14-19 multi-version shims live in one header.** `pg_background.h` keeps only
  the still-load-bearing `pg_analyze_and_rewrite_compat` and a `TupleDescAttr`
  fallback; the worker carries `PortalDefineQuery`/`PortalRun` arity shims for
  the PG 18 portal-API change `[verified-by-code: pg_background.h:30-61;
  pg_background_worker.c:73-100]`.

## Links into corpus

- [[knowledge/ideologies/pg_cron]] — the closest sibling: the other corpus
  extension whose core mechanism is the **bgworker lifecycle**. **Contrast:**
  pg_cron runs scheduled jobs over a fresh *libpq connection* to its own
  postmaster (the job is a normal client session); pg_background runs on-demand
  per-call workers and streams results through *DSM/shm_mq* in shared memory,
  with no socket — and pins the launcher's GUC + identity into the worker the way
  parallel query does.
- [[knowledge/ideologies/pgmq]] / [[knowledge/ideologies/pgque]] — the
  queue-without-a-worker foils: pgmq is pure SQL with no C and no bgworker;
  pgque is pure SQL ticked by an *external* scheduler. pg_background is the
  opposite extreme — it reaches all the way down to
  `RegisterDynamicBackgroundWorker` + `shm_mq`.
- [[knowledge/idioms/parallel-state-propagation]] — pg_background reimplements
  the parallel-worker contract (`SerializeGUCState`/`RestoreGUCState`,
  user/sec-context copy, `shm_toc` layout) for a general-purpose worker (#1, #4);
  core's version lives around `src/backend/access/transam/parallel.c`.
- [[knowledge/idioms/guc-variables]] — three `PGC_USERSET`
  `DefineCustomIntVariable`s + `MarkGUCPrefixReserved`, *and* the wholesale GUC
  copy to the worker (#4).
- [[knowledge/idioms/error-handling]] — the worker's `CopyErrorData` →
  DSM + `EmitErrorReport` → launcher `pq_parse_errornotice` →
  `throw_untranslated_error` re-throw chain (#5); the
  `QueryCancelPending`-not-`ProcDiePending` SIGTERM choice; the nested-PG_TRY
  OOM swallow.
- [[knowledge/idioms/fmgr]] — the `PG_FUNCTION_INFO_V1` surface and the
  `pg_background_result` SRF that drives the protocol state machine (#2).
- [[knowledge/idioms/memory-contexts]] — `WorkerInfoMemoryContext` for
  launcher-side tracking that outlives statements (#9); the lock-free
  publish-flag + memory-barrier DSM discipline (#6).
- [[knowledge/idioms/catalog-conventions]] — plain `CREATE EXTENSION`, no
  `shared_preload_libraries`, because the worker is dynamic (#1 load model).
- Core analogs in prose: dynamic-worker registration in
  `src/backend/postmaster/bgworker.c`; the shm_mq ring buffer in
  `src/backend/storage/ipc/shm_mq.c`; the parallel-query DSM/TOC + GUC/identity
  propagation in `src/backend/access/transam/parallel.c` (and the
  pqmq protocol-over-shm_mq redirect the worker reuses).

## Sources

| URL | HTTP |
|---|---|
| https://api.github.com/repos/vibhorkum/pg_background/git/trees/master?recursive=1 | 200 |
| https://raw.githubusercontent.com/vibhorkum/pg_background/master/pg_background.control | 200 |
| https://raw.githubusercontent.com/vibhorkum/pg_background/master/src/pg_background.h | 200 |
| https://raw.githubusercontent.com/vibhorkum/pg_background/master/src/pg_background_internal.h | 200 |
| https://raw.githubusercontent.com/vibhorkum/pg_background/master/src/pg_background.c | 200 |
| https://raw.githubusercontent.com/vibhorkum/pg_background/master/src/pg_background_worker.c | 200 |
| https://raw.githubusercontent.com/vibhorkum/pg_background/master/README.md | 200 (first fetch returned a CDN-cached *pg_amqp* README; re-fetch returned the correct pg_background README — see Fetch notes) |
| https://raw.githubusercontent.com/vibhorkum/pg_background/master/docs/ARCHITECTURE.md | 200 |

**Fetch notes / substitutions:**
- `master` resolved fine (no `main` fallback needed). The prompt's manifest hint
  (`README.md`, `*.control`, `*.sql`, `*.c` at root) was **stale**: this fork has
  reorganized C sources under `src/` (`src/pg_background.c` 2893 lines,
  `src/pg_background_worker.c` 711 lines, plus two private headers) and the
  install SQL under `extension/` and `sql/`. The control file is
  `pg_background.control` at root, `default_version = '2.0'`.
- **README CDN glitch:** the first `raw.githubusercontent.com` fetch of
  `README.md` returned the *pg_amqp* project README verbatim (a stale-cache /
  edge mismatch). An immediate re-fetch returned the correct
  "pg_background: Production-Grade Background SQL" README (md5 differed). All
  `[from-README]` cites in this doc are against the correct re-fetched copy.
- The install SQL (`extension/pg_background--2.0.sql`, ~49 KB) and the version
  upgrade scripts were **not** read line-by-line; the C entry points
  (`PG_FUNCTION_INFO_V1` registrations) and the README were sufficient to
  characterize the SQL-callable surface. Claims about the *exact* SQL
  signatures rely on the README's function tables `[from-README:
  README.md:556-570]` cross-checked against the C `PG_FUNCTION_INFO_V1` list.
- The launcher's `result_info`/`error_info`/`get_progress`/`stats` readers were
  confirmed to exist and to follow the same cookie-validate + barrier-read
  pattern but were not all transcribed; the divergence claims rest on the
  shared structs (`pg_background_internal.h`) and the representative readers
  cited above.
- This is a heavily-evolved fork of the original ~2014 Robert Haas
  dynamic-bgworker + shm_mq demo. Where a feature is clearly v1.9/v1.10/v2.0
  ("production-grade" additions — cookies, labels, list/stats, structured
  errors), the version tag is taken from in-code comments `[from-comment]` and
  is not independently verified against the git history.
