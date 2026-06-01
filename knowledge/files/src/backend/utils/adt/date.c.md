# `src/backend/utils/adt/date.c`

- **File:** `source/src/backend/utils/adt/date.c` (3302 lines)
- **Header:** `source/src/include/utils/date.h`
- **Last verified commit:** `ef6a95c7c64de07dff4dd1f1da88ffae7b086ef3` (2026-06-01)

## Purpose

Implements the SQL standard `DATE`, `TIME`, and `TIME WITH TIME ZONE`
data types: I/O, casts, comparison operators (including cross-type
date ↔ timestamp/timestamptz), arithmetic
(date+integer, date−date, time+interval), btree sort/skip support,
hashing, and `EXTRACT()`/`date_part()`. Companion to `timestamp.c`
(timestamp/timestamptz/interval) and `datetime.c` (shared
parsing/formatting).

## Top of file (verbatim)

```
 * date.c
 *    implements DATE and TIME data types specified in SQL standard
```
(`:1-13` [from-comment])

## Public surface (selected)

- **DATE I/O & basic ops:** `date_in` (`:107`), `date_out` (`:179`),
  `date_recv` (`:204`), `date_send` (`:226`), `make_date` (`:240`).
- **Comparison:** `date_eq/ne/lt/le/gt/ge/cmp` (`:385–439`),
  cross-type `date_*_timestamp[tz]` (`:565–`),
  `timestamp[tz]_*_date` reverse forms (`:781–`).
- **Sort/skip support:** `date_sortsupport` (`:453`),
  `date_skipsupport` (`:494`) — provide abbreviated-keys-style fast
  paths to nbtree.
- **Hash:** `hashdate` (`:506`), `hashdateextended` (`:512`).
- **Arithmetic:** `date_pli` (`:526`, date+int days), `date_mi`
  (`:535`, date−date → int), `date_mii` (`:547`, date−int).
- **Casts:** `date_timestamp` (`:1273`), `date_timestamptz` (`:1294`),
  `timestamp_date` (`:1312`), `timestamptz_date` (`:1329`).
- **Extract:** `extract_date` (`:1093`).
- **TIME I/O & ops:** `time_in` (`:1474`), `time_out` (`:1605`),
  `time_recv` / `time_send`, `make_time` (`:1731`),
  `time_eq/ne/.../cmp` (`:1787–1841`).
- **TIME WITH TZ:** `timetz_in` (`:2014`), `timetz_out`, and
  comparators including the inevitable `timetz_eq/cmp` (`:2599–`).

## Key types

- **`DateADT` = int32** (`date.h:21`) — *days* since the
  PostgreSQL epoch 2000-01-01 (POSTGRES_EPOCH_JDATE = J2451545).
  Signed → dates before 2000 are negative.
- **`TimeADT` = int64** (`date.h:23`) — *microseconds* since midnight.
- **`TimeTzADT`** (`date.h:25-28`) — `{TimeADT time; int32 zone;}`
  with zone as numeric seconds. `sizeof()` is 16 due to padding but
  `TIMETZ_TYPLEN = 12` is the on-disk size (`date.h:30-36`
  [from-comment]).

## Key invariants

- **Date storage is days-since-2000, not unix epoch.** Choice of
  J2000-1-1 lets date span ±5.8 million years in int32, while keeping
  arithmetic with timestamps trivial: timestamp − date·USECS_PER_DAY
  works directly (`date.c:649` comment: "date is days since 2000,
  timestamp is microseconds since same..." [from-comment]).
- **±Infinity dates use INT32_MIN/MAX.**
  `DATEVAL_NOBEGIN = PG_INT32_MIN`, `DATEVAL_NOEND = PG_INT32_MAX`
  (`date.h:42-44`). Every comparator must check `DATE_NOT_FINITE`
  before doing arithmetic.
- **Time has microsecond resolution.** `MAX_TIME_PRECISION = 6`
  (`date.h:51`). `AdjustTimeForTypmod` rounds to the requested
  precision.
- **timetz zone is signed seconds east of UTC.** Larger zone =
  earlier wall time for same UTC instant; comparator
  `timetz_cmp_internal` normalizes by computing UTC equivalent
  before comparing (`[inferred]` from generic conventions).
- **`date_in` rejects Julian-day overflow before saving.** Both
  `IS_VALID_JULIAN(tm)` and `IS_VALID_DATE(date)` guards are
  required because the Julian routines can otherwise overflow
  internally (`:158-170` [verified-by-code]).

## Functions of note

- **`date_in`** (`:107`) — calls shared `ParseDateTime` +
  `DecodeDateTime`, then converts the broken-down Y/M/D to days
  since 2000 via `date2j` − POSTGRES_EPOCH_JDATE (`:164`). Handles
  `DTK_EPOCH`/`LATE`/`EARLY` for `'epoch'`, `'infinity'`, `'-infinity'`.
- **`date_sortsupport`** (`:453`) — installs a comparator that
  short-circuits via `int32` subtraction; no abbrev needed because
  the datum already fits in a Datum word.
- **`date_skipsupport`** (`:494`) — used by nbtree's "skip scan"
  for `WHERE date BETWEEN…` to skip large runs; supplies
  predecessor/successor based on int32 ± 1 with infinity guards.
- **`date_pl_interval`** / **`time_pl_interval`** /
  **`timestamp_pl_interval`** (the last lives in `timestamp.c`,
  but date routes through it via `DirectFunctionCall2` `:1282`) —
  date+interval up-converts to timestamp because intervals can carry
  fractional seconds.
- **`extract_date`** (`:1093`) — implements SQL `EXTRACT(field FROM
  date)`. Returns `numeric`; cases enumerated for `year`, `month`,
  `day`, `dow`, `doy`, `isodow`, `isoyear`, `week`, `century`,
  `decade`, `millennium`, `epoch`, plus the perennial
  `julian`/`quarter`. Defers to ISO-week helpers in `datetime.c`
  (`date2isoweek` etc., declared `timestamp.h:153-158`).
- **`date_cmp_timestamp_internal`** (declared `date.h:111`,
  defined here) — used by btree opclasses to allow indexed
  cross-type comparisons date↔timestamp without casting.
  Converts the date to a 0:00:00 timestamp on the fly.

## Cross-references

- `source/src/backend/utils/adt/datetime.c` — `ParseDateTime`,
  `DecodeDateTime`, `EncodeDateOnly`, `j2date`, `date2j`.
- `source/src/backend/utils/adt/timestamp.c` — sibling type, called
  via `DirectFunctionCall2` for cross-type arithmetic.
- `source/src/backend/utils/adt/formatting.c` — `to_char`/`to_date`.
- `source/src/include/datatype/timestamp.h` — shared epoch and
  range constants.

## Open questions

- `date_skipsupport`'s exact contract (`SkipSupport` interface) lives
  in `utils/skipsupport.h`; this file just registers callbacks.
  `[unverified]` whether `extract_date(epoch from 'infinity')` returns
  `+Infinity` consistently across PG versions.
- timetz comparator's exact normalization rule
  (UTC-normalized vs. local-wall-clock) — needs a glance at
  `timetz_cmp_internal`. `[unverified]`

## Confidence tag tally

- `[verified-by-code]` × 1
- `[from-comment]` × 3
- `[inferred]` × 1
- `[unverified]` × 2
