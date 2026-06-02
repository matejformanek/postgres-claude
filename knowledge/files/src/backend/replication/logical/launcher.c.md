# `src/backend/replication/logical/launcher.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** 1721
- **Source:** `source/src/backend/replication/logical/launcher.c`

## Purpose

The logical-replication launcher process: a long-running bgworker that
spawns one apply worker per enabled subscription, plus tablesync /
sequencesync / parallel-apply workers as requested. Also manages the
internal `pg_conflict_detection` slot's xmin aggregation. [from-comment]

## Shared state

`LogicalRepCtxStruct` (`:60`):

- `launcher_pid` — pid of the supervisor.
- `last_start_dsa` / `last_start_dsh` — DSA + dshash to remember when
  each subscription last had an apply worker started, to throttle restarts.
- `workers[FLEXIBLE_ARRAY_MEMBER]` — fixed-size pool sized by
  `max_logical_replication_workers`.

Each `LogicalRepWorker` (`worker_internal.h`) holds: type (APPLY,
TABLESYNC, SEQUENCESYNC, PARALLEL_APPLY), subid, relid, generation, pid,
proc, relstate, last_lsn, last_send_time, oldest_nonremovable_xid.

## Spine

- `ApplyLauncherMain` (`:1205`) — supervisor loop: every cycle (≤3min)
  read `pg_subscription`, start any missing apply workers, drive the
  conflict-detection slot xmin advancement.
- `logicalrep_worker_launch` (`:334`) — common path for spawning any
  worker type via `RegisterDynamicBackgroundWorker`; waits for it to
  attach (`WaitForReplicationWorkerAttach` `:191`).
- `logicalrep_worker_stop_internal` (`:579`) — send signal, wait on CV,
  reap.
- `logicalrep_worker_find` / `_workers_find` (`:268`, `:303`) — lookup by
  (type, subid, relid).
- `compute_min_nonremovable_xid` (`:1448`) — aggregate per-apply-worker
  `oldest_nonremovable_xid` into a single xid for the conflict slot.
- `CreateConflictDetectionSlot` (`:1569`) — create the internal
  `pg_conflict_detection` logical slot the first time a subscription with
  `retain_dead_tuples` appears.
- `update_conflict_slot_xmin` (`:1500`) — call into slot.c to advance
  that slot's xmin.

## Throttling

`DEFAULT_NAPTIME_PER_CYCLE = 180000` ms (3 min) (`:51`). On
subscription change `ApplyLauncherWakeup` (`:1195`) sets the latch.

## GUCs

`max_logical_replication_workers = 4`,
`max_sync_workers_per_subscription = 2`,
`max_parallel_apply_workers_per_subscription = 2` (`:54-56`).

## SQL surface

`pg_stat_get_subscription` (`:1625`) — SRF for `pg_stat_subscription`.

## Synthesized by
<!-- backlinks:auto -->
- [architecture/replication.md](../../../../../architecture/replication.md)
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
