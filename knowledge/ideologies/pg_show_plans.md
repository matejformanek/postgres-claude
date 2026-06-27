# pg_show_plans — ideology / divergence notes

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `cybertec-postgresql/pg_show_plans` @ branch `master`. All `file:line`
> cites below point into that repo (not `source/`), since this doc characterizes
> an *external* extension's divergence from core idioms. Cites verified against
> the files fetched on 2026-06-27 (see Sources footer). Line numbers are for the
> `master` blobs as fetched.

pg_show_plans answers "what is every running backend's query plan, right now?"
— the live-plan analogue of `pg_stat_activity`'s live-query view. **Headline
divergence:** every backend, inside its own `ExecutorStart` hook, runs the full
`EXPLAIN` machinery on its own plan tree (`NewExplainState` → `ExplainPrintPlan`)
and `memcpy`s the rendered text into a *self-owned, PID-keyed shared-memory hash
entry* (`pg_show_plans.c:495-502`, `317-322`) `[verified-by-code]`. Core PG
renders a plan only on demand for the one session that asked (`EXPLAIN`); it
never materializes every backend's plan text into shmem on every execution. This
extension turns plan-rendering from a pull (one session, one query) into a push
(all sessions, every execution), and pays a measured ~14% pgbench penalty for it
(`README.md:103`) `[from-README]`. The single-writer-per-PID-entry discipline,
not an LWLock, is what keeps that shared write safe.

## Domain & purpose

pg_show_plans is a live operational-introspection tool: a DBA selects
`pg_show_plans` and sees the current `EXPLAIN` output of every executing
statement across the cluster, optionally in `text` / `json` / `yaml` / `xml`
(`README.md:1-4`, `pg_show_plans.control:2`) `[from-README]`
`[verified-by-code]`. It is the plan-shaped sibling of `pg_stat_activity` (which
shows live query *text* but not the plan) and a complement to
`pg_stat_statements` (aggregate post-hoc stats, no live plan). It handles nested
plans (a function that runs a query produces level-0 + level-1 plans) up to
`MAX_NEST_LEVEL = 10` (`pg_show_plans.c:43`, `README.md:128-132`)
`[verified-by-code]` `[from-README]`. The control file marks the extension
`relocatable = true` (`pg_show_plans.control:5`) `[verified-by-code]`.

## How it hooks into PG

pg_show_plans **requires** `shared_preload_libraries`: `_PG_init` returns early
unless `process_shared_preload_libraries_in_progress`
(`pg_show_plans.c:166-167`), and the SRF guards with `shmem_safety_check()` that
`ereport(ERROR …"Add 'pg_show_plans' to 'shared_preload_libraries'")` if shmem
is absent (`pg_show_plans.c:400-405`, `572`) `[verified-by-code]`. README states
the restart requirement (`README.md:25-37`) `[from-README]`.

- **Two executor hooks + two shmem hooks, all chained.** `_PG_init` saves the
  prior pointer for each of `shmem_startup_hook`, `ExecutorStart_hook`,
  `ExecutorRun_hook`, and (PG ≥ 15) `shmem_request_hook`, installing its own
  (`pg_show_plans.c:211-225`) `[verified-by-code]`. Note: it hooks
  `ExecutorStart`/`ExecutorRun` but **not** `ExecutorFinish`/`ExecutorEnd` — the
  plan is captured at start and cleared at run-unwind (divergence 3).
- **Shmem request.** On PG ≥ 15 `pgsp_shmem_request` calls
  `RequestAddinShmemSpace(shmem_required())` + `RequestNamedLWLockTranche(
  "pg_show_plans", 1)`; pre-15 the same two calls run inline in `_PG_init`
  (`pg_show_plans.c:416-425`, `215-216`) `[verified-by-code]`. Sizing is
  `MAXALIGN(sizeof(pgspSharedState))` + `hash_estimate_size(MaxConnections,
  offsetof(pgspEntry,plan)+max_plan_length)` (`pg_show_plans.c:228-242`)
  `[verified-by-code]`.
