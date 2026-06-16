# `src/backend/main/main.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~520
- **Source:** `source/src/backend/main/main.c`

The stub `main()` for the `postgres` executable. Every Postgres
server process — postmaster, standalone backend, bootstrap process,
single-user mode, and Windows EXEC_BACKEND children — starts here.
The job of this file is essential-subsystem init (locale, memory,
stack base, ps display) and then dispatching to the right
`FooMain()` based on argv. [verified-by-code §main.c:1-21]

The dispatch table is a small enum (`DispatchOption`) and a parallel
string array (`DispatchOptionNames`) wired together by
`parse_dispatch_option`. Names: `check`, `boot`, `forkchild`,
`describe-config`, `single`, with the implicit default
`DISPATCH_POSTMASTER` (no name). `DISPATCH_FORKCHILD` is only
reachable in `EXEC_BACKEND` builds (Windows; was also used for
historic EXEC_BACKEND testing on Unix). [verified-by-code §main.c:47-59, 243-270]

## API / entry points

- `int main(int argc, char *argv[])` — the entry point. Order of
  operations:
  1. `pgwin32_install_crashdump_handler()` on Windows.
  2. `progname = get_progname(argv[0])`.
  3. `startup_hacks(progname)` — Windows-only WSA startup, abort
     behaviour, error mode, CRT redirect.
  4. `save_ps_display_args(argc, argv)` — copies argv into a safe
     location so `set_ps_display` can rewrite it on platforms that
     need it.
  5. `MyProcPid = getpid(); MemoryContextInit();` — earliest point at
     which `elog`/`ereport` is allowed.
  6. `set_stack_base()` — reference for stack-depth checks.
  7. `set_pglocale_pgservice` + a fixed sequence of
     `init_locale(...)` calls forcing `LC_COLLATE/LC_MONETARY/
     LC_NUMERIC/LC_TIME` to `C` and absorbing the environment for
     `LC_CTYPE` and `LC_MESSAGES`.
  8. `unsetenv("LC_ALL")` so per-category `pg_perm_setlocale` calls
     win.
  9. Handle `--help`, `--version`, `--describe-config`, `-C var`.
  10. `check_root(progname)` (skipped for the read-only describe/-C
      cases).
  11. Parse leading `--<word>` into a `DispatchOption` and
      dispatch:
      - `DISPATCH_CHECK` / `DISPATCH_BOOT` → `BootstrapModeMain`
      - `DISPATCH_FORKCHILD` → `SubPostmasterMain` (Windows /
        EXEC_BACKEND)
      - `DISPATCH_DESCRIBE_CONFIG` → `GucInfoMain`
      - `DISPATCH_SINGLE` → `PostgresSingleUserMain`
      - default → `PostmasterMain`
  12. `abort()` if any of the above returns (none should).
  [verified-by-code §main.c:70-237]
- `DispatchOption parse_dispatch_option(const char *name)` — matches
  against `DispatchOptionNames`; `forkchild` uses prefix matching
  because it takes an argument; returns `DISPATCH_POSTMASTER` for
  no match. [verified-by-code §main.c:243-270]
- `__ubsan_default_options(void)` — weak symbol the sanitizer library
  picks up. Returns `getenv("UBSAN_OPTIONS")` only after
  `reached_main = true` — guards against re-entrancy when libsanitizer
  initialises before libc. The function is built without sanitizer
  instrumentation. [from-comment §main.c:486-520]

## Notable invariants / details

- **`reached_main` flag** is set on the first line of `main()` and
  consulted by `__ubsan_default_options` to know whether libc/getenv
  is safe to call. Without it, sanitizer init can recurse into
  itself. [verified-by-code §main.c:44-46, 76, 515-518]
- **Locale invariants:** `LC_COLLATE` is forced to `C` in the
  postmaster — per-database collation is applied later in
  `InitPostgres`. `LC_CTYPE` is taken from environment because the
  postmaster can't switch per-DB. `LC_MONETARY/NUMERIC/TIME` are
  always `C`. The comment in `pg_locale.c` is the canonical
  reference. [from-comment §main.c:127-152]
- **Root check has carve-outs:** `--describe-config` and `-C VAR`
  bypass `check_root` because they're read-only and pg_ctl on Windows
  invokes them while still holding administrator privileges. The
  carve-out only applies when these options appear FIRST in argv —
  the comment warns about misinterpreting a different mode's `-C`.
  [from-comment §main.c:178-192]
- **`getuid()/geteuid()` symmetry** is enforced on non-Windows so
  setuid-postgres can't escalate. The comment notes "nobody actually
  uses postgres as a setuid program", but the check is cheap.
  [from-comment §main.c:459-465]
- **`startup_hacks` is Unix-no-op** — Windows-only Winsock/CRT
  configuration. The XXX comment "code here is proof that the
  platform in question is too brain-dead" has been there since
  Windows support landed. [from-comment §main.c:272-282]

## Potential issues

- **File-line `main.c:113-114`.** Order matters: `MyProcPid = getpid()`
  must precede `MemoryContextInit()` because the latter's diagnostics
  (in failure paths) want `MyProcPid`. Not documented inline.
  [ISSUE-undocumented-invariant: MyProcPid before MemoryContextInit (nit)]
- **File-line `main.c:279-282`.** Long-standing `XXX` comment about
  `startup_hacks` — Windows-specific cleanups. Not actionable
  upstream. [ISSUE-stale-todo: avoid adding more platform hacks here (nit)]
- **File-line `main.c:383-385`.** `XXX` about non-ASCII help output
  on Windows console code pages. [ISSUE-stale-todo: Windows console codepage limitation (nit)]
- **File-line `main.c:189-191`.** The `-C` carve-out is positional
  (must be argv[1]). A user who runs `postgres -D /path -C foo` as
  root gets a confusing rejection. The error message doesn't hint
  that placement matters. [ISSUE-style: -C carve-out is silently positional (nit)]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `main`](../../../../issues/main.md)
<!-- issues:auto:end -->
