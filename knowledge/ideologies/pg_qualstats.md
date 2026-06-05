# pg_qualstats — forcing executor instrumentation from a hook to harvest per-qual selectivity error

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `powa-team/pg_qualstats` @ branch `master`. All `file:line` cites below
> point into that repo (not `source/`), since this doc characterizes an
> *external* extension's divergence from core idioms. Cites verified against the
> files fetched on 2026-06-05 (see Sources footer).

## Domain & purpose

pg_qualstats records statistics about the **WHERE-clause predicates (quals)**
that queries actually run: for each `column op constant`-style qual it tracks how
often it executed, with what constants, and — the payload feature — how badly the
planner mis-estimated its selectivity (estimated rows vs actual rows). That last
number is the raw material for an **index / extended-statistics advisor**: a qual
that is frequent *and* badly estimated is a prime candidate for a new index or a
`CREATE STATISTICS`. pg_qualstats is the data-collection half of the PoWA stack
and pairs naturally with hypothetical-index testing (see
`[[knowledge/ideologies/hypopg]]`). It is the worked answer to: *how does an
extension observe, after the fact, which predicates ran and how wrong the
planner's row estimate was for each one* — without modifying the planner or the
executor.

## How it hooks into PG

`PG_MODULE_MAGIC` (`pg_qualstats.c:80`). `_PG_init` chains the **four executor
hooks** — `ExecutorStart`/`ExecutorRun`/`ExecutorFinish`/`ExecutorEnd`, saving
each prior pointer (`pg_qualstats.c:388-395`) `[verified-by-code]`. When loaded
via `shared_preload_libraries` it also chains `shmem_request_hook` (PG ≥ 15) and
`shmem_startup_hook` to allocate a shared hashtable of qual entries
(`pg_qualstats.c:381-385`). It defines a tall stack of GUCs:
`pg_qualstats.enabled`, `.track_constants`, `.max`, `.resolve_oids`,
`.sample_rate`, `.min_err_estimate_ratio`, `.min_err_estimate_num`
(`pg_qualstats.c:397-510`).

The mechanism is two-phase: in **`ExecutorStart`** it decides whether to sample
this statement and, if so, *turns on instrumentation*; in **`ExecutorEnd`** it
walks the finished plan tree and extracts each qual together with the row counts
the instrumentation captured (`pg_qualstats.c:7-11` header comment, `:617-652`,
`:723+`).

## Where it diverges from core idioms

### 1. It mutates `queryDesc->instrument_options` from a hook to force EXPLAIN-grade instrumentation

The defining divergence. Instrumentation (per-node actual row counts, timing,
buffers) is normally only collected when the *caller* asked — e.g. `EXPLAIN
ANALYZE`. pg_qualstats reaches into the `QueryDesc` during `ExecutorStart` and
**OR-s the instrument flags in itself**: `queryDesc->instrument_options |=
PGQS_FLAGS`, where `PGQS_FLAGS = INSTRUMENT_ROWS | INSTRUMENT_BUFFERS`
(`pg_qualstats.c:91, 644-645`) `[verified-by-code]`. That single line silently
upgrades an ordinary query to a measured one so that, at `ExecutorEnd`, each
`PlanState` carries an `Instrumentation` with `ntuples`/`nloops` to compare
against the planner's `plan_rows`. Co-opting the executor's instrumentation
budget for passive observation — and paying its overhead on sampled queries — is
well outside the read-only spirit of the executor hooks. Cross-ref
`[[knowledge/subsystems/executor]]`, `[[knowledge/subsystems/optimizer]]`
(`plan_rows` / selectivity).

### 2. The selectivity-error metric reverse-engineers the planner's estimate per qual

In `ExecutorEnd`, pg_qualstats walks the plan/expression tree
(`pgqs_collectNodeStats` + `pgqs_whereclause_tree_walker`, dispatching to
`pgqs_process_opexpr`, `pgqs_process_scalararrayopexpr`, `pgqs_process_booltest`,
`pg_qualstats.c:332-338`) and, per qual, accumulates an *estimation-error* ratio
into the entry's `min/max/mean/sum_err_estim[2]` fields
(`pg_qualstats.c:277-280, 348`). It is computing, from the outside, how far the
planner's selectivity was from reality — a quantity core keeps internal to
costing. The `min_err_estimate_ratio`/`min_err_estimate_num` GUCs
(`pg_qualstats.c:468-490`) then let an advisor filter to the quals worth acting
on. Cross-ref `[[knowledge/subsystems/optimizer]]`.

### 3. One source tree, two memory models: shared-memory module *or* per-backend, switched at load

pg_qualstats is built to work even *without* `shared_preload_libraries`: if it
isn't preloaded, `_PG_init` sets `pgqs_backend = true` and warns that "only
current backend stats will be available" (`pg_qualstats.c:372-376`). The same
code then conditionally skips all shared-memory locking via a macro pair —
`PGQS_LWL_ACQUIRE(lock,mode)`/`PGQS_LWL_RELEASE(lock)` expand to real
`LWLockAcquire`/`Release` *only when* `!pgqs_backend`
(`pg_qualstats.c:96-101`) `[verified-by-code]`. So the identical hot path is
either a shared, LWLock-protected hashtable or an unlocked backend-local one,
chosen at startup. Even the GUC contexts flex: `pg_qualstats.max` is
`PGC_POSTMASTER` in shmem mode but `PGC_USERSET` in backend mode
(`pg_qualstats.c:426`). A module that ships both a global and a local
personality in one binary is an uncommon design. Cross-ref
`[[knowledge/subsystems/storage-ipc]]`, `.claude/skills/locking/SKILL.md`.

