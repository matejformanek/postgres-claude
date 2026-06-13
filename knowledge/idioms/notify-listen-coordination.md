# LISTEN/NOTIFY coordination — async.c queue mechanics

PostgreSQL's `LISTEN` / `NOTIFY` / `UNLISTEN` SQL statements
provide cluster-wide async message delivery: a backend
NOTIFIES a channel, and every backend that has LISTENed to
that channel receives the message at transaction-commit
time. Implemented via a shared SLRU queue in
`pg_notify/`, polled by listening backends.

Anchors:
- `source/src/backend/commands/async.c` — implementation
  [verified-by-code]
- `knowledge/idioms/cache-invalidation-registration.md` —
  similar callback-on-event pattern (different mechanism)
- `knowledge/subsystems/utils-cache.md` — sinval used for
  similar purposes inside the backend

## The model

Each backend has:
- **`listenChannels`** — set of channels this backend is
  listening to.
- **`pendingNotifies`** — queue of NOTIFY messages this
  backend has emitted but not yet committed.

The shared resources:
- **`asyncQueueControl`** — head / tail pointers shared
  between all backends [verified-by-code `async.c:358-359`].
- **`pg_notify/` SLRU** — disk-backed storage for messages.

## Phase 1: NOTIFY emits

```sql
NOTIFY mychannel, 'hello world';
```

1. **`Async_Notify(channel, payload)`** is called
   [verified-by-code `async.c:894`].
2. The message is added to **`pendingNotifies`** — a
   backend-local list.
3. No shared-memory mutation yet; the NOTIFY is
   transactional. Rollback discards it.

[from-comment `async.c:46`]

> 4. The NOTIFY statement (routine Async_Notify) stores the
> notification in a backend-local list.

## Phase 2: Commit-time fan-out

At transaction commit (in `AtCommit_Notify`):

1. Walk `pendingNotifies`.
2. For each message, append to the shared `pg_notify/`
   queue (under `asyncQueueLock`).
3. Update shared `QUEUE_HEAD` to point past the new
   entries.
4. **Signal every listening backend** via SIGUSR1.

If commit fails before step 2, the messages are lost — the
queue update is the durable-commit moment for NOTIFY.

## Phase 3: Listening backends receive

```sql
LISTEN mychannel;
```

The receiver:

1. Marks itself as a listener (adds `mychannel` to its
   per-backend `listenChannels`).
2. Sets a flag in shared state so notifiers signal it.
3. On SIGUSR1 (or periodic check at command boundary),
   runs **`ProcessIncomingNotify`**
   [verified-by-code `async.c:619`].

`ProcessIncomingNotify`:
1. Acquire `asyncQueueLock`.
2. Walk pg_notify entries between `lastNotifyQueuePos` and
   `QUEUE_HEAD`.
3. For each entry whose channel matches `listenChannels`,
   deliver to the client (PQnotifies).
4. Advance `lastNotifyQueuePos`.

## The duplicate-collapse trick

[from-comment `async.c:1003`]

> Unlike Async_Notify, we don't try to collapse out
> duplicates here.

`Async_Notify` (the in-transaction add) DOES collapse
duplicates within the same transaction — if you NOTIFY
the same channel-payload twice, only one entry goes into
the queue at commit.

The deferred-commit fan-out doesn't try this optimization;
all queued entries are sent.

## SLRU storage

The queue is backed by an SLRU (Simple LRU) — disk pages
managed by PG with a small in-memory cache. Storage is
`pg_notify/` directory under PGDATA.

When all listening backends have processed past a queue
position, that position can be truncated. The truncation
happens lazily at checkpoint.

If a listener falls far behind (idle session that LISTENed
but never SELECTs), `pg_notify/` grows. Bounded by
`max_notify_queue_pages` (PG 14+ has alarms when this is
exceeded).

## Channel matching

Channel names are case-sensitive identifiers (limited to
64 bytes). A backend can LISTEN to multiple channels; each
NOTIFY targets exactly one channel.

Wildcard channels are NOT supported. To "listen to all
events," the convention is one channel per event type and
LISTEN to all of them.

## The 8000-byte payload limit

```sql
NOTIFY ch, 'a string up to ~8000 bytes';
```

Payload is text, max ~8000 bytes. Larger payloads ERROR at
NOTIFY time. For larger structured data, send a small
"event ID" payload and have the receiver query a real table
for details.

## Cross-database visibility

NOTIFY/LISTEN is **per-database**. A NOTIFY in database
`foo` is invisible to a listener in database `bar`, even on
the same cluster. The channel namespace is scoped by
database OID in the queue.

## The "self-notify" rule

If a backend NOTIFYs a channel it's LISTENing to itself,
delivery happens — the backend gets its own message on the
next command. Useful for pipelining; sometimes surprising.

## Reliability semantics

- **At-least-once within the queue lifetime.** Once a
  NOTIFY commits, every listening backend that was alive at
  commit time gets it.
- **Lost on disconnection.** A backend that disconnects
  before reading notifications loses them.
- **NOT guaranteed durable across crashes.** Queue is
  flushed periodically but not per-message.

For durable messaging, use a real table + LISTEN/NOTIFY for
the "wake up" signal.

## Common review-time concerns

- **Long-LISTENing idle sessions grow `pg_notify/`.** Set
  `idle_in_transaction_session_timeout` to bound this.
- **Payload size limit is real** — clients sending JSON
  blobs should check size.
- **NOTIFY in a long transaction delays delivery** — every
  listener waits until commit.
- **Cross-database use requires intermediate** — a bridge
  process LISTENing in one DB and NOTIFYing in another.

## Invariants

- **[INV-1]** NOTIFY is transactional — committed at
  transaction commit, lost on rollback.
- **[INV-2]** Per-database channel namespace; not
  cross-database.
- **[INV-3]** Payload max ~8000 bytes.
- **[INV-4]** Duplicates collapsed within a transaction;
  not across transactions.
- **[INV-5]** Lost-on-disconnect; receiver must drain
  promptly.

## Useful greps

- The two main entry points:
  `grep -n 'Async_Notify\|ProcessIncomingNotify' source/src/backend/commands/async.c | head -10`
- The queue control:
  `grep -n 'QUEUE_HEAD\|QUEUE_TAIL\|asyncQueueControl' source/src/backend/commands/async.c | head -10`
- The signal handler:
  `grep -n 'HandleNotifyInterrupt' source/src/backend/commands/async.c | head -5`

## Cross-references

- `knowledge/idioms/cache-invalidation-registration.md` —
  similar event-broadcast pattern (sinval) inside the
  backend.
- `knowledge/idioms/sinvaladt-broadcast.md` — also similar
  broadcast mechanism.
- `knowledge/subsystems/storage-ipc.md` — SLRU
  infrastructure shared between many subsystems.
- `knowledge/data-structures/latch-waiteventset.md` —
  SIGUSR1 + latch wakeup pattern.
- `source/src/backend/commands/async.c` — implementation.
- `source/src/include/commands/async.h` — public API.
