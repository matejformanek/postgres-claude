# Citus — distributed PostgreSQL as an extension

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `citusdata/citus` @ branch `main`. All `file:line` cites below point
> into that repo (not `source/`), since this doc characterizes an *external*
> extension's divergence from core idioms. Cites verified against the files
> fetched on 2026-06-02 (see Sources footer).

## Domain & purpose

Citus is a PostgreSQL extension that turns single-node Postgres into a
distributed (sharded) database: tables are horizontally sharded across a
cluster of Postgres nodes, queries are routed/parallelized across those
shards, and the cluster scales out by adding worker nodes. `[from-README]`
(`README.md:18-30`). The architecture has a **coordinator** node (group id
0) holding distributed-table metadata + regular tables, and **worker** nodes
(group id > 0) holding the actual shards, which are *plain Postgres tables*
named `<table>_<shardid>` `[from-README]`
(`src/backend/distributed/README.md:98`, `:114-116`). Because shards are
ordinary Postgres tables, "all the usual PostgreSQL optimizations and
extensions can automatically be used" `[from-README]` (`README.md:424`).

It is, at heart, a worked answer to: *how far can you re-route Postgres'
behavior from inside an extension, without forking the server?* The answer
Citus gives is "almost arbitrarily far, via the hook surface."

## How it hooks into PG

Citus is `shared_preload_libraries = 'citus'` `[from-README]`
(`README.md:111`) and rides the standard core hook surface
(`src/backend/distributed/README.md:170-188`) `[from-README]`:

| Core mechanism | Citus use |
|---|---|
| `planner_hook` | After parse/analyze, detect any Citus table in the query tree and produce a plan tree containing a `CustomScan` that encapsulates the distributed plan (`README.md:178`, `:213`). |
| **CustomScan** (`nodes/extensible.h`) | The single executor entry point into Citus; its callbacks call the distributed executor, run remote shard queries, collect results (`README.md:180`, `:1557-1580`). |
| `ExecutorRun_hook` | Mostly to capture execution-time info; the one load-bearing use is executing **subplans** before the main scan (`README.md:1582`). |
| `ProcessUtility_hook` (`citus_ProcessUtility`) | Intercept DDL + COPY that touch Citus tables; propagate them to all nodes and shards (`README.md:184`, `:1780`). |
| **Transaction callbacks** (pre/post-commit, abort) | Implement distributed transactions / 2PC (`README.md:182`, `:2151-2161`). |
| **Background worker** | The per-database *maintenance daemon*: distributed deadlock detection, 2PC recovery, metadata sync, resource cleanup (`README.md:186`, `:126`). |
| **UDFs** | `create_distributed_table()`, `citus_add_node()`, etc. — sharding "DDL" is expressed as `SELECT fn(...)` because an extension cannot define new DDL grammar (`README.md:148-149`). |

The `CitusScanState` struct (`src/include/distributed/citus_custom_scan.h:21-40`)
embeds a core `CustomScanState` as its first member and hangs the
`DistributedPlan`, executor type, and a result `Tuplestorestate` off it — the
textbook "extend a core node by embedding it first" idiom. There are five
distinct registered custom-scan method tables (adaptive executor, sorted
merge, non-pushable INSERT…SELECT, delayed-error, non-pushable MERGE)
(`citus_custom_scan.h:44-48`) `[verified-by-code]`.

## Where it diverges from core idioms

This is the interesting part — where Citus *must* depart from how core
Postgres does things because the data is no longer local.

### 1. A second catalog parallel to `pg_depend`/`pg_class`

Citus maintains its own catalog tables (`pg_dist_node`, `pg_dist_shard`,
`pg_dist_placement`, `pg_dist_object`, `pg_dist_local_group`, …). The most
idiom-divergent is **`pg_dist_object`**: a hand-rolled mirror of `pg_depend`
semantics (same `classid, objid, objsubid` shape) recording which objects
must exist on *every* node `[from-README]`
(`src/backend/distributed/README.md:1939-1967`). Object creation walks
`pg_depend`/`pg_shdepend` via a DFS (`EnsureDependenciesExistOnAllNodes()`)
to replay dependencies in order on a newly-added node
(`README.md:2008-2018`, `:2030`). This is a deliberate re-implementation of
core's dependency machinery at cluster scope — core's `pg_depend` is
single-node and knows nothing about other servers.
Contrast with `[[knowledge/idioms/catalog-conventions]]`: core builtins live
in `pg_proc.dat`/BKI with assigned OIDs at bootstrap; Citus' distributed
objects get *ordinary* OIDs at runtime and are tracked separately.

### 2. DDL is a 6-step propagation pipeline, not one `ProcessUtility` call

Core runs DDL by `standard_ProcessUtility` taking locks and mutating the
catalog. Citus wraps every supported DDL in: qualify names → pre-process →
run locally on the shell table via the original ProcessUtility → post-process
→ run on all other nodes → run on shards `[from-README]`
(`src/backend/distributed/README.md:1780-1789`). New commands are registered
declaratively via a `DistributeObjectOps` struct
(`.deparse/.qualify/.preprocess/.postprocess/.markDistributed/.address`)
dispatched from `GetDistributeObjectOps()` (`README.md:1810-1865`). The
**deparse-then-reparse** approach (deparse the parse tree to a string, ship
the string, reparse on each worker / rewrite table names to shard names via
`worker_apply_shard_ddl_command`) is unlike anything in core and the doc
itself flags it as a shortcoming (`README.md:1804`).

