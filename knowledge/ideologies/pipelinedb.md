# pipelinedb — streams-as-foreign-tables feeding a private process-tree of dynamic bgworkers that incrementally maintain "continuous views" out of intercepted CREATE VIEW

> Ideology note produced by the `pg-extension-anthropologist` cloud routine.
> Repo: `pipelinedb/pipelinedb` @ branch `master`. All `file:line` cites below
> point into that repo (not `source/`), since this doc characterizes an
> *external* extension's divergence from core idioms. Cites verified against
> files fetched on 2026-06-18 (see Sources footer). The project is archived —
> "PipelineDB will not have new releases beyond `1.0.0`" (`README.md:3`) and the
> team joined Confluent — but it remains the corpus's most complete worked
> example of building a streaming/continuous-query engine *inside* the extension
> API. Read alongside `[[knowledge/ideologies/pg_ivm]]` (incremental view
> maintenance done the rewriter+trigger way, the conservative sibling),
> `[[knowledge/ideologies/wrappers]]` and `[[knowledge/ideologies/wasmer-postgres]]`
> (FDW-API repurposing), and `[[knowledge/ideologies/pg_cron]]` /
> `[[knowledge/ideologies/pg_auto_failover]]` (the "private bgworker hierarchy"
> pattern).

## Domain & purpose

PipelineDB is "a PostgreSQL extension for high-performance time-series
aggregation … [that] allows you to define continuous SQL queries that
perpetually aggregate time-series data and store **only the aggregate output**
in regular, queryable tables" — "extremely high-throughput, incrementally
updated materialized views that never need to be manually refreshed"
(`README.md:12-16`) `[from-README]`. The decisive property: "Raw time-series
data is never written to disk" (`README.md:16`). You insert events into a
*stream*, a continuous view aggregates them in flight, and only the running
aggregate touches storage.

The user model is two ordinary-looking DDL statements that the extension quietly
reinterprets (`README.md:98-101`) `[from-README]`:

```sql
CREATE FOREIGN TABLE test_stream (key int, value int) SERVER pipelinedb;
CREATE VIEW test_view WITH (action=materialize) AS
    SELECT key, COUNT(*) FROM test_stream GROUP BY key;
```

Events arrive as plain `INSERT INTO test_stream …` and are counted into
`test_view` continuously. The reason to document it: every one of those familiar
surfaces — `CREATE FOREIGN TABLE`, `INSERT`, `CREATE VIEW`, `SELECT` — is
load-bearing for a mechanism core never intended, and the extension reaches deep
into the executor, planner, FDW, and bgworker subsystems simultaneously to make
it work.

## How it hooks into PG

PipelineDB installs the full quartet of core extension hooks plus a custom
bgworker process tree and an FDW. (The `_PG_init` that wires these lives in a
`pipelinedb.c` not fetched here; the individual installers are cited below.)

- **`post_parse_analyze_hook`** — `InstallAnalyzerHooks` chains
  `PostParseAnalyzeHook`, which on any continuous query rewrites the target list
  (`transform_cont_select_tlist`) and stamps the sliding-window step factor
  (`analyzer.c:3684-3708`) `[verified-by-code]`. Gated on `PipelineDBExists()`
  and `!IsBinaryUpgrade` so a database without the extension is untouched
  (`analyzer.c:3690-3691`).
- **`planner_hook`** — `save_planner_hook = planner_hook; planner_hook =
  PipelinePlanner` (`planner.c:44-53`) `[verified-by-code]`. The hook calls
  through to the saved planner for ordinary queries (`planner.c:776-777`).
- **`set_rel_pathlist_hook` / `set_join_pathlist_hook`** — swapped in and out
  *transiently around individual plan calls*, not installed for the session:
  `add_tuplestore_scan_path` to make a continuous query scan its in-memory
  tuplestore instead of a heap (`planner.c:231-265`), and
  `add_physical_group_lookup_path` / `…_join_path` to give the combiner an
  efficient by-group probe into the materialization table (`planner.c:519-541`)
  `[verified-by-code]`. Each swap is wrapped in `PG_TRY/PG_CATCH` that restores
  the prior hook on error, with the explicit comment "Hooks won't be reset if
  there's an error, so we need to make sure that they're not set for whatever
  query is run next in this xact" (`planner.c:247-262`) — a discipline core
  hook authors must observe but rarely document so sharply
  (`[[knowledge/idioms/error-handling]]`).
