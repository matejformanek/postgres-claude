# `storage/ipc/signalfuncs.c`

- **Source:** `source/src/backend/storage/ipc/signalfuncs.c` (317 lines)
- **Header:** declared in `utils/fmgrprotos.h` (SQL-callable functions);
  no dedicated `.h`
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## Purpose

Thin SQL-callable wrappers around `kill(pid, signal)` for backend
cancel/terminate, plus `pg_reload_conf` and `pg_rotate_logfile`.
**The actual signal delivery uses raw `kill(2)` here — NOT
`SendProcSignal`** — because we just want to deliver SIGINT/SIGTERM,
not a procsignal-multiplexed reason.

## Privilege model — `pg_signal_backend` (`:51`)

Returns codes used to format an appropriate error message:
- `SIGNAL_BACKEND_SUCCESS = 0`
- `SIGNAL_BACKEND_ERROR = 1` — generic failure (already warned).
- `SIGNAL_BACKEND_NOPERMISSION = 2` — caller lacks privileges of
  target's role.
- `SIGNAL_BACKEND_NOSUPERUSER = 3` — target is owned by a superuser
  (or has no role), caller is not superuser.
- `SIGNAL_BACKEND_NOAUTOVAC = 4` — target is an autovac worker, caller
  lacks `pg_signal_autovacuum_worker`.

Lookup: `proc = BackendPidGetProc(pid)` (returns NULL for aux processes
and the postmaster — neither can be signaled via these functions).
`:54`.

Allowance matrix:
- Target's role unknown / superuser:
  - Target is `B_AUTOVAC_WORKER` ⇒ require `pg_signal_autovacuum_worker`.
  - Else require `superuser()`.
- Otherwise: caller must have privileges of target's role OR of
  `pg_signal_backend`.

## SQL functions

- **`pg_cancel_backend(pid)`** → SIGINT via `pg_signal_backend`.
- **`pg_terminate_backend(pid, timeout)`** → SIGTERM, then
  `pg_wait_until_termination(pid, timeout)` if timeout > 0.
  Polls with `kill(pid, 0)` + `WaitLatch(WL_LATCH_SET | WL_TIMEOUT |
  WL_EXIT_ON_PM_DEATH)` at 100 ms intervals.
- **`pg_reload_conf()`** → `kill(PostmasterPid, SIGHUP)` directly.
  Goes through *postmaster* (not the backends) — postmaster will
  re-read postgresql.conf and broadcast SIGHUP to children.
- **`pg_rotate_logfile()`** → `SendPostmasterSignal(PMSIGNAL_ROTATE_LOGFILE)`
  (so the logger is asked to rotate; not a `kill` directly).
  Requires `Logging_collector = on`.

## `kill(-pid, sig)` if `HAVE_SETSID`

`:113-116`. The negative pid signals the *process group*, not just
the backend. Postmaster calls `setsid()` so every backend is its own
group; this means the signal reaches any child processes the backend
might have forked (uncommon, but possible via extensions or
`COPY ... PROGRAM`).

## PID-recycling race

Comment at `:103-110`: "Can the process we just validated above end,
followed by the pid being recycled for a new process, before reaching
here? … That race condition possibility seems too unlikely to worry
about." On Linux with sequential PID allocation it's a non-issue; on
systems with randomized PID reuse (some BSDs, hardened distros), a
theoretical race exists.

## Cross-references

- `procarray.c::BackendPidGetProc` — pid → PGPROC lookup.
- `pmsignal.c::SendPostmasterSignal` — for `pg_rotate_logfile`.
- `pgstat`/SQL views use these for the typical "kill long-running
  query" admin workflow.

## Open questions

- Whether `pg_signal_backend` on a *parallel worker* (`B_BG_WORKER`
  with `bgw_type` set by parallel.c) gives the expected behavior.
  Reading the code, it does: the worker's PGPROC has the leader's
  roleId, so the privilege check accepts the same role. `[inferred]`.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
- [subsystems/storage-ipc.md](../../../../../subsystems/storage-ipc.md)
