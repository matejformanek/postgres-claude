---
path: src/include/storage/aio.h
anchor_sha: 4b0bf0788b0
loc: 369
depth: deep
---

# aio.h

- **Source path:** `source/src/include/storage/aio.h`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 369

## Purpose

The **main public AIO interface** — the header to include when actually
issuing asynchronous IO. Declares the `io_method` enum, the IO-handle
flags/operations/targets/callback-ID enums, the callback function-pointer
typedefs and `PgAioHandleCallbacks` vtable, and the full
`pgaio_io_*` / `pgaio_wref_*` / batchmode function set.
[from-comment, aio.h:1-16]

## Public symbols

| Symbol | Kind | Line | Notes |
|---|---|---|---|
| `IoMethod` | enum | `aio.h:32` | SYNC=0, WORKER, IO_URING (Linux only) |
| `DEFAULT_IO_METHOD` | macro | `aio.h:42` | **`IOMETHOD_WORKER`** — worker is the default |
| `IOMETHOD_IO_URING_ENABLED` | macro | `aio.h:27` | set iff `USE_LIBURING && !EXEC_BACKEND` |
| `PgAioHandleFlags` | enum | `aio.h:48` | `REFERENCES_LOCAL`, `SYNCHRONOUS`, `BUFFERED` |
| `PgAioOp` | enum | `aio.h:87` | INVALID/READV/WRITEV (fsync/flush/send/recv are TODO) |
| `PgAioTargetID` | enum | `aio.h:116` | INVALID/SMGR |
| `PgAioOpData` | union | `aio.h:134` | per-op `{fd, iov_length, offset}` |
| `PgAioHandleCallbackID` | enum | `aio.h:192` | INVALID/MD_READV/SHARED_BUFFER_READV/LOCAL_BUFFER_READV |
| `PgAioHandleCallbacks` | struct | `aio.h:213` | `{stage, complete_shared, complete_local, report}` |
| `PGAIO_HANDLE_MAX_CALLBACKS` | macro | `aio.h:267` | 4 |
| `pgaio_io_acquire` / `_nb` | fn | `aio.h:278-279` | acquire handle (blocking / non-blocking) |
| `pgaio_io_release` | fn | `aio.h:281` | release un-needed handle |
| `pgaio_io_set_flag` | fn | `aio.h:285` | OR a flag in |
| `pgaio_io_get_wref` | fn | `aio.h:290` | snapshot a wait reference before starting |
| `pgaio_io_start_readv` / `_writev` | fn | `aio.h:299-301` | lowest-level "define + stage" |
| `pgaio_io_set_target` / `_register_callbacks` | fn | `aio.h:305,311` | target + completion wiring |
| `pgaio_io_set_handle_data_32` / `_64` | fn | `aio.h:313-314` | attach buffer-ID array |
| `pgaio_wref_wait` / `_check_done` | fn | `aio.h:328-329` | block / poll on a reference |
| `pgaio_result_report` | fn | `aio.h:338` | raise error/log from a `PgAioResult` |
| `pgaio_enter_batchmode` / `_exit_` / `_submit_staged` / `_have_staged` | fn | `aio.h:348-351` | batch control |
| `pgaio_closing_fd` | fn | `aio.h:360` | flush IOs before an FD close |
| `io_method`, `io_max_concurrency` | GUC extern | `aio.h:365-366` | |

## Invariants & gotchas

- **Worker is the default method** (`DEFAULT_IO_METHOD`, aio.h:42), not
  io_uring — io_uring is opt-in and only compiled on Linux with
  liburing in a non-`EXEC_BACKEND` build (aio.h:25-28). Any doc that
  says "PG18 defaults to io_uring" is wrong.
- **`PGAIO_HF_SYNCHRONOUS = 1 << 0` but `PGAIO_HF_REFERENCES_LOCAL =
  1 << 1`** (aio.h:60,70) — the enum is declared out of bit order.
  `REFERENCES_LOCAL` is *required for correctness* (some methods can't
  touch process-local memory and must fall back to sync);
  `SYNCHRONOUS` and `BUFFERED` are advisory hints. Mislabeling a
  local-memory IO without `REFERENCES_LOCAL` is a correctness bug, not
  a perf nit. [from-comment, aio.h:50-77]
- **Only READV/WRITEV exist today** (aio.h:92-93). The block comment
  lists fsync/fdatasync/flush_range/send/recv/accept as planned. Code
  switching on `PgAioOp` must keep the `PGAIO_OP_INVALID` arm.
- **Callbacks are identified by ID, not pointer** (aio.h:174-201) for
  two reasons: shared-memory frugality (1 byte vs 8) and `EXEC_BACKEND`
  (ASLR makes function pointers non-portable across backends). New
  callbacks must be added to the `aio_handle_cbs[]` table in
  `aio_callback.c`, not registered dynamically.
- **`complete_shared` runs in the completing backend** (which may not
  be the issuer) and may only touch shared memory; **`complete_local`
  runs in the issuing backend** and can touch backend-local state
  (e.g. temp-buffer `BufferDesc`). Latest-registered callback runs
  first, so higher layers can rely on lower-layer callbacks having
  already run (aio.h:225-251).
- **`report` is what actually raises the ERROR**, deferred to the
  issuing code's control — completion callbacks run in critical
  sections and may run in another backend, so they can *never* ERROR
  the issuing query directly (aio.h:253-258). This is the whole reason
  `PgAioReturn` exists.

## Cross-refs

- Types-only header: `knowledge/files/src/include/storage/aio_types.h.md`.
- Internal structs/state machine: `knowledge/files/src/include/storage/aio_internal.h.md`.
- Implementations: `aio.c` (handles/wref/batch), `aio_callback.c`
  (callbacks/result), `aio_io.c` (start_readv/writev), `aio_target.c`
  (set_target).
- README: `source/src/backend/storage/aio/README.md`.

## Tally

`[verified-by-code]=3 [from-comment]=5 [inferred]=0`
