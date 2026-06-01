# `storage/ipc/ipc.c`

- **Source:** `source/src/backend/storage/ipc/ipc.c` (446 lines)
- **Header:** `source/src/include/storage/ipc.h`
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** deep-read

## Purpose

Despite the filename, this file no longer has anything to do with IPC.
It is the exit-time-cleanup machinery: `proc_exit` / `shmem_exit` and
the three callback registries (`on_proc_exit`, `on_shmem_exit`,
`before_shmem_exit`). [from-comment] `ipc.c:6-9`

## The three callback lists (LIFO each)

- **`on_proc_exit`** — last fence; runs *after* `shmem_exit` is done.
  Used for things that don't need shared memory.
- **`on_shmem_exit`** — low-level shared-memory releases (PGPROC slot,
  lock partition entries, etc.). Runs *after* `before_shmem_exit`.
- **`before_shmem_exit`** — user-level cleanup that still needs the
  full system (e.g. transaction abort, temp-relation drop with catalog
  access). [from-comment] `ipc.c:240-246`.

Each list is a fixed-size array (`MAX_ON_EXITS = 20`, `ipc.c:72`).
A `FATAL` is raised if you try to register more. `[verified-by-code]`.

## Exit sequence

`proc_exit(code)` → `proc_exit_prepare`:

1. Set `proc_exit_inprogress = true`; this changes `ereport()` behavior
   so an `ERROR` in a callback re-enters here instead of going back to
   the main loop. `[from-comment] :37-40, :169-172`.
2. Clear `InterruptPending`, `ProcDiePending`, `QueryCancelPending`;
   set `InterruptHoldoffCount = 1`, `CritSectionCount = 0`. `:179-183`.
3. Clear `error_context_stack` and `debug_query_string`. `:194-196`.
4. Call `shmem_exit(code)`:
   - `LWLockReleaseAll()` first, so callbacks can re-acquire and can
     touch DSM-detached memory safely. `:233-238`.
   - Run `before_shmem_exit_list` LIFO.
   - Call `dsm_backend_shutdown()` directly (not registered, to keep
     it on equal footing — if a DSM callback errors, the rest still
     run). `:254-269`.
   - Run `on_shmem_exit_list` LIFO.
5. Run `on_proc_exit_list` LIFO.
6. `exit(code)`.

Each callback is **decremented from the list before being invoked**, so
re-entry via `ereport(ERROR)` cannot create an infinite loop.
`[from-comment] :204-211`.

## Atexit backstop

The first registration in any of the three lists also calls
`atexit(atexit_callback)` once (`atexit_callback_setup`). If something
calls `exit()` directly bypassing `proc_exit`, the atexit handler
calls `proc_exit_prepare(-1)` anyway. `[verified-by-code] :300-306`.
`_exit()` (no underscore-less variant) bypasses even that — the
postmaster's dead-man switch (`pmsignal.c`) treats it as a crash.
`[from-comment] :294-298`.

## `cancel_before_shmem_exit`

Strict LIFO — caller must remove the exact entry it pushed last, else
`elog(ERROR)`. `[verified-by-code] :400-411`. Used for transient
push/pop patterns (e.g. inside `PG_TRY` blocks that want a cleanup
hook for the duration of a section).

## `on_exit_reset`

Called immediately after `fork()` in a child to drop the parent's
callback lists (the child must not run the parent's cleanups). Also
calls `reset_on_dsm_detach()`. `[verified-by-code] :421-429`.

## `check_on_shmem_exit_lists_are_empty`

Debug check that no shmem-exit callbacks were registered prematurely
(before InitPostgres / shared-memory attach). Used in startup paths.
`[verified-by-code] :438-446`.

## Globals exported

- `proc_exit_inprogress` — read by `ereport` to decide whether an error
  should longjmp back to the main loop or just fall through.
- `shmem_exit_inprogress` — set during `shmem_exit`, useful for
  callbacks that need to know "we're tearing down shmem".

## Cross-references

- Callers: every subsystem that needs cleanup. `proc.c::ProcKill`,
  `procsignal.c::CleanupProcSignalState`, `sinvaladt.c::CleanupInvalidationState`,
  `bufmgr.c`, `xact.c`, etc.
- `dsm.c::dsm_backend_shutdown` — explicitly called from `shmem_exit`
  rather than registered, see comment above.

## Open questions

None — this file is small and self-contained.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/storage-ipc.md](../../../../../subsystems/storage-ipc.md)
