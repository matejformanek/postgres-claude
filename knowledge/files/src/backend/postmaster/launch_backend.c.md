# launch_backend.c

- **Source:** `source/src/backend/postmaster/launch_backend.c` (1045 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** deep-read (top comment, dispatch table, fork+EXEC_BACKEND path)

## Purpose

Single abstraction over the two child-launch mechanisms — plain `fork()` on
Unix vs. `fork()+exec()` on Windows / `EXEC_BACKEND`. Holds the
`child_process_kinds[]` table that maps each `BackendType` to its
`main_fn` and `shmem_attach` flag. [from-comment] `:1-21`

## Mental model

- One entry per `BackendType`, generated from `postmaster/proctypelist.h`
  via the `PG_PROCTYPE` macro. `:179-184`
- After fork, child runs `MyBackendType = child_type`, closes inherited
  postmaster fds (`ClosePostmasterPorts`), calls `InitPostmasterChild`,
  optionally `dsm_detach_all() + PGSharedMemoryDetach()` if its kind has
  `shmem_attach = false` (only `B_LOGGER`, `B_INVALID`, datachecksums launcher).
  `:237-248`
- Child then enters its main function with `TopMemoryContext` current.
  Startup data lives in `PostmasterContext` which the main function deletes
  after consuming. `:250-256`
- On EXEC_BACKEND, `internal_forkexec` writes `BackendParameters` to a temp
  file the child re-reads in `SubPostmasterMain`. `:284-340`

## Key entry points

| Line | Symbol | Role |
|---|---|---|
| 179 | `child_process_kinds[]` | dispatch table populated from `proctypelist.h` |
| 187 | `PostmasterChildName` | name lookup |
| 204 | `postmaster_child_launch` | THE fork dispatcher — called from `BackendStartup`, `StartChildProcess`, `StartAutovacuumWorker`, `StartBackgroundWorker` |
| 284 | `internal_forkexec` (EXEC_BACKEND) | serialize backend vars, fork+exec |
| 700+ | `SubPostmasterMain` (EXEC_BACKEND) | child re-attach path |

## Control flow

`postmaster_child_launch(child_type, child_slot, startup_data, …, client_sock)` →
- Non-EXEC_BACKEND: `fork_process()` → child sets `MyBackendType`, closes
  postmaster sockets, `InitPostmasterChild`, optional shmem detach, then
  `child_process_kinds[child_type].main_fn(...)`. Parent returns child pid.
  `:217-272`
- EXEC_BACKEND: `internal_forkexec` returns parent-side pid; child execs
  the postgres binary, lands in `SubPostmasterMain`, restores state.

## Interactions

- Called by: `postmaster.c::BackendStartup` (per connection),
  `::StartChildProcess` (aux singletons), `::StartAutovacuumWorker`,
  `::StartBackgroundWorker`.
- `proctypelist.h` (header) is the canonical registry of what types exist.