- **Shmem startup.** `pgsp_shmem_startup` `ShmemInitStruct`s the
  `pgspSharedState` (wiring `pgsp->lock` to the named tranche) and
  `ShmemInitHash`es a `MaxConnections`-sized hash keyed by `pid`, with custom
  `gen_hash_key`/`compare_hash_key` (`pg_show_plans.c:427-466`, `244-257`)
  `[verified-by-code]`.
- **GUCs.** Three `DefineCustom*Variable`: `pg_show_plans.is_enabled` (bool,
  default true), `.max_plan_length` (int, 16K, range 1K–100K, `PGC_POSTMASTER`),
  `.plan_format` (enum text/json/yaml/xml) (`pg_show_plans.c:169-208`)
  `[verified-by-code]`. `is_enabled` and `plan_format` are `PGC_USERSET` on
  PG ≥ 15 but `PGC_POSTMASTER` pre-15, and both carry custom assign+show hooks
  that route through shmem (divergence 4).
- **Output SRF.** `pg_show_plans()` is `LANGUAGE C` returning `SETOF record`
  (pid, level, userid, dbid, plan), wrapped in the `pg_show_plans` view plus a
  `pg_show_plans_q` view that `LEFT JOIN`s `pg_stat_activity` for the query text;
  both granted to PUBLIC (`pg_show_plans--2.1.sql:6-29`) `[verified-by-code]`.
  The SRF uses the `SRF_*` ValuePerCall protocol with a `HASH_SEQ_STATUS`, not a
  materialized tuplestore (`pg_show_plans.c:556-677`) `[verified-by-code]`.

## Where it diverges from core idioms

### 1. It runs EXPLAIN on every execution, in every backend, into shmem — THE headline

Core renders a plan only when a session issues `EXPLAIN`. pg_show_plans makes
plan-rendering a side effect of *all* execution: inside `pgsp_ExecutorStart`,
after the standard start runs, it builds a fresh `ExplainState`, sets the
shmem-resident format, and calls `ExplainBeginOutput` / `ExplainPrintPlan` /
`ExplainEndOutput`, then `append_query_plan` copies the rendered `StringInfo`
into its shmem entry and `pfree`s the buffer (`pg_show_plans.c:495-503`)
`[verified-by-code]`. So every `SELECT`, every function call, every nested query
pays a full plan-rendering pass even though almost no one will ever read it. This
is the inversion of core's pull model and the source of the ~14% benchmark
penalty (`README.md:90-103`) `[from-README]`. The TEXT-format path even
hand-trims the trailing `'\n'` from the EXPLAIN output by decrementing
`new_plan->len` directly (`pg_show_plans.c:306-307`) `[verified-by-code]`.

### 2. Each backend owns and writes its own PID-keyed shmem entry — no shared writer

Instead of one collector writing a ring, each backend is the sole writer of its
own hash entry. `ensure_cached` lazily `create_hash_entry`s an entry keyed by
`MyProcPid` on first execution and registers an `on_shmem_exit(cleanup)` callback
to `HASH_REMOVE` it on disconnect (`pg_show_plans.c:259-277`, `325-333`)
`[verified-by-code]`. `append_query_plan` then writes the entry with bare
`memcpy` + direct field stores and **no lock** (`pg_show_plans.c:317-322`)
`[verified-by-code]` — correctness rests on the invariant that only the owning
backend ever writes its own PID entry. The heavyweight `LWLock` (`pgsp->lock`) is
taken **only** for hash-table structural mutation (`HASH_ENTER_NULL` /
`HASH_REMOVE`) and for the reader's full-table `LW_SHARED` scan
(`pg_show_plans.c:284-291`, `330-332`, `580`, `674`) `[verified-by-code]`; it
never guards the plan-text payload. This is a cleaner shmem-hygiene story than
[[pgsentinel]] (which requests tranches it never acquires), but it still leans on
an implicit ownership invariant rather than a lock around the payload write.

### 3. A per-entry spinlock guards only the n_plans "entry is live" flag, not the plan bytes

