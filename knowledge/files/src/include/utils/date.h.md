# `src/include/utils/date.h`

- **File:** `source/src/include/utils/date.h` (126 lines)
- **Last verified commit:** `ef6a95c7c64de07dff4dd1f1da88ffae7b086ef3` (2026-06-01)

## Purpose

Defines the `DateADT`, `TimeADT`, and `TimeTzADT` storage types,
their Datum macros, and the extern surface of `date.c` used by
other backend code that needs to construct, decompose, or convert
date/time values without going through fmgr.

## Top of file (verbatim)

```
 * date.h
 *    Definitions for the SQL "date" and "time" types.
```
(`:1-12` [from-comment])

## Public surface

- **Type defs:** `DateADT` = int32 (`:21`), `TimeADT` = int64
  (`:23`), `TimeTzADT` = `{TimeADT time; int32 zone;}` (`:25-28`).
- **Datum macros:** `DatumGetDateADT` (`:59`),
  `DatumGetTimeADT` (`:65`), `DatumGetTimeTzADTP` (`:71`),
  `DateADTGetDatum` (`:77`), `TimeADTGetDatum` (`:83`),
  `TimeTzADTPGetDatum` (`:89`), plus
  `PG_GETARG_*` / `PG_RETURN_*` macros (`:95-101`).
- **Sentinels:** `DATEVAL_NOBEGIN` (PG_INT32_MIN),
  `DATEVAL_NOEND` (PG_INT32_MAX), `DATE_NOBEGIN/NOEND`,
  `DATE_IS_NOBEGIN/NOEND`, `DATE_NOT_FINITE` macros (`:42-49`).
- **Precision cap:** `MAX_TIME_PRECISION` = 6 (`:51`).
- **Constants:** `TIMETZ_TYPLEN` = 12 (`:36`) — required because
  `sizeof(TimeTzADT)` is 16 on most platforms but pg_type's
  recorded typlen is 12.
- **Cast & accessor extern surface (`:104-124`):**
  `anytime_typmod_check`, `date2timestamp_no_overflow`,
  `date2timestamp_safe`, `date2timestamptz_safe`,
  `timestamp2date_safe`, `timestamptz2date_safe`,
  `date_cmp_timestamp_internal`, `date_cmp_timestamptz_internal`,
  `EncodeSpecialDate`, `GetSQLCurrentDate`, `GetSQLCurrentTime`,
  `GetSQLLocalTime`, `time2tm`, `timetz2tm`, `tm2time`,
  `tm2timetz`, `time_overflows`, `float_time_overflows`,
  `AdjustTimeForTypmod`.

## Key invariants

- **`DateADT` is days since 2000-01-01.** Signed int32 ⇒ approximate
  range ±5.8 million years. Lets date arithmetic interoperate
  trivially with µs-since-2000 timestamps.
- **`TimeADT` is microseconds since midnight.** Range
  [0, 86_400_000_000] (24 hours expressed in µs).
- **`TimeTzADT` is 16-byte struct but 12-byte typlen.** Pad-aware
  code must use `TIMETZ_TYPLEN` for on-disk math (`:30-36`
  [from-comment]: "In most places we can get away with using
  sizeof(TimeTzADT), but where it's important to match the
  declared typlen, use TIMETZ_TYPLEN.").
- **Infinity = min/max int32.** Comparators must short-circuit
  before arithmetic.
- **TimeADT pass-by-ref/value tracks int64.** "For TimeADT, we make
  use of the same support routines as for int64. Therefore TimeADT
  is pass-by-reference if and only if int64 is!" (`:53-57`
  [from-comment]) — relevant for 32-bit platforms.

## Cross-references

- `source/src/backend/utils/adt/date.c` — implementations.
- `source/src/include/datatype/timestamp.h` — `POSTGRES_EPOCH_JDATE`
  and `USECS_PER_DAY`.
- `source/src/backend/utils/adt/datetime.c` — `j2date`/`date2j`
  Julian helpers.

## Confidence tag tally

- `[from-comment]` × 2
- `[verified-by-code]` × 0
- `[unverified]` × 0
