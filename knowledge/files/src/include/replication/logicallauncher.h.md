# src/include/replication/logicallauncher.h

## Purpose

Public API for the **logical replication launcher** — the postmaster
child that starts/stops apply, tablesync, sequencesync, and parallel
apply workers based on `pg_subscription` rows. Also owns the
"conflict detection" internal slot.

## Role in PG

- Registered at server start via `ApplyLauncherRegister` (line 19) as a
  background worker; postmaster forks it.
- Main loop `ApplyLauncherMain` (line 20) polls `pg_subscription` and
  spawns apply workers for enabled subscriptions; obeys
  `max_logical_replication_workers` (line 15).
- `max_sync_workers_per_subscription` (line 16) and
  `max_parallel_apply_workers_per_subscription` (line 17) are GUCs
  exported here so other modules (catalog views, worker bookkeeping)
  can read them.
- `ApplyLauncherWakeupAtCommit` (line 24) is the standard "queue a
  wake-up to run after this xact commits" pattern; subscription DDL
  (CREATE/ALTER SUBSCRIPTION) calls it so the launcher reacts
  immediately.
- `AtEOXact_ApplyLauncher(isCommit)` (line 26) drains the pending
  wake-up at xact end.
- `CreateConflictDetectionSlot` (line 28) — sets up the cluster-wide
  `pg_conflict_detection` internal slot used by apply workers to publish
  `oldest_nonremovable_xid` for conflict-detection logic. Documented in
  `worker_internal.h:90-101`.

## Key types/struct fields

API only. The launcher itself is a `LogicalRepWorker` with
`type = WORKERTYPE_UNKNOWN` and `subid = InvalidOid` (see
`worker_internal.h:28-35`). `IsLogicalLauncher` (line 30) lets calling
code distinguish launcher from workers.

`GetLeaderApplyWorkerPid(pid)` (line 32) — given a parallel apply
worker PID, returns the leader's PID; used by `pg_stat_activity` views
to display the relationship.

## Phase D notes

- The launcher is a single-process bottleneck. If it dies, postmaster
  will restart it (standard bgworker `bgw_restart_time` policy), but
  during the restart window no new subscriptions are picked up.
- `ApplyLauncherForgetWorkerStartTime(subid)` (line 22) clears the
  rate-limiter timestamp for relaunching workers after a fast crash.
  Without forgetting, the launcher backs off to avoid storms.

## Potential issues

- [ISSUE-dos: a malicious or buggy output-plugin on the publisher can
  poison an apply worker repeatedly; the launcher's back-off via
  `last_start_time` (worker_internal.h) prevents tight loops, but
  `ApplyLauncherForgetWorkerStartTime` (line 22) can be called from
  subscription ALTER to short-circuit the back-off. Caller is trusted
  (subscription owner), but worth flagging. (low)]
- [ISSUE-undocumented-invariant: header doesn't say that the launcher
  process must NOT hold catalog locks across the worker-launch window
  — a long ALTER SUBSCRIPTION can stall it. (maybe)]
- [ISSUE-state-transition: `CreateConflictDetectionSlot` (line 28) has
  no companion drop in this header; lifetime/teardown of
  `pg_conflict_detection` lives elsewhere. Search needed to confirm
  the slot survives a launcher crash cleanly. (maybe)]
