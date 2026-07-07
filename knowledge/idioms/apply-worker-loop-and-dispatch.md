# Logical-rep apply worker — main loop and dispatch

The apply worker is the subscriber-side process that consumes
the WAL-decoded change stream from a publisher and replays it
into local tables.  It's a single background worker process per
subscription, with optional parallel apply workers spawned for
streaming transactions.

This doc covers the **loop and dispatch** — how the worker
receives bytes off the wire, peels off the message type byte,
and routes to per-message handlers.  The per-row handlers
(insert/update/delete) are
[[apply-handlers-insert-update-delete]].  The streaming /
parallel-apply mode is [[apply-streaming-and-parallel]].

**Anchors** (all cites against `source/` at commit `e18b0cb7344`):
- `source/src/backend/replication/logical/worker.c` — `ApplyWorkerMain`, `LogicalRepApplyLoop`, `apply_dispatch`
- `source/src/backend/replication/logical/launcher.c` — `ApplyLauncherMain`, worker registration
- `source/src/include/replication/logicalproto.h` — `LogicalRepMsgType` enum
- `source/src/backend/replication/logical/proto.c` — message serialization

## Process layout — who runs what

PG's logical replication has three process roles:

| Role | One per | Source file | Purpose |
|---|---|---|---|
| **Apply launcher** | cluster | `launcher.c` | spawn apply workers from `pg_subscription` |
| **Apply worker** | subscription | `worker.c` (`ApplyWorkerMain`) | main per-subscription consumer; runs `LogicalRepApplyLoop` |
| **Parallel apply worker** | streamed-txn in progress | `applyparallelworker.c` | helper for streaming-mode "parallel" sub-mode |
| **Tablesync worker** | initial-sync table | `tablesync.c` | bulk copy + catchup for a freshly subscribed table |

The launcher is a permanent autovac-class worker (registered
in `BackgroundWorker_Init`).  Apply workers are spawned by
`logicalrep_worker_launch` when a subscription becomes active
or after a restart.  Tablesync and parallel-apply workers are
spawned by the apply worker itself.

The apply worker is the **only** role that opens the
publisher-side connection (`LogRepWorkerWalRcvConn`).  Other
worker roles either don't touch the network (parallel apply
processes messages forwarded from the leader) or open their
own short-lived connection (tablesync).

## Where the apply loop lives

`worker.c:5646` [verified-by-code]:

```c
LogicalRepApplyLoop(origin_startpos);
```

— this is the call from `ApplyWorkerMain` after the worker has
connected to the publisher, advertised its replica identity,
and started streaming.  `LogicalRepApplyLoop` itself is at
`worker.c:4003-end-of-function` [verified-by-code] (around 280
lines including timeouts and feedback handling).

## The main loop, structurally

`worker.c:4003-4244` [verified-by-code].  Shape:

```
Init ApplyMessageContext   (per-message reset)
Init LogicalStreamingContext  (per-stream reset)
Push apply_error_callback

for (;;) {
    CHECK_FOR_INTERRUPTS()
    MemoryContextSwitchTo(ApplyMessageContext)
    len = walrcv_receive(LogRepWorkerWalRcvConn, &buf, &fd)

    if (len != 0) {
        for (;;) {                          # inner loop: drain all available
            if (len == 0) break
            if (len < 0) { endofstream = true; break }

            c = pq_getmsgbyte(&s)
            if (c == PqReplMsg_WALData)
                apply_dispatch(&s)
            elif (c == PqReplMsg_Keepalive)
                send_feedback(...)
            elif (c == PqReplMsg_PrimaryStatusUpdate)
                maybe_advance_nonremovable_xid(&rdt_data, true)
            # other types ignored

            MemoryContextReset(ApplyMessageContext)
            len = walrcv_receive(...)
        }
    }

    send_feedback(last_received, false, false)

    if (!in_remote_transaction && !in_streamed_transaction) {
        AcceptInvalidationMessages()
        maybe_reread_subscription()
        ProcessSyncingRelations(last_received)
    }

    MemoryContextReset(ApplyMessageContext)
    if (endofstream) break

    wait_time = !dlist_is_empty(&lsn_mapping) ? WalWriterDelay : NAPTIME_PER_CYCLE
    WaitLatchOrSocket(MyLatch, WL_SOCKET_READABLE | WL_LATCH_SET | WL_TIMEOUT | WL_EXIT_ON_PM_DEATH, ...)
}
```

