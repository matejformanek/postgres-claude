# `src/bin/pg_waldump/compat.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~64
- **Source:** `source/src/bin/pg_waldump/compat.c`

Provides client-side reimplementations of two timestamp utility
functions (`timestamptz_to_time_t`, `timestamptz_to_str`) that the
shared `*desc.c` rmgr description files in `src/backend/access/...`
reference. The shared `*desc.c` files are compiled into the
frontend `pg_waldump` binary with `FRONTEND 1` defined; this file
fills the small gap of functions otherwise only available in the
backend's `utils/adt/timestamp.c`. [verified-by-code]

## API / entry points

- `pg_time_t timestamptz_to_time_t(TimestampTz t)` — converts a
  PostgreSQL TimestampTz (microseconds since 2000-01-01 UTC) to a
  Unix time_t by dividing by `USECS_PER_SEC` and adjusting the
  Julian-day epoch difference. [verified-by-code]
- `const char *timestamptz_to_str(TimestampTz t)` — formats a
  timestamp as `YYYY-MM-DD HH:MM:SS.ffffff TZ` using local time.
  Returns a pointer to a static buffer of size `MAXDATELEN + 1`.
  [verified-by-code]

## Notable invariants / details

- Uses the `#define FRONTEND 1` + `#include "postgres.h"` "ugly hack"
  (comment on line 17) — same trick as `pg_controldata` — to pull
  in backend headers while staying linkable in frontend.
  [verified-by-code]
- `timestamptz_to_str` returns a pointer into a `static char buf[]`
  (line 51): the next call clobbers the previous result. Single-call
  per `printf` is required. [verified-by-code]
- `localtime(&result)` is non-reentrant; OK for single-threaded
  pg_waldump. [verified-by-code]

## Potential issues

- Line 42 comment "XXX the return value points to a static buffer,
  so beware of using more than one result value concurrently." This
  is a known-limitation comment, not a bug. [verified-by-code]
  [ISSUE-stale-todo: XXX comment notes static-buffer reuse hazard;
  callers OK so far (nit)]
- Line 45 comment "XXX: The backend timestamp infrastructure should
  instead be split out and moved into src/common." Long-standing
  refactoring desire. [verified-by-code] [ISSUE-stale-todo: XXX
  suggests moving timestamp utilities to src/common (nit)]
- `localtime()` may return NULL on libc errors; not checked. A
  `time_t` value out of range of `struct tm` would crash on the
  `strftime` call. In practice, this is reachable only with crafted
  WAL data; pg_waldump already trusts WAL content. [verified-by-code]
  [ISSUE-correctness: localtime() return not NULL-checked (nit)]
- `t % USECS_PER_SEC` on line 61: for negative `TimestampTz` the
  result is implementation-defined in C89 but well-defined as
  truncated-to-zero in C99. The cast `(int)` is fine but could
  print a negative microsecond fragment for pre-2000 timestamps.
  [verified-by-code] [ISSUE-correctness: pre-epoch TimestampTz could
  show negative usec fraction (nit)]
