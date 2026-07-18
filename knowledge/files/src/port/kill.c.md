---
path: src/port/kill.c
anchor_sha: e18b0cb7344
loc: 97
depth: read
---

# src/port/kill.c

## Purpose

Windows replacement for POSIX `kill(2)`: a function `pgkill(pid, sig)` that
sends a signal the backend can recognize. Windows has no real Unix-signal
model, so PG fakes it with a per-process named pipe (`\\.\pipe\pgsignal_%u`)
that each backend listens on; this file is the **sender** side. The
receiver side lives in `src/backend/port/win32/signal.c`. Special-case for
SIGKILL: skips the pipe and calls `TerminateProcess`. Gated by `#ifdef WIN32`.
`[verified-by-code]` `[from-comment]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `int pgkill(int pid, int sig)` | `kill.c:22` | Returns 0 on success, -1 with errno on failure |

## Internal landmarks

- Signal validation (`:30-40`) — rejects sig out of range, pid <= 0 (no
  process-group support).
- SIGKILL fast path (`:43-60`) — `OpenProcess(PROCESS_TERMINATE)` +
  `TerminateProcess(handle, 255)`. The exit code 255 is what the parent
  postmaster sees on `WaitForSingleObject`; it's the convention for
  "killed by signal" on Win32.
- Named-pipe send (`:61-71`) — `CallNamedPipe(pipename, &sigData, 1, &sigRet,
  1, &bytes, 1000)` writes one byte (the signal number), expects one byte
  back (echo of the signal), with a 1s timeout. The receiver in
  `signal.c` does `pg_queue_signal(sig)` from the pipe servicing thread.
- Error translation (`:73-93`) — Win32 errors mapped to POSIX errno:
  - `ERROR_BROKEN_PIPE` / `ERROR_BAD_PIPE` → return 0 (transient
    during process exit, treated like POSIX zombie process). `[from-comment]`
  - `ERROR_FILE_NOT_FOUND` → ESRCH (pipe is gone, process is gone)
  - `ERROR_ACCESS_DENIED` → EPERM
  - else → EINVAL.

## Invariants & gotchas

- **The receiver MUST have spun up a pipe servicing thread** before a
  signal can land. `pg_queue_signal` is called by that thread; before
  postmaster initialization completes the pipe doesn't exist, and
  `pgkill` returns ESRCH. This is fine for Unix-equivalent semantics
  because the analog there (signal handlers not yet installed) is similarly
  broken.
- **Echo-byte protocol is the integrity check.** If the byte echoed
  doesn't equal the byte sent (`:65`), we treat it as `ESRCH` rather
  than mysterious success. This handles a pipe-name collision (two
  unrelated processes with the same PID-derived pipe name).
- **No support for SIGKILL via the pipe.** SIGKILL has to be enforced by
  the kernel (TerminateProcess) because the target may be unresponsive;
  routing it through the pipe servicing thread would let a hung process
  ignore SIGKILL. `[from-comment]`
- **1s pipe timeout** (`:63`) — if the target backend is wedged servicing
  another signal, we wait up to 1 second before declaring it gone. Aligns
  with POSIX `kill()` semantics: nonblocking, fire-and-forget.

## Cross-refs

- `source/src/backend/port/win32/signal.c` — receiver side; defines
  `pg_queue_signal` and the pipe-servicing thread.
- `source/src/include/port/win32_port.h` — `pgkill` prototype, `PG_SIGNAL_COUNT`.
- `knowledge/files/src/port/pgstrsignal.c.md` — sibling signal-name shim
  used in log lines.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/port.md](../../../subsystems/port.md)
