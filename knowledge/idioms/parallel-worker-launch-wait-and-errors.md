# Parallel queries — launch, wait, and error propagation

A parallel-aware operation goes through three coordination
phases with its workers:

1. **Launch** — `LaunchParallelWorkers` calls
   `RegisterDynamicBackgroundWorker` to ask the postmaster to
   fork each worker.
2. **Attach** — `WaitForParallelWorkersToAttach` polls each
   worker's error queue until it's been claimed, confirming
   the worker is alive.
3. **Finish** — `WaitForParallelWorkersToFinish` drains the
   error queues and updates `XactLastRecEnd` from the
   workers' final XLog positions.

Plus the **asynchronous error path**: workers report errors
via shm_mq error queues; the leader's signal handler flags
`ParallelMessagePending`, and `CHECK_FOR_INTERRUPTS` calls
`ProcessParallelMessages` which dispatches by message type.

This doc covers all four mechanisms.  The context/DSM setup
is [[parallel-context-and-dsm]].  The state-propagation
subsystems are [[parallel-state-propagation]].

**Anchors** (all cites against `source/` at commit `e18b0cb7344`):
- `source/src/backend/access/transam/parallel.c` — launch / wait / signal handler
- `source/src/backend/storage/lmgr/proc.c` — `BecomeLockGroupLeader`
- `source/src/backend/postmaster/bgworker.c` — `RegisterDynamicBackgroundWorker`

## `LaunchParallelWorkers` — register N bgworkers

`parallel.c:580-667` [verified-by-code].  The function does
four things:

### 1. Become a lock group leader

`parallel.c:595` [verified-by-code]:

```c
BecomeLockGroupLeader();
```

The **lock group** is what makes parallel workers safely share
lock requests with the leader.  Without it, two workers trying
to acquire the same lock that's held by the leader would block
each other (deadlock).  With lock groups, the lock manager
treats all group members as one logical lock holder for
conflict-detection purposes.

`BecomeLockGroupLeader` (in `proc.c`) initializes
`MyProc->lockGroupLeader = MyProc` and adds itself to the
lock-group hash.  Workers attach via `BecomeLockGroupMember`
during their startup.

### 2. Configure the `BackgroundWorker` template

`parallel.c:603-616` [verified-by-code]:

```c
memset(&worker, 0, sizeof(worker));
snprintf(worker.bgw_name, BGW_MAXLEN, "parallel worker for PID %d",
         MyProcPid);
snprintf(worker.bgw_type, BGW_MAXLEN, "parallel worker");
worker.bgw_flags =
    BGWORKER_SHMEM_ACCESS | BGWORKER_BACKEND_DATABASE_CONNECTION
    | BGWORKER_CLASS_PARALLEL;
worker.bgw_start_time = BgWorkerStart_ConsistentState;
worker.bgw_restart_time = BGW_NEVER_RESTART;
sprintf(worker.bgw_library_name, "postgres");
sprintf(worker.bgw_function_name, "ParallelWorkerMain");
worker.bgw_main_arg = UInt32GetDatum(dsm_segment_handle(pcxt->seg));
worker.bgw_notify_pid = MyProcPid;
```

The seven settings worth understanding:

| Field | Value | Meaning |
|---|---|---|
| `bgw_flags` | `SHMEM_ACCESS \| BACKEND_DATABASE_CONNECTION \| CLASS_PARALLEL` | shared-mem attach, full backend, count against `max_parallel_workers` not `max_worker_processes` |
| `bgw_start_time` | `BgWorkerStart_ConsistentState` | wait for streaming-replication consistency before starting (relevant on standbys) |
| `bgw_restart_time` | `BGW_NEVER_RESTART` | if the worker dies, don't restart it; the parallel operation fails |
| `bgw_library_name` | `"postgres"` | the framework's `ParallelWorkerMain` is in the main binary |
| `bgw_function_name` | `"ParallelWorkerMain"` | always this — the user's entrypoint is looked up later via the DSM |
| `bgw_main_arg` | `dsm_segment_handle(pcxt->seg)` | the DSM handle to attach to |
| `bgw_notify_pid` | `MyProcPid` | postmaster sends SIGUSR1 to the leader on worker state changes |

