---
path: src/backend/storage/aio/aio_io.c
anchor_sha: 4b0bf0788b0
loc: 235
depth: deep
---

# aio_io.c

- **Source path:** `source/src/backend/storage/aio/aio_io.c`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 235

## Purpose

Low-level, **IO-method-independent** handling for the individual IO
operations (currently `readv` / `writev`): the `pgaio_io_start_*()`
entry points that associate operation-specific data with a handle and
hand it to `pgaio_io_stage()`, the synchronous-execution primitive that
all methods can fall back to, and small op-introspection helpers.
[from-comment, aio_io.c:1-17]

## Public symbols

| Symbol | Line | Role |
|---|---|---|
| `pgaio_io_get_iovec(ioh, **iov)` | `aio_io.c:41` | hand caller the handle's iovec slot (returns `PG_IOV_MAX`) |
| `pgaio_io_get_op(ioh)` | `aio_io.c:51` | the `PgAioOp` |
| `pgaio_io_get_op_data(ioh)` | `aio_io.c:57` | `&ioh->op_data` |
| `pgaio_io_start_readv(ioh, fd, iovcnt, offset)` | `aio_io.c:77` | define a readv + stage |
| `pgaio_io_start_writev(ioh, fd, iovcnt, offset)` | `aio_io.c:90` | define a writev + stage |
| `pgaio_io_perform_synchronously(ioh)` | `aio_io.c:115` | `pg_preadv`/`pg_pwritev` + process completion (internal) |
| `pgaio_io_get_op_name(ioh)` | `aio_io.c:174` | "readv"/"writev"/"invalid" |
| `pgaio_io_uses_fd(ioh, fd)` | `aio_io.c:196` | does this IO reference `fd`? (for FD-close) |
| `pgaio_io_get_iovec_length(ioh, **iov)` | `aio_io.c:218` | iovec count (debug/introspection) |

## Internal landmarks

- **The start routines are a 3-step protocol** (aio_io.c:65-75):
  `pgaio_io_before_start()` (assertions only), fill the op-specific
  fields in `op_data`, then `pgaio_io_stage(ioh, op)`. Both readv and
  writev follow it identically.
- **`pgaio_io_perform_synchronously` (aio_io.c:115)** is the workhorse
  used by `method_sync.c` *and* as a fallback by worker mode and the
  synchronous-hint path: it wraps the `pg_preadv`/`pg_pwritev` in a
  critical section, sets `wait_event` to `DATA_FILE_READ`/`_WRITE`,
  stores `result < 0 ? -errno : result`, then calls
  `pgaio_io_process_completion`.

## Invariants & gotchas

- **`pgaio_io_before_start` asserts interrupts cannot be processed**
  (aio_io.c:167) — otherwise the FDs referenced by the IO could be
  closed under it by interrupt processing. It also asserts the handle
  is HANDED_OUT with a target set and `op == INVALID`.
- **The FD in `op_data` is not reliable for re-issue** — see `aio.h`'s
  warning: a worker or a partial-read retry may run in a different
  process where that FD is meaningless. That's why worker mode calls
  `pgaio_io_reopen` (via the target's `reopen` callback) before
  executing. `pgaio_io_uses_fd` is only valid for the FD-close check in
  the *issuing* process while the IO is staged/in-flight there.
- **Synchronous execution stores `-errno`, not `errno`**
  (aio_io.c:144) — the negative convention matches io_uring's `cqe->res`
  so completion callbacks can interpret both uniformly.
- **Only one iovec region per handle** — `pgaio_io_get_iovec` returns
  the handle's pre-reserved slot in `PgAioCtl->iovecs` (offset
  `iovec_off`), capacity `PG_IOV_MAX`; the actual length is recorded in
  `op_data.{read,write}.iov_length` by the start routine.

## Cross-refs

- Stage/submit core: `aio.c::pgaio_io_stage`,
  `aio.c::pgaio_io_process_completion`.
- iovec/handle-data pools: `aio_internal.h` (`PgAioCtl`).
- Reopen for worker mode: `aio_target.c::pgaio_io_reopen`.
- `pg_preadv`/`pg_pwritev`: `src/port/pg_iovec.h` (via `storage/fd.h`).

## Tally

`[verified-by-code]=5 [from-comment]=2 [inferred]=0`
