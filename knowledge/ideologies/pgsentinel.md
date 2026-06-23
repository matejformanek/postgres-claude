# pgsentinel — ideology / divergence notes

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `pgsentinel/pgsentinel` @ branch `master`. All `file:line` cites below
> point into that repo (not `source/`), since this doc characterizes an
> *external* extension's divergence from core idioms. Cites verified against the
> files fetched on 2026-06-23 (see Sources footer). Line numbers are for the
> `master` blobs as fetched.

pgsentinel is an Oracle-ASH-style sampler: a background worker wakes on a timer,
snapshots which sessions are active, and writes each snapshot row into an
in-memory ring buffer exposed as the `pg_active_session_history` view
(`README.md:18-23`, `src/pgsentinel.control:1`) `[from-README]`
`[verified-by-code]`. **Headline divergence:** to capture the *non-normalized
query text and command type of every other running backend*, it installs a
`post_parse_analyze_hook` in *all* backends that writes each backend's just-parsed
query string into a shared-memory slot keyed by that backend's `PGPROC` index
(`src/get_parsedinfo.c:101-187`), then the sampler reads it back by running
**actual SQL over `pg_stat_activity` via SPI** — joined to its own
`get_parsedinfo(pid)` SRF — from inside the bgworker
(`src/pgsentinel.c:94-143`, `978-996`) `[verified-by-code]`. Core PG has no
sanctioned way for one backend to read another backend's transient parse state;
pgsentinel manufactures one out of a hook + a `PGPROC`-indexed shmem array.

## Domain & purpose

pgsentinel answers: *what were my sessions actually doing over time?* It samples
`pg_stat_activity` on a period (default 1s) and keeps a configurable ring of
recent samples so a DBA can reconstruct wait-event / state / blocker history
without polling the view by hand (`README.md:9-23`) `[from-README]`. The control
comment is just `'active session history'` (`src/pgsentinel.control:1`)
`[verified-by-code]`. It deliberately pairs with `pg_stat_statements`: the ASH
`queryid` column links a sampled session to that view, and a second ring
(`pg_stat_statements_history`) snapshots the per-queryid statement stats at the
same instant, but *only* for queryids that were active in the latest sample
(`README.md:25-32`, `src/pgsentinel.c:198-227`) `[from-README]`
`[verified-by-code]`. It is the historical-sampling sibling of
pg_stat_statements (aggregate counters) and the wait-event view (instantaneous
state), reifying the *time dimension* neither of those keeps.

## How it hooks into PG

pgsentinel **requires** `shared_preload_libraries`: most of `_PG_init` returns
early unless `process_shared_preload_libraries_in_progress`, and the SRF
`ereport(ERROR …"must be loaded via shared_preload_libraries")` if the ring is
absent (`src/pgsentinel.c:1416-1417`, `1473-1476`) `[verified-by-code]`. The
README states the restart requirement plainly (`README.md:14-16`)
`[from-README]`.

- **Two hooks + one static bgworker.** `_PG_init` chains `shmem_startup_hook`
  and `post_parse_analyze_hook` (saving the prior pointer each time), and on
  PG ≥ 15 also `shmem_request_hook`; pre-15 it calls `ash_shmem_request()`
  inline (`src/pgsentinel.c:1419-1433`) `[verified-by-code]`. Then it fills a
  `BackgroundWorker` struct and calls **`RegisterBackgroundWorker(&worker)`**
  — the static, preload-time registration path — with
  `BGWORKER_SHMEM_ACCESS | BGWORKER_BACKEND_DATABASE_CONNECTION`,
  `bgw_start_time = BgWorkerStart_ConsistentState`, and
  `bgw_library_name`/`bgw_function_name = "pgsentinel"/"pgsentinel_main"`
  (`src/pgsentinel.c:1435-1457`) `[verified-by-code]`.
- **Shmem request.** `ash_shmem_request` calls `RequestAddinShmemSpace` for
  four regions (ASH ring, proc-entry array, a 1-element counter struct,
  optionally the pgssh ring) and `RequestNamedLWLockTranche` for each
  (`src/pgsentinel.c:1996-2016`) `[verified-by-code]`. **It never acquires any
  of those LWLocks — see divergence 3.**