Note `bgw_function_name` is always `"ParallelWorkerMain"` — a
single framework entrypoint that demultiplexes by reading the
caller's `(library_name, function_name)` from the DSM's
`PARALLEL_KEY_ENTRYPOINT` chunk.

### 3. Register N workers

`parallel.c:626-653` [verified-by-code]:

```c
for (i = 0; i < pcxt->nworkers_to_launch; ++i)
{
    memcpy(worker.bgw_extra, &i, sizeof(int));
    if (!any_registrations_failed &&
        RegisterDynamicBackgroundWorker(&worker,
                                        &pcxt->worker[i].bgwhandle))
    {
        shm_mq_set_handle(pcxt->worker[i].error_mqh,
                          pcxt->worker[i].bgwhandle);
        pcxt->nworkers_launched++;
    }
    else
    {
        any_registrations_failed = true;
        pcxt->worker[i].bgwhandle = NULL;
        shm_mq_detach(pcxt->worker[i].error_mqh);
        pcxt->worker[i].error_mqh = NULL;
    }
}
```

Three things:

#### `bgw_extra` carries the worker number

`memcpy(worker.bgw_extra, &i, sizeof(int))` writes the
worker index into the bgworker's extra-data field.  Workers
read it back via `ParallelWorkerNumber = *(int *) MyBgworkerEntry->bgw_extra`,
which is what gives each worker a unique ID for partitioning
work.

#### `shm_mq_set_handle` ties error mq to bgw handle

`shm_mq_set_handle(error_mqh, bgwhandle)` lets the shm_mq
machinery notice when the bgworker dies.  Without it, a
crashed worker would never deliver an EOF on the error mq and
the leader would wait forever.

#### "Any registration failed" short-circuit

After the first `RegisterDynamicBackgroundWorker` returns
false (out of slots), all subsequent iterations skip the
registration call but still execute the bookkeeping
(`shm_mq_detach`, NULL the bgwhandle).  The comment at
`parallel.c:639-647` [from-comment]:

> If we weren't able to register the worker, then we've
> bumped up against the max_worker_processes limit, and
> future registrations will probably fail too, so arrange to
> skip them.  But we still have to execute this code for the
> remaining slots to make sure that we forget about the error
> queues we budgeted for those workers.  Otherwise, we'll
> wait for them to start, but they never will.

The "detach the unused error mq" is the critical bit — it
records "this slot is dead" so `WaitForParallelWorkersToFinish`
doesn't sit waiting for messages from a worker that was
never created.

### 4. Allocate `known_attached_workers`

`parallel.c:659-663` [verified-by-code]:

```c
if (pcxt->nworkers_launched > 0)
{
    pcxt->known_attached_workers = palloc0_array(bool, pcxt->nworkers_launched);
    pcxt->nknown_attached_workers = 0;
}
```

A bit-per-worker tracking who has acknowledged attachment.
Populated by `WaitForParallelWorkersToAttach`.

## `WaitForParallelWorkersToAttach` — confirm workers are alive

`parallel.c:701-791` [verified-by-code].  The polling loop:

