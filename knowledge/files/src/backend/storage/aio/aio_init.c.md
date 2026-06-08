---
path: src/backend/storage/aio/aio_init.c
anchor_sha: 4b0bf0788b0
loc: 255
depth: deep
---

# aio_init.c

- **Source path:** `source/src/backend/storage/aio/aio_init.c`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 255

## Purpose

**Per-server and per-backend initialization** of the AIO subsystem:
shared-memory sizing/request/init/attach for the global `PgAioCtl`
(handle array, per-backend state, iovec pool, handle-data pool), the
auto-tuning of `io_max_concurrency`, and `pgaio_init_backend()` which
wires a backend to its slice of the handle array and registers the
shutdown hook. Each IO method's own shmem callbacks are chained in.
[from-comment, aio_init.c:1-13]

## Public symbols

| Symbol | Line | Role |
|---|---|---|
| `AioShmemCallbacks` | `aio_init.c:34` | `{request_fn, init_fn, attach_fn}` registered with the subsystem framework |
| `pgaio_init_backend(void)` | `aio_init.c:237` | per-backend setup; sets `pgaio_my_backend`, registers `pgaio_shutdown` |

## Internal landmarks

- **`AioProcs()` (aio_init.c:45)** = `MaxBackends + NUM_AUXILIARY_PROCS`
  — one AIO context per potential PGPROC. IO workers don't strictly need
  their own context but get a slot anyway (comment: can't guarantee a
  worker's ProcNumber stays unassigned).
- **Sizing functions (aio_init.c:56-93)** — the handle array is
  `AioProcs() × io_max_concurrency × sizeof(PgAioHandle)`; the iovec and
  handle-data pools are `× io_max_combine_limit` on top of that. All use
  `mul_size`/`add_size` overflow-checked arithmetic.
- **`AioChooseMaxConcurrency()` (aio_init.c:104)** — auto-tune: roughly
  `NBuffers / (MaxBackends + NUM_AUXILIARY_PROCS)` pins per backend,
  floored at 1, **capped at 64**. This is what `io_max_concurrency = -1`
  (the default) resolves to.
- **`AioShmemInit` (aio_init.c:178)** — lays out the four pointers into
  the one allocation, then loops every proc × every handle: sets
  `generation = 1`, `owner_procno`, `iovec_off`, inits the CV, and
  pushes each handle onto its backend's `idle_ios`.

## Invariants & gotchas

- **`generation` starts at 1, never 0** (aio_init.c:209). Zero is the
  reserved "invalid" generation — `pgaio_io_get_wref` and
  `pgaio_io_from_wref` both assert non-zero. A wait reference can thus
  never accidentally alias a never-used handle.
- **`io_max_concurrency = -1` must be resolved *before* shmem sizing**
  (aio_init.c:134-144). The trick: set it via `PGC_S_DYNAMIC_DEFAULT`,
  but if the DBA explicitly wrote `-1` in the config, that source can't
  override, so it force-sets with `PGC_S_OVERRIDE`. This is a subtle
  GUC-source-precedence dance worth not breaking.
- **`io_handle_off` partitions the global handle array per backend**
  (aio_init.c:197) — backend N owns handles `[N*conc, (N+1)*conc)`. The
  static handle→PGPROC mapping (`owner_procno`) is why
  `pgaio_io_get_owner` works even for an idle PGPROC.
- **IO workers skip per-backend init** — `pgaio_init_backend` returns
  early for `B_IO_WORKER` (aio_init.c:243); workers process *other*
  backends' IOs and never acquire handles of their own.
- **`pgaio_init_backend` requires a normal PGPROC** with
  `MyProcNumber < AioProcs()` (aio_init.c:246-247).
- **Method shmem callbacks are chained, not replaced** — request/init/
  attach each call the configured method's corresponding
  `shmem_callbacks.*` if present (aio_init.c:171,226,233), so worker /
  io_uring can carve their own shmem (submission queue, ring memory).

## Cross-refs

- Globals + structs: `knowledge/files/src/include/storage/aio_internal.h.md`.
- Shutdown hook target: `aio.c::pgaio_shutdown`.
- Method shmem callbacks: `method_worker.c::pgaio_worker_shmem_*`,
  `method_io_uring.c::pgaio_uring_shmem_*`.
- `io_max_combine_limit` / `io_max_concurrency` GUCs: `aio.c`, `bufmgr.c`.

## Tally

`[verified-by-code]=6 [from-comment]=3 [inferred]=0`
