# `src/include/utils/timestamp.h`

- **File:** `source/src/include/utils/timestamp.h` (162 lines)
- **Last verified commit:** `ef6a95c7c64de07dff4dd1f1da88ffae7b086ef3` (2026-06-01)

## Purpose

The fmgr-side header for `timestamp`, `timestamptz`, and `interval`:
Datum macros, typmod packing macros, the `PgStartTime` /
`PgReloadTime` global timestamps, comparison helpers, and the
extern surface of `timestamp.c` used by callers that need to build
or break apart timestamps without going through fmgr. The
representation-level definitions (the actual `Timestamp` /
`TimestampTz` / `Interval` typedefs and epoch constants) live in
`source/src/include/datatype/timestamp.h` because they need to be
includable from frontend code as well.

## Top of file (verbatim)

```
 * timestamp.h
 *    Definitions for the SQL "timestamp" and "interval" types.
```
(`:1-11` [from-comment])

## Public surface

- **Datum macros:** `DatumGetTimestamp` (`:26`),
  `DatumGetTimestampTz` (`:32`), `DatumGetIntervalP` (`:38`),
  `TimestampGetDatum` (`:44`), `TimestampTzGetDatum` (`:50`),
  `IntervalPGetDatum` (`:56`), plus `PG_GETARG_*` / `PG_RETURN_*`
  macros (`:63-69`).
- **Typmod macros:** `INTERVAL_FULL_RANGE` (0x7FFF),
  `INTERVAL_RANGE_MASK`, `INTERVAL_FULL_PRECISION` (0xFFFF),
  `INTERVAL_PRECISION_MASK`, `INTERVAL_TYPMOD(p,r)`,
  `INTERVAL_PRECISION(t)`, `INTERVAL_RANGE(t)` (`:76-82`).
- **Arithmetic helpers:** `TimestampTzPlusMilliseconds`,
  `TimestampTzPlusSeconds` (`:85-86`),
  `TimestampDifferenceMicroseconds` inline (`:89-96`).
- **Globals:** `PgStartTime` (`:99`), `PgReloadTime` (`:102`).
- **Internal API (extern):** `anytimestamp_typmod_check`,
  `GetCurrentTimestamp`, `GetSQLCurrentTimestamp`,
  `GetSQLLocalTimestamp`, `TimestampDifference`,
  `TimestampDifferenceMilliseconds`,
  `TimestampDifferenceExceeds`,
  `TimestampDifferenceExceedsSeconds`, `time_t_to_timestamptz`,
  `timestamptz_to_time_t`, `timestamptz_to_str`,
  `tm2timestamp`, `timestamp2tm`, `dt2time`,
  `interval2itm`, `itm2interval`, `itmin2interval`,
  `SetEpochTimestamp`, `GetEpochTime`,
  `timestamp_cmp_internal`,
  `timestamp2timestamptz_safe`, `timestamptz2timestamp_safe`,
  `timestamp_cmp_timestamptz_internal`,
  `isoweek2j`, `isoweek2date`, `isoweekdate2date`,
  `date2isoweek`, `date2isoyear`, `date2isoyearday`,
  `TimestampTimestampTzRequiresRewrite` (`:105-160`).
- **Alias:** `timestamptz_cmp_internal = timestamp_cmp_internal`
  (`:143` [from-comment]: "timestamp comparison works for
  timestamptz also") — because both are int64 µs.

## Key invariants

- **`Timestamp` / `TimestampTz` are int64 microseconds since
  2000-01-01.** Defined in `datatype/timestamp.h`, but every
  caller of this header must remember the units.
- **`Timestamp` pass-by-ref/value tracks int64.** "For Timestamp,
  we make use of the same support routines as for int64.
  Therefore Timestamp is pass-by-reference if and only if int64
  is!" (`:21-25` [from-comment]).
- **`Interval` is always pass-by-pointer.** Three-field struct
  doesn't fit in a Datum.
- **Interval typmod packs (precision, range) into 32 bits.**
  Range in high 16, precision in low 16
  (`INTERVAL_TYPMOD`, `:80`).
- **`TimestampDifferenceMicroseconds` clamps negative differences
  to 0.** Returns unsigned (`:89-96` [verified-by-code]) — useful
  for delays/durations but caller can't detect ordering from the
  return.
- **`PgStartTime` set once at postmaster start; `PgReloadTime`
  refreshed each `SIGHUP`.** `:98, :101` [from-comment].
- **TZ comparison works for non-TZ.** Single `timestamp_cmp_internal`
  serves both via macro alias; reflects that the storage is
  byte-identical.

## Cross-references

- `source/src/include/datatype/timestamp.h` — representation +
  range constants, `USECS_PER_*`, `POSTGRES_EPOCH_JDATE`.
- `source/src/backend/utils/adt/timestamp.c` — implementations.
- `source/src/backend/utils/adt/datetime.c` — `EncodeDateTime`,
  ParseDateTime, `j2date`, `date2j`.
- `source/src/include/utils/date.h` — sibling DATE/TIME types.

## Open questions

- `TimestampTimestampTzRequiresRewrite` (`:160`) — what triggers
  it returning true? Comment in the .c file would clarify.
  `[unverified]`

## Confidence tag tally

- `[from-comment]` × 3
- `[verified-by-code]` × 1
- `[unverified]` × 1
