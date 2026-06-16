---
path: src/backend/storage/aio/method_io_uring.c
anchor_sha: 4b0bf0788b0
loc: 812
depth: deep
---

# method_io_uring.c

- **Source path:** `source/src/backend/storage/aio/method_io_uring.c`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 812

## Purpose

The **`io_method=io_uring`** implementation (Linux 5.1+, requires
liburing, incompatible with `EXEC_BACKEND`). One io_uring instance per
backend, created in the postmaster during startup so *other* backends
can drain its completions if the owning backend is busy. Submits IO
from within the issuing process (no context switch to a worker),
lowering latency. The whole file is wrapped in
`#ifdef IOMETHOD_IO_URING_ENABLED`. [from-comment, method_io_uring.c:1-30]

## Public symbols

| Symbol | Line | Role |
|---|---|---|
| `pgaio_uring_ops` | `method_io_uring.c:63` | the `IoMethodOps` vtable for `IOMETHOD_IO_URING` |

(All other functions are file-static method callbacks; nothing else is
exported.)

## Internal landmarks

- **`PgAioUringContext` (method_io_uring.c:85)** — per-backend: a
  cacheline-aligned struct holding an LWLock (`completion_lock`) and the
  `struct io_uring`. Alignment prevents false sharing between one
  backend's lock and the previous backend's ring.
- **`pgaio_uring_check_capabilities` (method_io_uring.c:144)** — probes
  whether `io_uring_queue_init_mem()` (kernel 6.5+) can put ring memory
  in *our* shared memory, avoiding a per-ring mmap (many mmaps slow
  backend exit). Determines exact per-ring size by test-creating a ring.
- **`pgaio_uring_submit` (method_io_uring.c:414)** — get an SQE per
  staged IO, `pgaio_io_prepare_submit`, translate via
  `pgaio_uring_sq_from_io`, then loop `io_uring_submit()` handling EINTR.
- **`pgaio_uring_drain_locked` (method_io_uring.c:513)** — the
  completion reaper: under `completion_lock`, peek a batch of CQEs
  (≤ `PGAIO_MAX_LOCAL_COMPLETED_IO = 32`) and call
  `pgaio_io_process_completion(ioh, cqe->res)` for each, inside a
  critical section.
- **`pgaio_uring_wait_one` / `pgaio_uring_check_one`
  (method_io_uring.c:571,647)** — the `wait_one`/`check_one` vtable
  entries: take the *owner's* completion lock and drain; `check_one` is
  the non-blocking poll with a cheap unlocked `io_uring_cq_ready`
  pre-check.
- **`pgaio_uring_should_use_async` (method_io_uring.c:715)** — heuristic
  for setting `IOSQE_ASYNC` on reads (force background processing): only
  for buffered IO, and only when queue depth > 4 or the IO is ≥ 4×BLCKSZ.

## Invariants & gotchas

- **Rings are created in the postmaster, one per backend, and a backend
  may only *submit* to its own ring** (method_io_uring.c:6-13). Other
  backends may *drain* (complete) it — that's the
  deadlock-avoidance guarantee (any backend can make progress on a
  blocked issuer's IO) — but submitting to a foreign ring would need
  extra locking and is forbidden.
- **`completion_lock` serializes completion, not submission.** Multiple
  backends draining the same ring must not race, so all
  `io_uring_peek_batch_cqe`/`_cqe_seen` happen under the owner's
  `completion_lock` (LWTRANCHE_AIO_URING_COMPLETION).
- **`wait_on_fd_before_close = true`** (method_io_uring.c:71) — io_uring
  is mostly fine with FDs closing under in-flight IO, **except IOs
  submitted with `IOSQE_ASYNC`**, so `aio.c::pgaio_closing_fd` must
  drain io_uring IOs on that FD before closing. This flag is the only
  reason that drain path exists.
- **Submit failures escalate to PANIC, deliberately.** EAGAIN isn't
  retried (the manpage's "wait and retry" is rejected: the caller may
  hold critical locks, and waiting would delay a likely crash-restart
  under kernel memory pressure) → `elog(PANIC)` (method_io_uring.c:449-
  472). A short submit (`ret != num_staged_ios`) is also PANIC.
- **Startup errors carry actionable hints** (method_io_uring.c:370-400):
  EPERM → check `/proc/sys/kernel/io_uring_disabled`; EMFILE → raise
  `ulimit -n`; ENOSYS → kernel lacks io_uring. RLIMIT_NOFILE must cover
  one ring FD per backend plus `set_max_safe_fds()` headroom — an
  `XXX` notes PG should probably bump the soft limit itself.
- **io_uring can be *slower than worker mode for heavy buffered IO**
  (method_io_uring.c:688-714) — it copies page-cache→userspace in the
  foreground (no DMA offload as with direct IO), where worker mode
  parallelizes the copy across processes. Hence the `IOSQE_ASYNC`
  heuristic. With direct IO there's no benefit to forcing async (DIO is
  never executed synchronously during submission).
- **One context per `pgaio_uring_procs()` = MaxBackends +
  NUM_AUXILIARY_PROCS − MAX_IO_WORKERS** (method_io_uring.c:131-139) —
  io_uring and worker mode are never used at the same time, so the
  worker slots are subtracted.

## Cross-refs

- Core submit/complete contract: `aio.c::pgaio_io_prepare_submit`,
  `aio.c::pgaio_io_process_completion`, `aio.c::pgaio_closing_fd`.
- Vtable type: `aio_internal.h` (`IoMethodOps`).
- Sibling fallback for un-async-able IO: `method_sync.c`,
  `aio_io.c::pgaio_io_perform_synchronously`.
- LWLock tranche `LWTRANCHE_AIO_URING_COMPLETION`: `lwlocknames`.

<!-- issues:auto:begin -->
- [Issue register — `storage-aio`](../../../../../issues/storage-aio.md)
<!-- issues:auto:end -->

## Potential issues

- **[ISSUE-question: submit/EAGAIN → PANIC is a kernel-pressure crash
  amplifier]** `method_io_uring.c:449-472` — under severe kernel memory
  pressure `io_uring_submit` can return EAGAIN; PG chooses PANIC
  (crash-restart) over retry. Defensible (caller may hold locks) and
  documented, but means a transient kernel condition takes down the
  whole cluster rather than one query. Severity: maybe.
- **[ISSUE-todo: RLIMIT_NOFILE not auto-adjusted for ring FDs]**
  `method_io_uring.c:330-345` — the `XXX` says PG "probably should
  adjust the soft RLIMIT_NOFILE"; today a high `max_connections` with
  io_uring can hit EMFILE at startup and only a hint tells the DBA to
  raise `ulimit -n`. Severity: nit.

## Tally

`[verified-by-code]=7 [from-comment]=6 [inferred]=0`
