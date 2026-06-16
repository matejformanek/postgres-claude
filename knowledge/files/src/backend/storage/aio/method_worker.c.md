---
path: src/backend/storage/aio/method_worker.c
anchor_sha: 4b0bf0788b0
loc: 1031
depth: deep
---

# method_worker.c

- **Source path:** `source/src/backend/storage/aio/method_worker.c`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 1031

## Purpose

The **`io_method=worker`** implementation — the default, available on
every platform. IO workers (auxiliary processes) consume IO handle IDs
from a shared-memory **submission queue**, run ordinary blocking
`pg_preadv`/`pg_pwritev`, and run the shared completion handling
immediately. Client backends submit by pushing into the queue and wait
(if needed) on the handle CV. The worker pool **elastically resizes**
between `io_min_workers` and `io_max_workers` based on observed demand.
[from-comment, method_worker.c:1-27]

## Public symbols

| Symbol | Line | Role |
|---|---|---|
| `pgaio_worker_ops` | `method_worker.c:121` | the `IoMethodOps` vtable for `IOMETHOD_WORKER` |
| `io_min_workers` / `io_max_workers` | `method_worker.c:131-132` | GUCs (default 2 / 8) |
| `io_worker_idle_timeout` / `io_worker_launch_interval` | `method_worker.c:133-134` | GUCs (60000 ms / 100 ms) |
| `IoWorkerMain(startup_data, len)` | `method_worker.c:665` | the IO worker main loop (aux process entry) |
| `pgaio_workers_enabled(void)` | `method_worker.c:1027` | `io_method == IOMETHOD_WORKER` |
| `pgaio_worker_pm_test_grow` / `_test_grow_signal_sent` / `_clear_grow_signal_sent` | `method_worker.c:328,339,348` | postmaster-side grow protocol |

## Internal landmarks

- **`PgAioWorkerSubmissionQueue` (method_worker.c:71)** — a single
  shared ring buffer of IO handle IDs (`sqes[]`), power-of-two sized
  (default `io_worker_queue_size = 64`), protected by
  `AioWorkerSubmissionQueueLock`. Insert/consume/depth at
  method_worker.c:412-470.
- **`PgAioWorkerControl` + `PgAioWorkerSet` bitmap (method_worker.c:90-111)**
  — worker membership and idleness tracked in a `uint64` bitmap
  (`static_assert` ≥ `MAX_IO_WORKERS`). The `pgaio_workerset_*` helpers
  (method_worker.c:143-231) are a small set ADT.
- **`pgaio_worker_submit` (method_worker.c:481)** — client side: prepare
  each IO for submit, conditionally acquire the queue lock and insert;
  on a full queue or lock-contention, **run the remainder
  synchronously** in the issuing backend. Wakes exactly one idle worker
  (which propagates wakeups).
- **`IoWorkerMain` (method_worker.c:665)** — register in shmem, then
  loop: consume a queue entry (or mark self idle), maybe wake a higher
  worker / request pool growth, `pgaio_io_reopen` + execute the IO
  synchronously, else sleep on the latch with a possibly-finite timeout.
- **Elastic sizing**: `pgaio_worker_request_grow` (method_worker.c:277)
  signals the postmaster (`PMSIGNAL_IO_WORKER_GROW`) when the queue is
  deeper than the worker count; idle highest-numbered workers time out
  via `pgaio_worker_can_timeout` (method_worker.c:646).

## Invariants & gotchas

- **Some IOs *can't* go to a worker** —
  `pgaio_worker_needs_synchronous_execution` (method_worker.c:472)
  forces in-issuer execution when not under postmaster, when the IO
  references process-local memory (`PGAIO_HF_REFERENCES_LOCAL`), or when
  the target can't `reopen`. The worker has no access to the issuer's
  local memory and must reopen the file by identity, not FD.
- **Worker error recovery completes the IO as failed, then exits.** The
  `sigsetjmp` block (method_worker.c:705-734): on any ereport the worker
  marks the in-progress `error_ioh` failed via
  `pgaio_io_process_completion(error_ioh, -error_errno)` in a critical
  section, then `proc_exit(1)` — the postmaster starts a replacement.
  An IO must never be left forever in SUBMITTED because its worker died.
- **`reopen` is bracketed by `HOLD_INTERRUPTS()`** (method_worker.c:872)
  so the freshly reopened FD can't be closed by interrupt processing
  before the read/write runs. `error_errno = ENOENT` is pre-armed
  because reopen can fail (permissions, OOM) and there's "not really a
  good errno."
- **Only the highest-numbered worker may idle-time-out, and only above
  `io_min_workers`** (method_worker.c:636-663) — this keeps worker IDs
  packed in `0..N` with no gaps and avoids undershooting the minimum.
  All workers are woken on pool/GUC changes so the "who is highest"
  decision is eventually consistent.
- **Wakeup-propagation chain** (method_worker.c:766-798): a woken worker
  that finds work wakes the next-higher idle worker only if it isn't
  itself getting spurious wakeups (`hist_wakeups <= hist_ios`). This
  builds a "frontier" beyond which idle workers stay asleep — an
  exponentially-decaying wakeups:IOs ratio (`PGAIO_WORKER_WAKEUP_RATIO_
  SATURATE = 4`, method_worker.c:66).
- **Grow heuristic is admittedly crude**: request a new worker when
  `queue_depth > nworkers` (method_worker.c:843), combined with the
  wakeup test and `io_worker_launch_interval` throttle. There's an
  `XXX` musing that queueing/control theory could do better.
- **A wake targeting an exiting worker is safe** — if the chosen worker
  is mid-exit, `pgaio_worker_die` wakes all remaining workers so
  *someone* sees the queued IO; if none remain, the postmaster starts
  one (method_worker.c:388-398, 562-568).
- **SIGTERM is ignored**; shutdown is via SIGUSR2 late in the sequence,
  like checkpointer (method_worker.c:683-692).

## Cross-refs

- Core submit/complete: `aio.c::pgaio_submit_staged`,
  `aio.c::pgaio_io_process_completion`; synchronous exec
  `aio_io.c::pgaio_io_perform_synchronously`.
- Reopen: `aio_target.c::pgaio_io_reopen`.
- Vtable type: `aio_internal.h` (`IoMethodOps`).
- Postmaster grow handling: `postmaster.c` (`PMSIGNAL_IO_WORKER_GROW`,
  `MaybeStartIoWorkers`); `io_worker.h`.
- Locking: `AioWorkerSubmissionQueueLock`, `AioWorkerControlLock` —
  see `knowledge/idioms/locking-overview.md`.

<!-- issues:auto:begin -->
- [Issue register — `storage-aio`](../../../../../issues/storage-aio.md)
<!-- issues:auto:end -->

## Potential issues

- **[ISSUE-question: single global submission queue is a known
  scalability ceiling]** `method_worker.c:84-88` — the comment itself
  says if we wanted more than `MAX_IO_WORKERS` workers "the contention
  on the single queue would surely get too high," suggesting multiple
  pools. On many-core boxes with worker mode (the default), the one
  `AioWorkerSubmissionQueueLock` serializes all submission + all
  consumption. Severity: maybe (design-acknowledged scaling limit).
- **[ISSUE-question: full-queue fallback can do large synchronous IO in
  a latency-sensitive issuer]** `method_worker.c:498-533` — when the
  queue is full or the lock is contended, the issuing backend runs the
  *remaining batch* synchronously, including potentially many blocks,
  defeating the async intent precisely under load. Documented behavior,
  but a tail-latency cliff worth knowing. Severity: nit.

## Tally

`[verified-by-code]=7 [from-comment]=5 [inferred]=1`
