# `src/include/storage/io_worker.h`

- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
- **Lines:** 31

## Role

PG18 **AIO worker** entrypoint — a separate auxiliary process
that performs blocking I/O on behalf of backends when the
`io_method = worker` GUC is selected (alternative to
`io_uring`/`sync`). Bridges into the `storage/aio` subsystem.

[verified-by-code] `source/src/include/storage/io_worker.h:18-29`

## Public API

- `pg_noreturn extern void IoWorkerMain(const void *startup_data,
  size_t startup_data_len);` — bgworker main
- Public GUCs:
  - `io_min_workers` (default 1, presumably)
  - `io_max_workers`
  - `io_worker_idle_timeout`
  - `io_worker_launch_interval`
- Postmaster-visible helpers:
  - `pgaio_worker_pm_test_grow_signal_sent()`
  - `pgaio_worker_pm_clear_grow_signal_sent()`
  - `pgaio_worker_pm_test_grow()`

## Invariants

- INV-1: AIO workers are auxiliary processes — they DON'T have
  database connections; they execute I/O requests via shared
  submission queue + DSM scratch.
- INV-2: `pg_noreturn` on `IoWorkerMain` — the worker process
  cannot return to postmaster.

## Trust boundary (Phase D)

- AIO workers operate on `RelFileLocator`+block from the
  shared submission queue. A buggy backend could enqueue a
  malformed request; the worker must validate or it will
  segfault and respawn (postmaster will eventually treat as
  crash).
- Submission-queue capacity (`io_max_workers`) is a DoS knob —
  exhausting workers causes backends to fall back to
  synchronous I/O.

## Cross-refs

- `knowledge/subsystems/storage-aio.md` (if exists) — the
  surrounding subsystem
- `knowledge/files/src/include/storage/aio.h.md` (existing) —
  caller-side API
- `knowledge/files/src/backend/storage/aio/io_worker.c.md` (if
  exists)
- `knowledge/files/src/include/storage/read_stream.h.md` —
  primary consumer of AIO

## Issues

None at header level.
