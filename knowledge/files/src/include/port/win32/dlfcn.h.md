---
path: src/include/port/win32/dlfcn.h
anchor_sha: e18b0cb7344
loc: 1
depth: read
---

# dlfcn.h (win32)

## Purpose
POSIX `<dlfcn.h>` placeholder for the Windows port. Empty file (just the
upstream `src/include/port/win32/dlfcn.h` comment) — exists so `#include
<dlfcn.h>` in portable code resolves cleanly during a Windows build with this
directory on the include path; actual `dlopen`/`dlsym` shims live in
`src/port/dlopen.c` and are declared by `port.h`.

## Public symbols
None — header is a placeholder.

## Internal landmarks
- One line: `/* src/include/port/win32/dlfcn.h */`.

## Invariants & gotchas
- The win32 include directory is added to the search path by the build only on Windows builds — POSIX builds don't see this file.
- The actual replacement API (`dlopen`, `dlsym`, `dlclose`, `dlerror`) is declared elsewhere (port.h / dlfcn.h itself doesn't redeclare them) because backend internals primarily call `pkglib_load_file` / `LookupExternalFunction`, not raw `dl*`.

## Cross-refs
- [[knowledge/files/src/include/port.h.md]] — the umbrella.
- [[knowledge/files/src/include/port/win32_port.h.md]] — main Windows shim.
