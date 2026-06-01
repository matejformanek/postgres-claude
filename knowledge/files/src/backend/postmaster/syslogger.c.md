# syslogger.c

- **Source:** `source/src/backend/postmaster/syslogger.c` (1599 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** skim (top comment + key entry points)

## Purpose

Captures all stderr output from postmaster + every child by redirecting
the inherited stderr fd to a pipe whose read end the syslogger owns. Writes
captured chunks to logfiles, rotating by size/age as configured. Added in
PG 8.0. [from-comment] `:5-12`

## Special-case: NOT attached to shared memory

The syslogger is the **only** aux process that does not attach to shared
memory. In `proctypelist.h:46`: `B_LOGGER` has `shmem_attach = false`.
This means it has no `PGPROC` slot, holds no lwlocks, and survives a
crash-restart cycle (postmaster keeps it across resets so logs aren't
lost). [verified-by-code] `proctypelist.h:46`, `miscadmin.h:376-379`,
`launch_backend.c:238` (`ClosePostmasterPorts(child_type == B_LOGGER)`
keeps the syslogger pipe open in postmaster).

## Pipe protocol

Chunks come down the pipe in `PIPE_CHUNK_SIZE` units with a header so the
syslogger can reassemble multi-process interleaved writes. Read buffer is
sized to twice a chunk so a partial trailing chunk can be moved forward.
[from-comment] `:57-61`

## Rotation

- Size: `Log_RotationSize` (KB).
- Age: `Log_RotationAge` (minutes; default 1440 = 1 day).
- Manual: presence of file `$PGDATA/logrotate` triggers rotation. `:64`

## Lifecycle

- `main_fn = SysLoggerMain`.
- Started via `StartSysLogger` (`postmaster.c:4056`) only if
  `logging_collector=on`.
- Postmaster respawns it on crash; pipe fd persists.
- Header: `postmaster/syslogger.h`.

## GUC visibility

`Logging_collector` cannot be changed after postmaster start; others are
SIGHUP-reloadable. [from-comment] `:67-70`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