- **Shmem startup.** `ash_shmem_startup` carves ~16 separate `ShmemInitStruct`
  regions: the `ashEntry` array plus one fixed-width char buffer per text
  column (usename, datname, query, …), wiring each `ashEntry`'s `char *` field
  to point into its buffer at a `NAMEDATALEN` or
  `pgstat_track_activity_query_size` stride (`src/pgsentinel.c:434-751`)
  `[verified-by-code]`. The `ProcEntryArray` (one slot per possible backend)
  and its query/cmdtype buffers are allocated the same way
  (`src/pgsentinel.c:474-515`) `[verified-by-code]`.
- **GUCs.** Six `DefineCustom*Variable` calls: `pgsentinel_ash.sampling_period`
  and `.track_idle_trans` (`PGC_SIGHUP`), `.max_entries`,
  `pgsentinel_pgssh.max_entries`, `.enable`, and `pgsentinel.db_name`
  (`PGC_POSTMASTER`; `db_name` is `GUC_SUPERUSER_ONLY`)
  (`src/pgsentinel.c:1322-1398`) `[verified-by-code]`. Placeholders are flushed
  with the legacy `EmitWarningsOnPlaceholders` (`src/pgsentinel.c:1363,1389`)
  rather than `MarkGUCPrefixReserved` `[verified-by-code]`.
- **Output SRFs.** `pg_active_session_history()` and
  `pg_stat_statements_history()` are `LANGUAGE C STRICT VOLATILE PARALLEL SAFE`
  set-returning functions, each wrapped in a like-named view granted to PUBLIC;
  `get_parsedinfo(int)` is the internal helper SRF (`src/pgsentinel--1.0.sql:4-83`)
  `[verified-by-code]`. All three use `SFRM_Materialize` + a tuplestore
  (`src/pgsentinel.c:1483-1502`, `src/get_parsedinfo.c:206-211`)
  `[verified-by-code]`.

## Where it diverges from core idioms — THE headline

### 1. It reads other backends' transient parse state via a hook + a PGPROC-indexed shmem array

This is the un-Postgres move. Core exposes a backend's *current* query text in
`pg_stat_activity` only through `pgstat_report_activity`, and never exposes the
parsed `Query` (queryid / command type) of *another* backend. pgsentinel
fabricates that channel:

- Every backend runs `getparsedinfo_post_parse_analyze` after parse-analysis.
  It computes its own slot index as `MyProc - ProcGlobal->allProcs` — i.e. it
  uses its position in the global `PGPROC` array as a shmem array index — and
  `memcpy`s the source text into `ProcEntryArray[i].query`, sets `.cmdtype` from
  `query->commandType`, and stores `query->queryId`
  (`src/get_parsedinfo.c:101-187`) `[verified-by-code]`.
- For utility statements (queryId == 0) it **manufactures a queryid** by hashing
  the query string with `hash_any_extended` (PG ≥ 11) / `hash_any`
  (`src/get_parsedinfo.c:55-69,175-186`) `[verified-by-code]` — inventing an
  identifier core would leave as 0.
- It re-implements pg_stat_statements' query-text trimming: honoring
  `query->stmt_location`/`stmt_len` and stripping leading/trailing
  `scanner_isspace` whitespace so the captured text matches lexer behavior
  (`src/get_parsedinfo.c:107-138`) `[verified-by-code]`.
- The reader, `get_parsedinfo(pid)`, walks **`ProcGlobal->allProcs[0 ..
  allProcCount]`**, and for a matching (or `-1` wildcard) pid returns that
  slot's stored queryid / query / cmdtype (`src/get_parsedinfo.c:214-236`)
  `[verified-by-code]`. So one SRF reads the parse state another backend wrote
  into shmem under no lock — the slot is reused across the lifetime of whatever
  backend currently owns that `PGPROC`.

### 2. The sampler runs real SQL over pg_stat_activity via SPI, then joins it to its own SRF

