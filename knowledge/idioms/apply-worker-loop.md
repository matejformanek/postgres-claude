# Apply worker loop — subscriber-side message processing

The **logical-replication apply worker** is a background worker
spawned by the launcher (`launcher.c`) for each active
SUBSCRIPTION. It connects to the publisher as a walreceiver,
receives pgoutput-format messages, and applies them to the
local database — INSERT, UPDATE, DELETE, TRUNCATE, and
streaming-xact messages. `LogicalRepApplyLoop` is the main
read-decode-apply loop; `ApplyWorkerMain` is the bgworker
entry point.

Anchors:
- `source/src/backend/replication/logical/worker.c:6003` —
  ApplyWorkerMain [verified-by-code]
- `source/src/backend/replication/logical/worker.c:4003` —
  LogicalRepApplyLoop [verified-by-code]
- `knowledge/idioms/output-plugin-callbacks.md` — companion
  (the publisher side)
- `knowledge/idioms/tablesync-initial-copy.md` — companion
  (initial-sync phase)
- `knowledge/idioms/apply-conflict-resolution.md` — companion
- `knowledge/idioms/wal-receiver-loop.md` — companion
  (physical-rep counterpart)
- `.claude/skills/replication-overview/SKILL.md` — companion

## The two entry points

[verified-by-code `worker.c:4003, 6003`]

```c
void ApplyWorkerMain(Datum main_arg);          /* bgworker entry */
static void LogicalRepApplyLoop(XLogRecPtr last_received);  /* main loop */
```

`ApplyWorkerMain` runs at bgworker startup:
1. Set up signal handlers + TopMemoryContext.
2. Connect to publisher via libpqwalreceiver.
3. Set up replication origin (`replorigin_session_setup`).
4. Send START_REPLICATION SLOT ... LOGICAL.
5. Enter `LogicalRepApplyLoop`.

The loop runs forever (until SIGTERM); each iteration:
1. Receive a copydata message from publisher.
2. Switch on message type byte.
3. Dispatch to the appropriate handler.

## The pgoutput message types

[from `pgoutput.c` + `proto.c`]

| Byte | Message |
|---|---|
| `B` | BEGIN |
| `I` | INSERT |
| `U` | UPDATE |
| `D` | DELETE |
| `C` | COMMIT |
| `T` | TRUNCATE |
| `R` | RELATION |
| `Y` | TYPE |
| `O` | ORIGIN |
| `M` | MESSAGE (pg_logical_emit_message) |
| `S` | STREAM_START |
| `E` | STREAM_STOP |
| `c` | STREAM_COMMIT |
| `A` | STREAM_ABORT |
| `P` | PREPARE |
| `K` | COMMIT_PREPARED |
| `r` | ROLLBACK_PREPARED |
| `s` | STREAM_PREPARE |

Each is handled by `apply_dispatch` switching to
`apply_handle_insert`, `apply_handle_update`,
`apply_handle_delete`, etc.

## apply_dispatch — the switch

```c
static void
apply_dispatch(StringInfo s)
{
    LogicalRepMsgType action = pq_getmsgbyte(s);

    switch (action) {
        case LOGICAL_REP_MSG_BEGIN:
            apply_handle_begin(s);
            break;
        case LOGICAL_REP_MSG_INSERT:
            apply_handle_insert(s);
            break;
        /* ... ~15 more ... */
    }
}
```

(simplified from worker.c)

The handler functions parse the message body, apply the
operation, and update progress.

## Per-message commit-WAL semantics

For each commit message, the apply worker:
1. Writes its own COMMIT record to local WAL (with origin_id
   set to its session origin).
2. Calls `replorigin_session_advance` to update the durable
   progress.
3. Sends a STANDBY_STATUS_UPDATE feedback message back to
   publisher with `flush_lsn = commit_lsn`.

The feedback lets the publisher advance the slot's
`confirmed_flush_lsn` and clean up retained WAL.

## Streaming xact handling