The payload (`plan[]`, `plan_len[]`) is written lock-free, but the *visibility*
flag `n_plans` is guarded by a per-entry `slock_t mutex`
(`pg_show_plans.c:54`). On run-unwind, when `nest_level` drops below 1, the
backend takes the spinlock just to set `n_plans = 0` (mark the entry empty)
(`pg_show_plans.c:535-539`), and the reader takes the same spinlock just to read
`n_plans` into its loop context (`pg_show_plans.c:636-638`)
`[verified-by-code]`. So the spinlock is a 1-int handshake: writer publishes
"entry has N plans / entry is empty", reader sees a consistent N — but the reader
then walks the plan bytes for that N with no further synchronization. The clear
happens in *both* the `PG_TRY` success path and the `PG_CATCH` path so an error
mid-execution still empties the entry, followed by `PG_RE_THROW`
(`pg_show_plans.c:516-553`) `[verified-by-code]`. Capture-at-start /
clear-at-run-unwind (rather than clear-at-ExecutorEnd) is why no
`ExecutorFinish`/`End` hook is needed.

### 4. GUC assign/show hooks read and write shared memory, not the backend-local var

Core's `DefineCustom*Variable` show/assign hooks normally operate on the
process-local C variable. pg_show_plans routes `is_enabled` and `plan_format`
through shmem so a `SET` in one backend affects all backends: `set_state` writes
`pgsp->is_enabled` (`pg_show_plans.c:335-345`), `show_state` reads it back
(`pg_show_plans.c:349-356`), and `prop_format_to_shmem` → `set_format` writes
`pgsp->plan_format` (gated on `is_allowed_role()`) with `show_format` reading it
(`pg_show_plans.c:358-392`) `[verified-by-code]`. The comment explains the
design tension: start-time GUC assignment runs before shmem is fully available,
so the safety check is deliberately commented out in the assign hooks
(`pg_show_plans.c:338-341`, `361-364`) `[verified-by-code]`. This makes a
nominally per-session GUC behave as a cluster-global toggle — a semantics core
GUCs don't have.

### 5. Plan storage is a fixed-stride char arena indexed by nest level, not palloc'd text

Each `pgspEntry` has a flexible `char plan[]` of `max_plan_length` bytes holding
*all* nested-level plans concatenated, with a `plan_len[MAX_NEST_LEVEL]` array
recording each level's byte length (`pg_show_plans.c:51-60`, `231`)
`[verified-by-code]`. Writes compute an offset by summing prior levels'
`plan_len[i]+1` (`pg_show_plans.c:301-304`), and the reader recomputes the same
offset arithmetic to slice out level *curr_nest* (`pg_show_plans.c:643-645`,
`652`) `[verified-by-code]`. When the arena fills, the write is refused with a
`WARNING` (not truncated silently) advising a bigger `max_plan_length`
(`pg_show_plans.c:309-314`) `[verified-by-code]`, and the README is blunt that
the hash table "is not resizable, thus, no new plans can be added once it has
been filled up" (`README.md:6-7`) `[from-README]`. This is a hand-rolled
fixed-width store chosen because shmem can't hold palloc pointers across
backends — the same constraint that drives [[pgsentinel]]'s NAMEDATALEN arenas.

### 6. The SRF abuses call_cntr to emit multiple rows per hash entry

The ValuePerCall SRF must emit one row per (entry × nest level), but
`funcctx->max_calls` is set to `hash_get_num_entries` — the *entry* count, not
the row count (`pg_show_plans.c:588`). To emit a second nested-plan row for the
same entry, the code **decrements `call_cntr`** so the loop revisits the same
entry, with a candid comment: "May not be legal, but it works"
(`pg_show_plans.c:655-659`) `[verified-by-code]`. Skipping empty /
unauthorized entries similarly *increments* `call_cntr` inside an inner `for(;;)`
that re-drives `hash_seq_search` (`pg_show_plans.c:618-635`) `[verified-by-code]`.
This manual fiddling with the SRF's own counter is exactly the bookkeeping core's
`SFRM_Materialize` tuplestore path exists to avoid.

### 7. Privilege filtering is re-implemented at read time against pg_read_all_stats

Because the views are granted to PUBLIC (`pg_show_plans--2.1.sql:28-29`), the SRF
re-codes `pg_stat_activity`'s redaction rule in C: `is_allowed_role()` tests
`is_member_of_role(GetUserId(), ROLE_PG_READ_ALL_STATS)`
(`pg_show_plans.c:407-414`), and an entry is emitted only if the caller is
allowed or owns the entry (`pgsp_tmp_entry->user_id == GetUserId()`)
(`pg_show_plans.c:621-627`) `[verified-by-code]`. The same gate also restricts
who may change the cluster-global `plan_format` (`pg_show_plans.c:366`)
`[verified-by-code]`. So the security boundary core would enforce in a catalog
view is hand-rolled in the extension's C.