- **The stream FDW** — `stream_fdw_handler` returns an `FdwRoutine` wired so
  that a SELECT over a stream is a foreign scan that pulls from an IPC micro-
  batch (`GetForeignRelSize`/`GetForeignPaths`/`GetForeignPlan`/`Begin/Iterate/
  End StreamScan`), and an INSERT into a stream is a foreign modify
  (`PlanForeignModify` … `ExecStreamInsert`) that pushes the event into the
  in-process queue rather than to disk (`stream_fdw.c:87-112`)
  `[verified-by-code]`. `SERVER pipelinedb` is the FDW server; "Any `INSERT`
  target that isn't a table is considered a stream" (`README.md:103`).
- **The bgworker process tree** — a scheduler bgworker spawns per-database
  *worker* and *combiner* continuous-query procs via
  `RegisterDynamicBackgroundWorker`, each carrying `bgw_function_name =
  "cont_bgworker_main"`, `bgw_flags = BGWORKER_SHMEM_ACCESS |
  BGWORKER_BACKEND_DATABASE_CONNECTION | BGWORKER_IS_CONT_QUERY_PROC`, and
  `bgw_restart_time = BGW_NEVER_RESTART` (`scheduler.c:526-560`)
  `[verified-by-code]`. Cross-ref `[[knowledge/idioms/bgworker-and-extensions]]`.

## Where it diverges from core idioms

### 1. A "stream" is a foreign table whose foreign side is an in-process ZeroMQ micro-batch, so INSERT bypasses storage entirely

The FDW is the structural trick. `ExecStreamInsert` does not write a heap tuple;
it serializes the event into a micro-batch and hands it to the continuous-query
processes over IPC. PipelineDB uses **ZeroMQ** for that IPC — "PipelineDB uses
[ZeroMQ] for inter-process communication" (`README.md:37`), wrapped in
`pzmq.[ch]` and pulled into `stream_fdw.c` (`#include "pzmq.h"`,
`stream_fdw.c:36`) `[verified-by-code]`. This is a divergence on two axes at
once: (a) it repurposes the FDW API so the "foreign" data is a transient
in-memory stream local to the cluster (cf. `[[knowledge/ideologies/wrappers]]`
and `[[knowledge/ideologies/wasmer-postgres]]` which also bend FdwRoutine away
from "remote database"), and (b) it introduces an *external message-queue
library* as the cross-process transport instead of building solely on core's
shared memory + latches (`[[knowledge/idioms/locking]]`,
`[[knowledge/subsystems/ipc]]`). The payoff is the headline property: raw events
never hit disk (`README.md:16`).

### 2. CREATE VIEW is intercepted and exploded into a fan of hidden relations

A continuous view is not a `pg_rewrite` view. The DDL `CREATE VIEW … WITH
(action=materialize)` is recognized via `GetContQueryAction(ViewStmt *)`
(`analyzer.c:3713`) and turned into a cluster of physical relations, each named
by suffixing the CV name: a **materialization table** (`CVNameToMatRelName`,
`CQ_MATREL_SUFFIX`), a **defrel**, an **output-stream rel**
(`CVNameToOSRelName`, `CQ_OSREL_SUFFIX`), and a **sequence**
(`CVNameToSeqRelName`) (`matrel.c:224-277`) `[verified-by-code]`. The
user-visible "view" is an overlay query that reads the matrel
(`GetContViewOverlayPlan`, `planner.c:270-287`). Core has exactly one notion of
a view (a stored rewrite rule); PipelineDB builds a parallel, catalog-backed
notion of a view whose backing store, output stream, and sequence are managed by
hand.

### 3. Aggregates are split into a partial (worker) and a combine (combiner) stage — incremental MV maintenance rebuilt from scratch

`make_aggs_partial(plan->planTree)` rewrites a continuous query's plan so
workers compute *partial* aggregate states over each micro-batch
(`planner.c:223`) `[verified-by-code]`. A second process class, the **combiner**
(`combiner.c`), merges those partial states into the existing matrel rows. The
matrel update path is hand-rolled executor code: `ExecCQMatRelUpdate` wraps
`simple_heap_update` and re-inserts index tuples, and
`ExecInsertCQMatRelIndexTuples` is described in-tree as "a trimmed-down version
of ExecInsertIndexTuples" (`matrel.c:87-92, 149-221`) `[verified-by-code]`.
This is the same problem `[[knowledge/ideologies/pg_ivm]]` solves with the
rewriter + AFTER triggers; PipelineDB instead owns the whole loop in dedicated
processes and copies/pares core executor internals to do the incremental write
— a much deeper reach into `[[knowledge/subsystems/executor]]` and
`[[knowledge/access-method-apis]]` (`index_insert`, `simple_heap_update`).

