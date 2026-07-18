---
path: src/port/win32gettimeofday.c
anchor_sha: e18b0cb7344
loc: 75
depth: read
---

# src/port/win32gettimeofday.c

## Purpose

Windows replacement for `gettimeofday(2)`. Built on
`GetSystemTimePreciseAsFileTime`, which (since Windows 8 / Server
2012) provides ~1µs-resolution wall-clock time. Filetime is in
100-ns units since 1601-01-01 UTC; the conversion to Unix
`struct timeval` subtracts a constant offset and rescales.
`[verified-by-code]`

This is the PG-wide time source on Windows for `timestamp` types,
`clock_timestamp()`, log-line timestamps, and similar — every place
backend code does `gettimeofday(&tv, NULL)`.

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `int gettimeofday(struct timeval *tp, void *tzp)` | `win32gettimeofday.c:53` | `tzp` must be `NULL` (asserted) |

## Internal landmarks

- `epoch` constant `116444736000000000` (`win32gettimeofday.c:36`) —
  the FILETIME value of Unix epoch (Jan 1 1970 00:00:00 UTC), in 100-ns
  units since 1601-01-01.
- Conversion factors `FILETIME_UNITS_PER_SEC = 10000000`,
  `FILETIME_UNITS_PER_USEC = 10` (`:42-43`).
- Body (`:66-72`): `GetSystemTimePreciseAsFileTime(&file_time)`, pack
  into `ULARGE_INTEGER`, subtract `epoch`, then split into seconds
  (`/ FILETIME_UNITS_PER_SEC`) and microseconds (`% / 10`).
- `Assert(tzp == NULL)` (`:64`) — POSIX says `tzp` is "behavior
  unspecified if non-null"; PG enforces "always-null" in debug builds.

## Invariants & gotchas

- **Precision**: ~1 µs on Win8+; ~15 ms on older Windows where
  `GetSystemTimeAsFileTime` (without `Precise`) backs the system
  clock. The header `<sysinfoapi.h>` (`:31`) ensures the precise
  variant is available.
- **Monotonicity not guaranteed.** This is wall-clock time; it can
  jump backward on system clock adjustments (NTP, manual user
  change). Code that needs monotonicity should use
  `GetTickCount64`/`QueryPerformanceCounter` (see `elapsed_time()` in
  the backend, referenced in the comment at `:49-50`).
- The conversion is integer-only; no FP rounding. `tv_sec` cast to
  `long` is safe for any Unix timestamp until year 2038 on 32-bit
  builds (and beyond on 64-bit `time_t`).
- BSD-style copyright at the top (`win32gettimeofday.c:7-26`) — this
  is a separately-licensed contribution, not the standard PostgreSQL
  Global Development Group license. Don't remove the notice.

## Cross-refs

- `source/src/backend/utils/adt/timestamp.c` — consumer for
  timestamp generation.
- `source/src/port/elapsed_time.c` (no longer present at this anchor)
  / the in-tree monotonic-time helpers — preferred for duration
  measurements.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/port.md](../../../subsystems/port.md)
