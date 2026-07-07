# Logical-rep apply — streaming mode and parallel apply workers

The default apply mode buffers each transaction on the
publisher until it commits, then ships the whole thing to the
subscriber.  That's fine for OLTP-scale transactions but
catastrophic for bulk loads: a `COPY` of 100M rows would
inflate publisher memory and stall WAL sender progress.

**Streaming mode** is the way out.  `SUBSCRIPTION ... WITH
(streaming = on|parallel)` makes the publisher ship in-progress
transaction changes as `STREAM_START` / row-events /
`STREAM_STOP` chunks before commit, then a final `STREAM_COMMIT`
that finalizes them.  The subscriber either **spools to disk**
and replays at commit (streaming = on) or **forwards to a
parallel apply worker** that applies in real time (streaming
= parallel).

This doc covers both subscriber-side paths.  The dispatch
context is [[apply-worker-loop-and-dispatch]]; row handlers
that participate via `handle_streamed_transaction` are
[[apply-handlers-insert-update-delete]].

**Anchors** (all cites against `source/` at commit `e18b0cb7344`):
- `source/src/backend/replication/logical/worker.c` — `apply_handle_stream_*`, the action machine
- `source/src/backend/replication/logical/applyparallelworker.c` — `ParallelApplyWorkerInfo`, the deadlock-detection lock graph

## The five-action enum

`worker.c:374-384` [verified-by-code]:

```c
typedef enum
{
    TRANS_LEADER_APPLY,
    TRANS_LEADER_SERIALIZE,
    TRANS_LEADER_SEND_TO_PARALLEL,
    TRANS_LEADER_PARTIAL_SERIALIZE,
    TRANS_PARALLEL_APPLY,
} TransApplyAction;
```

The header comment at lines 340-373 [from-comment] enumerates
when each fires:

| Action | Who | When |
|---|---|---|
| `TRANS_LEADER_APPLY` | leader / tablesync | non-streaming transactions, OR replay of a previously-spooled streamed transaction at commit |
| `TRANS_LEADER_SERIALIZE` | leader / tablesync | streaming=on; spool to disk and replay at commit |
| `TRANS_LEADER_SEND_TO_PARALLEL` | leader | streaming=parallel; forward chunks to a parallel apply worker via shm_mq |
| `TRANS_LEADER_PARTIAL_SERIALIZE` | leader | streaming=parallel but the shm_mq filled up — switched to disk for the rest of the transaction |
| `TRANS_PARALLEL_APPLY` | parallel apply | applying chunks received from a leader |

`get_transaction_apply_action(xid, &winfo)` (`worker.c:632`)
returns the right value based on `MySubscription->stream`,
whether we're already a parallel worker, and whether the
parallel queue is healthy.  Every streaming-message handler
dispatches on this enum.

## `apply_handle_stream_start` — the five-way switch

`worker.c:1742-1870` [verified-by-code].  Walking it path by path:

### Common preamble

```c
StringInfoData original_msg = *s;
if (in_streamed_transaction)
    ereport(ERROR, ... "duplicate STREAM START message");
Assert(!TransactionIdIsValid(stream_xid));

in_streamed_transaction = true;
stream_xid = logicalrep_read_stream_start(s, &first_segment);
set_apply_error_context_xact(stream_xid, InvalidXLogRecPtr);

if (first_segment)
    pa_allocate_worker(stream_xid);

apply_action = get_transaction_apply_action(stream_xid, &winfo);
```

Three things:

1. **`original_msg` saved** before consumption — needed if we
   later have to write the raw message to a spool file.
2. **`in_streamed_transaction = true`** is the flag the row
   handlers check via `handle_streamed_transaction` to know
   they should spool instead of apply.
3. **`pa_allocate_worker(stream_xid)`** runs only on the
   first segment of a new transaction (subsequent segments
   reuse the same worker if one was acquired).

### TRANS_LEADER_SERIALIZE — start a real local transaction

`worker.c:1780-1791` [verified-by-code]:

```c
case TRANS_LEADER_SERIALIZE:
    stream_start_internal(stream_xid, first_segment);
    break;
```

`stream_start_internal` opens or creates the per-transaction
spool file (named by subid + xid), starts a local SQL
transaction so the BufFile machinery has a transaction
context, and seeks to the end if this isn't the first segment.

The comment at lines 1781-1789 [from-comment]:

