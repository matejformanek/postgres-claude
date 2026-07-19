---
path: src/include/port/win32/sys/resource.h
anchor_sha: e18b0cb7344
loc: 20
depth: read
---

# sys/resource.h (win32)

## Purpose
Replacement for POSIX `<sys/resource.h>` on Windows. Declares the `rusage`
struct and `getrusage()` so portable code (e.g. log_min_duration_statement
timing, pgstat resource accounting) compiles. Only the user/system CPU time
fields are provided — Windows can't fill in the other POSIX rusage fields
(`ru_maxrss`, `ru_minflt`, etc.).

## Public symbols
| Symbol | Kind | File:line | Notes |
|---|---|---|---|
| `RUSAGE_SELF` | macro | `:9` | `0` — same value as Linux. |
| `RUSAGE_CHILDREN` | macro | `:10` | `(-1)` — same value as Linux. |
| `struct rusage` | type | `:12-16` | Only `ru_utime` and `ru_stime` populated. |
| `getrusage` | extern | `:18` | Implementation: `src/port/getrusage.c`. |

## Internal landmarks
- Header-guard `WIN32_SYS_RESOURCE_H` (`:4-5`, `:20`).
- Pulls in `<sys/time.h>` for `struct timeval` (`:7`).

## Invariants & gotchas
- The reduced `rusage` struct means any backend stat that reads `ru_maxrss` etc. is silently zero on Windows. Watch for "rss = 0 on win32" surprises in monitoring tools.
- `getrusage` for `RUSAGE_CHILDREN` on Windows returns the postmaster's children CPU time accumulated via `GetProcessTimes`; not all process-exit events flush correctly, see `src/port/getrusage.c` for the gotchas.

## Cross-refs
- [[knowledge/files/src/include/port/win32_port.h.md]]
- [[knowledge/files/src/include/port.h.md]]

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/port.md](../../../../../../subsystems/port.md)
