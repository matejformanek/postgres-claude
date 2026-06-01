# autovacuum.c

- **Source:** `source/src/backend/postmaster/autovacuum.c` (3706 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read (top comment + entry-point survey)

## Purpose

Implements the autovacuum daemon as two process roles: the **launcher** (one
per cluster, always-running when `autovacuum=on`) and **workers** (up to
`autovacuum_max_workers`, postmaster-spawned, one-shot per scheduling
decision). [from-comment] `:5-13`

## Architecture (the load-bearing detail)

- **The launcher cannot fork workers itself.** Workers are forked by the
  postmaster. Reason: the launcher is attached to shmem and therefore is not
  as robust as postmaster. Workflow: launcher writes target DB into an
  autovacuum shmem area, raises `PMSIGNAL_START_AUTOVAC_WORKER`, postmaster
  forks the worker, which then reads the shmem entry to find out what to do.
  [from-comment] `:15-27`
- If fork fails, postmaster sets a flag, signals the launcher; launcher
  retries. Permanent failures (e.g. DB gone) are detected by the worker
  itself and handled by clean exit. [from-comment] `:29-36`
- Worker → launcher signal: `SIGUSR2` when worker is done, so launcher can
  re-balance cost-delay across remaining workers and possibly start another.
  [from-comment] `:38-42`
- Multiple workers per DB allowed; collision avoidance via shmem
  per-table list, with a small window vulnerability noted in the comment.
  [from-comment] `:44-52`

## Key entry points

| Line | Symbol | Role |
|---|---|---|
| 413 | `AutoVacLauncherMain` | launcher main loop (`main_fn` for `B_AUTOVAC_LAUNCHER`) |
| 791 | `ProcessAutoVacLauncherInterrupts` | drain SIGHUP / shutdown |
| 1138 | `do_start_worker` | decide which DB next, write shmem entry, signal postmaster |
| 1350 | `launch_worker` | wrapper |
| 1402 | `AutoVacWorkerFailed` | launcher-side flag set when postmaster's fork failed |
| 1424 | `AutoVacWorkerMain` | worker main (`main_fn` for `B_AUTOVAC_WORKER`); connects to DB, calls `do_autovacuum` |
| 1926 | `do_autovacuum` | actual table-scan + VACUUM/ANALYZE dispatch |
| 3530 | `AutoVacuumShmemRequest` / 3553 `AutoVacuumShmemInit` | shmem allocation |
| 3459 | `AutoVacuumingActive` | helper for callers checking the GUC |

## Signals on the launcher

`avl_sigusr2_handler` (`:1409`) — workers signal here when done.

## Shared memory

- `AutoVacuumShmem` struct (see `:3530-3580`) holds the worker-coordination
  flags, the "next worker target DB", and the wakeup flag.
- Workers' currently-vacuuming table id is published to a per-worker shmem
  slot so peers can skip it.

## Interactions

- Postmaster: receives `PMSIGNAL_START_AUTOVAC_WORKER`, calls
  `StartAutovacuumWorker` (`postmaster.c:4081`) which forks via
  `postmaster_child_launch(B_AUTOVAC_WORKER, ...)`.
- Stats: reads `pg_stat_*` tables to decide what to vacuum.
- Header: `postmaster/autovacuum.h`.