Rather than read `BackendStatusArray` / `PgBackendStatus` directly in C (the way
`pg_stat_get_activity` does), the bgworker connects to a database and **executes
a literal `SELECT … from pg_stat_activity act … , get_parsedinfo(act.pid) gpi`**
through SPI on every tick (`src/pgsentinel.c:978-996`) `[verified-by-code]`. The
query is a giant version-#ifdef'd string constant (one variant per PG major from
9.6 through ≥16) that also self-joins `pg_stat_activity` to itself on
`(pg_blocking_pids(act.pid))[1]` to capture the blocker's pid and state, and
filters `act.pid != pg_backend_pid()` to skip itself
(`src/pgsentinel.c:94-196`) `[verified-by-code]`. The lateral
`get_parsedinfo(act.pid)` join is what pulls each active backend's captured
query text/queryid/cmdtype (divergence 1) into the same row. So the "sampler" is
really a SQL client embedded in a worker — it inherits the planner, the snapshot,
and the parser, and pays a full transaction per sample
(`SetCurrentStatementStartTimestamp` → `StartTransactionCommand` →
`PushActiveSnapshot` → `SPI_execute` → `CommitTransactionCommand`,
`src/pgsentinel.c:967-1253`) `[verified-by-code]`.

### 3. Four LWLock tranches are *requested* but *never acquired* — the rings are lock-free

`ash_shmem_request` dutifully calls `RequestNamedLWLockTranche` four times
(`src/pgsentinel.c:2003,2006,2009,2014`) `[verified-by-code]`, yet **nothing in
the codebase ever calls `GetNamedLWLockTranche`, `LWLockAcquire`, or any
spinlock** — verified by absence across `pgsentinel.c` and `get_parsedinfo.c`
`[verified-by-code]`. The bgworker writes ring slots with bare `memcpy`s
(`ash_entry_store`, `src/pgsentinel.c:797-860`), the per-backend hook `memcpy`s
into its `PGPROC`-indexed slot with no synchronization
(`src/get_parsedinfo.c:140-187`), and the reader SRFs scan the ring with no lock
held (`src/pgsentinel.c:1504-…`). The ring write index lives in a 1-element
shared `IntEntryArray[0].inserted`, advanced as `(inserted % max_entries) + 1`
non-atomically (`src/pgsentinel.c:883`) `[verified-by-code]`. Correctness rests
on the *assumption* that only the single sampler writes the ASH ring and only
the owning backend writes its own proc slot — an implicit single-writer
discipline standing in for the locking core would require. This is the sharpest
divergence from core shmem hygiene: requesting a lock you never take is itself a
tell.

### 4. Text columns are fixed-width char arenas indexed by slot, not palloc'd strings

Every text-valued ASH column is a separate flat shmem buffer of
`max_entries * NAMEDATALEN` (or `* pgstat_track_activity_query_size` for query
text), and each `ashEntry.char *` field is pre-pointed at its row's offset at
startup (`src/pgsentinel.c:517-740`) `[verified-by-code]`. Writes `memcpy` at
most `NAMEDATALEN-1` / `track_activity_query_size-1` bytes and rely on the
buffers being zeroed once (`MemSet` at startup) for NUL-termination
(`src/pgsentinel.c:817-842`) `[verified-by-code]`. The SRF treats an empty
first byte (`[i].x[0] != '\0'`) as the NULL sentinel
(`src/pgsentinel.c:1526-1527,1554-1576`) `[verified-by-code]`. This is a
hand-rolled column-store in shmem rather than core's variable-length palloc'd
text — chosen because shmem can't hold palloc pointers across backends.

### 5. The ring is sized at NAMEDATALEN even for values that overflow it

Several captured columns are wider than `NAMEDATALEN` in reality —
`application_name`, `wait_event`, and especially `query`/`top_level_query` — yet
all non-query text buffers are `NAMEDATALEN`-strided (`src/pgsentinel.c:383-409`)
`[verified-by-code]`. `application_name` and the blocker/wait strings are
silently truncated to 63 bytes. The query text gets the wider
`pgstat_track_activity_query_size` arena (`src/pgsentinel.c:399-405,656-688`),
matching the README's instruction to bump `track_activity_query_size`
(`README.md:62-63`) `[from-README]`. Tradeoff: a flat fixed stride keeps slot
addressing arithmetic trivial at the cost of correctness for long identifiers.

### 6. Privilege filtering is bolted on at read time, mimicking pg_stat_activity