### 4. A custom bgworker-flag bit and a self-managed restart policy on top of core's

The proc flags include `BGWORKER_IS_CONT_QUERY_PROC` OR-ed alongside the two
core flags (`scheduler.c:539`) `[verified-by-code]` — an extension-defined bit
layered onto core's `bgw_flags` space to tag "this bgworker is one of mine." The
workers register with `BGW_NEVER_RESTART` because "the scheduler will restart
procs as necessary" (`scheduler.c:547`): PipelineDB deliberately opts out of the
postmaster's restart machinery and re-implements supervision in the scheduler.
It even re-implements the wait-for-startup primitive, because "the continuous
query scheduler isn't a normal backend and so cannot be signaled by the
postmaster," so it cannot use `WaitForBackgroundWorkerStartup` and instead polls
`GetBackgroundWorkerPid` in a `pg_usleep` loop (`scheduler.c:496-521`)
`[verified-by-code]`. Contrast the textbook lifecycle in
`[[knowledge/idioms/bgworker-and-extensions]]`.

### 5. Workers force `XactReadOnly = true` and run their own executor mode

`ContinuousQueryWorkerMain` sets `XactReadOnly = true` with the comment "Workers
never perform any writes, so only need read only transactions"
(`worker.c:347-348`) `[verified-by-code]` — only the combiner writes the matrel.
Workers drive the executor with a private flag, `ExecutorStart(state->query_desc,
PIPELINE_EXEC_CONTINUOUS)` (`worker.c:119`), and loop over micro-batches with
`ContExecutorStartBatch` / `ContExecutorStartNextQuery`
(`worker.c:350-359`, `combiner.c:2064-2066`). Each per-query iteration is
wrapped in `PG_TRY/PG_CATCH` that `EmitErrorReport` + `FlushErrorState` and
keeps the worker alive (`worker.c:300-309`, also `matrel.c:160-171`) — a
long-running backend's error-survival idiom, not the "let it ERROR and abort the
xact" model of a normal backend (`[[knowledge/idioms/error-handling]]`).

### 6. Bounded-memory streaming requires probabilistic aggregate types as first-class objects

Because the aggregate must fit in fixed memory regardless of stream cardinality,
PipelineDB ships native probabilistic structures used as aggregate transition
types: a Bloom filter (`bloom.c`/`bloomfuncs.c`), Count-Min sketch
(`cmsketch.c`), HyperLogLog (`hll.c`/`hllfuncs.c`), t-digest (`tdigest.c`),
Filtered-Space-Saving / top-k (`fss.c`/`topkfuncs.c`), and a frequency estimator
(`freqfuncs.c`) `[verified-by-code, from tree listing]`. This overlaps
`[[knowledge/ideologies/postgresql-hll]]` (HLL as a standalone type) but here the
sketches exist specifically to make `COUNT(DISTINCT)`, percentile, and top-k
queries *combinable* across micro-batches in the worker→combiner split.

### 7. Deep internal-API coupling pins it to PostgreSQL 10/11

The extension "currently supports … PostgreSQL 10: 10.1–10.5; PostgreSQL 11:
11.0" (`README.md:22-26`) `[from-README]`. The source is dense with
`#if PG_VERSION_NUM` shims around bgworker `bgw_type`, proc-name logging, and
JSONB macros (`scheduler.c:487-489, 535-537`, and a `compat.c` /`compat.h`
compatibility layer) `[verified-by-code]`. Reaching this far into the planner,
executor, and FDW internals is exactly what makes a continuous-query engine
possible as an extension *and* what makes it version-locked — the same tradeoff
seen in `[[knowledge/ideologies/orioledb]]` and
`[[knowledge/ideologies/citus]]`.

## Notable design decisions with cites

- **Streams are schemaless until read.** "streams don't need to have a schema
  created in advance … Any `INSERT` target that isn't a table is considered a
  stream" (`README.md:103`); the FDW projects incoming events against the
  reader's expected `TupleDesc` per micro-batch via `StreamProjectionInfo`,
  whose `indesc` "will change between micro batches" so projection state is reset
  each time (`stream_fdw.c:55-82`) `[verified-by-code]`.
