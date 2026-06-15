---
path: src/port/win32env.c
anchor_sha: e18b0cb7344
loc: 170
depth: read
---

# src/port/win32env.c

## Purpose

Windows replacements for `putenv`/`setenv`/`unsetenv` —
`pgwin32_putenv`, `pgwin32_setenv`, `pgwin32_unsetenv`. The
non-obvious part: a Windows process can have **multiple CRT (C
runtime) instances loaded simultaneously**, each with its own private
environment cache. To make a variable visible to every loaded library,
this file iterates over all known CRT module names and calls each
one's `_putenv` separately, plus updates the process-wide environment
via `SetEnvironmentVariable`. `[from-comment]` `[verified-by-code]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `int pgwin32_putenv(const char *envval)` | `win32env.c:27` | `"NAME=value"` or `"NAME="` (to unset) |
| `int pgwin32_setenv(const char *name, const char *value, int overwrite)` | `win32env.c:121` | Builds `"name=value"` then calls `pgwin32_putenv` |
| `int pgwin32_unsetenv(const char *name)` | `win32env.c:150` | Builds `"name="` then calls `pgwin32_putenv` |

## Internal landmarks

- **Known CRT module names** (`win32env.c:32-52`) — exhaustive list
  from MSVCRT (VC6/MinGW) through every Visual Studio version up to
  UCRT (VS2015+). Each name and its debug variant (`...d`) are listed.
  Loop tries `GetModuleHandleEx` for each; if loaded, looks up
  `_putenv` via `GetProcAddress` and calls it.
- **Order of operations** (`win32env.c:55-117`):
  1. `SetEnvironmentVariable` first (`:81`) — affects child processes
     and CRTs that initialize *after* this call. Skipped when removing
     a variable (passing `NULL` value), because passing `NULL` here
     "crashes on at least certain versions of MinGW" (`:78-80`).
  2. Loop over CRT modules, calling each `_putenv` (`:96-110`).
  3. Final `_putenv` on our own CRT (`:117`) — redundant with step 2
     except in the rare case where PG itself is linked to a CRT not
     listed in the loop.
- `pgwin32_setenv` validates per POSIX: rejects `NULL` name, empty
  name, name containing `=` (`win32env.c:127-132`); short-circuits when
  variable exists and `overwrite==0` (`:135`).

## Invariants & gotchas

- **Address invalidation hazard** (`win32env.c:92-94`): function
  pointers obtained via `GetProcAddress` may become invalid the moment
  `FreeLibrary` is called. The loop is careful to re-acquire the
  pointer fresh each iteration and `FreeLibrary` immediately after
  use — never caching across iterations.
- **`envval` ownership semantics differ from POSIX `putenv`**
  (`:23-24`): POSIX requires the caller's string to remain valid
  forever (it becomes part of the environment). This wrapper internally
  `strdup`s for parsing — but the underlying `_putenv` calls per CRT
  still copy the string. Effect: callers can free `envval` after
  return without breaking the environment. This is *safer* than POSIX
  but means a caller relying on POSIX-strict "putenv reuses my buffer"
  semantics could be surprised in the other direction.
- The CRT-list is **best-effort**: if PG loads a CRT not in the table
  (some future MS toolchain), variables set after that CRT initialized
  may not be visible to it. The fallback `_putenv` at `:117` mitigates
  this for the *current* PG binary's CRT but not for third-party DLLs.
- `pgwin32_unsetenv` passes `"NAME="` to `_putenv` — this is the
  CRT-documented way to remove a variable, but does NOT call
  `SetEnvironmentVariable(name, NULL)` because of the MinGW crash
  noted in the source comment.

## Cross-refs

- `source/src/include/port.h` — macro indirection that routes
  `putenv`/`setenv`/`unsetenv` to these on Windows.
- `knowledge/files/src/port/win32setlocale.c.md` — sibling "Windows
  libc surprise" wrapper file.