Because the ring is readable by PUBLIC (`src/pgsentinel--1.0.sql:42`), the SRF
re-implements pg_stat_activity's text-redaction rule itself: it computes
`is_allowed_role = IS_ALLOWED_ROLE(userid)` — a version-#ifdef'd macro over
`pg_read_all_stats` / `ROLE_PG_READ_ALL_STATS` / `DEFAULT_ROLE_READ_ALL_STATS`
(`src/pgsentinel.c:44-51`) — and only emits the query / top_level_query columns
when `is_allowed_role || usesysid == userid`
(`src/pgsentinel.c:1469-1470,1638-1644`) `[verified-by-code]`. So the security
boundary core enforces in the catalog view is re-coded in C in the extension.

## Notable design decisions (with cites)

- **`PgSentinelHasBeenLoaded()` gate each tick.** Before sampling, the worker
  checks `get_extension_oid(EXTENSION_NAME, true)` and whether the extension
  script is still being created, and *skips* the sample (via `goto letswait`)
  if `CREATE EXTENSION` hasn't finished — so the worker can start at
  `BgWorkerStart_ConsistentState` before the SQL objects exist
  (`src/pgsentinel.c:971-976`, `1967-1990`) `[verified-by-code]`.
- **Classic WaitLatch loop.** `WaitLatch(MyLatch, WL_LATCH_SET | WL_TIMEOUT |
  WL_POSTMASTER_DEATH, period*1000, PG_WAIT_EXTENSION)` → `ResetLatch` →
  `CHECK_FOR_INTERRUPTS` → `proc_exit(1)` on postmaster death
  (`src/pgsentinel.c:935-949`) `[verified-by-code]`. Signal handlers are the
  hand-rolled pre-`SignalHandlerForConfigReload` style: bespoke
  `pgsentinel_sigterm`/`_sighup` that set a `volatile sig_atomic_t` flag and
  `SetLatch` (`src/pgsentinel.c:769-795`) `[verified-by-code]`.
- **`bgw_restart_time` is a custom 2s** via `ash_restart_wait_time`
  (`src/pgsentinel.c:87,1448`) `[verified-by-code]` — the worker is meant to
  come back fast after a crash, not stay down (`BGW_NEVER_RESTART` would lose
  history collection).
- **Single-DB sampling.** The worker connects to exactly one database
  (`pgsentinel.db_name`, default `postgres`) via
  `BackgroundWorkerInitializeConnection` (`src/pgsentinel.c:912-917`); ASH for
  other databases' query *text* is whatever `pg_stat_activity` exposes
  cross-DB, but `get_parsedinfo`'s catalog-free `PGPROC` scan works regardless
  of DB `[inferred]`.
- **pgssh ring only sampled when sessions were active.** The
  `pg_stat_statements_history` snapshot runs only if `gotactives && pgssh_enable`,
  and its query restricts to queryids present in the most recent ASH sample
  (`src/pgsentinel.c:204-226,1257-1310`) `[verified-by-code]` — avoiding a full
  pg_stat_statements dump every tick.
- **`get_parsedinfo` SRF leaks-by-design on early datums.** It uses the
  pattern `if (CStringGetTextDatum(...)) values[n] = ...; else nulls[n] = true`
  (`src/get_parsedinfo.c:221-232`) — `CStringGetTextDatum` always allocates, so
  the "else" never fires; a quirk inherited into the ASH SRF too
  (`src/pgsentinel.c:1515-1522` etc.) `[verified-by-code]`.
- **`_PG_fini` only restores two of the three hooks** (shmem_startup +
  post_parse_analyze, not shmem_request) (`src/pgsentinel.c:1959-1965`)
  `[verified-by-code]` — moot under preload (no unload) but an asymmetry.
- **Version compat by `#if PG_VERSION_NUM` everywhere**, not a `version_compat.h`
  shim: the SPI query strings, the `leader_pid`/`query_id`/`backend_type`
  columns, the `JumbleState` hook signature, the privilege macro, and the
  pg_stat_statements column renames (`total_time`→`total_exec_time`,
  `blk_*_time`→`shared_blk_*_time`) are all inline ifdefs spanning 9.6→17
  (`src/pgsentinel.c:45-51,94-227,239-241`, `src/get_parsedinfo.c:33-37,88-92,151-155`,
  `src/pgsentinel.h:16-20`) `[verified-by-code]`.

## Links into corpus