```c
for (;;)
{
    CHECK_FOR_INTERRUPTS();

    for (i = 0; i < pcxt->nworkers_launched; ++i)
    {
        if (pcxt->known_attached_workers[i])
            continue;

        if (pcxt->worker[i].error_mqh == NULL)
        {
            /* Worker already exited cleanly. */
            pcxt->known_attached_workers[i] = true;
            ++pcxt->nknown_attached_workers;
            continue;
        }

        status = GetBackgroundWorkerPid(pcxt->worker[i].bgwhandle, &pid);
        if (status == BGWH_STARTED)
        {
            mq = shm_mq_get_queue(pcxt->worker[i].error_mqh);
            if (shm_mq_get_sender(mq) != NULL)
            {
                pcxt->known_attached_workers[i] = true;
                ++pcxt->nknown_attached_workers;
            }
        }
        else if (status == BGWH_STOPPED)
        {
            /* If stopped without attaching, that's an error. */
            mq = shm_mq_get_queue(pcxt->worker[i].error_mqh);
            if (shm_mq_get_sender(mq) == NULL)
                ereport(ERROR, ...
                        "parallel worker failed to initialize");

            pcxt->known_attached_workers[i] = true;
            ++pcxt->nknown_attached_workers;
        }
        else
        {
            /* BGWH_NOT_YET_STARTED — wait */
            rc = WaitLatch(MyLatch,
                           WL_LATCH_SET | WL_EXIT_ON_PM_DEATH,
                           -1, WAIT_EVENT_BGWORKER_STARTUP);
            if (rc & WL_LATCH_SET)
                ResetLatch(MyLatch);
        }
    }

    if (pcxt->nknown_attached_workers >= pcxt->nworkers_launched)
        break;
}
```

Three states per worker:

| BGWH state | Action |
|---|---|
| `BGWH_NOT_YET_STARTED` | wait on latch |
| `BGWH_STARTED` + mq sender set | mark attached |
| `BGWH_STARTED` + mq sender NULL | not yet attached; continue polling |
| `BGWH_STOPPED` + mq sender set | worker started, attached, ran briefly, exited cleanly |
| `BGWH_STOPPED` + mq sender NULL | worker died before attaching → ERROR |

The "stopped without attaching" detection is the critical
failure check.  Two cases lead here:

1. **`fork()` failure** in the postmaster.  Rare but
   real.
2. **Worker process crash** during early startup before
   `pq_redirect_to_shm_mq` claimed the error queue.

In both cases the leader gets a clear error message: *"parallel
worker failed to initialize / More details may be available in
the server log"*.  The hint points at the postmaster log
because that's where fork failures get logged.

### When to call `WaitForParallelWorkersToAttach`

The header comment at `parallel.c:690-699` [from-comment]:

> In general, the leader process should do as much work as
> possible before calling this function.  fork() failures
> and other early-startup failures are very uncommon, and
> having the leader sit idle when it could be doing useful
> work is undesirable.

So the typical pattern: launch workers, **do the leader's
share of work**, then call `WaitForParallelWorkersToAttach`
just before doing something that would deadlock if a worker
isn't actually attached (like waiting for a specific worker's
tuple queue).

Or skip it entirely: `WaitForParallelWorkersToFinish` will
catch any fork failures eventually.

## `WaitForParallelWorkersToFinish` — drain to completion

`parallel.c:804-908` [verified-by-code].  The main wait
function called after all useful work is done:

```c
for (;;)
{
    bool anyone_alive = false;
    int  nfinished = 0;

    CHECK_FOR_INTERRUPTS();

    for (i = 0; i < pcxt->nworkers_launched; ++i)
    {
        if (pcxt->worker[i].error_mqh == NULL)
            ++nfinished;
        else if (pcxt->known_attached_workers[i])
        {
            anyone_alive = true;
            break;
        }
    }

    if (!anyone_alive)
    {
        if (nfinished >= pcxt->nworkers_launched)
            break;

        /* check for stopped-without-attaching */
        for (i = 0; i < pcxt->nworkers_launched; ++i)
        {
            /* ... same check as WaitForParallelWorkersToAttach ... */
        }
    }

    (void) WaitLatch(MyLatch, WL_LATCH_SET | WL_EXIT_ON_PM_DEATH, -1,
                     WAIT_EVENT_PARALLEL_FINISH);
    ResetLatch(MyLatch);
}
```

Three states tracked:

- **`error_mqh == NULL`** — worker has sent a `PqMsg_Terminate`
  (clean exit); `ProcessParallelMessage` nulled the mq.
- **`known_attached_workers[i]`** — confirmed alive at least
  once; still listening.
- Anything else — not yet attached, or attached then exited
  without `Terminate` (a bug — error queue should always
  send Terminate before exit).

The loop exits when all workers are confirmed `Terminate`d
(`nfinished == nworkers_launched`).

### Final XLog-end update