## Notable design decisions (with cites)

- **Capture at ExecutorStart, clear at ExecutorRun-unwind.** Nesting is tracked
  by a process-local `nest_level` bumped in `pgsp_ExecutorRun` and decremented as
  each nested run returns; the entry is marked empty only when the outermost run
  unwinds (`pg_show_plans.c:136`, `515-539`) `[verified-by-code]`. There is no
  `ExecutorFinish`/`ExecutorEnd` hook — the lifecycle is start-to-run-unwind, so
  a plan is visible for the duration of execution.
- **`max_plan_length` is `PGC_POSTMASTER`** because it sizes shmem
  (`pg_show_plans.c:181-195`); the GUC's long_desc warns that too large a value
  can prevent server start (`pg_show_plans.c:185-188`, `README.md:111-113`)
  `[verified-by-code]` `[from-README]`.
- **`is_enabled` short-circuit keeps the entry alive but skips rendering.** When
  disabled, `pgsp_ExecutorStart` still calls `ensure_cached` (so the PID entry
  and `on_shmem_exit` cleanup exist) but returns before the EXPLAIN pass
  (`pg_show_plans.c:482-493`) `[verified-by-code]` — toggling on/off mid-session
  is cheap.
- **Hash-full and plan-too-long both degrade to WARNING, not ERROR.**
  `create_hash_entry` uses `HASH_ENTER_NULL` and returns NULL when the
  `MaxConnections`-sized table is full; `ensure_cached` propagates that to a
  `WARNING` and the backend simply runs without plan capture
  (`pg_show_plans.c:280-291`, `482-488`) `[verified-by-code]`.
- **Reader holds `pgsp->lock` `LW_SHARED` for the whole multi-call SRF.** The
  lock is acquired in `SRF_IS_FIRSTCALL` and released only at `SRF_RETURN_DONE`
  or early-out (`pg_show_plans.c:580`, `629-631`, `674`) `[verified-by-code]` —
  i.e. across every per-call return, blocking concurrent entry create/remove for
  the duration of one `SELECT * FROM pg_show_plans`.
- **PG ≥ 18 EXPLAIN header split + ExecutorRun signature change handled inline.**
  Includes `explain_state.h`/`explain_format.h` only on PG ≥ 18
  (`pg_show_plans.c:19-22`) and drops the `execute_once` arg from the
  `ExecutorRun` signature on PG ≥ 18 (`pg_show_plans.c:118-121`, `508-531`)
  `[verified-by-code]`. `ShmemInitHash`'s init-size arg is dropped on PG ≥ 19
  (`pg_show_plans.c:459-461`) `[verified-by-code]`. Compat is all inline
  `#if PG_VERSION_NUM`, no shim header; PG < 14 is a hard `#error`
  (`pg_show_plans.c:39-41`) `[verified-by-code]`.
- **`relocatable = true`** — the extension defines only functions/views with no
  schema-qualified internal references, so it can be moved between schemas
  (`pg_show_plans.control:5`) `[verified-by-code]`.

## Links into corpus

- [[executor-and-planner]] — the core divergence: `ExecutorStart_hook` /
  `ExecutorRun_hook` wrapping `standard_ExecutorStart`/`standard_ExecutorRun`,
  and driving `ExplainPrintPlan` over `queryDesc` from inside the hook
  (`pg_show_plans.c:468-554`, `495-499`).
- [[bgworker-and-extensions]] / [[extension-development]] — `_PG_init` hook
  chaining at preload, `process_shared_preload_libraries_in_progress` gate, and
  `shmem_request_hook`/`shmem_startup_hook` pairing (`pg_show_plans.c:162-226`,
  `416-466`).
- [[locking]] — the LWLock-for-structure / spinlock-for-1-int-flag /
  lock-free-payload split (divergences 2-3): `pgsp->lock` only around hash
  enter/remove/scan; per-entry `slock_t` only around `n_plans`
  (`pg_show_plans.c:284-291`, `535-539`, `636-638`).