### 3. Locking gains a whole new layer (advisory locks at cluster scope)

Citus leans on core for table- and row-level locks — it deliberately calls
`standardProcess_Utility()` first precisely so Postgres acquires the normal
table locks and Citus inherits core's concurrency semantics
(`src/backend/distributed/README.md:2298-2302`) `[from-README]`. Where it
*adds* a layer is **advisory locks**, used as cluster-wide coordination
flags (`README.md:2322-2419`):

- **Executor shard locks** (`AcquireExecutorShardLocksForExecution`,
  "ShardResourceLocks") — serialize replicated-table writes in a consistent
  order to keep replicas in sync and avoid distributed deadlocks
  (`README.md:2334-2348`).
- **Metadata locks** (`AcquireMetadataLocks`, `LockShardDistributionMetadata`)
  — serialize modify queries against shard-move placement-metadata changes;
  notably **SELECTs do not take them** (they run on old placements, cleaned
  via deferred drop) (`README.md:2351-2361`).
- **Colocation locks** (`AcquireRebalanceColocationLock`,
  `AcquirePlacementColocationLock`) — prevent placement divergence under
  concurrent `create_distributed_table` + shard move/split
  (`README.md:2402-2410`).
- **First-worker-node serialization** — reference-table writes serialize by
  taking the advisory lock on the deterministically-chosen first worker
  rather than the coordinator, to avoid loading the coordinator and to work
  when the coordinator isn't in the metadata (`README.md:2385`).

It also re-states core's spinlock rule with a war story: never `palloc`
while holding a SpinLock, because (unlike heavyweight/LWLocks) it is **not**
auto-released on error and a failed `palloc` once leaked one until restart
(`README.md:2426-2430`). Cross-ref `[[knowledge/idioms/locking-overview]]`
and `[[knowledge/subsystems/storage-lmgr]]`.

### 4. Transactions: atomic + durable, but no distributed snapshot isolation

Multi-node writes use core's built-in **2PC** machinery driven from the
pre/post-commit callbacks: `PREPARE TRANSACTION` on all worker connections +
a commit record on the coordinator at pre-commit; `COMMIT PREPARED` at
post-commit; the maintenance daemon reconciles in-doubt transactions by
comparing coordinator commit records to worker pending-prepared lists
`[from-README]` (`src/backend/distributed/README.md:2159-2161`). The
explicit, documented divergence from core's MVCC guarantees: **no
distributed snapshot isolation** — because the prepared transactions become
visible at slightly different times across nodes, a multi-shard read can see
a concurrent transaction as committed on one node and not another, yielding
anomalies with more outcomes than serializability would allow
(`README.md:2167-2207`). Single-node-scoped transactions retain full
Postgres guarantees (`README.md:2155-2157`). Cross-ref
`[[knowledge/architecture/mvcc]]`.

### 5. Distributed deadlock detection rebuilt on top of core's wait graph

Core's deadlock detector is single-process. Citus runs its own in the
maintenance daemon (`CheckForDistributedDeadlocks`): it tags backends with
**distributed transaction ids** (`assign_distributed_transaction_id`), builds
a local wait graph per node from Postgres' own lock-wait info
(`BuildLocalWaitGraph`, `AddEdgesForLockWaits`, `AddEdgesForWaitQueue`),
combines them on the coordinator, DFS-searches for a cycle, and cancels the
*youngest* transaction (`README.md:2223-2249`). It runs ~2× slower than
core's detector so core usually breaks any purely-local cycle first; the race
is safe (`README.md:2251`). Per-backend state lives in a `BackendData`
struct (`MyBackendData`) (`README.md:2261`).

### 6. The adaptive executor: a per-process connection pool + state machines

Rather than one-connection-per-query (old router executor) or
one-connection-per-shard (old real-time executor), the **adaptive executor**
keeps a *per-process pool of connections per node*, starts at 1 connection,
and grows via TCP-style **slow start** (~1 new connection per 10 ms while the
pool-level ready queue is non-empty) when task runtimes justify parallelism
(`src/backend/distributed/README.md:1659-1695`) `[from-README]`. It is built
as connection + transaction **state machines** driven by a `WaitEventSet`
over libpq in non-blocking mode (`README.md:1681`). Two correctness
invariants drive much of the connection-management complexity
(`README.md:2074-2095`): after a write/lock on a shard group, all subsequent
access to that shard group must reuse the *same* connection (uncommitted
state is only visible there); global/metadata changes must all use one
connection. When these conflict, Citus errors (`cannot perform query with
placements that were modified over multiple connections`) rather than risk
incorrectness, and suggests `citus.multi_shard_modify_mode = 'sequential'`
(`README.md:2088-2095`, `:2133`). A global `citus.max_shared_pool_size`
throttles outgoing connections across processes, converging to ~1
connection/node/process under high concurrency via an "optional vs required"
connection distinction (`README.md:2143-2147`).