`parallel.c:900-907` [verified-by-code]:

```c
if (pcxt->toc != NULL)
{
    FixedParallelState *fps;

    fps = shm_toc_lookup(pcxt->toc, PARALLEL_KEY_FIXED, false);
    if (fps->last_xlog_end > XactLastRecEnd)
        XactLastRecEnd = fps->last_xlog_end;
}
```

Each worker, before exiting, updates `fps->last_xlog_end`
under the spinlock with its own `XactLastRecEnd` (if it
generated any WAL — usually parallel index builds, never plain
parallel SELECT).  The leader takes the max so its own
`XactLastRecEnd` accounts for the workers' contribution; this
is what makes parallel-write operations wait for sync
replication correctly.

## Asynchronous error path — the signal-handler chain

### `HandleParallelMessageInterrupt` — signal handler

`parallel.c:1045-1051` [verified-by-code]:

```c
void
HandleParallelMessageInterrupt(void)
{
    InterruptPending = true;
    ParallelMessagePending = true;
    /* latch will be set by procsignal_sigusr1_handler */
}
```

Signal-safe: just two flag writes.  The actual processing
happens later inside `CHECK_FOR_INTERRUPTS` →
`ProcessInterrupts` → `ProcessParallelMessages`.

The signal is `SIGUSR1` with the procsignal multiplexer
demuxing to `PROCSIG_PARALLEL_MESSAGE`.  The leader's
postmaster-registered `bgw_notify_pid` is what gets SIGUSR1
when a worker writes to its error queue.

### `ProcessParallelMessages` — drain all queues

`parallel.c:1056-1144` [verified-by-code].  Walks every
active `pcxt` in `pcxt_list`, then every worker in each
context, calling `shm_mq_receive(error_mqh, ...)` until the
queue is empty.  Each received message goes to
`ProcessParallelMessage`.

The function brackets its work with `HOLD_INTERRUPTS` /
`RESUME_INTERRUPTS` because — per the comment at lines
1064-1070 [from-comment] — recursive calls into
`ProcessInterrupts` during message processing could be
unsafe.

A private `hpm_context` memory context is used to avoid
leaking deserialized errors into the surrounding context.

### `ProcessParallelMessage` — the four message types

`parallel.c:1145-1254` [verified-by-code].  Switch on
`pq_getmsgbyte`:

#### `PqMsg_ErrorResponse` / `PqMsg_NoticeResponse`

Parse with `pq_parse_errornotice` into an `ErrorData` struct,
then:

```c
edata.elevel = Min(edata.elevel, ERROR);

if (debug_parallel_query != DEBUG_PARALLEL_REGRESS)
{
    if (edata.context)
        edata.context = psprintf("%s\n%s", edata.context,
                                 _("parallel worker"));
    else
        edata.context = pstrdup(_("parallel worker"));
}

save_error_context_stack = error_context_stack;
error_context_stack = pcxt->error_context_stack;

ThrowErrorData(&edata);

error_context_stack = save_error_context_stack;
```

Three subtleties:

1. **Cap elevel at ERROR.**  A worker's `FATAL` becomes our
   `ERROR` — *"Death of a worker isn't enough justification
   for suicide"* (line 1170 [from-comment]).  The leader
   continues normally after handling.
2. **Append "parallel worker" context.**  So error output
   shows which side of the parallel boundary the error came
   from.  Suppressed in `DEBUG_PARALLEL_REGRESS` mode to keep
   regression tests deterministic.
3. **Switch error context stack to context-creation-time
   stack.**  The leader's *current* error context might be
   inside some unrelated function; the worker's error should
   show context from where the `ParallelContext` was created.

`ThrowErrorData` re-throws the error in the leader.  For
ERROR-level messages, control doesn't return; for NOTICE/INFO/
etc., the line after restores the previous error context.

#### `PqMsg_NotificationResponse`

