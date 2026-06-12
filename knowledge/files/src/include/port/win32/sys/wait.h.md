---
path: src/include/port/win32/sys/wait.h
anchor_sha: e18b0cb7344
loc: 3
depth: read
---

# sys/wait.h (win32)

## Purpose
POSIX `<sys/wait.h>` placeholder for Windows. Empty — Windows has no
`waitpid()`/`WIFEXITED`-style API. Backend reaping on Windows goes through
`WaitForSingleObject`/`GetExitCodeProcess` wrappers declared in `port.h` and
`win32_port.h`. File exists so `#include <sys/wait.h>` in portable code
compiles cleanly.

## Public symbols
None — placeholder.

## Internal landmarks
- Two-line file: comment only.

## Invariants & gotchas
- Don't use `WIFEXITED`/`WEXITSTATUS` macros on Windows builds — they're not defined here. PG's exit-code interpretation goes through `pgwin32_get_signal()` and `wait_result_to_str()` family in `port.h`.

## Cross-refs
- [[knowledge/files/src/include/port.h.md]]
- [[knowledge/files/src/include/port/win32_port.h.md]]
