---
path: src/backend/storage/aio/method_sync.c
anchor_sha: 4b0bf0788b0
loc: 47
depth: read
---

# method_sync.c

- **Source path:** `source/src/backend/storage/aio/method_sync.c`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 47

## Purpose

The **`io_method=sync`** implementation — "AIO" that isn't: it executes
every IO synchronously through the AIO API. Mainly a regression-check
baseline, but also the fallback other methods use for IOs they cannot
execute asynchronously. [from-comment, method_sync.c:1-17]

## Public symbols

| Symbol | Line | Role |
|---|---|---|
| `pgaio_sync_ops` | `method_sync.c:28` | the `IoMethodOps` vtable for `IOMETHOD_SYNC` |

## Internal landmarks / invariants

- **`needs_synchronous_execution` always returns true** (method_sync.c:35)
  — so the AIO core (`aio.c::pgaio_io_stage`) runs the IO inline via
  `pgaio_io_perform_synchronously` and never calls `submit`.
- **`submit` is an `elog(ERROR, "IO should have been executed
  synchronously")`** (method_sync.c:42) — it's wired into the vtable but
  is unreachable in correct operation; reaching it means the
  needs-synchronous gate was bypassed.
- The vtable provides **only** `needs_synchronous_execution` + `submit`;
  no shmem callbacks, no `wait_one`/`check_one` — there's never an
  in-flight IO to wait for, completion happens inline during stage.

## Cross-refs

- The actual synchronous execution: `aio_io.c::pgaio_io_perform_synchronously`.
- Vtable type: `aio_internal.h` (`IoMethodOps`).
- Sibling methods: `method_worker.c`, `method_io_uring.c`.
- `read_stream.c` checks `io_method == IOMETHOD_SYNC` to enable
  posix_fadvise-based pseudo-readahead (it can't get real async IO here).

## Tally

`[verified-by-code]=3 [from-comment]=1 [inferred]=0`
