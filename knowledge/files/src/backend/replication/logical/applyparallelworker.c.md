# `src/backend/replication/logical/applyparallelworker.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** 1658
- **Source:** `source/src/backend/replication/logical/applyparallelworker.c`

## Purpose

Parallel apply of large streamed transactions. When
`subscription.streaming = parallel`, the leader apply (LA) hands each
streamed transaction off to a parallel apply worker (PA) over shm_mq.
Avoids file I/O most of the time. Worker pool retained at half of
`max_parallel_apply_workers_per_subscription`. [from-comment]
(`applyparallelworker.c:1-44`)

## DSM layout per PA

Three keys in one DSM segment per worker:

1. `PARALLEL_APPLY_KEY_SHARED` — `ParallelApplyWorkerShared` struct.
2. `PARALLEL_APPLY_KEY_MQ` — 16MB shm_mq, LA → PA, messages.
3. `PARALLEL_APPLY_KEY_ERROR_QUEUE` — 16KB shm_mq, PA → LA, errors.

(`:178-198`)

## Deadlock prevention

Two session-level lmgr locks are the load-bearing trick to expose
LA↔PA waits to the deadlock detector:

- **Stream lock** (`pa_lock_stream`) — LA holds AccessExclusive while
  sending STREAM_STOP; PA briefly takes AccessShare after STREAM_STOP and
  STREAM_ABORT(sub). This creates a wait edge from PA to LA in lmgr so
  when LA is stuck on a unique-key conflict caused by PA's earlier insert,
  lmgr sees the cycle.
- **Transaction lock** (`pa_lock_transaction`) — PA holds AccessExclusive
  for the lifetime of the txn; LA takes AccessShare at xact-finish to
  preserve commit order. Detects the PA-A → PA-B → LA chain when commits
  must be ordered. (`:60-148`) [from-comment]

`XactLockTableWait()` is **not** used because it considers prepared
txns as in-progress, so the lock would not release after PA's PREPARE.
(`:131-134`)

## Buffer-full handling

If the LA→PA shm_mq is full, LA serializes pending messages to a file
and tells PA to read the file for the rest — avoiding a non-lmgr wait
that would be invisible to deadlock detection. See `pa_send_data` and
`TransApplyAction`. (`:137-148`)

## Spine

- `pa_launch_parallel_worker` — pick from pool or `logicalrep_worker_launch`.
- `pa_send_data` — non-blocking shm_mq put, fallback to file on timeout.
- `pa_lock_stream`, `pa_unlock_stream`, `pa_lock_transaction`,
  `pa_unlock_transaction` — the lmgr coordination above.
- `ParallelApplyWorkerMain` (declared in `logicalworker.h:20`) — PA
  entry: attach DSM, register error mq, process incoming messages by
  calling `apply_dispatch` from `worker.c`.
- `HandleParallelApplyMessageInterrupt` / `ProcessParallelApplyMessages`
  — LA-side handler for PA errors and progress signals.

## Why the file-spool fallback isn't enough by itself

Even when LA spills the rest of a txn to a file, it still must wait for
PA to commit before LA itself commits the next txn (to preserve order).
The transaction lock ensures that wait is visible.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
- [subsystems/replication.md](../../../../../subsystems/replication.md)
- [idioms/apply-streaming-and-parallel.md](../../../../../idioms/apply-streaming-and-parallel.md)

## Appears in scenarios

<!-- scenarios:auto:begin -->

- [Scenario — Add a new replication / logical-decoding message](../../../../../scenarios/add-new-replication-message.md)

<!-- scenarios:auto:end -->

