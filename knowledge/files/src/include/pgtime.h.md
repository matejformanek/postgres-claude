# `src/include/pgtime.h`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~101
- **Source:** `source/src/include/pgtime.h`

PostgreSQL's internal timezone library API. PG ships its own forked
IANA timezone code (`src/timezone/`) for reproducibility across
platforms. This header exposes a libc-shaped surface using
`pg_time_t` (an `int64`, definitely signed unlike POSIX `time_t`),
`struct pg_tm`, and the opaque `pg_tz` / `pg_tzenum` types.
[verified-by-code]

## API / declarations

- `typedef int64 pg_time_t` (`pgtime.h:23`) — 64-bit signed,
  contrasting with POSIX's possibly-32-bit, possibly-unsigned
  time_t.
- `struct pg_tm` (`pgtime.h:34-47`) — analog of `struct tm` with the
  same fields PLUS `tm_gmtoff` and `tm_zone`. **CAUTION** in comment
  (`pgtime.h:28-32`): the IANA library follows POSIX (`tm_mon`
  counting from 0, `tm_year` relative to 1900), but PG's datetime
  functions use `tm_mon` from 1 and `tm_year` relative to 1 BC. Code
  bridging the two domains MUST adjust.
- `typedef struct pg_tz pg_tz` (`pgtime.h:50`) — opaque outside the
  timezone library.
- `typedef struct pg_tzenum pg_tzenum` (`pgtime.h:51`) — opaque
  iterator over installed timezones.
- `TZ_STRLEN_MAX = 255` (`pgtime.h:54`) — max timezone name length
  (excluding null).

### Functions in localtime.c (`pgtime.h:56-81`)

- `pg_localtime(timep, tz)`, `pg_gmtime(timep)` — broken-down time.
- `pg_next_dst_boundary(timep, &before_gmtoff, &before_isdst,
  &boundary, &after_gmtoff, &after_isdst, tz)`.
- `pg_interpret_timezone_abbrev(abbrev, timep, &gmtoff, &isdst, tz)`,
  `pg_timezone_abbrev_is_known(abbrev, &isfixed, &gmtoff, &isdst,
  tz)`.
- `pg_get_next_timezone_abbrev(&indx, tz)`.
- `pg_get_timezone_offset(tz, &gmtoff)`,
  `pg_get_timezone_name(tz)`.
- `pg_tz_acceptable(tz)` — heuristic.

### Functions in strftime.c

- `pg_strftime(s, maxsize, format, t)` — same shape as libc.

### Functions / globals in pgtz.c (`pgtime.h:88-99`)

- `session_timezone` PGDLLIMPORT global — set by `SET TIMEZONE`.
- `log_timezone` PGDLLIMPORT global — independent timezone for log
  output (so logs stay consistent across user sessions).
- `pg_timezone_initialize(void)` — postinit setup.
- `pg_tzset(tzname)` — look up by name.
- `pg_tzset_offset(gmtoffset)` — manufactured by offset.
- `pg_tzenumerate_start/_next/_end` — iterator over installed
  timezones.

## Notable invariants / details

- `pg_time_t` is **definitely** 64-bit signed (`pgtime.h:23`).
  This sidesteps the 2038 problem and the year-1970 lower-bound for
  unsigned. [from-comment]
- `tm_mon` / `tm_year` convention mismatch is a recurring bug source.
  The header CAUTION is one of the clearest in the entire tree.
  [from-comment]
- `pg_tz` / `pg_tzenum` opaque types: this is correct — the timezone
  binary database changes shape across IANA tzdata releases.
- `session_timezone` and `log_timezone` are SEPARATE globals
  (`pgtime.h:90-91`). Setting `log_timezone` independently is the
  correct way to ensure consistent log timestamps across user
  sessions. [verified-by-code]
- `pg_tzset_offset(gmtoffset)` synthesizes a timezone from a raw
  offset (e.g. SQL `'UTC+05:00'`). The implementation caches a
  per-process pool; the cache is not bounded.
  [ISSUE-resource: `pg_tzset_offset` cache unbounded (maybe)]

## Potential issues

- `pgtime.h:28-32` — the `tm_mon`/`tm_year` convention mismatch is
  the only documentation; new datetime code routinely hits it.
  [ISSUE-correctness: pg_tm convention mismatch is comment-only;
  no static helper to convert (likely)]
- `pgtime.h:54` — `TZ_STRLEN_MAX = 255`. Callers that copy names
  must use this constant; some code paths use raw `char buf[256]`
  instead.
- `pgtime.h:90-91` — `session_timezone` and `log_timezone` are
  mutable PGDLLIMPORT pointers; extension code can scribble.
  [ISSUE-defense-in-depth: session/log_timezone are
  PGDLLIMPORT-mutable (nit)]
- `pgtime.h:81` — `pg_tz_acceptable(tz)` is heuristic; what counts
  as "acceptable" is comment-only at the implementation. New
  callers may misunderstand. [ISSUE-documentation:
  pg_tz_acceptable contract opaque (nit)]
- `pgtime.h:67-71` — `pg_interpret_timezone_abbrev` and
  `pg_timezone_abbrev_is_known` overlap in purpose; abbrev handling
  for DST-spanning abbrevs (e.g. "EST" vs "EDT") is subtle.
  [ISSUE-doc-drift: timezone-abbreviation function family is
  duplicative (nit)]
