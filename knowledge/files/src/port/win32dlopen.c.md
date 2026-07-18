---
path: src/port/win32dlopen.c
anchor_sha: e18b0cb7344
loc: 93
depth: read
---

# src/port/win32dlopen.c

## Purpose

Windows implementation of the POSIX dynamic-loader API — `dlopen`,
`dlsym`, `dlclose`, `dlerror` — built on top of `LoadLibrary` /
`GetProcAddress` / `FreeLibrary`. Used by the backend's extension
loader (`dfmgr.c`) so the same code path that does `_PG_init` lookup on
Linux/macOS works unchanged on Windows. `[verified-by-code]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `void *dlopen(const char *file, int mode)` | `win32dlopen.c:76` | `mode` is ignored; popup error dialogs suppressed |
| `void *dlsym(void *handle, const char *symbol)` | `win32dlopen.c:61` | `GetProcAddress` wrapper |
| `int dlclose(void *handle)` | `win32dlopen.c:49` | Returns `0` on success, `1` on error (matches POSIX) |
| `char *dlerror(void)` | `win32dlopen.c:40` | Returns `NULL` if no error; otherwise pointer to static buffer |

## Internal landmarks

- `static char last_dyn_error[512]` (`win32dlopen.c:18`) — single
  process-global error string. Cleared (first byte set to `\0`) on
  every successful call; populated by `set_dl_error` on failure.
- `set_dl_error` (`win32dlopen.c:20-37`) — calls `FormatMessage` with
  `LANG_ENGLISH` to fill the buffer; on `FormatMessage` failure itself,
  falls back to `"unknown error %lu"`. The English-only message is a
  deliberate simplification — PG's translation pipeline handles user-
  visible text elsewhere.
- `dlopen` (`win32dlopen.c:76-93`) — toggles `SetErrorMode` around
  `LoadLibrary` to suppress the modal "Could not find DLL" popup that
  Windows would otherwise display in interactive sessions. The previous
  mode is saved and restored.

## Invariants & gotchas

- **`dlerror` is not thread-safe.** The static `last_dyn_error[]`
  buffer is shared across all threads in the process. Backend
  extension loading happens in the postmaster's main thread so this is
  a non-issue there, but libpq-using applications calling `dlopen`
  from multiple threads can race.
- `dlerror` returns `NULL` (not empty string) when there's no error
  (`:42-45`) — POSIX-compliant.
- `dlclose` returns `1` (not negative) on failure (`:55`). POSIX
  specifies non-zero, so this is fine, but some Linux man-pages
  document -1 — don't compare strict-equal to -1.
- The `mode` argument to `dlopen` is **ignored** (no `RTLD_NOW`/`LAZY`
  distinction on Windows — `LoadLibrary` is always eager).
- Note that **`dlopen` is the only function here that clears
  `last_dyn_error` on success** (`:91`). Calling `dlerror` between a
  successful `dlopen` and any failing call still returns `NULL` as
  expected.
- `SetErrorMode` is process-wide (`:82`) — toggling it temporarily
  around `LoadLibrary` means a parallel `LoadLibrary` from another
  thread could see the suppressed mode. This is acceptable since PG
  extension loading is single-threaded on Windows.

## Cross-refs

- `source/src/backend/utils/fmgr/dfmgr.c` — primary consumer
  (extension loader).
- `knowledge/files/src/port/win32error.c.md` — sibling Win32→errno
  mapping; `set_dl_error` here uses `FormatMessage` directly rather
  than going through `_dosmaperr` because callers want the human
  string, not an errno code.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/port.md](../../../subsystems/port.md)
