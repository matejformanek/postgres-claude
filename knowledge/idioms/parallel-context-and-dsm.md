# Parallel queries — `ParallelContext` lifecycle and the DSM table-of-contents

A parallel-aware PG operation (parallel sequential scan, parallel
build of an index, parallel vacuum, etc.) lives inside a
**`ParallelContext`**.  The struct itself is small — a list of
worker handles, a DSM segment, a few bookkeeping fields — but
its real complexity is the **dynamic shared memory segment** it
manages, which carries everything a worker needs to bootstrap
into the leader's view of the world: GUCs, transaction state,
snapshots, the combo-CID map, the library list, and so on.

This doc covers the **context lifecycle and DSM layout**:
`CreateParallelContext` → `InitializeParallelDSM` → DSM
table-of-contents (shm_toc) with fixed-OID keys.  The
**launch/wait/error** mechanics are
[[parallel-worker-launch-wait-and-errors]].  The
**state-propagation** (Serialize/Restore of every shared
subsystem) is [[parallel-state-propagation]].

**Anchors** (all cites against `source/` at commit `e18b0cb7344`):
- `source/src/backend/access/transam/parallel.c` — entire infrastructure
- `source/src/include/access/parallel.h` — `ParallelContext` struct
- `source/src/backend/storage/ipc/shm_toc.c` — table-of-contents allocator

## The contract — `IsInParallelMode` and parallel-safe operations

The first line of `CreateParallelContext` (`parallel.c:182`)
[verified-by-code] is the contract:

```c
Assert(IsInParallelMode());
```

`EnterParallelMode` / `ExitParallelMode` (in `xact.c`) bracket
the parallel operation.  Inside parallel mode:

- **No writes** — including no XID acquisition, no shmem
  invalidations.
- **No system catalog modifications.**
- **No CommandCounterIncrement** that changes visibility for
  other backends.
- **No subtransactions that would commit independently.**

Parallel mode is what makes the snapshot-sharing model safe:
since nobody is allowed to write, the snapshot the leader
shared at launch time stays valid for the entire parallel
operation.

The check at `parallel.c:247-248` [verified-by-code]:

```c
if (!INTERRUPTS_CAN_BE_PROCESSED())
    pcxt->nworkers = 0;
```

If the leader is in a non-interruptible section, it pretends
no workers were requested — launching them would be unsafe
because the leader can't poll their error queues.  Silent
degradation to serial mode.

## `ParallelContext` struct

`parallel.h:35-67` (referenced by usage in `parallel.c`):

```c
typedef struct ParallelContext
{
    dlist_node       node;                 /* entry in pcxt_list */
    SubTransactionId subid;                /* owning subxact */
    int              nworkers;
    int              nworkers_to_launch;
    int              nworkers_launched;
    char            *library_name;
    char            *function_name;
    ErrorContextCallback *error_context_stack;
    shm_toc_estimator estimator;
    dsm_segment     *seg;
    void            *private_memory;
    shm_toc         *toc;
    ParallelWorkerInfo *worker;
    int              nknown_attached_workers;
    bool            *known_attached_workers;
} ParallelContext;
```

Three structural choices to notice:

### 1. `nworkers` vs. `nworkers_to_launch` vs. `nworkers_launched`

| Field | When meaningful |
|---|---|
| `nworkers` | The number of workers budgeted in the DSM (memory was reserved for this many error queues, worker info, etc.) |
| `nworkers_to_launch` | The number we actually call `RegisterDynamicBackgroundWorker` for — can be less than `nworkers` on a relaunch via `ReinitializeParallelDSM` |
| `nworkers_launched` | How many `RegisterDynamicBackgroundWorker` returned true — can be less than `nworkers_to_launch` if `max_worker_processes` is exhausted |

The DSM is sized for `nworkers` and **doesn't shrink** if
launch fails — the leader still has to drain unused error
queues.  More on this in
[[parallel-worker-launch-wait-and-errors]].

### 2. `seg` (DSM) vs. `private_memory` fallback

`parallel.c:328-341` [verified-by-code]:

```c
segsize = shm_toc_estimate(&pcxt->estimator);
if (pcxt->nworkers > 0)
    pcxt->seg = dsm_create(segsize, DSM_CREATE_NULL_IF_MAXSEGMENTS);
if (pcxt->seg != NULL)
    pcxt->toc = shm_toc_create(PARALLEL_MAGIC,
                               dsm_segment_address(pcxt->seg),
                               segsize);
else
{
    pcxt->nworkers = 0;
    pcxt->private_memory = MemoryContextAlloc(TopMemoryContext, segsize);
    pcxt->toc = shm_toc_create(PARALLEL_MAGIC, pcxt->private_memory,
                               segsize);
}
```

Two failure modes funnel into the **same fallback**: zero workers
requested (`nworkers == 0`), or `dsm_create` returned NULL
because `max_dsm_segments` is exhausted.  In both cases we
allocate `private_memory` from `TopMemoryContext` and run the
operation serially.  The caller never sees the difference at
the API level — same `shm_toc_lookup` calls — just no workers
arrive.

The "graceful degradation to serial" property is what makes
parallel-aware code safe to write: you call `LaunchParallelWorkers`,
then call `WaitForParallelWorkersToFinish` (or `gather_readnext`,
etc.), and if there were no workers the leader just does all
the work itself.

### 3. `pcxt_list` — the global registry

`parallel.c:129` [verified-by-code]:

```c
static dlist_head pcxt_list = DLIST_STATIC_INIT(pcxt_list);
```

Every active `ParallelContext` is on this list.  Used by:

- **Subtransaction abort** — pop contexts whose `subid >=
  aborted_level`.
- **CCI handler** — propagate command-counter increments to
  active contexts.
- **Error handling** — terminate workers if the leader
  aborts.

A `ParallelContext` must be destroyed before its owning
subtransaction exits, or the abort handler will reap it
unpredictably.

## `CreateParallelContext` — the entry point

`parallel.c:174-205` [verified-by-code]:

```c
ParallelContext *
CreateParallelContext(const char *library_name, const char *function_name,
                      int nworkers)
{
    MemoryContext oldcontext;
    ParallelContext *pcxt;

    Assert(IsInParallelMode());
    Assert(nworkers >= 0);

    oldcontext = MemoryContextSwitchTo(TopTransactionContext);

    pcxt = palloc0_object(ParallelContext);
    pcxt->subid = GetCurrentSubTransactionId();
    pcxt->nworkers = nworkers;
    pcxt->nworkers_to_launch = nworkers;
    pcxt->library_name = pstrdup(library_name);
    pcxt->function_name = pstrdup(function_name);
    pcxt->error_context_stack = error_context_stack;
    shm_toc_initialize_estimator(&pcxt->estimator);
    dlist_push_head(&pcxt_list, &pcxt->node);

    MemoryContextSwitchTo(oldcontext);

    return pcxt;
}
```

Four observations:

### `(library_name, function_name)` — not a function pointer

Workers will be a different process; passing a function pointer
across processes is unsafe even on the same machine because
**EXEC_BACKEND builds may map shared libraries to different
addresses** in each process.  So PG passes the entrypoint by
*name*, and workers look it up at startup.

`LookupParallelWorkerFunction` at `parallel.c:1649` registers
five built-ins (`ParallelQueryMain`, `_bt_parallel_build_main`,
`_brin_parallel_build_main`, `_gin_parallel_build_main`,
`parallel_vacuum_main`); custom callers (extensions) provide
their own library name.

### `error_context_stack` snapshotted at creation

`pcxt->error_context_stack = error_context_stack` — the
context records the leader's error context at creation time.
When `ProcessParallelMessage` forwards a worker's error, it
temporarily restores this stack so the worker's error gets
the right context lines.

### `TopTransactionContext` allocation

The context itself lives in `TopTransactionContext`, so it's
freed on transaction (or subtransaction) end.  Memory leaks
get cleaned up wholesale.

### `pcxt->estimator` initialized

`shm_toc_initialize_estimator(&pcxt->estimator)` sets up the
incremental size tracker.  Subsequent
`shm_toc_estimate_chunk(&pcxt->estimator, N)` calls accumulate
the total DSM size needed.  When all chunks are estimated,
`shm_toc_estimate(&pcxt->estimator)` returns the final size.

## `InitializeParallelDSM` — the big assembly

`parallel.c:212-504` [verified-by-code].  Four logical phases:

### Phase 1 — Estimate

Lines 237-303 [verified-by-code].  For each shared subsystem,
ask "how much space do you need?":