### 7. Local execution + local plan caching

When a shard is on the coordinating node itself, Citus skips the network and
invokes the planner/executor directly (`local_executor.c`), always *after*
remote execution so it can still fail over (`README.md:1699-1709`). It even
piggybacks on core's plancache: for single local shard groups with deferred
pruning it stores the regular PG plan inside the distributed plan (`Job`) so
core caches it with the right lifecycle — but must skip this when volatile
functions are present, because local plan caching re-evaluates function calls
that are normally only run once in `BeginCustomScan`
(`README.md:1651-1657`). This is an unusually deep entanglement with core's
`plancache.c` for an extension.

## Notable design decisions (cited)

- **Shards are vanilla Postgres tables, hidden from the catalog** unless
  `SET citus.override_table_visibility TO off`
  (`src/backend/distributed/README.md:98`). Keeps the entire Postgres feature
  surface usable on each shard.
- **Sharding "DDL" expressed as UDFs** because an extension cannot add DDL
  grammar (`README.md:148-149`). Pervasive ideology consequence: the whole
  control surface is `SELECT`-callable C functions — see
  `[[knowledge/idioms/fmgr]]`.
- **Coordinator = group id 0 sentinel.** Group 0 is treated "almost
  everywhere in the code as the coordinator"; resetting a worker's local
  group id is deliberately deferred until node removal to avoid a worker
  masquerading as coordinator (`README.md:110-112`).
- **Layered planner** (fast-path router → router → recursive planning →
  logical planner/optimizer) trades planning overhead against query
  generality, so cheap OLTP queries skip expensive analysis
  (`README.md:213`, `:1385`). Cross-ref `[[knowledge/architecture/planner]]`.
- **Prepared-statement handling deliberately dissuades generic plans** for
  multi-shard queries: returns a mock `PlannedStmt` with extreme cost
  (`DissuadePlannerFromUsingPlan`) so PG keeps using custom plans with known
  parameter values, and pre-resolves `Param`→`Const`
  (`ResolveExternalParams`) before distributed planning
  (`README.md:1622`). The doc candidly calls the whole area technical debt
  that is nonetheless "battle hardened" (`README.md:1649`).
- **Function evaluation on the coordinator** for `nextval()`/`now()` etc., to
  avoid divergent values across replicated placements
  (`ExecuteCoordinatorEvaluableExpressions`) (`README.md:1590-1604`).

## Links into corpus

- `[[knowledge/idioms/catalog-conventions]]` — core's `pg_proc.dat`/OID model
  vs Citus' runtime `pg_dist_object` dependency mirror.
- `[[knowledge/idioms/locking-overview]]` + `[[knowledge/subsystems/storage-lmgr]]`
  — heavyweight/advisory/LW/spin lock taxonomy Citus builds on; the
  no-palloc-under-spinlock rule.
- `[[knowledge/architecture/mvcc]]` — the snapshot-isolation guarantee Citus
  explicitly does *not* extend across nodes.
- `[[knowledge/architecture/planner]]` + `[[knowledge/subsystems/optimizer]]`
  — `planner_hook` entry, custom-plan dissuasion, layered planner.
- `[[knowledge/architecture/executor]]` + `[[knowledge/subsystems/executor]]`
  — CustomScan integration, `ExecutorRun_hook`, plancache reuse.
- `[[knowledge/idioms/fmgr]]` — UDF-as-control-surface pattern.
- `[[knowledge/idioms/bgworker-and-parallel]]` — the maintenance-daemon
  background worker.
- `[[knowledge/architecture/wal]]` — 2PC commit-record durability (core
  machinery Citus drives via transaction callbacks).
- `.claude/skills/extension-development/SKILL.md` — the hook-chaining /
  `_PG_init` / `shared_preload_libraries` idioms Citus exemplifies at scale.

## Sources

Fetched 2026-06-02 (branch `main`):

- `https://raw.githubusercontent.com/citusdata/citus/main/README.md`
  @ 2026-06-02T09:31Z → HTTP 200 (496 lines).
- `https://raw.githubusercontent.com/citusdata/citus/main/src/backend/distributed/README.md`
  @ 2026-06-02T09:31Z → HTTP 200 (2840 lines; technical documentation —
  primary source for the divergence analysis).
- `https://raw.githubusercontent.com/citusdata/citus/main/src/include/distributed/citus_custom_scan.h`
  @ 2026-06-02T09:31Z → HTTP 200 (63 lines).
- Tree listing
  `https://api.github.com/repos/citusdata/citus/git/trees/main?recursive=1`
  @ 2026-06-02T09:31Z → HTTP 200 (3426 entries).

All manifest files fetched successfully — no gaps. Cites into the architecture
README are by line number within the fetched revision; C-function names are
quoted as the README presents them (the README itself is `[from-README]`,
i.e. the project's own design narrative, not independently re-verified against
Citus' `.c` sources). The header struct cite is `[verified-by-code]` against
the fetched `citus_custom_scan.h`.
</content>