- [[bgworker-and-extensions]] — static `RegisterBackgroundWorker` at preload,
  the `BackgroundWorker` flag/start-time fields, `BackgroundWorkerInitializeConnection`,
  and the `WaitLatch` + bespoke-signal-handler loop are all the canonical
  bgworker idioms (`src/pgsentinel.c:1435-1457`, `935-949`).
- [[memory-contexts]] — the long-lived `pgsentinel loop context` under
  `TopMemoryContext` reset every tick (`src/pgsentinel.c:919-923,1311`); SRF
  output built in `ecxt_per_query_memory` (`src/pgsentinel.c:1490-1502`).
- [[locking]] / [[locking-overview]] — the *anti-example*: tranches requested,
  never acquired; ring rings written lock-free under an implicit single-writer
  assumption (divergence 3).
- [[gucs-config]] — six `DefineCustom*Variable` + legacy
  `EmitWarningsOnPlaceholders` (`src/pgsentinel.c:1322-1398`).
- [[fmgr-and-spi]] — SPI-in-a-bgworker sampling (`src/pgsentinel.c:978-1253`)
  and `SFRM_Materialize` SRFs (`src/pgsentinel.c:1483-1502`).
- Sibling ideologies / subsystems: [[pg_tracing]] (closest sibling — also a
  shmem-ring observability extension with a bgworker, but builds its own ring in
  C and *does* take a tranche lock; pgsentinel instead samples via SQL and skips
  the lock), [[pg_stat_statements]] (pgsentinel snapshots its view and copies its
  query-text trimming + queryid logic), [[pgaudit]] / [[pg_qualstats]]
  (hook-chain observers layered on `_PG_init`). A pgstat / backend-status
  subsystem doc is the natural home for the `pg_stat_activity` /
  `BackendStatusArray` contrast.

> Corpus gap: there is no idiom doc for **"reading another backend's transient
> parse state from a sampler"** — the `post_parse_analyze_hook` writing into a
> `PGPROC`-indexed shmem array (`MyProc - ProcGlobal->allProcs`) so a separate
> worker can read it back. pgsentinel is the canonical example; worth an
> `idioms/cross-backend-parse-state-capture.md`.
> Corpus gap: no idiom doc for the **"request-tranche-but-never-acquire /
> implicit single-writer shmem ring"** pattern, nor for the **fixed-width
> NAMEDATALEN char-arena-as-column-store** layout (divergence 4) that several
> shmem extensions reach for because palloc pointers can't cross backends.

## Sources

All fetched 2026-06-23.

- Tree listing: `https://api.github.com/repos/pgsentinel/pgsentinel/git/trees/master?recursive=1` — 200
- `https://raw.githubusercontent.com/pgsentinel/pgsentinel/master/README.md` — 200 (188 lines)
- `https://raw.githubusercontent.com/pgsentinel/pgsentinel/master/src/pgsentinel.control` — 200 (4 lines)
- `https://raw.githubusercontent.com/pgsentinel/pgsentinel/master/src/pgsentinel.h` — 200 (34 lines)
- `https://raw.githubusercontent.com/pgsentinel/pgsentinel/master/src/pgsentinel.c` — 200 (2016 lines)
- `https://raw.githubusercontent.com/pgsentinel/pgsentinel/master/src/get_parsedinfo.c` — 200 (238 lines)
- `https://raw.githubusercontent.com/pgsentinel/pgsentinel/master/src/pgsentinel--1.0.sql` — 200 (83 lines)
- `https://raw.githubusercontent.com/pgsentinel/pgsentinel/master/src/pgsentinel.conf` — 200 (3 lines; confirms `shared_preload_libraries` + pgssh enable for regression)
- `https://raw.githubusercontent.com/pgsentinel/pgsentinel/master/src/Makefile` — 200 (fetched; PGXS build wiring, not cited)

Skimmed-but-not-fetched (paths resolved against the tree, behavior inferred from
call sites in the cited files): `src/pgsentinel--1.0--1.3.1.sql`,
`src/pgsentinel--1.3.1--1.4.0.sql`, `src/pgsentinel--1.4.0--1.4.1.sql` (extension
upgrade scripts), `src/sql/pgsentinel-test.sql`,
`src/expected/pgsentinel-test.out`. No 404s; no path substitutions needed.