- [[gucs-config]] — three `DefineCustom*Variable` with shmem-routing
  assign/show hooks and the version-split `PGC_USERSET`/`PGC_POSTMASTER` context
  (`pg_show_plans.c:169-208`, `335-392`).
- [[fmgr-and-spi]] — `PG_FUNCTION_INFO_V1` SRF using the `SRF_*` ValuePerCall
  protocol with `HASH_SEQ_STATUS` rather than a materialized tuplestore, and the
  `call_cntr` manipulation (`pg_show_plans.c:556-677`).
- [[memory-contexts]] — SRF state palloc'd in `multi_call_memory_ctx`; the
  per-execution `ExplainState->str` buffer `pfree`d immediately after copy into
  shmem (`pg_show_plans.c:577-585`, `502`).
- [[parser-and-nodes]] — capture reads `queryDesc->plannedstmt` indirectly via
  `ExplainPrintPlan`, the boundary where the plan tree becomes text.
- Sibling ideologies: [[pgsentinel]] (closest sibling — shmem-resident
  observability, fixed-width char arena because palloc can't cross backends; but
  pgsentinel *samples* via a bgworker + SPI and requests tranches it never takes,
  whereas pg_show_plans has each backend *push* into its own PID entry under a
  real lock for structure), [[pg_tracing]] (executor-hook + shmem-ring tracer,
  also renders per-execution detail), [[pg_stat_statements]] (aggregate post-hoc
  counters vs. pg_show_plans' live plan text — the two are complementary, and the
  `pg_show_plans_q` view joins `pg_stat_activity` the way pgss links queryids),
  [[pg_qualstats]] (hook-chain observer layered on `_PG_init`).

> Corpus gap: no idiom doc for the **"each backend pushes into its own PID-keyed
> shmem hash entry, single-writer-per-entry, lock only on structural mutation"**
> pattern — the cleaner cousin of pgsentinel's PGPROC-indexed array. pg_show_plans
> is the canonical example; worth an `idioms/per-backend-shmem-self-publish.md`.
> Corpus gap: no idiom doc for **"rendering EXPLAIN output from inside an
> executor hook"** (`NewExplainState` → `ExplainPrintPlan` over another query's
> `QueryDesc`), the push-model inversion of `EXPLAIN`. This is the load-bearing
> move and has no corpus home.

## Sources

All fetched 2026-06-27.

- Tree listing: `https://api.github.com/repos/cybertec-postgresql/pg_show_plans/git/trees/master?recursive=1` — 200
- `https://raw.githubusercontent.com/cybertec-postgresql/pg_show_plans/master/README.md` — 200 (135 lines)
- `https://raw.githubusercontent.com/cybertec-postgresql/pg_show_plans/master/pg_show_plans.control` — 200 (5 lines)
- `https://raw.githubusercontent.com/cybertec-postgresql/pg_show_plans/master/pg_show_plans.c` — 200 (677 lines)
- `https://raw.githubusercontent.com/cybertec-postgresql/pg_show_plans/master/pg_show_plans--2.1.sql` — 200 (29 lines)
- `https://raw.githubusercontent.com/cybertec-postgresql/pg_show_plans/master/pg_show_plans--2.0--2.1.sql` — 200 (8 lines; ADD format column upgrade, not cited)
- `https://raw.githubusercontent.com/cybertec-postgresql/pg_show_plans/master/pg_show_plans--1.1--2.0.sql` — 200 (6 lines; upgrade, not cited)
- `https://raw.githubusercontent.com/cybertec-postgresql/pg_show_plans/master/pg_show_plans--1.0--1.1.sql` — 200 (34 lines; upgrade, not cited)

Skimmed-but-not-fetched (paths resolved against the tree, behavior inferred from
the cited files): `Makefile` (PGXS build wiring), `pg_show_plans.md` (mirrors
README), `sql/pg_show_plans.sql`, `sql/formats.sql`,
`expected/pg_show_plans.out` (+ `_1`), `expected/formats.out` (+ `_1`/`_2`)
(regression tests), `.github/workflows/installcheck.yml`. No 404s; no path
substitutions needed.
