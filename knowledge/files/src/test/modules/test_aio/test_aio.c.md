---
path: src/test/modules/test_aio/test_aio.c
anchor_sha: e18b0cb7344
loc: 1256
depth: read
---

# src/test/modules/test_aio/test_aio.c

## Purpose

Heavy-duty SQL-driven probe of the asynchronous I/O subsystem
(`storage/aio.h`). Exposes ~30 internal entry points so the regression
suite can: construct AIO handles manually (`handle_get` /
`handle_release_last`), drive read-stream and read-buffers code paths,
inject **short-read** and **reopen** errors at well-known injection
points, synchronize on AIO completion (`inj_io_completion_wait` /
`continue`), exercise `PinBuffer` / `StartBufferIO` / `TerminateBufferIO`
directly, grow and modify relation blocks, and force buffer eviction.
The module is documented as deliberately exporting "not safe in
production" hooks for testing only. `[verified-by-code]` `test_aio.c:1-16`

## Public symbols

(30+ SQL functions, only the high-impact ones listed; all registered via
`PG_FUNCTION_INFO_V1`)

| Symbol | Site | Notes |
|---|---|---|
| `_PG_init` | `:145` | Registers shmem callbacks (`RegisterShmemCallbacks`); preload only |
| `errno_from_string(text)` | `:154` | Helper: convert errno string to int for testing errors-from-AIO |
| `grow_rel(regclass, blocks)` | `:177` | Extend a relation to N blocks |
| `modify_rel_block(...)` | `:216` | Write a synthesized contents block (good or bad checksum) |
| `read_rel_block_ll(...)` | `:380` | Low-level AIO read; bypasses normal buffer manager |
| `invalidate_rel_block`, `evict_rel`, `buffer_create_toy` | `:523,540,589` | Buffer state manipulation |
| `buffer_call_start_io`, `buffer_call_terminate_io` | `:608,643` | Direct `StartBufferIO` / `TerminateBufferIO` exercise |
| `read_buffers(...)` | `:695` | Drive `StartReadBuffers` / `WaitReadBuffers` path |
| `read_stream_for_blocks(...)` | `:852` | Drive the `read_stream.h` streaming API |
| `handle_get`, `handle_release_last`, `handle_get_and_error`, `handle_get_twice`, `handle_get_release` | `:919-960` | Raw `PgAioHandle` lifecycle tests |
| `batch_start`, `batch_end` | `:972,980` | `pgaio_enter_batchmode` / exit |
| `inj_io_short_read_attach`, `inj_io_short_read_detach` | `:1201,1221` | Toggle injected short-read error |
| `inj_io_reopen_attach`, `inj_io_reopen_detach` | `:1233,1246` | Toggle injected re-open error |
| `inj_io_completion_wait`, `inj_io_completion_continue` | `:1165,1184` | Block tests at AIO-completion injection point until released |

## Internal landmarks

- `InjIoErrorState` (`:47-64`) — shared-memory control block for the
  three injection toggles plus a `ConditionVariable` for the
  completion-wait gate. Sits behind `inj_io_error_state`.
- `ShmemCallbacks inj_io_shmem_callbacks` (`:81-85`) — request / init /
  attach callbacks; `_PG_init` calls `RegisterShmemCallbacks` only when
  `process_shared_preload_libraries_in_progress` (`:147-150`).
- `test_aio_shmem_init` (`:101`) attaches injection points
  `aio-process-completion-before-shared` (→ `inj_io_completion_hook`)
  and `aio-worker-after-reopen` (→ `inj_io_reopen`), and `Load`s them
  so they can fire from inside critical sections. Guarded by
  `#ifdef USE_INJECTION_POINTS` so a non-injection build silently
  skips.
- `test_aio_shmem_attach` (`:131`) re-`InjectionPointLoad`s the same
  points in each new backend so a worker can hit them during AIO
  completion.
- `inj_io_completion_hook` (`:1070`) and `inj_io_short_read_hook`
  (`:1092`) — the actual injection callback bodies; they consult
  `inj_io_error_state` flags and call `ConditionVariableSignal` to
  coordinate with SQL waiters.
- `read_buffers` (`:695`) — accepts a block-list array and runs the
  full StartReadBuffers / wait protocol, allowing tests to drive
  reordering, batching, and partial completion paths.
- `last_handle` (`:88`) — static pointer to the most recently obtained
  `PgAioHandle`; lets `handle_release_last` and
  `inj_io_completion_continue` operate without the caller juggling
  opaque ids.

## Invariants & gotchas

- TEST MODULE — explicitly NOT SAFE to enable in production
  `[from-comment]` `:7-9`. Exports internal AIO operations directly to
  SQL, including state corruption paths used to test error handling.
- Most functions require `USE_INJECTION_POINTS` to be effective; the
  injection-driven tests no-op (or behave normally) on a non-injection
  build.
- `_PG_init` must run during shared-memory request phase, so the module
  must be in `shared_preload_libraries`; loading via `LOAD` will miss
  the shmem-request callback and the injection-point preloads.
- The `last_handle` static is per-backend; mixing SQL functions that
  expect a fresh handle with ones that expect `last_handle` to still be
  valid within the same backend session is a common test-author trap.
- The injection-point hooks contribute irreversible global state once
  installed `[verified-by-code]` `:113-128`.

## Cross-refs

- `source/src/backend/storage/aio/` — AIO implementation tree.
- `source/src/include/storage/aio.h`,
  `source/src/include/storage/aio_internal.h` — public + internal API.
- `source/src/include/storage/read_stream.h` — read-stream API.
- `source/src/include/utils/injection_point.h` — injection-point API
  the test attaches into.
- `knowledge/files/src/test/modules/injection_points/injection_points.c.md`
  — the injection-points module this depends on.
