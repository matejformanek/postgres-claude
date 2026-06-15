# src/test/modules/test_shm_mq/setup.c

**Pin:** `b78cd2bda5b1a306e2877059011933de1d0fb735`
**LOC:** 325
**Verification depth:** full read

## Role

Builds the DSM segment, table-of-contents, ring of shm_mq queues, and the
fan-out of dynamic background workers that the test harness round-trips a
message through, then waits for all workers to report ready before returning
the queue handles to the caller. [verified-by-code] `source/src/test/modules/test_shm_mq/setup.c:51-83`

## Public API

- `test_shm_mq_setup(queue_size, nworkers, segp, output, input)` — the single
  exported entry point; sets up DSM + workers, attaches the caller's outbound
  (queue 0) and inbound (queue nworkers) handles, and registers a
  cancel-on-detach cleanup. [verified-by-code] `source/src/test/modules/test_shm_mq/setup.c:51-83`

## Invariants

- INV-1: There are `nworkers + 1` message queues (loop `i = 0 .. nworkers`),
  one more than the worker count, forming the ring back to the caller. [verified-by-code] `source/src/test/modules/test_shm_mq/setup.c:144-165`
- INV-2: Queue 0's sender is the caller (`MyProc`); queue `nworkers`'s receiver
  is the caller. The caller writes the first queue and reads the last. [verified-by-code] `source/src/test/modules/test_shm_mq/setup.c:153-164`
- INV-3: TOC key layout — header at key 0, queue `i` at key `i + 1`; estimator
  reserves `2 + nworkers` keys. [verified-by-code] `source/src/test/modules/test_shm_mq/setup.c:128,142,151`
- INV-4: `queue_size` must be `>= shm_mq_minimum_size` and must round-trip
  through `Size` without overflow, else ERROR. [verified-by-code] `source/src/test/modules/test_shm_mq/setup.c:104-113`
- INV-5: The worker handles must outlive the ExprContext so the on_dsm_detach
  hook can still terminate workers — hence allocation in a transaction-lifetime
  context. [verified-by-code] `source/src/test/modules/test_shm_mq/setup.c:183-194`

## Notable internals

- `setup_dynamic_shared_memory` estimates each chunk separately (TOC may pad
  odd-sized requests), creates the DSM via `dsm_create`, lays out a
  `test_shm_mq_header` control region plus the queue ring with
  `shm_mq_create`. [verified-by-code] `source/src/test/modules/test_shm_mq/setup.c:115-170`
- `setup_background_workers` registers `nworkers` dynamic bgworkers with
  `BGWORKER_SHMEM_ACCESS`, `BgWorkerStart_ConsistentState`,
  `BGW_NEVER_RESTART`, library `test_shm_mq` / function `test_shm_mq_main`,
  passing the DSM handle in `bgw_main_arg` and `MyProcPid` in `bgw_notify_pid`. [verified-by-code] `source/src/test/modules/test_shm_mq/setup.c:218-240`
- `on_dsm_detach` is registered up front to kill workers on abort; once all
  workers are ready `cancel_on_dsm_detach` removes it (workers then self-exit
  via cascading queue-detach). [verified-by-code] `source/src/test/modules/test_shm_mq/setup.c:215-216,80-81`
- `wait_for_workers_to_become_ready` spins on `hdr->workers_ready` under the
  spinlock, polls `check_worker_status` for dead workers/postmaster, and sleeps
  on `MyLatch` with the custom `TestShmMqBgWorkerStartup` wait event and
  `WL_EXIT_ON_PM_DEATH`. [verified-by-code] `source/src/test/modules/test_shm_mq/setup.c:259-305`
- `cleanup_background_workers` calls `TerminateBackgroundWorker` over the
  registered handles in reverse. [verified-by-code] `source/src/test/modules/test_shm_mq/setup.c:247-257`

## Cross-refs

- `source/src/backend/storage/ipc/shm_mq.c` — `shm_mq_create`, `shm_mq_attach`,
  `shm_mq_set_sender`/`set_receiver`, `shm_mq_minimum_size`.
- `source/src/backend/storage/ipc/shm_toc.c` — TOC estimator/allocate/insert.
- `source/src/backend/storage/ipc/dsm.c` — `dsm_create`, `cancel_on_dsm_detach`.
- `source/src/backend/postmaster/bgworker.c` — `RegisterDynamicBackgroundWorker`,
  `GetBackgroundWorkerPid`, `TerminateBackgroundWorker`.
- `source/src/test/modules/test_shm_mq/worker.c` — the `test_shm_mq_main` body.

## Potential issues

- **[ISSUE-doc-drift: comment names wrong memory context]** `setup.c:183-194` —
  the comment says the worker_state and handles must be allocated in
  `CurTransactionContext rather than ExprContext`, and the code does
  `MemoryContextSwitchTo(CurTransactionContext)` at line 189, but the actual
  `MemoryContextAlloc` at line 192 passes `TopTransactionContext` explicitly,
  so the switch is dead for the allocation that matters and the comment's named
  context does not match the allocation site. The handles end up in
  `TopTransactionContext`; the switched-to `CurTransactionContext` governs no
  allocation in this function. Functionally both outlive the ExprContext so the
  test works, but the comment/code mismatch is misleading. Severity: nit.
