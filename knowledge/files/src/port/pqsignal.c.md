---
path: src/port/pqsignal.c
anchor_sha: 4abf411e2328
loc: 220
depth: read
---

# src/port/pqsignal.c

## Purpose

The PG-wide reliable `signal()` wrapper. Installs a signal handler with
explicit `sa_flags = SA_RESTART` via `sigaction(2)`, bypassing the
implementation-defined behavior of plain `signal()` (where the C and
POSIX standards leave both handler-reset-on-entry and signal-blocking
unspecified). Every backend and frontend signal handler in the tree
goes through this wrapper. `[from-comment]` `[verified-by-code]`

The header comment at `pqsignal.c:14-42` is authoritative: classic SVR4
"unreliable signals" + Windows quirks + POSIX-advice rationale.

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `void pqsignal(int signo, pqsigfunc func)` | `pqsignal.c:156` | Actual name is `pqsignal_be` (backend) or `pqsignal_fe` (frontend) — selected by `-DFRONTEND` to avoid clashing with libpq's legacy `pqsignal` |
| `pqsigfunc` (typedef in `port/pg_pthread.h`/`libpq/pqsignal.h`) | — | Callback: `void (*)(int signo, pg_signal_info *info)` |

## Internal landmarks

- **PG_NSIG ceiling** (`pqsignal.c:58-64`): array size for
  `pqsignal_handlers[]`. Prefers `PG_SIGNAL_COUNT` (Windows), then
  `NSIG` (Unix), falls back to a hard-coded 64. `StaticAssertDecl`s at
  `:75-78` verify `SIGUSR2/SIGHUP/SIGTERM/SIGALRM` all fit.
- **Indirection through `wrapper_handler`** (`pqsignal.c:94-146`): all
  non-`SIG_IGN`/`SIG_DFL` handlers go through this wrapper. The wrapper:
  1. saves `errno` (signals can interrupt at any point — restoring
     `errno` is mandatory; `:101`).
  2. backend-only: asserts `MyProcPid` is set, and bails out if
     `MyProcPid != getpid()` — i.e. we're inside a `system(3)` child
     that has inherited the parent's handlers (`:113-121`). The
     bailout reinstalls `SIG_DFL` and re-raises, so a fork-exec'd grep
     doesn't accidentally muck with shared memory.
  3. populates `pg_signal_info` from `siginfo_t` (`pid`, `uid`) when
     `HAVE_SA_SIGINFO` is set (`:124-132`); otherwise zeros them
     (`:133-141`).
  4. calls the user handler with the platform-independent `pg_info`.
  5. restores `errno` (`:145`).
- **USE_SIGACTION** (`pqsignal.c:66-68`): every platform except
  `FRONTEND && WIN32` uses `sigaction` with `SA_RESTART`. Frontend on
  Windows uses native `signal()`.
- **SIGCHLD gets SA_NOCLDSTOP** when supported (`:198-201`) — we don't
  want stopped-child notifications, only exits.
- The static `pqsignal_handlers[]` table is `volatile pqsigfunc[]`
  (`:80`) so the compiler doesn't reorder stores around the
  `sigaction` call.

## Invariants & gotchas

- **Use `pqsignal`, not `signal`, in PG code.** Direct `signal(2)`
  calls give SVR4-unreliable semantics on a few corners.
- The wrapper means `SIG_IGN` and `SIG_DFL` callers go straight to the
  OS — only "real" handlers get indirected. `:170-173` carefully
  records the handler *before* installing, so a signal that arrives
  mid-install still finds the new handler in the table.
- The "MyProcPid != getpid()" check (`:116`) is the **fork-after-handler
  safety net**. Without it, a `system("pg_dump")` child would still
  have PG handlers installed but would lack the connection state
  those handlers expect — and a signal arrival could corrupt PG's
  shared-memory invariants from a process that has no business
  touching them.
- Windows frontend path (`:204-219`) uses `signal(2)` directly. The
  header warns this gives SA_RESETHAND-like behavior for everything
  except `SIGFPE`, signals don't interrupt system calls, and `SIGINT`
  handlers run on a different thread. Frontend code that wants
  cross-platform behavior should structure itself accordingly.
- `Assert(false)` on `sigaction` failure (`:203`) — a `sigaction`
  failure for a valid `signo` indicates a coding error (bad flags or
  unknown signal). Production builds silently drop the install.

## Cross-refs

- `source/src/backend/port/win32/signal.c` — `pqsigaction()` does the
  actual Windows backend signal emulation that this file's wrapper
  expects.
- `knowledge/subsystems/` — backend signal flow (postmaster reaper,
  CHECK_FOR_INTERRUPTS) consumes handlers installed through this
  function.
- `source/src/include/libpq/pqsignal.h` — `pqsigfunc` typedef and
  `pg_signal_info` struct.