When `streaming = parallel` is set:
- STREAM_START messages route to a parallel apply worker
  (one per concurrent stream).
- The parallel worker applies changes immediately without
  waiting for commit.
- STREAM_COMMIT finalizes; STREAM_ABORT discards.

When `streaming = on` (non-parallel):
- Changes are spilled to disk in
  `pg_logical/<subid>/<xid>` files.
- At STREAM_COMMIT, the worker reads them back and applies as
  one xact.

Without streaming, large publisher xacts buffer entirely on
publisher → publisher RAM pressure → spill to publisher's
ReorderBuffer disk.

## Skip-LSN — the conflict workaround

```sql
ALTER SUBSCRIPTION s SKIP (lsn = '0/12345678');
```

Tells the apply worker: "when you next see a commit at LSN
0/12345678, skip the entire xact". Used to manually skip a
conflicting transaction after an apply failure.

The skip LSN is stored in `pg_subscription.subskiplsn` and
checked at each `apply_handle_commit`.

## Worker lifecycle

- **Launcher** (`launcher.c`) — periodically scans
  pg_subscription, starts apply workers for enabled
  subscriptions.
- **Apply worker** (`worker.c`) — long-running; reconnects
  on transient failures with exponential backoff.
- **Tablesync workers** (per-table during initial sync) —
  short-lived; one per table.
- **Parallel apply workers** — spawned by apply worker for
  large concurrent xacts.

All workers register via `RegisterDynamicBackgroundWorker`
with `BGWORKER_BACKEND_DATABASE_CONNECTION` set.

## Common review-time concerns

- **Apply worker is a single backend** — operations serial
  within a worker.
- **Origin must be set up first** — drives loop prevention.
- **STANDBY_STATUS_UPDATE feedback** is the slot-advance
  signal; missing it = slot bloat on publisher.
- **Streaming requires opt-in** + extra protocol callbacks.
- **SKIP LSN** is a manual override; clears at next restart.
- **Worker death + restart** — replorigin progress survives;
  apply resumes from origin_lsn.

## Invariants

- **[INV-1]** Apply worker = bgworker via launcher; one per
  enabled SUBSCRIPTION.
- **[INV-2]** Loop = receive pgoutput msg → dispatch → apply
  → feedback.
- **[INV-3]** replorigin progress advances per commit.
- **[INV-4]** Streaming + parallel apply require opt-in
  (subscription option).
- **[INV-5]** SKIP LSN is a manual conflict-bypass; cleared
  per-subscription.

## Useful greps

- The loop + handlers:
  `grep -n 'LogicalRepApplyLoop\|apply_handle_' source/src/backend/replication/logical/worker.c | head -20`
- Apply dispatch:
  `grep -n 'apply_dispatch\|LogicalRepMsgType' source/src/backend/replication/logical/worker.c | head -10`
- Launcher:
  `grep -n 'logicalrep_worker_launch\|ApplyLauncherMain' source/src/backend/replication/logical/launcher.c | head -10`

## Cross-references

- `knowledge/idioms/output-plugin-callbacks.md` — publisher
  side that emits these messages.
- `knowledge/idioms/tablesync-initial-copy.md` — companion
  (initial-sync phase).
- `knowledge/idioms/apply-conflict-resolution.md` — companion
  (conflict handling).
- `knowledge/idioms/replication-origin-tracking.md` —
  replorigin progress.
- `knowledge/idioms/wal-receiver-loop.md` — physical-rep
  counterpart.
- `knowledge/idioms/walsender-state-machine.md` — publisher
  walsender.
- `knowledge/idioms/background-worker-startup.md` — bgworker
  registration.
- `knowledge/subsystems/replication.md` — replication
  overview.
- `.claude/skills/replication-overview/SKILL.md` — companion.
- `source/src/backend/replication/logical/worker.c:6003` —
  apply worker entry.
- `source/src/backend/replication/logical/launcher.c` —
  worker launcher.