### 4. Cross-process sampling coordination via a `sampled[]` array indexed by backend number

The sampling decision must be shared between a parallel leader and its workers so
a query is wholly sampled or wholly not. pg_qualstats keeps a shmem
`bool sampled[FLEXIBLE_ARRAY_MEMBER]` array (`pg_qualstats.c:221-222`) sized by
the connection count: the leader writes its decision at `sampled[MyProcNumber]`
under `sampledlock` (`pg_qualstats.c:542-544`), and a worker reads
`sampled[ParallelLeaderProcNumber]` to inherit it (`pg_qualstats.c:563-565`).
Indexing shared state by backend/proc number to thread a decision across the
parallel boundary is a low-level coordination idiom most extensions never reach
for. Cross-ref `[[knowledge/subsystems/storage-ipc]]`,
`.claude/skills/gucs-bgworker-parallel/SKILL.md` (parallel-leader/worker).

### 5. It redefines a core macro (`ShmemInitHash`) for version portability

To bridge a signature change, pg_qualstats `#define`s `ShmemInitHash(n, nelem, i,
f)` to call the real four-vs-five-arg core function
(`pg_qualstats.c:109`) — i.e. it shadows a core API name in its own translation
unit. Locally redefining a core symbol is a portability hack core never needs.

## Notable design decisions (cited)

- **Rate sampling at the top statement only.** `ExecutorStart` rolls
  `pg_prng_double(&pg_global_prng_state) < pgqs_sample_rate` (PG ≥ 15) or the
  `random()` form before, but *only* at `nesting_level == 0` and not in a
  parallel worker (`pg_qualstats.c:626-640`); nested statements inherit the
  top-level decision, so a query is sampled all-or-nothing.
- **Bounded entry tables with eviction.** `pg_qualstats.max` caps tracked quals
  (default 1000, `pg_qualstats.c:85, 419-430`); `PGQS_MAX_LOCAL_ENTRIES` is
  `pgqs_max * 0.2` (`pg_qualstats.c:86`) and `pgqs_entry_dealloc` /
  `pgqs_localentry_dealloc` evict victims when full.
- **Optional OID name resolution, off by default.** `pg_qualstats.resolve_oids`
  stores relation/attribute *names* beside the OIDs and is documented to eat
  "MUCH more space" (`pg_qualstats.c:433-434`); only defined in shmem mode.
- **`track_constants`** controls whether literal constants are captured (richer
  advisor input vs lower cardinality / less churn), `pg_qualstats.c:408-417`.
- **Instrumentation also requests `INSTRUMENT_BUFFERS`** (`pg_qualstats.c:91`),
  not just rows — collected for the same passive-observation purpose.

## Links into corpus

- `[[knowledge/subsystems/executor]]` — the `ExecutorStart`/`End` hook points,
  `QueryDesc.instrument_options`, and the `Instrumentation` row counts
  pg_qualstats forces on and reads back.
- `[[knowledge/subsystems/optimizer]]` — planner `plan_rows`/selectivity, the
  estimate pg_qualstats measures error against.
- `[[knowledge/subsystems/storage-ipc]]` — `shmem_request_hook`/
  `shmem_startup_hook`, the shared qual hashtable, and the `sampled[]` array.
- `[[knowledge/idioms/memory-contexts]]` — per-query local entry hash and
  eviction.
- `[[knowledge/ideologies/hypopg]]` — the hypothetical-index sibling; pg_qualstats
  supplies the "which index to try" signal hypopg then tests for free.
- `.claude/skills/locking/SKILL.md` — the conditional `PGQS_LWL_ACQUIRE` LWLock
  discipline (and its absence in backend mode).
- `.claude/skills/gucs-bgworker-parallel/SKILL.md` — the parallel-leader/worker
  sampling coordination via proc-number-indexed shmem.

## Sources

Fetched 2026-06-05 (branch `master` — the queue manifest said `main`, but the
repo's default branch is `master`; the root `README.md` is an empty symlink, so
the real readme was fetched from `doc/README.md`):

- `https://raw.githubusercontent.com/powa-team/pg_qualstats/master/pg_qualstats.c`
  @ 2026-06-05 → HTTP 200 (2666 lines).
- `https://raw.githubusercontent.com/powa-team/pg_qualstats/master/pg_qualstats.control`
  @ 2026-06-05 → HTTP 200 (4 lines; `default_version = '2.1.3'`,
  `relocatable = false`).
- `https://raw.githubusercontent.com/powa-team/pg_qualstats/master/doc/README.md`
  @ 2026-06-05 → HTTP 200 (232 lines).
- `https://raw.githubusercontent.com/powa-team/pg_qualstats/master/README.md`
  @ 2026-06-05 → HTTP 200 (0 lines; symlink → `doc/README.md`).
- Tree listing
  `https://api.github.com/repos/powa-team/pg_qualstats/git/trees/master?recursive=1`
  @ 2026-06-05 → HTTP 200.

All `pg_qualstats.c` cites are `[verified-by-code]` against the fetched file
(the `instrument_options` mutation, the dual shmem/backend mode + conditional
LWLock macros, the `sampled[]` cross-process array, the qual-tree walkers). The
exact selectivity-error arithmetic inside `pgqs_entry_err_estim` was located but
not fully derived line-by-line; the advisor-pairing narrative is `[from-README]`
(`doc/README.md`).