A `LISTEN/NOTIFY` notification from a worker (rare —
parallel workers shouldn't usually NOTIFY).  Forwarded to the
leader's client via `NotifyMyFrontEnd`.

#### `PqMsg_Progress`

A worker's `pgstat_progress_update_param` call.  The leader
adds the worker's increment to its own progress counter.  This
is what makes EXPLAIN ANALYZE's "rows processed" counts
combine leader + workers correctly.

#### `PqMsg_Terminate`

The worker is shutting down cleanly.  Detach the mq and null
the handle:

```c
case PqMsg_Terminate:
    shm_mq_detach(pcxt->worker[i].error_mqh);
    pcxt->worker[i].error_mqh = NULL;
    break;
```

This is what makes `WaitForParallelWorkersToFinish`'s
"`error_mqh == NULL`" branch fire.  Without it, the leader
would wait forever.

#### Default — unknown message type

`elog(ERROR, "unrecognized message type received from parallel worker: %c (message length %d bytes)")`.
A bug in the worker's message generation; should never
happen.

## Cleanup paths — `DestroyParallelContext` and `AtEO*_Parallel`

### `DestroyParallelContext`

`parallel.c:958-1027` [verified-by-code].  The full
six-step cleanup, walked in [[parallel-context-and-dsm]]:

1. `dlist_delete` from `pcxt_list` (must be first — abort
   safety).
2. `TerminateBackgroundWorker` on each worker.
3. `shm_mq_detach` on each error queue.
4. `dsm_detach` (this implicitly destroys the segment).
5. `HOLD_INTERRUPTS` + `WaitForParallelWorkersToExit` (uninterruptible
   wait — workers must finish dying before we proceed).
6. Free memory and the struct.

### `AtEOSubXact_Parallel` and `AtEOXact_Parallel`

`parallel.c:1262-1295` [verified-by-code].  Pop and destroy
every parallel context owned by the closing subxact (or top
xact); warn on commit if any are still present (caller leaked
the context).

```c
void
AtEOSubXact_Parallel(bool isCommit, SubTransactionId mySubId)
{
    while (!dlist_is_empty(&pcxt_list))
    {
        pcxt = dlist_head_element(ParallelContext, node, &pcxt_list);
        if (pcxt->subid != mySubId)
            break;
        if (isCommit)
            elog(WARNING, "leaked parallel context");
        DestroyParallelContext(pcxt);
    }
}
```

The walk only touches the head while it matches `mySubId` —
deeper subxact contexts have already been cleaned by the
subxact that owned them, so the first non-match means we're
done.

`AtEOXact_Parallel` is simpler: clean everything that's left.

## `WaitForParallelWorkersToExit` — full shutdown

`parallel.c:918-948` [verified-by-code].  Loops calling
`WaitForBackgroundWorkerShutdown` per worker:

```c
status = WaitForBackgroundWorkerShutdown(pcxt->worker[i].bgwhandle);

if (status == BGWH_POSTMASTER_DIED)
    ereport(FATAL,
            (errcode(ERRCODE_ADMIN_SHUTDOWN),
             errmsg("postmaster exited during a parallel transaction")));

pfree(pcxt->worker[i].bgwhandle);
pcxt->worker[i].bgwhandle = NULL;
```

The function comment at lines 911-916 [from-comment]
distinguishes:

> The difference between WaitForParallelWorkersToFinish and
> this function is that the former just ensures that last
> message sent by a worker backend is received by the leader
> backend whereas this ensures the complete shutdown.

So `Finish` is the "drain messages" wait; `Exit` is the
"workers are actually dead" wait.  Both are needed: `Finish`
catches errors, `Exit` ensures the DSM can be released.

The `BGWH_POSTMASTER_DIED` → `FATAL` is the only path where
parallel-query handling can escalate to FATAL — and rightly,
because without the postmaster nothing can be cleaned up.

## Invariants worth remembering

1. **`BecomeLockGroupLeader` before `RegisterDynamicBackgroundWorker`.**
   Workers attach via `BecomeLockGroupMember` during startup.
2. **`bgw_function_name` is always `"ParallelWorkerMain"`.**
   The caller's entrypoint is in the DSM's
   `PARALLEL_KEY_ENTRYPOINT` chunk.
3. **`bgw_extra` carries the worker number.**  Each worker
   gets a unique `ParallelWorkerNumber`.
4. **Failed registration → `any_registrations_failed = true`.**
   Subsequent slots get detached so the leader doesn't wait
   for them.
5. **`WaitForParallelWorkersToAttach` is optional** but
   catches early failures earlier.
6. **`error_mqh == NULL`** is the "worker finished cleanly"
   marker.  Set by `ProcessParallelMessage(PqMsg_Terminate)`.
7. **Worker errors cap at `ERROR`-level.**  Worker FATAL
   becomes leader ERROR.
8. **Worker error context appends "parallel worker"** unless
   in `DEBUG_PARALLEL_REGRESS`.
9. **`SIGUSR1` → `ParallelMessagePending` flag → next
   `CHECK_FOR_INTERRUPTS` runs `ProcessParallelMessages`.**
10. **`DestroyParallelContext` is unconditional** —
    `HOLD_INTERRUPTS` + `WaitForParallelWorkersToExit` ensures
    workers die before we return.
11. **`AtEO*Xact_Parallel` warns on leak then forcibly cleans
    up.**  Callers should always destroy in
    `PG_CATCH`/`PG_END_TRY`.

## Useful greps

```bash
# Launch + attach + finish
grep -n "LaunchParallelWorkers\|WaitForParallelWorkersToAttach\|WaitForParallelWorkersToFinish\|WaitForParallelWorkersToExit" \
    source/src/backend/access/transam/parallel.c

# Signal handler chain
grep -n "HandleParallelMessageInterrupt\|ProcessParallelMessages\|ProcessParallelMessage\|ParallelMessagePending" \
    source/src/backend/access/transam/parallel.c

# Message types
grep -n "PqMsg_ErrorResponse\|PqMsg_NoticeResponse\|PqMsg_NotificationResponse\|PqMsg_Progress\|PqMsg_Terminate" \
    source/src/backend/access/transam/parallel.c

# Lock group
grep -rn "BecomeLockGroupLeader\|BecomeLockGroupMember\|lockGroupLeader" source/src/backend/storage/lmgr/

# BGWH_* status codes
grep -rn "BGWH_NOT_YET_STARTED\|BGWH_STARTED\|BGWH_STOPPED\|BGWH_POSTMASTER_DIED" source/src/include/postmaster/
```

## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/access/transam/parallel.c`](../files/src/backend/access/transam/parallel.c.md) | — | launch / wait / signal handler |
| [`src/backend/postmaster/bgworker.c`](../files/src/backend/postmaster/bgworker.c.md) | — | RegisterDynamicBackgroundWorker |
| [`src/backend/storage/lmgr/proc.c`](../files/src/backend/storage/lmgr/proc.c.md) | — | BecomeLockGroupLeader |

<!-- /callsites:auto -->

## Scenarios that use me
<!-- scenarios:auto -->

*Auto-derived from direct references + transitive file-overlap.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

- [`add-new-bgworker`](../scenarios/add-new-bgworker.md)
- [`add-new-protocol-message`](../scenarios/add-new-protocol-message.md)

<!-- /scenarios:auto -->
## Cross-references

- [[parallel-context-and-dsm]] — the `ParallelContext` setup
  this doc consumes.
- [[parallel-state-propagation]] — the Serialize/Restore
  subsystems that workers process before
  `LookupParallelWorkerFunction` returns.
- [[bgworker-and-extensions]] — `RegisterDynamicBackgroundWorker`
  + `BgWorkerStart_ConsistentState` + the
  `BackgroundWorker` template fields.
- [[error-handling]] — `ThrowErrorData`, error context
  stacks, the elog/ereport flow that worker-forwarded errors
  re-enter.
- [[xmin-horizon-management]] — lock groups make the leader's
  xmin contribution cover all workers.
- [[wal-write-internals]] — `XactLastRecEnd` synchronization
  via `last_xlog_end` ensures sync-rep waits for parallel
  WAL too.
- [[memory-contexts]] — `hpm_context` is the per-message
  scratch context for `ProcessParallelMessages`.
