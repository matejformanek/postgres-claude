# `storage/ipc.h`

- **Source:** `source/src/include/storage/ipc.h` (88 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** full-read

Public API for `ipc.c` (exit cleanup) and `ipci.c` (shmem init).

> "This file is misnamed, as it no longer has much of anything
> directly to do with IPC. The functionality here is concerned with
> managing exit-time cleanup." `:6-8`.

## `PG_ENSURE_ERROR_CLEANUP` macro

```c
PG_ENSURE_ERROR_CLEANUP(cleanup_function, arg)
{
    ... code that might throw ereport(ERROR) or ereport(FATAL) ...
}
PG_END_ENSURE_ERROR_CLEANUP(cleanup_function, arg);
```

Expansion: registers `cleanup_function` via `before_shmem_exit`,
wraps the body in `PG_TRY`. On `PG_CATCH`, calls
`cancel_before_shmem_exit` AND runs `cleanup_function(0, arg)`
manually, then `PG_RE_THROW`. On normal exit, just
`cancel_before_shmem_exit`.

The cleanup function will run on **either** ERROR/FATAL exit. It will
**not** run on successful exit unless the caller explicitly invokes it
after the block. **Macro args are multiply evaluated** — avoid
side effects.

## Functions

### From `ipc.c`

- `proc_exit(code)` — `pg_noreturn`. The only proper way to exit a
  backend process.
- `shmem_exit(code)` — run shmem-related cleanup but don't exit.
  Used by postmaster on crash-restart.
- `on_proc_exit` / `on_shmem_exit` / `before_shmem_exit` — register
  callbacks. Run LIFO in reverse registration order, each removed
  from its list before being invoked (re-entry safe).
- `cancel_before_shmem_exit` — strict-LIFO removal of the last
  before-shmem-exit callback.
- `on_exit_reset` — drop all callbacks (called after fork).
- `check_on_shmem_exit_lists_are_empty` — debug check.

### From `ipci.c`

- `shmem_startup_hook` — extension hook called at end of shmem init.
- `RegisterBuiltinShmemCallbacks` — walks `subsystemlist.h`.
- `CalculateShmemSize` — sum of all requested shmem.
- `CreateSharedMemoryAndSemaphores` — top-level init (postmaster).
- `AttachSharedMemoryStructs` — EXEC_BACKEND child init.
- `InitializeShmemGUCs` — set runtime-computed GUCs.

## Globals

- `proc_exit_inprogress` — true during `proc_exit`; `ereport` checks
  this to decide whether to long-jump back to the main loop.
- `shmem_exit_inprogress` — true during `shmem_exit` body.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/storage-ipc.md](../../../../subsystems/storage-ipc.md)