```c
shm_toc_estimate_chunk(&pcxt->estimator, sizeof(FixedParallelState));
shm_toc_estimate_keys(&pcxt->estimator, 1);

if (pcxt->nworkers > 0)
{
    library_len = EstimateLibraryStateSpace();
    shm_toc_estimate_chunk(&pcxt->estimator, library_len);
    guc_len = EstimateGUCStateSpace();
    shm_toc_estimate_chunk(&pcxt->estimator, guc_len);
    /* ... combocid, snapshots, transaction state, ... */
    shm_toc_estimate_keys(&pcxt->estimator, 12);

    /* Error queues — one per worker */
    shm_toc_estimate_chunk(&pcxt->estimator,
                           mul_size(PARALLEL_ERROR_QUEUE_SIZE,
                                    pcxt->nworkers));
    shm_toc_estimate_keys(&pcxt->estimator, 1);

    /* Entrypoint info */
    shm_toc_estimate_chunk(&pcxt->estimator, strlen(pcxt->library_name) +
                           strlen(pcxt->function_name) + 2);
    shm_toc_estimate_keys(&pcxt->estimator, 1);
}
```

Each `Estimate*StateSpace()` returns the number of bytes that
subsystem needs to serialize itself.  The TOC needs to know
both chunk count and key count to size its own header.

### Phase 2 — Create the DSM

Lines 328-341 [verified-by-code].  Either `dsm_create` or the
`private_memory` fallback (see §`seg` vs `private_memory`).
The TOC is initialized over whichever backing memory we got:

```c
pcxt->toc = shm_toc_create(PARALLEL_MAGIC,
                           dsm_segment_address(pcxt->seg),
                           segsize);
```

`PARALLEL_MAGIC` is a fixed magic number — workers can
verify they've attached to a real parallel-query segment, not
some other DSM the leader uses for unrelated purposes.

### Phase 3 — Populate fixed state

Lines 343-363 [verified-by-code]:

```c
fps = (FixedParallelState *)
    shm_toc_allocate(pcxt->toc, sizeof(FixedParallelState));
fps->database_id = MyDatabaseId;
fps->authenticated_user_id = GetAuthenticatedUserId();
fps->session_user_id = GetSessionUserId();
fps->outer_user_id = GetCurrentRoleId();
GetUserIdAndSecContext(&fps->current_user_id, &fps->sec_context);
fps->session_user_is_superuser = GetSessionUserIsSuperuser();
fps->role_is_superuser = current_role_is_superuser;
GetTempNamespaceState(&fps->temp_namespace_id,
                      &fps->temp_toast_namespace_id);
fps->parallel_leader_pgproc = MyProc;
fps->parallel_leader_pid = MyProcPid;
fps->parallel_leader_proc_number = MyProcNumber;
fps->xact_ts = GetCurrentTransactionStartTimestamp();
fps->stmt_ts = GetCurrentStatementStartTimestamp();
fps->serializable_xact_handle = ShareSerializableXact();
SpinLockInit(&fps->mutex);
fps->last_xlog_end = InvalidXLogRecPtr;
shm_toc_insert(pcxt->toc, PARALLEL_KEY_FIXED, fps);
```

The `FixedParallelState` struct (definition at
`parallel.c:84-109`) [verified-by-code] is a single
contiguous block of scalars — small enough to fit in one
TOC chunk.  It carries:

- **Identity OIDs** — database, authenticated/session/outer/
  current users, security context.
- **Temp-namespace OIDs** — so workers see the same temp
  schema as the leader.
- **Leader's PGPROC pointer + PID + proc number** — workers
  need this to advertise group membership.
- **Transaction and statement start timestamps** — so
  `now()`, `transaction_timestamp()`, etc. agree across
  processes.
- **`serializable_xact_handle`** — for SSI predicate-locking
  participation.
- **`mutex`** + **`last_xlog_end`** — workers report their
  XLog end LSN here for flush-position tracking.

The mutex is the **only synchronization primitive** in the
fixed state; everything else is read-once.

### Phase 4 — Populate variable state

Lines 366-497 [verified-by-code].  Twelve subsystems each get
one chunk + one TOC key.  See
[[parallel-state-propagation]] for what each one carries.

## The TOC — `shm_toc` table-of-contents

The TOC is a header-plus-chunk-table at the start of the DSM
segment.  Each chunk has:

- A 64-bit **key** (`uint64`) — fixed values defined as
  `PARALLEL_KEY_*` constants.
