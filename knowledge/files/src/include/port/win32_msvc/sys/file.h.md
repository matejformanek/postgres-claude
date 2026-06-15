---
path: src/include/port/win32_msvc/sys/file.h
anchor_sha: e18b0cb7344
loc: 1
depth: read
---

# src/include/port/win32_msvc/sys/file.h

## Purpose

Empty placeholder header. POSIX `<sys/file.h>` provides `flock()` and the
`LOCK_SH/LOCK_EX/LOCK_NB/LOCK_UN` constants for advisory file locking;
Windows has no equivalent (PG uses `LockFileEx` + the `pgwin32_open`
shim instead). This file exists purely so any backend translation unit
that says `#include <sys/file.h>` finds a header — the actual
file-locking calls go through `src/port/win32_pwrite.c`,
`src/backend/storage/file/fd.c`, and `pgwin32_open`. `[inferred]`

## Public symbols

None — file body is empty. `[verified-by-code]`

## Internal landmarks

One comment line: `/* src/include/port/win32_msvc/sys/file.h */`. No
guard, no declarations.

## Invariants & gotchas

- Active only on the Microsoft VC toolchain.
- Do not add `flock()` declarations here unless you also provide an
  implementation in `src/port/`. PG's locking on Windows is done with
  `LockFileEx` via wrappers, not POSIX `flock`.
- Do not delete: removal breaks any cross-platform file that includes
  `<sys/file.h>` unconditionally.

## Cross-refs

- `knowledge/subsystems/storage-fd.md` — where Windows file locking is
  actually wired up.
- `knowledge/subsystems/port-layer.md` — Windows portability strategy.
