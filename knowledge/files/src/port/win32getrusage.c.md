---
path: src/port/win32getrusage.c
anchor_sha: e18b0cb7344
loc: 61
depth: read
---

# src/port/win32getrusage.c

## Purpose

Windows implementation of `getrusage(int who, struct rusage *)`. Maps
to `GetProcessTimes()`, which returns kernel and user CPU times for
the current process. Only `RUSAGE_SELF` is supported — Windows has no
equivalent of `RUSAGE_CHILDREN`. `[verified-by-code]`

PG calls `getrusage` in `EXPLAIN (BUFFERS, COSTS, ...)`,
`log_executor_stats`, and various trace points. On Windows, those
features get accurate kernel/user CPU breakdown via this shim — but
nothing else (no `ru_maxrss`, no `ru_inblock`, no fault counts).

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `int getrusage(int who, struct rusage *rusage)` | `win32getrusage.c:21` | Only `RUSAGE_SELF`; sets `EINVAL` otherwise |

## Internal landmarks

- Argument validation: `who != RUSAGE_SELF` → `errno=EINVAL`
  (`:29-34`); `rusage == NULL` → `errno=EFAULT` (`:36-40`).
- `memset(rusage, 0, sizeof(struct rusage))` (`:41`) — zeros the
  output struct before populating, so unsupported fields (e.g.
  `ru_maxrss`, `ru_majflt`) read as 0.
- `GetProcessTimes(GetCurrentProcess(), &starttime, &exittime,
  &kerneltime, &usertime)` (`:42-43`) — `starttime` and `exittime`
  are returned but ignored.
- **FILETIME → timeval conversion** (`:50-58`): `FILETIME` is 100-ns
  units. Divide by 10 → microseconds. Then `tv_sec = us / 1000000`,
  `tv_usec = us % 1000000`. The kernel/user split goes into
  `ru_stime`/`ru_utime` respectively.

## Invariants & gotchas

- **Only CPU times are populated.** All other `struct rusage` fields
  remain zero. Callers reading `ru_maxrss` or `ru_inblock` on Windows
  always see 0, not "unsupported error".
- The PG-tree `struct rusage` definition lives in
  `src/include/port/win32.h` — it's a minimal POSIX-compatible struct
  with the standard timeval + counter fields. Note this is **not** the
  same as MSVC CRT's `rusage` (CRT doesn't ship one).
- `GetProcessTimes` failure → `_dosmaperr(GetLastError())` (`:45-46`).
- A `RUSAGE_CHILDREN` request returns `EINVAL` rather than 0-filled
  data — this is **different from Linux**, where `RUSAGE_CHILDREN` is
  supported and would normally return parent-side waits. PG code that
  uses `getrusage` portably should not assume `RUSAGE_CHILDREN`
  works.

## Cross-refs

- `source/src/include/port/win32.h` — the local `struct rusage` and
  `RUSAGE_SELF` macro definitions.
- `source/src/backend/utils/misc/pg_rusage.c` — primary backend
  consumer.
