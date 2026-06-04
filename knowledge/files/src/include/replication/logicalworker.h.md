# src/include/replication/logicalworker.h

## Purpose

Public entry points for the four logical-replication worker process
flavors (apply / parallel apply / table sync / sequence sync), plus the
small inter-worker signal-handling surface.

## Role in PG

- Each `*Main` is the bgworker `bgw_function_name` for that flavor; the
  launcher (`logicallauncher.h`) calls
  `RegisterDynamicBackgroundWorker` with one of these as the entry point.
- `IsLogicalWorker` / `IsLogicalParallelApplyWorker` (lines 24-25) are
  process-type predicates used by code paths that need to know
  "am I running inside a logical-rep worker?" (e.g. fmgr permission
  checks, error reporting).
- `ParallelApplyMessagePending` (line 17) is a `sig_atomic_t` set by the
  signal handler when a parallel apply worker has queued a message for
  the leader; `HandleParallelApplyMessageInterrupt` (line 27) is the
  CFI-side responder, and `ProcessParallelApplyMessages` (line 28)
  drains the shm_mq.
- `LogicalRepWorkersWakeupAtCommit(subid)` (line 30) is the cousin of
  `ApplyLauncherWakeupAtCommit` — used when DDL (e.g. ALTER SUBSCRIPTION
  ... REFRESH PUBLICATION) needs to nudge the workers post-commit.
- `AtEOXact_LogicalRepWorkers(isCommit)` (line 32) finalizes any pending
  wake-ups at xact end.

## Key types/struct fields

API only — no public structs. The four `*Main` functions take the
standard bgworker `Datum main_arg` and never return.

## Phase D notes

- `ParallelApplyMessagePending` is the standard PG "set in signal
  handler, check at CFI" pattern. `[from-comment]` Failing to call
  `CHECK_FOR_INTERRUPTS` regularly inside a parallel apply leader path
  delays error propagation from the parallel worker.
- The four worker flavors are dispatched by `LogicalRepWorkerType` in
  `worker_internal.h:28-35`; this header is the postmaster-facing slice
  that doesn't drag in the full internal struct.

## Potential issues

- [ISSUE-undocumented-invariant: header doesn't say which functions are
  safe to call from which worker type. e.g. `LogicalRepWorkersWakeupAtCommit`
  presumably must be called from a regular backend, not from a worker
  — but it's not annotated. (low)]
- [ISSUE-state-transition: `ParallelApplyMessagePending` is volatile +
  sig_atomic_t (line 17), but the surrounding shm_mq drain isn't
  documented as edge-triggered vs level-triggered. (low)]
