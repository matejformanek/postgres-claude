# async.c

- **Source path:** `source/src/backend/commands/async.c`
- **Lines:** 3299
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `access/transam/slru.c` (the on-disk queue), `storage/ipc/sinvaladt.c` (inval queue, structurally similar).

## Purpose

"Asynchronous notification: NOTIFY, LISTEN, UNLISTEN." [from-comment, async.c:3-4] The top-of-file design-doc comment (~140 lines, async.c:18-160) is the authoritative reference; key points:

1. A single SLRU-backed disk queue under `pg_notify/`, shared across all databases; messages carry the sender's database OID so listeners filter.
2. Notifications are delivered **after commit, in commit order**. The queue write happens during `AtCommit_Notify`; pre-commit a backend just accumulates a per-xact NOTIFY list (de-duplicated by channel+payload).
3. Every listening backend's PID lives in a slot in shared memory (`AsyncQueueControl`). When a backend commits new entries, it advances the queue tail and SIGUSR1s any listener whose read pointer is behind.
4. Listeners read by walking from their read pointer to the current head, filtering by database OID + their LISTEN channel set, and emitting `NotificationResponse` protocol messages to the frontend.
5. Crash-recovery wipes the queue (`pg_notify/`) — notifications are explicitly NOT durable.

## Public surface

- `Async_Notify` — collect a NOTIFY into the per-xact list.
- `Async_Listen` / `Async_Unlisten` / `Async_UnlistenAll` — manage the per-backend channel set.
- `AtCommit_Notify`, `AtAbort_Notify`, `AtPrepare_Notify`, `AtSubCommit_Notify`, `AtSubAbort_Notify` — xact lifecycle hooks.
- `ProcessIncomingNotify`, `HandleNotifyInterrupt` — interrupt-driven read path.
- `pg_notification_queue_usage` — SQL func reporting queue fill ratio.
- `pg_listening_channels` — SRF: my own channels.

## GUC

`max_notify_queue_pages` (PG 17+) caps the SLRU size; defaults to 1048576 (so 8 GB of notifications).

## Confidence tag tally

`[verified-by-code]=3 [from-comment]=4`