- A pointer/offset to the chunk's data.
- The chunk's size.

Workers call `shm_toc_lookup(toc, KEY, noError)` to find data
by key.  The lookup is **linear** through the chunk table —
it's a small table (≤ 16 chunks in practice) so a hash table
would be overkill.

### The PARALLEL_KEY_* registry

`parallel.c:67-81` [verified-by-code]:

```c
#define PARALLEL_KEY_FIXED                  UINT64CONST(0xFFFFFFFFFFFF0001)
#define PARALLEL_KEY_ERROR_QUEUE            UINT64CONST(0xFFFFFFFFFFFF0002)
#define PARALLEL_KEY_LIBRARY                UINT64CONST(0xFFFFFFFFFFFF0003)
#define PARALLEL_KEY_GUC                    UINT64CONST(0xFFFFFFFFFFFF0004)
#define PARALLEL_KEY_COMBO_CID              UINT64CONST(0xFFFFFFFFFFFF0005)
#define PARALLEL_KEY_TRANSACTION_SNAPSHOT   UINT64CONST(0xFFFFFFFFFFFF0006)
#define PARALLEL_KEY_ACTIVE_SNAPSHOT        UINT64CONST(0xFFFFFFFFFFFF0007)
#define PARALLEL_KEY_TRANSACTION_STATE      UINT64CONST(0xFFFFFFFFFFFF0008)
#define PARALLEL_KEY_ENTRYPOINT             UINT64CONST(0xFFFFFFFFFFFF0009)
#define PARALLEL_KEY_SESSION_DSM            UINT64CONST(0xFFFFFFFFFFFF000A)
#define PARALLEL_KEY_PENDING_SYNCS          UINT64CONST(0xFFFFFFFFFFFF000B)
#define PARALLEL_KEY_REINDEX_STATE          UINT64CONST(0xFFFFFFFFFFFF000C)
#define PARALLEL_KEY_RELMAPPER_STATE        UINT64CONST(0xFFFFFFFFFFFF000D)
#define PARALLEL_KEY_UNCOMMITTEDENUMS       UINT64CONST(0xFFFFFFFFFFFF000E)
#define PARALLEL_KEY_CLIENTCONNINFO         UINT64CONST(0xFFFFFFFFFFFF000F)
```

The high 48 bits being `0xFFFFFFFFFFFF` is a convention —
**framework-reserved keys** start with these magic high bits;
caller-specific keys (e.g. parallel query's per-worker
tuple-queue) use smaller numeric keys (typically 0..N).
This way, framework keys and caller keys never collide.

The key registry is the **stable ABI** between the
framework's serialization and worker restoration code.  Each
key has a single chunk per parallel context.

## The session DSM — `PARALLEL_KEY_SESSION_DSM`

`parallel.c:256-266` [verified-by-code]:

```c
if (pcxt->nworkers > 0)
{
    session_dsm_handle = GetSessionDsmHandle();

    if (session_dsm_handle == DSM_HANDLE_INVALID)
        pcxt->nworkers = 0;
}
```

The **session DSM** is a separate DSM segment that's per-
session, not per-parallel-context.  It holds things that must
agree across all parallel operations within a session — most
importantly, the **RECORD typmod registry**.

The comment at lines 259-264 [from-comment]:

> If we weren't able to create a per-session DSM segment,
> then we can continue but we can't safely launch any workers
> because their record typmods would be incompatible so they
> couldn't exchange tuples.

So if the session DSM can't be created, parallel operations
silently degrade to serial.  This is a rare case (only when
`max_session_dsm_segments` is exhausted).

The `session_dsm_handle` (32-bit) gets stored in the parallel
context's DSM under `PARALLEL_KEY_SESSION_DSM` so workers can
attach to it.

## `ReinitializeParallelDSM` — relaunch a context

`parallel.c:510-577` [verified-by-code].  For operations that
do multiple parallel passes (e.g. parallel index build's
"build then compare" phases), the same `ParallelContext` can
be reinitialized without rebuilding the DSM:

```c
void
ReinitializeParallelDSM(ParallelContext *pcxt)
{
    /* Wait for any old workers to exit. */
    if (pcxt->nworkers_launched > 0)
    {
        WaitForParallelWorkersToFinish(pcxt);
        WaitForParallelWorkersToExit(pcxt);
        pcxt->nworkers_launched = 0;
        /* ... */
    }
    /* ... reset shm_mq handles, refresh transient state ... */
}
```

