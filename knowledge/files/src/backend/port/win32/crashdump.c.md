---
path: src/backend/port/win32/crashdump.c
anchor_sha: e18b0cb7344
loc: 168
depth: read
---

# src/backend/port/win32/crashdump.c

## Purpose

Installs a Win32 unhandled-exception filter that, on a crash, writes a
Windows MiniDump (`.mdmp`) file into `<DataDir>/crashdumps/`. The dump can
be opened later in WinDbg / Visual Studio against a matching PG build to
get a post-mortem stack trace. Originally contributed by Craig Ringer
(`crashdump.c:13`). Cross-platform analog is core-dump production via
SIGSEGV/SIGABRT on Unix; Windows defaults to silent termination unless a
filter is installed. `[from-comment]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `void pgwin32_install_crashdump_handler(void)` | `crashdump.c:164` | Wires `crashDumpHandler` into `SetUnhandledExceptionFilter` |

## Internal landmarks

- **`crashDumpHandler`** (`crashdump.c:76`) — the filter itself. Runs in
  crash context, so the comment at `:71-73` warns it must avoid PG
  helpers (palloc, ereport) and minimize memory use.
- **Opt-in via `crashdumps/` directory.** `GetFileAttributesA("crashdumps")`
  at `:82-84`: the handler does nothing unless the user creates a
  `crashdumps/` subdirectory under DataDir. This is the
  zero-configuration gate that keeps dumps off most installs.
- **Late-bound `MiniDumpWriteDump`.** Resolved at crash time via
  `LoadLibrary("dbghelp.dll")` + `GetProcAddress` (`:102-115`). If
  `dbghelp.dll` isn't on the path, the handler returns
  `EXCEPTION_CONTINUE_SEARCH` after a `write_stderr` and the OS runs the
  default abort.
- **Dump-type tiering** (`:123-131`) — base type is
  `MiniDumpNormal | MiniDumpWithHandleData | MiniDumpWithDataSegs`. If
  dbghelp.dll ≥ 5.2 (detected by presence of `EnumDirTree`), upgrade to
  `MiniDumpWithIndirectlyReferencedMemory | MiniDumpWithPrivateReadWriteMemory`
  for fatter, more-useful dumps.
- **Filename pattern** `crashdumps\postgres-pid<PID>-<ticks>.mdmp`
  (`:134-136`) — `GetTickCount` for uniqueness within a PID.

## Invariants & gotchas

- **Doesn't work in OOM / stack overflow.** Header comment `:16-22`:
  these scenarios prevent the handler from running. To fix would require
  a separate helper process or alternative stack — out of scope.
- **Always returns `EXCEPTION_CONTINUE_SEARCH`.** Even after a successful
  dump (`:159`). PG wants the normal CRT termination to also happen,
  producing the standard error dialog / log line.
- **No shutdown order issues.** Runs at exception time, not via
  `on_proc_exit` / `on_shmem_exit`. Even if PG cleanup hooks are broken
  by the crash, the dump still gets written.
- **Returns `FALSE`/`EXCEPTION_CONTINUE_SEARCH` quietly when
  `crashdumps/` is absent.** No warning is logged on startup or at
  crash; users without the directory get default OS behavior.
- **No equivalent on Unix.** Unix relies on the OS core-dump mechanism
  (`ulimit -c`, `/proc/sys/kernel/core_pattern`) — PG doesn't ship
  Unix-side crash-dump infrastructure.

## Cross-refs

- `knowledge/files/src/backend/port/win32/signal.c.md` — sister Win32
  infrastructure file. Installed by the same Win32-startup path.
- `knowledge/files/src/backend/main/main.c.md` — calls
  `pgwin32_install_crashdump_handler` early in backend init (Win32 only).
