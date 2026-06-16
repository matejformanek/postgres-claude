# `src/include/datatype/timestamp.h`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~269
- **Source:** `source/src/include/datatype/timestamp.h`

The base typedefs and arithmetic / Julian-date constants for
`timestamp`, `timestamptz`, `interval`, `date`, and `time`. Frontend-
and backend-safe ("Note: this file must be includable in both
frontend and backend contexts" — explicit). Higher-level fmgr/io
APIs live in `utils/timestamp.h` and `utils/date.h`. [from-comment]

## API / declarations

### Typedefs

- `typedef int64 Timestamp;` — absolute time, microseconds since
  2000-01-01. [from-comment]
- `typedef int64 TimestampTz;` — same, with-time-zone flavor.
- `typedef int64 TimeOffset;` — interval temporary.
- `typedef int32 fsec_t;` — fractional seconds (microseconds);
  "Do not use fsec_t in values stored on-disk." [from-comment]

### Interval storage

- `Interval { TimeOffset time; int32 day; int32 month; }` — three
  separate fields because the elapsed time of "1 month" depends on
  what month it lands on. Order of fields chosen for alignment.

### Broken-down interval

- `pg_itm { int tm_usec, tm_sec, tm_min; int64 tm_hour; int
  tm_mday, tm_mon, tm_year; }` — used by interval_to_char path.
  `tm_hour` is int64 because intervals can be huge.
- `pg_itm_in { int64 tm_usec; int tm_mday, tm_mon, tm_year }` —
  decoding-time, omits seconds/mins/hours.

### Precision + rounding

- `MAX_TIMESTAMP_PRECISION = 6`, `MAX_INTERVAL_PRECISION = 6`.
- `TS_PREC_INV = 1000000.0`.
- `TSROUND(j) := rint(j * TS_PREC_INV) / TS_PREC_INV`.

### Calendar constants

- `DAYS_PER_YEAR 365.25`, `MONTHS_PER_YEAR 12`,
  `DAYS_PER_MONTH 30` ("very imprecise. The more accurate value
  is 365.2425/12 = 30.436875"), `DAYS_PER_WEEK 7`,
  `HOURS_PER_DAY 24` (no DST).
- `SECS_PER_YEAR = 36525 * 864` — phrased to avoid floating-point.
- `SECS_PER_DAY 86400`, `SECS_PER_HOUR 3600`, `SECS_PER_MINUTE 60`,
  `MINS_PER_HOUR 60`.
- Microsecond variants: `USECS_PER_DAY`, `USECS_PER_HOUR`,
  `USECS_PER_MINUTE`, `USECS_PER_SEC` (all INT64CONST).

### Timezone

- `MAX_TZDISP_HOUR 15`, `TZDISP_LIMIT = 16*3600` — accommodates
  historical zones up to Asia/Manila's -15:56:08. [from-comment]

### Infinity

- `TIMESTAMP_MINUS_INFINITY = PG_INT64_MIN`,
  `TIMESTAMP_INFINITY = PG_INT64_MAX`. Aliases `DT_NOBEGIN`,
  `DT_NOEND`. Macros: `TIMESTAMP_NOBEGIN(j)`, `_NOEND`,
  `TIMESTAMP_IS_NOBEGIN`, `_IS_NOEND`, `_NOT_FINITE`.
- Interval ±∞ is represented by setting ALL THREE fields to INT
  ±MAX simultaneously — `INTERVAL_NOBEGIN(i)`, `_NOEND`,
  `_IS_NOBEGIN`, `_IS_NOEND`, `_NOT_FINITE`. [verified-by-code]

### Julian-date range

- `JULIAN_MINYEAR -4713`, `JULIAN_MINMONTH 11`, `JULIAN_MINDAY 24`.
- `JULIAN_MAXYEAR 5874898`, `JULIAN_MAXMONTH 6`, `JULIAN_MAXDAY 3`.
- `IS_VALID_JULIAN(y,m,d)` — month-boundary check (cheaper than
  exact day-of-year math).
- `UNIX_EPOCH_JDATE 2440588` (= date2j(1970,1,1)).
- `POSTGRES_EPOCH_JDATE 2451545` (= date2j(2000,1,1)).

### Date / timestamp range

- `DATETIME_MIN_JULIAN 0`, `DATE_END_JULIAN 2147483494`,
  `TIMESTAMP_END_JULIAN 109203528`.
- `MIN_TIMESTAMP = (DATETIME_MIN_JULIAN - POSTGRES_EPOCH_JDATE) *
  USECS_PER_DAY = -211813488000000000`.
- `END_TIMESTAMP =  9223371331200000000`.
- `IS_VALID_DATE(d)` (Postgres-numbering), `IS_VALID_TIMESTAMP(t)`.

## Notable invariants / details

- "Once upon a time they were double values with units of seconds"
  — current int64-microseconds layout dates from PG 8.4ish. On-disk
  format is the int64. [from-comment]
- "JULIAN_MINYEAR is -4713, not -4714; it is defined to allow easy
  comparison to tm_year values" — note the off-by-one convention
  where `tm_year <= 0` means abs(tm_year)+1 BC. [from-comment]
- "It is correct that JULIAN_MINYEAR is -4713" — the file
  pre-emptively defends a confusing constant. [from-comment]
- Interval-infinity requires ALL three fields at the sentinel; any
  one-field flip leaves it finite. [verified-by-code]
- The date upper bound (5874897-12-31) is "a bit less than what the
  Julian-date code can allow" — the slack avoids corner-case
  overflow on timezone rotation. [from-comment]

## Potential issues

- `DAYS_PER_MONTH = 30` and `DAYS_PER_YEAR = 365.25` are used in
  the EXTRACT(epoch FROM interval) computation; users sometimes
  treat the result as "real" and get surprises. The header flags
  the imprecision but it's still a foot-gun. [ISSUE-question:
  document EXTRACT(epoch FROM interval) imprecision more
  prominently (nit)]
- `Interval` aligns to 16 bytes (time:8, day:4, month:4) — every
  on-disk interval costs 16 bytes even when month/day are zero.
  Cannot change without breaking on-disk compat. [ISSUE-undocumented-invariant:
  Interval is 16-byte fixed (likely)]
- `fsec_t` (int32 microseconds) is documented "only meant for
  *fractional* seconds; beware of overflow if the value you need
  to store could be many seconds." Real foot-gun in custom code.
  [from-comment] [ISSUE-stale-todo: fsec_t overflow risk in callers
  (likely)]
- `IS_VALID_JULIAN` is intentionally looser than `IS_VALID_DATE`
  (month-boundary vs day-boundary). A reviewer adding a new
  validator must keep that ordering. [ISSUE-undocumented-invariant:
  IS_VALID_JULIAN must remain ≥ IS_VALID_DATE coverage (nit)]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `include-misc`](../../../../issues/include-misc.md)
<!-- issues:auto:end -->