- **Output streams chain CVs into networks.** Continuous queries "produce their
  own output streams and thus can be chained together into arbitrary networks of
  continuous SQL" (`README.md:18`); each CV gets an `_osrel` output-stream
  relation (`matrel.c:224-235`) and a `CQOSRelOpen`/`CQOSRelClose` pair that
  fabricates a throwaway `ResultRelInfo` with `ri_RangeTableIndex = 1 /* dummy
  */` (`matrel.c:32-52`) `[verified-by-code]`.
- **Continuous transforms can be no-ops.** A `CONT_TRANSFORM` query with no
  trigger function and no downstream stream readers is skipped:
  `should_exec_query` returns false when `!OidIsValid(query->tgfn) &&
  bms_is_empty(GetAllStreamReaders(query->osrelid))` (`worker.c:315-333`)
  `[verified-by-code]`.
- **Matrel writes are guardrailed by a GUC.** `bool matrels_writable`
  (`matrel.c:25`) gates whether users may write the hidden materialization table
  directly — normally only the combiner does.

## Links into corpus

- `[[knowledge/ideologies/pg_ivm]]` — the conservative counterpart: incremental
  view maintenance via query rewriter + AFTER triggers, no bgworkers, no FDW, no
  IPC. PipelineDB and pg_ivm are the two poles of "incrementally-maintained
  aggregates as an extension."
- `[[knowledge/ideologies/wrappers]]`, `[[knowledge/ideologies/wasmer-postgres]]`,
  `[[knowledge/ideologies/tds_fdw]]` — the FDW-API spectrum; PipelineDB's stream
  FDW is the case where "foreign" means "in-process IPC stream."
- `[[knowledge/ideologies/pg_cron]]`, `[[knowledge/ideologies/pg_auto_failover]]`
  — sibling "scheduler bgworker spawns per-database dynamic worker procs"
  topologies.
- `[[knowledge/ideologies/postgresql-hll]]` — HLL as a type, vs PipelineDB's
  family of combinable streaming sketches.
- `[[knowledge/idioms/bgworker-and-extensions]]` — the lifecycle PipelineDB
  partly bypasses (`BGW_NEVER_RESTART`, custom flag bit, hand-rolled
  wait-for-startup).
- `[[knowledge/idioms/error-handling]]` — the long-running-worker survival
  pattern (`PG_TRY` + `EmitErrorReport` + `FlushErrorState`) and the
  reset-hooks-on-error discipline in the planner.
- `[[knowledge/subsystems/executor]]`, `[[knowledge/access-method-apis]]` — the
  copied/pared `ExecInsertIndexTuples`, `simple_heap_update`, `index_insert`
  matrel write path.
- `[[knowledge/subsystems/foreign-data]]` — the FdwRoutine surface bent into the
  stream transport.

## Sources

Fetched 2026-06-18 via `raw.githubusercontent.com/pipelinedb/pipelinedb/master`:

- `README.md` @ 2026-06-18 → 200
- `pipelinedb.control` @ 2026-06-18 → 200
- `src/scheduler.c` @ 2026-06-18 → 200
- `src/stream_fdw.c` @ 2026-06-18 → 200 (read head; FdwRoutine + projection)
- `src/matrel.c` @ 2026-06-18 → 200 (full)
- `src/analyzer.c` @ 2026-06-18 → 200 (4709 lines; read the hook-install +
  PostParseAnalyzeHook region, not the full analyzer)
- `src/planner.c` @ 2026-06-18 → 200 (hook swaps + partial-agg + overlay plan)
- `src/combiner.c` @ 2026-06-18 → 200 (2351 lines; skimmed for the
  ContExecutor batch loop, not fully read)
- `src/worker.c` @ 2026-06-18 → 200 (worker main + read-only + survival loop)
- `src/pipeline_query.c` @ 2026-06-18 → 200 (3158 lines; catalog metadata for
  continuous queries — skimmed, not cited in detail)

Manifest note: the probabilistic-type files (`bloom.c`, `cmsketch.c`, `hll.c`,
`tdigest.c`, `fss.c`, `topkfuncs.c`, `freqfuncs.c`) and the IPC layer
(`pzmq.c`, `microbatch.c`, `queue.c`) were identified from the recursive tree
listing but not fetched in full; claims about them are tagged
`[from tree listing]` where they rest only on filenames. `_PG_init` lives in a
`pipelinedb.c` not fetched; the individual hook installers are cited directly.
