# fork_process.c

- **Source:** `source/src/backend/postmaster/fork_process.c` (128 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read (entire file)

## Purpose

Thin wrapper around POSIX `fork()` used everywhere postmaster needs to spawn
a child. Unix only — EXEC_BACKEND has its own path in `launch_backend.c`.
[from-comment] `:1-11`

## What it actually does

1. `fflush(NULL)` to avoid duplicated stdio output across the fork. `:46`
2. Saves and restores `LINUX_PROFILE` itimer (so child profiling works). `:48-56`
3. **Blocks all signals before fork** so child can install its own handlers
   before unblocking — prevents races where the child runs the postmaster's
   handler and drops a control signal. `:59-66`
4. In child: `MyProcPid = getpid()`, optionally writes
   `$PG_OOM_ADJUST_VALUE` to `$PG_OOM_ADJUST_FILE` so the Linux OOM-killer
   targets children rather than postmaster, and re-seeds `pg_strong_random`.
   `:67-118`
5. In parent: restores prior signal mask. `:119-123`

## Notes

- This file is `#ifndef WIN32` only. [from-comment] `:25`
- Header: `postmaster/fork_process.h`.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
