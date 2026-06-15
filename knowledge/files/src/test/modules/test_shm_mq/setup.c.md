---
path: src/test/modules/test_shm_mq/setup.c
anchor_sha: e18b0cb7344
loc: 325
depth: read
---

# src/test/modules/test_shm_mq/setup.c

## Purpose

Driver-side plumbing for the `test_shm_mq` module: allocates the DSM
segment + TOC, lays down the synchronization header and `nworkers + 1`
message queues, registers `nworkers` dynamic bgworkers, and waits until
all workers have signaled "ready" before returning. The whole setup is
wired to an `on_dsm_detach` callback so an early abort terminates the
workers cleanly. `[verified-by-code]` `setup.c:48-83`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `test_shm_mq_setup(queue_size, nworkers, &seg, &out, &in)` | `:52` | One-shot driver that returns attached output / input queue handles |

## Internal landmarks

- `setup_dynamic_shared_memory` (`:92`) — estimates segment size via
  `shm_toc_estimator`, calls `dsm_create` + `shm_toc_create` with
  `PG_TEST_SHM_MQ_MAGIC`, lays down the header at key 0 and queues at
  keys `1..nworkers+1`. The driver writes queue 0, reads queue `nworkers`.
- `setup_background_workers` (`:175`) — allocates the `worker_state`
  flexible array in `TopTransactionContext` (`:192-194`) so it outlives
  the executor's ExprContext; registers an `on_dsm_detach` callback
  *before* spawning so a mid-spawn abort cleans up.
- Worker template (`:218-228`) — `BGWORKER_SHMEM_ACCESS`,
  `BgWorkerStart_ConsistentState`, `BGW_NEVER_RESTART`,
  `bgw_main_arg = dsm_segment_handle(seg)`, `bgw_notify_pid = MyProcPid`
  (so worker can signal back via `BackendPidGetProc`).
- `wait_for_workers_to_become_ready` (`:259`) — sleeps on
  `WaitLatch(MyLatch, WL_LATCH_SET | WL_EXIT_ON_PM_DEATH, 0,
  we_bgworker_startup)` using a custom wait event registered via
  `WaitEventExtensionNew("TestShmMqBgWorkerStartup")`.
- `check_worker_status` (`:307`) — polls each worker handle via
  `GetBackgroundWorkerPid`; returns false if any worker reports
  `BGWH_STOPPED` or `BGWH_POSTMASTER_DIED`.
- `cleanup_background_workers` (`:247`) — DSM detach callback;
  `TerminateBackgroundWorker` on each handle in reverse order.

## Invariants & gotchas

- TEST MODULE — never load in production: it provides DSM-handle-tied
  bgworker management for regression purposes only.
- The DSM segment carries `nworkers + 1` queues; the extra queue closes
  the ring back to the driver (`[from-comment]` `:85-90`).
- `worker_state` must live in `TopTransactionContext` — putting it in
  `CurTransactionContext` (the function's caller context) is wrong
  because the `on_dsm_detach` hook may run after the transaction's
  ExprContext has gone (`[from-comment]` `:184-188`).
- After all workers signal ready, the driver calls `cancel_on_dsm_detach`
  (`:80`) so the on-detach callback won't fire — from that point the
  queues handle cascading worker exits naturally `[from-comment]`
  `:75-79,197-214`.
- Queue size below `shm_mq_minimum_size` errors out (`:104-109`).

## Cross-refs

- `knowledge/files/src/test/modules/test_shm_mq/worker.c.md` — worker
  side that completes the handshake.
- `knowledge/files/src/test/modules/test_shm_mq/test.c.md` — SQL driver.
- `source/src/include/storage/dsm.h` — `dsm_create`, `dsm_segment_handle`,
  `on_dsm_detach`.
- `source/src/include/postmaster/bgworker.h` —
  `RegisterDynamicBackgroundWorker`, `BackgroundWorkerHandle`.