> Function stream_start_internal starts a transaction. This
> transaction will be committed on the stream stop unless it
> is a tablesync worker in which case it will be committed
> after processing all the messages. We need this transaction
> for handling the BufFile, used for serializing the streaming
> data and subxact info.

So serialize mode actually opens a *local* transaction at
every STREAM_START, commits it at STREAM_STOP (saving the spool
file's offset), and re-opens for the next segment.  This is
because BufFile lifetime is tied to a transaction.

### TRANS_LEADER_SEND_TO_PARALLEL — forward via shm_mq

`worker.c:1793-1820` [verified-by-code]:

```c
case TRANS_LEADER_SEND_TO_PARALLEL:
    Assert(winfo);

    if (pa_send_data(winfo, s->len, s->data))
    {
        if (!first_segment)
            pa_unlock_stream(winfo->shared->xid, AccessExclusiveLock);

        pg_atomic_add_fetch_u32(&winfo->shared->pending_stream_count, 1);
        pa_set_stream_apply_worker(winfo);
        break;
    }

    /* Switch to serialize mode when we are not able to send */
    pa_switch_to_partial_serialize(winfo, !first_segment);

    pg_fallthrough;
```

Two paths in this case:

- **`pa_send_data` succeeds** — the chunk is now in the
  parallel worker's input shm_mq.  Increment the atomic
  pending counter and cache the worker for subsequent
  messages.
- **`pa_send_data` fails** (mq full, timeout) —
  `pa_switch_to_partial_serialize` flips the action to
  `TRANS_LEADER_PARTIAL_SERIALIZE` and **falls through** to
  that case below.

The `pa_unlock_stream(AccessExclusiveLock)` at line 1809 is
the **deadlock-protection unlock** documented at the top of
`applyparallelworker.c`.  See §Locking below.

### TRANS_LEADER_PARTIAL_SERIALIZE — graceful fallback

`worker.c:1829-1844` [verified-by-code]:

```c
case TRANS_LEADER_PARTIAL_SERIALIZE:
    Assert(winfo);

    if (apply_action != TRANS_LEADER_SEND_TO_PARALLEL)
        stream_start_internal(stream_xid, first_segment);

    stream_write_change(LOGICAL_REP_MSG_STREAM_START, &original_msg);

    pa_set_stream_apply_worker(winfo);
    break;
```

The leader has a parallel worker assigned but can't deliver
via shm_mq right now — instead the chunk is written to a spool
file.  Critically: the worker is *still* the parallel apply
worker that will pick it up at commit — the difference is
**how** the data reaches it (file vs shm_mq).

Why two cases?  The comment at lines 364-369 [from-comment]:

> We can't use TRANS_LEADER_SERIALIZE for this case because,
> in addition to serializing changes, the leader worker also
> needs to serialize the STREAM_XXX message to a file, and
> wait for the parallel apply worker to finish the transaction
> when processing the transaction finish command.

So `PARTIAL_SERIALIZE` knows there's still a parallel worker
to coordinate with at commit time.  `SERIALIZE` doesn't.

### TRANS_PARALLEL_APPLY — we're in the parallel worker

`worker.c:1846-1862` [verified-by-code]:

```c
case TRANS_PARALLEL_APPLY:
    if (first_segment)
    {
        pa_lock_transaction(MyParallelShared->xid, AccessExclusiveLock);
        pa_set_xact_state(MyParallelShared, PARALLEL_TRANS_STARTED);

        logicalrep_worker_wakeup(WORKERTYPE_APPLY,
                                 MyLogicalRepWorker->subid, InvalidOid);
    }

    parallel_stream_nchanges = 0;
    break;
```

Inside a parallel apply worker.  On the first segment:

1. **Take the transaction lock** — the leader will need to
   wait on this at commit-time to preserve commit order.
2. **Mark `PARALLEL_TRANS_STARTED`** — the leader can now
   detect "this worker has begun applying" and proceed past
   its own waits.
3. **Wake the leader** — useful if the leader was sleeping
   waiting for this worker to be ready.

## `apply_handle_stream_stop` — the chunk boundary

`worker.c:1901-1998` [verified-by-code].  Same five-way
switch, but the semantics flip:

### TRANS_LEADER_SERIALIZE — commit the local txn, reset
`LogicalStreamingContext`

```c
case TRANS_LEADER_SERIALIZE:
    stream_stop_internal(stream_xid);
    break;
```

`stream_stop_internal` at `worker.c:1878-1896`
[verified-by-code]:

```c
void
stream_stop_internal(TransactionId xid)
{
    subxact_info_write(MyLogicalRepWorker->subid, xid);
    stream_close_file();

    Assert(IsTransactionState());

    CommitTransactionCommand();
    MemoryContextReset(LogicalStreamingContext);
}
```

Three actions: write the **subxact info file** (the offset
table for sub-transactions), close the spool, commit the per-
chunk transaction.  `LogicalStreamingContext` reset frees
the chunk's transient palloc'd state.

### TRANS_LEADER_SEND_TO_PARALLEL — take the stream lock, then send

`worker.c:1920-1935` [verified-by-code]:

```c
case TRANS_LEADER_SEND_TO_PARALLEL:
    pa_lock_stream(winfo->shared->xid, AccessExclusiveLock);

    if (pa_send_data(winfo, s->len, s->data))
    {
        pa_set_stream_apply_worker(NULL);
        break;
    }

    pa_switch_to_partial_serialize(winfo, true);
    pg_fallthrough;
```

Notice the order: **take the lock first, then send the
STOP**.  The comment at lines 1923-1927 [from-comment]:

> Lock before sending the STREAM_STOP message so that the
> leader can hold the lock first and the parallel apply
> worker will wait for leader to release the lock.  See
> Locking Considerations atop applyparallelworker.c.

This is the deadlock-detection edge — see §Locking below.

### TRANS_PARALLEL_APPLY — decrement, possibly wait

`worker.c:1950-1977` [verified-by-code]:

```c
case TRANS_PARALLEL_APPLY:
    elog(DEBUG1, "applied %u changes in the streaming chunk",
         parallel_stream_nchanges);

    pa_decr_and_wait_stream_block();
    break;
```

`pa_decr_and_wait_stream_block` decrements
`pending_stream_count`; if it reaches zero, takes
`AccessShare` on the stream lock, which **blocks** until the
leader releases it (which it does after STREAM_START of the
next chunk).  This is the symmetric edge.

## `apply_handle_stream_commit` — replay the buffered changes

`worker.c:2407-` [verified-by-code]:

```c
case TRANS_LEADER_APPLY:
    /* The transaction has been serialized to file, so replay all
     * the spooled operations. */
    apply_spooled_messages(MyLogicalRepWorker->stream_fileset, xid,
                           commit_data.commit_lsn);

    apply_handle_commit_internal(&commit_data);
    break;
```

`apply_spooled_messages` (`worker.c:2335-2401`) is the loop
that reads the spool file back and feeds the bytes through
`apply_dispatch` one message at a time:

```c
while (true)
{
    nbytes = BufFileReadMaybeEOF(stream_fd, &len, sizeof(len), true);
    if (nbytes == 0) break;
    BufFileReadExact(stream_fd, buffer, len);

    initReadOnlyStringInfo(&s2, buffer, len);
    oldcxt = MemoryContextSwitchTo(ApplyMessageContext);
    apply_dispatch(&s2);
    MemoryContextReset(ApplyMessageContext);
    MemoryContextSwitchTo(oldcxt);

    nchanges++;
}
```

The cycle is identical to the network-receive loop — same
`apply_dispatch`, same per-message context reset — just with
`BufFileReadExact` substituted for `walrcv_receive`.  This is
why the recursive nature of `apply_dispatch` (saved/restored
`apply_error_callback_arg.command`) matters: the dispatch
called here is one level deep.

## Subxact info — `subxact_info_write` / `subxact_info_read`

When a subtransaction starts mid-stream (the publisher's
output plugin marks each row event with its subxid), the
apply worker has to remember enough to support
`STREAM_ABORT (subxid)` later.  The mechanism: per-stream
files plus a **subxact info file** that maps each subxid to
its spool offset.

The subxact info file is rewritten at every STREAM_STOP via
`subxact_info_write`.  STREAM_ABORT reads the offset map,
**truncates the spool file** to that offset, and removes
subxact entries with higher offsets — effectively "rolling
back" the streaming data.

The comment in `stream_abort_internal` at `worker.c:2014-2021`
[from-comment]:

> OK, so it's a subxact. We need to read the subxact file for
> the toplevel transaction, determine the offset tracked for
> the subxact, and truncate the file with changes. We also
> remove the subxacts with higher offsets (or rather higher
> XIDs).
>
> We intentionally scan the array from the tail, because we're
> likely [to find the target near the end]

Subxact handling on the parallel-apply path is different —
the worker just rolls back the in-progress local subtransaction
via `RollbackToSavepoint` because the changes were never
spooled.

## Parallel apply — the deadlock-detection lock graph

This is the most subtle part.  The header comment at
`applyparallelworker.c:60-130` [from-comment] documents two
deadlock scenarios and the two session-level locks that
detect them.

### Two locks per worker pair

| Lock | Holder | Purpose |
|---|---|---|
| **Stream lock** | leader (between STREAM_STOP and next STREAM_START / STREAM_COMMIT) | "I'm not done sending you chunks" |
| **Transaction lock** | parallel worker (during entire transaction) | "I'm not done applying this transaction" |

Both are session-level lmgr locks on synthetic OIDs.

### Edge 1: LA → PA → LA

When the parallel apply (PA) waits for the leader (LA) to
send the next stream chunk, PA takes `AccessShare` on the
stream lock.  LA holds `AccessExclusive`.  So PA blocks on
LA.

If LA is also waiting for PA — typical case: LA blocked on a
unique-key violation against a row PA is in the middle of
inserting — then we have:

```
LA (waiting for unique-key conflict) → PA (waiting for stream lock) → LA
```

lmgr's wait graph contains a cycle, deadlock is detected,
one of LA / PA is aborted, replication retries.

### Edge 2: LA → PA₂ → PA₁ → LA

Two parallel workers (PA-1 and PA-2) for two streamed
transactions.  PA-1 is still applying TX-1; PA-2 is applying
TX-2 but blocked on a unique-key conflict against TX-1.  LA
is waiting for PA-2 to finish so it can call STREAM_COMMIT
in publisher commit order.

```
LA (waiting for transaction lock on TX-2) → PA-2 (waiting for
   unique-key conflict on TX-1's row) → PA-1 (waiting for
      stream lock on TX-1) → LA
```

Again, lmgr's wait graph contains a cycle.  Detection,
abort, retry.

### How the locks get taken

Leader side (from `worker.c`):

- `pa_lock_stream(xid, AccessExclusive)` — before sending
  STREAM_STOP (line 1929).
- `pa_unlock_stream(xid, AccessExclusive)` — after sending
  STREAM_START (line 1809), STREAM_ABORT, STREAM_PREPARE,
  STREAM_COMMIT.
- `pa_lock_transaction(xid, AccessShare)` — at transaction-
  finish commands (PREPARE / COMMIT) so leader will wait if
  PA still holds.

Parallel-worker side (also from `worker.c`):

- `pa_lock_transaction(xid, AccessExclusive)` — at first
  STREAM_START's TRANS_PARALLEL_APPLY case (line 1850).
- `pa_decr_and_wait_stream_block()` — at STREAM_STOP, takes
  `AccessShare` on stream lock and waits.

The key insight from the comment at lines 101-103
[from-comment]:

> This way, when PA is waiting for LA for the next stream of
> changes, we can have a wait-edge from PA to LA in lmgr,
> which will make us detect the deadlock between LA and PA.

Without these locks, the wait would happen via shm_mq or
condition variables — invisible to lmgr — and deadlocks
wouldn't be detected, they'd just hang.

## Worker pool — `ParallelApplyWorkerPool`

The header comment at `applyparallelworker.c:33-44`
[from-comment]:

> A worker pool is used to avoid restarting workers for each
> streaming transaction.  We maintain each worker's
> information (ParallelApplyWorkerInfo) in the
> ParallelApplyWorkerPool.  After successfully launching a
> new worker, its information is added to the
> ParallelApplyWorkerPool.  Once the worker finishes applying
> the transaction, it is marked as available for re-use.
> Now, before starting a new worker to apply the streaming
> transaction, we check the list for any available worker.
> Note that we retain a maximum of half the
> max_parallel_apply_workers_per_subscription workers in the
> pool and after that, we simply exit the worker after
> applying the transaction.

Worker creation cost matters because every streamed
transaction is a chance to need a fresh worker.  The pool
caps reuse at half of
`max_parallel_apply_workers_per_subscription` — beyond that,
workers exit after their transaction (the assumption: if we
have so many active streams we exceeded N/2 pool slots, the
demand is real and we should churn workers to free their
DSM).

## DSM segment per worker — why not one shared

`applyparallelworker.c:46-58` [from-comment]:

> The leader apply worker will create a separate dynamic
> shared memory segment when each parallel apply worker
> starts.  The reason for this design is that we cannot
> predict how many workers will be needed.  It may be
> possible to allocate enough shared memory in one segment
> based on the maximum number of parallel apply workers
> (max_parallel_apply_workers_per_subscription), but this
> would waste memory if no process is actually started.

Each parallel-worker DSM contains:

- **shm_mq** for change forwarding (leader → worker).
- **shm_mq** for error reporting (worker → leader).
- **`ParallelApplyWorkerShared`** struct with `xid`,
  `pending_stream_count`, `xact_state`, etc.

The leader's error-mq listener forwards parallel-worker
errors into the leader's error stack so a failed parallel
apply still raises an ereport to the leader's log context.

## Invariants worth remembering

1. **One streamed transaction at a time per worker.**
   `in_streamed_transaction` is a single boolean, not a
   stack.
2. **`get_transaction_apply_action` is the central
   dispatcher.**  Every streaming-message handler routes
   through it.
3. **`TRANS_LEADER_PARTIAL_SERIALIZE` exists because the
   leader still needs to wait for the parallel worker at
   commit, even after spilling.**  `TRANS_LEADER_SERIALIZE`
   doesn't have that concern.
4. **`pa_send_data` may fail with timeout** — the leader
   gracefully falls through to `pa_switch_to_partial_serialize`.
5. **The stream lock prevents PA→LA invisible-wait
   deadlocks.**  LA holds exclusive between STOPs; PA waits
   on share at STOP.
6. **The transaction lock preserves commit order across
   parallel workers.**  LA waits on share at COMMIT; PA holds
   exclusive from STREAM_START to COMMIT.
7. **Subxact info file maps subxid → spool offset** for
   `STREAM_ABORT (subxid)` truncation.
8. **`apply_spooled_messages` recursively calls
   `apply_dispatch`** at commit time.  The save/restore of
   `apply_error_callback_arg.command` makes this safe.
9. **Worker pool retains at most
   `max_parallel_apply_workers_per_subscription / 2`** to
   avoid memory bloat.
10. **Each parallel worker has its own DSM segment**,
    allocated lazily on first use, not pre-allocated for the
    max.

## Useful greps

```bash
# The action enum and its dispatcher
grep -n "TransApplyAction\|get_transaction_apply_action" \
    source/src/backend/replication/logical/worker.c

# Streaming message handlers
grep -n "apply_handle_stream_start\|apply_handle_stream_stop\|apply_handle_stream_abort\|apply_handle_stream_commit\|apply_handle_stream_prepare" \
    source/src/backend/replication/logical/worker.c

# Parallel apply API
grep -n "^pa_\|^ParallelApply" \
    source/src/backend/replication/logical/applyparallelworker.c

# Deadlock locks
grep -n "pa_lock_stream\|pa_unlock_stream\|pa_lock_transaction\|pa_decr_and_wait_stream_block" \
    source/src/backend/replication/logical/worker.c \
    source/src/backend/replication/logical/applyparallelworker.c

# Spool replay
grep -n "apply_spooled_messages\|stream_write_change\|stream_open_file\|subxact_info_write\|subxact_info_read" \
    source/src/backend/replication/logical/worker.c
```



## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/replication/logical/applyparallelworker.c`](../files/src/backend/replication/logical/applyparallelworker.c.md) | — | ParallelApplyWorkerInfo, the deadlock-detection lock graph |
| [`src/backend/replication/logical/worker.c`](../files/src/backend/replication/logical/worker.c.md) | — | apply_handle_stream_, the action machine |

<!-- /callsites:auto -->



## Scenarios that use me
<!-- scenarios:auto -->

*Auto-derived from direct references + transitive file-overlap.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

- [`add-new-replication-message`](../scenarios/add-new-replication-message.md)

<!-- /scenarios:auto -->

## Cross-references

- [[apply-worker-loop-and-dispatch]] — `apply_dispatch` is
  called recursively from `apply_spooled_messages` at commit.
- [[apply-handlers-insert-update-delete]] —
  `handle_streamed_transaction` shunts row events to spool
  in serialize/parallel-serialize modes.
- [[parallel-worker-coordination]] — DSM + shm_mq is the
  same primitive used by parallel query.
- [[abort-transaction-cleanup]] — `stream_abort_internal`
  on parallel-apply path uses `RollbackToSavepoint`.
- [[buffer-manager]] — `BufFile` is the spool mechanism;
  lives in per-relation tempfile space.
- [[memory-contexts]] — `LogicalStreamingContext` is reset
  at every STREAM_STOP.
- [[wal-write-internals]] — `XactLastCommitEnd` at apply
  time feeds back to publisher; relevant for synchronous
  streamed replication.