Five things worth noticing:

### 1. The two memory contexts

`worker.c:4012-4025` [verified-by-code]:

```c
ApplyMessageContext = AllocSetContextCreate(ApplyContext,
                                            "ApplyMessageContext",
                                            ALLOCSET_DEFAULT_SIZES);
LogicalStreamingContext = AllocSetContextCreate(ApplyContext,
                                                "LogicalStreamingContext",
                                                ALLOCSET_DEFAULT_SIZES);
```

| Context | Reset at | Lives for |
|---|---|---|
| `ApplyContext` | worker exit | the whole worker's life |
| `ApplyMessageContext` | end of each message | one protocol message |
| `LogicalStreamingContext` | `apply_handle_stream_stop` | one stream segment |

The per-message reset (`worker.c:4160`) [verified-by-code] is
the canonical pattern: switch into `ApplyMessageContext`,
deserialize and apply the message, switch back and reset.  Any
palloc the handler does is automatically freed.

Long-lived state (the LSN-mapping list, the relation cache, the
worker's `MyLogicalRepWorker` record) lives in
`ApplyContext`, which is not reset.

### 2. The outer/inner loop structure

The **outer** loop is one iteration per wait — it sleeps in
`WaitLatchOrSocket` until either data arrives, the latch is
set, or `NAPTIME_PER_CYCLE` (60s default) elapses.

The **inner** loop drains all currently-available data without
sleeping.  This is the standard "consume what you can without
blocking" pattern for a network reader:

```c
len = walrcv_receive(LogRepWorkerWalRcvConn, &buf, &fd);
if (len != 0)
{
    for (;;)
    {
        if (len == 0) break;       /* no more data ready */
        if (len < 0) { endofstream = true; break; }
        /* process one message */
        len = walrcv_receive(LogRepWorkerWalRcvConn, &buf, &fd);
    }
}
```

`walrcv_receive` returns 0 when no data is immediately
available — distinct from -1 which is end-of-stream.  The
inner loop processes messages back-to-back until the kernel
buffer drains, then the outer loop sleeps for more data.

### 3. Three top-level message types

`worker.c:4097-4157` [verified-by-code] — the byte from
`pq_getmsgbyte(&s)` is the **transport-level** message type:

| Byte | Constant | Action |
|---|---|---|
| `'w'` | `PqReplMsg_WALData` | apply_dispatch(&s) on the embedded logical-rep message |
| `'k'` | `PqReplMsg_Keepalive` | send_feedback if requested |
| `'s'` | `PqReplMsg_PrimaryStatusUpdate` | advance retain-dead-tuples bookkeeping |

The `WALData` envelope carries `(start_lsn, end_lsn, send_time,
payload)`.  `start_lsn` and `end_lsn` track the WAL extent the
payload covers — the apply worker uses these to update
`last_received`, which is what feedback messages report back
to the publisher.

The Keepalive path at `worker.c:4119-4137` [verified-by-code]
honors the `reply_requested` byte; if set, the worker sends an
immediate feedback regardless of pending transactions.

### 4. The "between-transactions" maintenance

`worker.c:4175-4190` [verified-by-code]:

```c
if (!in_remote_transaction && !in_streamed_transaction)
{
    AcceptInvalidationMessages();
    maybe_reread_subscription();
    ProcessSyncingRelations(last_received);
}
```

These three operations would be unsafe mid-transaction:

- **`AcceptInvalidationMessages`** can change the contents of
  relcache or syscache, which mid-apply handlers depend on.
- **`maybe_reread_subscription`** can change the worker's
  understanding of which tables to replicate — disastrous
  mid-transaction.
- **`ProcessSyncingRelations`** can spawn / kill tablesync
  workers, which holds locks that would conflict.

So PG defers all three until the apply state is quiescent —
`in_remote_transaction == false && in_streamed_transaction
== false`.

### 5. The `lsn_mapping`-aware wait

`worker.c:4207-4210` [verified-by-code]:

```c
if (!dlist_is_empty(&lsn_mapping))
    wait_time = WalWriterDelay;
else
    wait_time = NAPTIME_PER_CYCLE;
```

`lsn_mapping` is the list of `(remote_lsn → local_lsn)` pairs
recorded at each commit (via `store_flush_position`).  When
the list is non-empty, there are unflushed commits whose flush
position the publisher needs to learn about — so wait at most
`WalWriterDelay` (200ms default) instead of `NAPTIME_PER_CYCLE`
(60s).

This is what makes synchronous replication actually responsive
under low load: the WAL writer flushes the apply'd
transaction, then the apply worker wakes up within
`WalWriterDelay` to send the feedback.

## `apply_dispatch` — the message type switch

`worker.c:3796-3901` [verified-by-code] is the routing table.
After reading the message type byte:

```c
LogicalRepMsgType action = pq_getmsgbyte(s);
...
switch (action)
{
    case LOGICAL_REP_MSG_BEGIN:           apply_handle_begin(s); break;
    case LOGICAL_REP_MSG_COMMIT:          apply_handle_commit(s); break;
    case LOGICAL_REP_MSG_INSERT:          apply_handle_insert(s); break;
    case LOGICAL_REP_MSG_UPDATE:          apply_handle_update(s); break;
    case LOGICAL_REP_MSG_DELETE:          apply_handle_delete(s); break;
    case LOGICAL_REP_MSG_TRUNCATE:        apply_handle_truncate(s); break;
    case LOGICAL_REP_MSG_RELATION:        apply_handle_relation(s); break;
    case LOGICAL_REP_MSG_TYPE:            apply_handle_type(s); break;
    case LOGICAL_REP_MSG_ORIGIN:          apply_handle_origin(s); break;
    case LOGICAL_REP_MSG_MESSAGE:         /* ignored - generic */ break;

    case LOGICAL_REP_MSG_STREAM_START:    apply_handle_stream_start(s); break;
    case LOGICAL_REP_MSG_STREAM_STOP:     apply_handle_stream_stop(s); break;
    case LOGICAL_REP_MSG_STREAM_ABORT:    apply_handle_stream_abort(s); break;
    case LOGICAL_REP_MSG_STREAM_COMMIT:   apply_handle_stream_commit(s); break;

    case LOGICAL_REP_MSG_BEGIN_PREPARE:    apply_handle_begin_prepare(s); break;
    case LOGICAL_REP_MSG_PREPARE:          apply_handle_prepare(s); break;
    case LOGICAL_REP_MSG_COMMIT_PREPARED:  apply_handle_commit_prepared(s); break;
    case LOGICAL_REP_MSG_ROLLBACK_PREPARED:apply_handle_rollback_prepared(s); break;
    case LOGICAL_REP_MSG_STREAM_PREPARE:   apply_handle_stream_prepare(s); break;

    default:
        ereport(ERROR, ... "invalid logical replication message type");
}
```

Three families to recognize:

1. **Transaction control**: `BEGIN`, `COMMIT`, plus
   prepare/commit-prepared variants for 2PC.
2. **Row events**: `INSERT`, `UPDATE`, `DELETE`, `TRUNCATE`
   plus the metadata messages `RELATION` and `TYPE` that
   declare schemas before data flows.  See
   [[apply-handlers-insert-update-delete]].
3. **Streaming control**: `STREAM_START`, `STREAM_STOP`,
   `STREAM_ABORT`, `STREAM_COMMIT` for large transactions
   sent before commit.  See [[apply-streaming-and-parallel]].

### Recursive-call safety

`worker.c:3802-3808` [verified-by-code]:

```c
LogicalRepMsgType saved_command;
saved_command = apply_error_callback_arg.command;
apply_error_callback_arg.command = action;
...
/* at end of switch */
apply_error_callback_arg.command = saved_command;
```

`apply_dispatch` can recurse — when applying spooled
streaming changes, the streaming-commit handler reads buffered
messages off disk and calls `apply_dispatch` for each.  The
save/restore preserves the outer command's name in the error
context callback so error messages stay sensible:

```
ERROR: ... during apply of UPDATE on table foo
```

— even if the streaming-commit was the outer command.

## `apply_handle_begin` and the `in_remote_transaction` flag

`worker.c:1228-1252` [verified-by-code]:

```c
static void
apply_handle_begin(StringInfo s)
{
    LogicalRepBeginData begin_data;

    /* There must not be an active streaming transaction. */
    Assert(!in_streamed_transaction);

    logicalrep_read_begin(s, &begin_data);
    set_apply_error_context_xact(begin_data.xid, begin_data.final_lsn);

    remote_final_lsn = begin_data.final_lsn;

    maybe_start_skipping_changes(begin_data.final_lsn);

    in_remote_transaction = true;

    pgstat_report_activity(STATE_RUNNING, NULL);
}
```

`in_remote_transaction` is the simple boolean that tells the
inner loop "we're inside a transaction".  Together with
`in_streamed_transaction` it determines whether the
between-transactions maintenance can fire.

`remote_final_lsn` is the publisher's commit LSN — recorded
now so that the commit handler can match it later.  This is
used by the `maybe_start_skipping_changes` machinery
(SUBSCRIPTION ... SKIP) to suppress everything between BEGIN
and COMMIT when an LSN is being skipped.

The `set_apply_error_context_xact(xid, lsn)` populates the
error-context callback so that any subsequent error in a row
handler shows `... during transaction T at LSN X/Y`.

## `apply_handle_commit_internal`

`worker.c:2520-2580` [verified-by-code] is the shared body
between regular commit and streamed-commit (and prepared
variants).  Three actions:

```c
CommitTransactionCommand();
store_flush_position(commit_data->end_lsn, XactLastCommitEnd);
in_remote_transaction = false;
pgstat_report_stat(false);
pgstat_report_activity(STATE_IDLE, NULL);
```

- `CommitTransactionCommand` — actually commits the local
  transaction.
- `store_flush_position` — adds the `(remote_end_lsn,
  local_end_lsn)` pair to `lsn_mapping`.  This is what the
  feedback path drains later when reporting flush position.
- `in_remote_transaction = false` — re-opens the gate for
  between-transactions maintenance on the next loop iteration.

The `XactLastCommitEnd` global is the local-side LSN of the
just-committed transaction — produced by the commit-record
WAL insert.

## Feedback — `send_feedback`

`worker.c:572` declares it; the implementation reports back to
the publisher with three LSNs:

- **write position**: the maximum `remote_end_lsn` we've
  acknowledged receiving.
- **flush position**: the maximum `remote_end_lsn` whose
  corresponding `local_end_lsn` has been flushed (per
  `GetFlushRecPtr`).
- **apply position**: same as flush, since we apply in WAL
  order.

The `get_flush_position` function at `worker.c:3916-3955`
[verified-by-code] walks `lsn_mapping`, evicting entries whose
`local_end` is ≤ `local_flush` (already flushed) and reporting
the highest evicted as the flush position.  Live entries that
aren't yet flushed bump `*have_pending_txes = true`.

Feedback is sent **on every iteration of the outer loop** with
`send_feedback(last_received, false, false)` (line 4168), plus
on demand when the publisher requests a reply.

## `maybe_advance_nonremovable_xid` — retain-dead-tuples

`worker.c:4117, 4134, 4154` [verified-by-code] — three call
sites.  The retain-dead-tuples machinery
(`RetainDeadTuplesData rdt_data`) keeps the publisher informed
of the oldest XID the subscriber still needs.  This is what
lets `pg_subscription`'s
`max_retention_duration` work: the publisher won't vacuum
dead tuples for committed XIDs newer than what subscribers
have apply'd.

The three call sites are after each of the three message types
(`WALData`, `Keepalive`, `PrimaryStatusUpdate`), so the
non-removable XID gets re-evaluated whenever the worker hears
anything from the publisher.

## Error handling — `apply_error_callback`

`worker.c:464` declares `apply_error_callback_arg`.  The
callback (pushed onto `error_context_stack` at line 4034-4036
[verified-by-code]) fires inside any `elog` / `ereport` and
adds context lines like:

```
CONTEXT:  processing remote data for replication origin "pg_X" during message
          type "UPDATE" in transaction T at LSN X/Y
```

Three fields drive it:

- `command` — current `LogicalRepMsgType` being applied
- `xid` — the remote XID from BEGIN
- `lsn` — the remote LSN from BEGIN

`set_apply_error_context_xact` is called by `apply_handle_begin`,
`apply_handle_begin_prepare`, `apply_handle_stream_start`.
Cleared at commit.  This is what makes apply-time error
messages actionable.

## The shutdown path

When `endofstream == true` (the publisher closed the
connection), the outer loop breaks.  When the worker is killed
via SIGTERM, it lands inside `CHECK_FOR_INTERRUPTS` at line
4049 or 4060.

The actual exit sequence happens in `apply_worker_exit` (line
592), which performs final feedback and frees the connection.
The worker's `BackgroundWorkerHandle` is freed by the launcher
or by the parent backend's `before_shmem_exit` callback.

## Invariants worth remembering

1. **One apply worker per subscription.**  Multiple
   subscriptions = multiple workers.  Parallel-apply
   subworkers are a sub-mode of the streaming protocol, not
   independent.
2. **`apply_dispatch` is the only message router.**  Every
   protocol message goes through the byte switch.
3. **`ApplyMessageContext` is reset after every message.**
   Don't keep pointers into it across iterations.
4. **`ApplyContext` is the worker's lifetime context.**
   `lsn_mapping`, error-context buffers, and the relcache
   live here.
5. **`in_remote_transaction` and `in_streamed_transaction`
   gate the between-transactions maintenance.**  Inval
   processing and subscription re-reads happen only when both
   are false.
6. **`apply_dispatch` is recursive.**  Streaming commits call
   it on spooled messages.  `apply_error_callback_arg.command`
   saves/restores around the switch.
7. **Feedback runs every loop iteration**, not just on
   commit.  This is what keeps publisher-side WAL retention
   bounded.
8. **`walrcv_receive(...)` returns 0 (no data ready) vs
   < 0 (end-of-stream).**  Don't confuse them.
9. **`store_flush_position` is the only way `lsn_mapping`
   grows** — every commit handler must call it.
10. **`AcceptInvalidationMessages` mid-transaction would
    corrupt the relcache.**  This is *why* the between-
    transactions gate exists.

## Useful greps

```bash
# Main loop entry
grep -n "LogicalRepApplyLoop\|ApplyWorkerMain\|apply_dispatch" \
    source/src/backend/replication/logical/worker.c

# All apply_handle_* dispatch targets
grep -n "^apply_handle_\|static void apply_handle" \
    source/src/backend/replication/logical/worker.c

# Message-type byte vs envelope-type byte
grep -n "PqReplMsg_WALData\|PqReplMsg_Keepalive\|LOGICAL_REP_MSG_" \
    source/src/backend/replication/logical/worker.c \
    source/src/include/replication/logicalproto.h

# Memory context reset sites
grep -n "ApplyMessageContext\|ApplyContext\|LogicalStreamingContext" \
    source/src/backend/replication/logical/worker.c

# Flush-position bookkeeping
grep -n "store_flush_position\|get_flush_position\|lsn_mapping" \
    source/src/backend/replication/logical/worker.c
```



## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/replication/logical/launcher.c`](../files/src/backend/replication/logical/launcher.c.md) | — | ApplyLauncherMain, worker registration |
| [`src/backend/replication/logical/proto.c`](../files/src/backend/replication/logical/proto.c.md) | — | message serialization |
| [`src/backend/replication/logical/worker.c`](../files/src/backend/replication/logical/worker.c.md) | — | ApplyWorkerMain, LogicalRepApplyLoop, apply_dispatch |
| [`src/include/replication/logicalproto.h`](../files/src/include/replication/logicalproto.h.md) | — | LogicalRepMsgType enum |

<!-- /callsites:auto -->

## Cross-references

- [[apply-handlers-insert-update-delete]] — the row-event
  handlers and replica-identity lookup.
- [[apply-streaming-and-parallel]] — streaming protocol +
  parallel apply worker dispatch.
- [[logical-decoding-snapshot]] — publisher-side decoding
  that produces these messages.
- [[wal-write-internals]] — `XactLastCommitEnd` is the
  local-side LSN that drives flush feedback.
- [[memory-contexts]] — the per-message-reset pattern is
  canonical PG.
- [[parallel-worker-coordination]] — same DSM segment + latch
  primitives as parallel-apply workers.
- [[cache-invalidation-registration]] —
  `AcceptInvalidationMessages` is gated by the
  in-transaction state here.
- [[snapshot-acquisition]] — apply worker takes a snapshot at
  each `apply_handle_begin` for the local transaction.
