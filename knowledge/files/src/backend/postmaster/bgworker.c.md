# bgworker.c

- **Source:** `source/src/backend/postmaster/bgworker.c` (1465 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read (top comment + entry-point survey; canonical doc is the
  bgworker skill agent)

## Purpose

Implements PostgreSQL's pluggable background-worker subsystem: registration
(static via `RegisterBackgroundWorker` in `_PG_init`; dynamic via
`RegisterDynamicBackgroundWorker`), shared-memory slot accounting, startup,
crash-restart, and lifecycle queries for the launcher (parallel-query
leaders, logical replication, extensions). [from-comment] `:1-10`

## Canonical doc

The bgworker skill agent already produced the in-depth write-up. This file
note is intentionally a stub to avoid duplication. Cross-reference:
`.claude/skills/<bgworker-skill>` (canonical) and the API at
`src/include/postmaster/bgworker.h`.

## Key invariants (worth surfacing here because they're load-bearing for
the postmaster's no-shmem-lock rule)

- Postmaster reads `BackgroundWorkerSlot::in_use` without locks; backends
  initializing a slot must do a **write memory barrier** before flipping
  `in_use = true`. Once `in_use`, the slot belongs to postmaster until the
  worker exits and the slot is released. [from-comment] `:47-78`
- Backends coordinate among themselves via `BackgroundWorkerLock`
  (exclusive to mutate, shared to read).
- The `terminate` flag is the one exception: a backend may flip it on an
  in-use slot to tell postmaster not to restart.

## Key entry points

| Line | Symbol | Role |
|---|---|---|
| 180 | `BackgroundWorkerShmemRequest` | reserve shmem for the slot array |
| 198 | `BackgroundWorkerShmemInit` | init the array |
| 272 | `BackgroundWorkerStateChange` | postmaster-side scan of slots after backend posted a state change |
| 658 | `SanityCheckBackgroundWorker` | validate the `BackgroundWorker` struct supplied by extensions |
| 741 | `BackgroundWorkerMain` | the `main_fn` for `B_BG_WORKER`; resolves library + function, calls into the user's worker function |
| 875 / 909 | `BackgroundWorkerInitializeConnection[ByOid]` | the worker-side helper that calls `InitPostgres` |
| 962 | `RegisterBackgroundWorker` | static (shared_preload_libraries) registration |
| 1068 | `RegisterDynamicBackgroundWorker` | dynamic registration via shmem slot |
| 1180 | `GetBackgroundWorkerPid` | poll worker state |
| 1235 | `WaitForBackgroundWorkerStartup` | block until started or failed |
| 1280 | `WaitForBackgroundWorkerShutdown` | block until exited |
| 1319 | `TerminateBackgroundWorker` | set the terminate flag |

## Headers

- `postmaster/bgworker.h` — public API for extensions.
- `postmaster/bgworker_internals.h` — `BackgroundWorkerSlot`,
  `RegisteredBgWorker`, internal helpers.

## Synthesized by
<!-- backlinks:auto -->
- [idioms/bgworker-and-parallel.md](../../../../idioms/bgworker-and-parallel.md)
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
