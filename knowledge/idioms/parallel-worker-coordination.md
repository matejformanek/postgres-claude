# Parallel worker coordination — ParallelContext lifecycle

Parallel query in PostgreSQL fans a single query across N
**parallel workers** — separate backend processes that share
the leader's snapshot and execute a portion of the plan. The
coordination is non-trivial: the leader sets up shared memory,
launches workers, waits for them to attach, processes their
results, and joins them at end-of-query. The
`ParallelContext` struct holds the coordination state.

Anchors:
- `source/src/include/access/parallel.h:33-83` — full API
  [verified-by-code]
- `source/src/backend/access/transam/parallel.c` —
  implementation
- `knowledge/subsystems/storage-ipc.md` — DSM segments + shm_mq
  are the underlying IPC primitives
- `knowledge/idioms/subtransaction-stack.md` — workers
  share leader's snapshot, not their own subxacts

## The ParallelContext struct

```c
typedef struct ParallelContext
{
    dlist_node             node;
    SubTransactionId       subid;
    int                    nworkers;
    int                    nworkers_to_launch;
    int                    nworkers_launched;
    char                  *library_name;
    char                  *function_name;
    ErrorContextCallback  *error_context_stack;
    shm_toc_estimator      estimator;
    dsm_segment           *seg;
    void                  *private_memory;
    shm_toc               *toc;
    ParallelWorkerInfo    *worker;
    int                    nknown_attached_workers;
    bool                  *known_attached_workers;
} ParallelContext;
```

[verified-by-code `parallel.h:33-50`]

Key fields:
- **`nworkers`** — max workers; may not be reached.
- **`nworkers_to_launch`** — actual count the leader wants.
- **`nworkers_launched`** — actual count successfully started.
- **`seg`** — the DSM (Dynamic Shared Memory) segment shared
  across all workers.
- **`toc`** — Table of Contents indexing shared structures
  within the DSM.
- **`worker[]`** — per-worker handles (bgwhandle + error
  message queue).

## The 6-step lifecycle

[verified-by-code `parallel.h:64-72`]

```c
pcxt = CreateParallelContext(library_name, function_name, nworkers);
EstimateParallelDSMRequired(pcxt);    /* leader's responsibility */
InitializeParallelDSM(pcxt);           /* allocate + populate DSM */
LaunchParallelWorkers(pcxt);           /* fork the workers */
WaitForParallelWorkersToFinish(pcxt);  /* leader joins */
DestroyParallelContext(pcxt);          /* cleanup */
```

Between steps 3 and 5, the leader does its own work in parallel
with the workers — receives results from them via shm_mq
queues, processes/aggregates, finishes.

## CreateParallelContext

```c
ParallelContext *CreateParallelContext(const char *library_name,
                                       const char *function_name,
                                       int nworkers);
```

[verified-by-code `parallel.h:64-65`]

- **`library_name`** + **`function_name`** — the dynamic
  function the worker will call once attached. Typically
  `"postgres"` + `"ParallelQueryMain"` for executor parallel
  workers.
- **`nworkers`** — desired worker count.

Allocates the context struct in `TopTransactionContext`.

## InitializeParallelDSM

The leader's responsibility to:

1. Estimate the DSM size — call `shm_toc_estimate_chunk`
   for each piece of data to share.
2. Allocate the DSM with `dsm_create`.
3. Populate the DSM — copy plan, query parameters, snapshot,
   subxact stack, etc.
4. Build the `shm_toc` (Table of Contents) indexing
   each chunk by key.

Workers attach to the DSM, look up structures by TOC key,
and find their inputs.

## LaunchParallelWorkers

Forks `nworkers_to_launch` background-worker processes via
the bgworker infrastructure. Each worker:

1. Attaches to the DSM.
2. Looks up state via the TOC.
3. Inherits the leader's snapshot (NOT a fresh one).
4. Calls the named function with `(seg, toc)` as args.

The bgworker registration uses
`BGW_BACKEND_DATABASE_CONNECTION` to get the worker into the
right database state.

## WaitForParallelWorkersToAttach vs Finish

[verified-by-code `parallel.h:70-71`]