The DSM segment, TOC, and fixed state stay; the variable
state (snapshots, GUCs, etc.) is **not** re-serialized
either — the assumption is that nothing has changed.  Only
the per-worker bookkeeping (error queues, worker handles) is
reset.

This is what makes "parallel index build, phase 2" cheap —
no fresh DSM allocation, no fresh state serialization.

## `DestroyParallelContext` — the cleanup path

`parallel.c:1262-end-of-function` [verified-by-code].  Three
phases:

1. **Kill workers** that haven't terminated naturally
   (`TerminateBackgroundWorker` for each).
2. **Drain error queues** so any final messages get
   forwarded.
3. **Detach DSM**, free `private_memory` if used, remove from
   `pcxt_list`, `pfree` the struct.

Always safe to call: if `LaunchParallelWorkers` was never
called, the cleanup is a no-op.  This makes
`PG_TRY/PG_CATCH` patterns straightforward — set up the
context, do the parallel work, destroy unconditionally.

## Invariants worth remembering

1. **`CreateParallelContext` requires `IsInParallelMode()`.**
   Enter parallel mode first (via `EnterParallelMode`).
2. **`nworkers` budgets the DSM; `nworkers_to_launch`
   triggers registration; `nworkers_launched` reports
   actual success.**
3. **Function pointers don't cross processes** — workers look
   up their entry by `(library_name, function_name)`.
4. **`PARALLEL_MAGIC` validates the DSM** when a worker
   attaches.  Mismatch = ERROR.
5. **TOC keys with high bits `0xFFFFFFFFFFFF` are reserved
   for the framework.**  Caller keys must be smaller.
6. **The session DSM is per-session, not per-context.**
   Failure to allocate it forces serial fallback.
7. **`FixedParallelState.mutex` is the only sync primitive
   in the fixed block.**  Used for `last_xlog_end` updates.
8. **DSM failure falls back to `private_memory`** — same
   API, no workers.  Callers must tolerate
   `nworkers_launched == 0`.
9. **A context lives in `TopTransactionContext` and `pcxt_list`.**
   Subxact abort or transaction abort cleans up both.
10. **`ReinitializeParallelDSM` reuses the DSM** —
    snapshots/GUCs/etc. are not re-serialized.

## Useful greps

```bash
# Lifecycle API
grep -n "CreateParallelContext\|InitializeParallelDSM\|ReinitializeParallelDSM\|DestroyParallelContext" \
    source/src/backend/access/transam/parallel.c

# DSM key registry
grep -n "PARALLEL_KEY_" source/src/backend/access/transam/parallel.c

# FixedParallelState fields
grep -n "fps->\|FixedParallelState" source/src/backend/access/transam/parallel.c | head -30

# Estimation hooks
grep -n "Estimate.*Space\|EstimateSnapshotSpace\|EstimateGUCStateSpace\|EstimateLibraryStateSpace" \
    source/src/backend/

# Session DSM
grep -rn "GetSessionDsmHandle\|PARALLEL_KEY_SESSION_DSM" source/src/backend/
```



## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/access/transam/parallel.c`](../files/src/backend/access/transam/parallel.c.md) | — | entire infrastructure |
| [`src/backend/storage/ipc/shm_toc.c`](../files/src/backend/storage/ipc/shm_toc.c.md) | — | table-of-contents allocator |
| [`src/include/access/parallel.h`](../files/src/include/access/parallel.h.md) | — | ParallelContext struct |

<!-- /callsites:auto -->

## Cross-references

- [[parallel-worker-launch-wait-and-errors]] — how the context
  gets connected to actual worker processes.
- [[parallel-state-propagation]] — each Estimate/Serialize/
  Restore subsystem.
- [[snapshot-export-historic-parallel]] — `SerializeSnapshot` /
  `RestoreSnapshot` are called for both snapshot keys here.
- [[parallel-worker-coordination]] — older single-file
  summary; this doc family supersedes it.
- [[memory-contexts]] — `TopTransactionContext` is the
  context's home; `TopMemoryContext` holds `private_memory`
  for serial fallback.
- [[bgworker-and-extensions]] — `BackgroundWorker` struct +
  `RegisterDynamicBackgroundWorker` are the substrate.
- [[wal-write-internals]] — `last_xlog_end` in
  `FixedParallelState` is what workers update via spinlock.