- **`WaitForParallelWorkersToAttach`** — block until every
  launched worker has attached to the DSM. Use before reading
  worker-produced data; prevents the leader from racing the
  workers' startup.
- **`WaitForParallelWorkersToFinish`** — block until every
  worker has exited cleanly. Use at end-of-query; ensures
  no dangling state.

Failure modes:
- A worker fails to launch → `nworkers_launched <
  nworkers_to_launch`.
- A worker fails to attach → bgworker reported "exited" via
  the bgwhandle.
- A worker raises an ERROR → its error_mqh queue carries the
  message; leader re-raises in its own context.

## The error-propagation channel

Each `ParallelWorkerInfo` carries:
- **`bgwhandle`** — process management.
- **`error_mqh`** — a `shm_mq` queue for ereport messages.

When a worker calls `ereport(ERROR, ...)`, the error gets
serialized into the queue. The leader's
`ProcessParallelMessages` walks the queues, deserializes
errors, and re-raises them.

So a worker error becomes a leader error, properly attributed.
The user sees `ERROR: <worker's message>` rather than a
mysterious worker crash.

## The IsParallelWorker macro

[verified-by-code `parallel.h:62`]

```c
#define IsParallelWorker()    (ParallelWorkerNumber >= 0)
```

`ParallelWorkerNumber` is `-1` in leader, `0..N-1` in
workers. Code paths that must behave differently in workers
check this — e.g., catalog-modification paths refuse to run.

## Parallel safety levels

Each function/predicate is labeled:

- **`PARALLEL UNSAFE`** — Cannot run in worker; whole query
  must run in leader.
- **`PARALLEL RESTRICTED`** — Can run in leader OR in worker
  but not BOTH; restricted to one or the other depending on
  query shape.
- **`PARALLEL SAFE`** — Can run anywhere.

The planner respects these in path enumeration; only PARALLEL
SAFE leaves can appear below a Gather node.

## Common review-time concerns

- **`PARALLEL UNSAFE` is the default** for new C functions
  without explicit declaration. Make a deliberate choice.
- **Workers inherit the leader's snapshot.** Don't acquire a
  new one; visibility would diverge.
- **No catalog writes in workers.** No DDL, no
  `pg_class.relpages` updates. Read-only catalog access OK.
- **Errors from workers are re-raised in leader** — the
  user-visible error context is the leader's. Worker stack
  is lost.
- **`AtEOXact_Parallel`** is called at commit/abort to clean
  up any leftover parallel state. Don't dangle.

## Invariants

- **[INV-1]** Workers inherit the leader's snapshot; never
  acquire their own.
- **[INV-2]** Workers must NOT write to shared catalogs.
- **[INV-3]** `IsParallelWorker()` discriminates worker
  vs leader code paths.
- **[INV-4]** Worker errors propagate via shm_mq to leader's
  ereport.
- **[INV-5]** `nworkers_launched` may be less than
  `nworkers_to_launch` if bgworker pool was full.

## Useful greps

- The parallel context lifecycle:
  `grep -RIn 'CreateParallelContext\|InitializeParallelDSM\|LaunchParallelWorkers' source/src/backend | head -10`
- All IsParallelWorker checks:
  `grep -RIn 'IsParallelWorker' source/src/backend | head -20`
- Parallel-safe declarations:
  `grep -RIn 'PARALLEL_SAFE\|PARALLEL_RESTRICTED\|PARALLEL_UNSAFE' source/src/backend | head -10`

## Cross-references

- `knowledge/subsystems/storage-ipc.md` — DSM + shm_mq
  underlying IPC.
- `knowledge/idioms/snapshot-acquisition.md` — workers
  share snapshot; don't acquire their own.
- `knowledge/idioms/subtransaction-stack.md` — workers
  can't push subxacts.
- `knowledge/idioms/error-context-callbacks.md` — worker
  errors re-raised in leader.
- `.claude/skills/executor-and-planner.md` — Gather /
  GatherMerge nodes are the planner's parallel-query
  primitives.
- `.claude/skills/parallel-query/SKILL.md` — companion
  skill covering parallel-query design.
- `source/src/include/access/parallel.h` — full API.
- `source/src/backend/access/transam/parallel.c` —
  implementation.
