# `src/backend/utils/adt/timestamp.c`

- **File:** `source/src/backend/utils/adt/timestamp.c` (7003 lines —
  largest in `utils/adt/`)
- **Header:** `source/src/include/utils/timestamp.h` +
  `source/src/include/datatype/timestamp.h`
- **Last verified commit:** `ef6a95c7c64de07dff4dd1f1da88ffae7b086ef3` (2026-06-01)

## Purpose

The fmgr surface for `timestamp`, `timestamp with time zone`, and
`interval`: I/O, recv/send, typmod handling, comparison (incl.
cross-type with date), arithmetic, `EXTRACT()` / `date_part()`,
`date_trunc`, `date_bin`, `generate_series`, and the
`avg(interval)`/`sum(interval)` aggregate machinery. Backing storage
is int64 microseconds since 2000-01-01.

## Top of file (verbatim)

```
 * timestamp.c
 *    Functions for the built-in SQL types "timestamp" and "interval".
```
(`:1-13` [from-comment])

## Public surface (selected)

- **I/O:** `timestamp_in/_out/_recv/_send` (`:157, 226, 252, 285`),
  `timestamptz_in/_out/_recv/_send` (`:340, 660, 681, 721`),
  `interval_in/_out/_recv/_send` (`:1126, 1265, 1329, 1532`).
- **Typmod:** `timestamptypmodin/out` (`:296, 304`),
  `timestamptztypmodin/out` (`:772, 800`),
  `intervaltypmodin/out` (`:1612, 1618`).
- **Planner support:** `timestamp_support` (`:319`), `interval_support`
  (`:1630`) — used to fold typmod casts when no precision change.
- **Constructors:** `make_timestamp` (`:413`), `make_timestamptz`
  (`:640`), `make_timestamptz_at_timezone` (`:660`), `make_interval`
  (`:1694`).
- **Current time:** `now` (`:2158`), `statement_timestamp` (`:2166`),
  `clock_timestamp` (`:2227`), `pg_postmaster_start_time` (`:2236`),
  `pg_conf_load_time` (`:2245`), `timeofday` (`:2254`).
- **Comparison:** `timestamp_eq/ne/.../cmp` (`:2333–`),
  `interval_eq/.../cmp` (`:2575–`), cross-type
  `timestamp_eq_timestamptz` etc (`:2933–`).
- **Arithmetic:** `timestamp_mi` (timestamp−timestamp→interval,
  `:2809`), `timestamp_pl_interval` (`:3104`),
  `interval_um` (`:3469`), `interval_pl/mi/mul/div` (`:~3500-3900`).
- **Extract / truncate / bin:** `timestamp_part` (`:5773`) and
  `extract_timestamp[_tz]`, `timestamp_trunc`, `date_trunc_interval`,
  `timestamp_bin` / `timestamptz_bin`.
- **Aggregates:** `interval_avg_accum/_combine/_serialize/_deserialize/
  _avg/_sum` (uses `IntervalAggState`, `:71-78`).
- **generate_series:** `generate_series_timestamp[_tz][_at_zone]`
  with both 2-arg and 3-arg step variants.

## Key types

- **`Timestamp` / `TimestampTz` = int64** (`datatype/timestamp.h:38-39`)
  — microseconds since PG epoch 2000-01-01 00:00:00. *Both* types are
  identical on disk; the difference is purely whether values are
  interpreted as UTC instants (TZ) or local wall-clock-with-no-zone
  (plain).
- **`Interval`** (`datatype/timestamp.h:47-53`) — three fields:
  `TimeOffset time` (microseconds), `int32 day`, `int32 month`.
  Kept separate because adding "1 month" or "1 day" to a timestamp
  depends on the timestamp (DST, varying month length).
- **`TimeOffset` = int64**, **`fsec_t` = int32 microseconds**
  (`datatype/timestamp.h:40-41`).
- **`IntervalAggState`** (`:71-78`) — aggregate transition state:
  `N` finite-count, `Interval sumX`, plus separate
  `+Inf` and `-Inf` counts because `+Inf + -Inf` must error.
- **`generate_series_timestamp[tz]_fctx`** (`:48-65`) — SRF state for
  generate_series; the `_tz` variant additionally remembers the
  `pg_tz *attimezone` so per-tick DST math is correct.

## Key invariants

- **int64 µs since 2000-01-01, not since 1970.** Was once
  `double` seconds; switched to int64 µs to make arithmetic exact
  and to match SQL standard's "fractional seconds" semantics
  (`datatype/timestamp.h:28-30`: "Timestamps … are stored as int64
  values with units of microseconds. (Once upon a time they were
  double values with units of seconds.)" [from-comment]).
- **No ambiguity in `timestamptz` storage.** It is always UTC; the
  session timezone only affects parsing/printing
  (`[inferred]` from `timestamp_in` vs `timestamptz_in` paths).
- **±Infinity uses INT64_MIN/MAX.** `TIMESTAMP_NOBEGIN/NOEND` and
  `INTERVAL_NOBEGIN/NOEND` macros (defined in
  `datatype/timestamp.h`). Every comparator must check first.
- **Interval comparison normalizes via `interval_cmp_value`** —
  collapses (months, days, time) into a 128-bit "approximate
  microseconds" using DAYS_PER_MONTH=30 and HOURS_PER_DAY=24
  (`:2530` comment "in the case of integer timestamps with days
  assumed to be always 24 hours" [from-comment]). Not exact but
  satisfies trichotomy.
- **`AdjustTimestampForTypmod` rounds away from zero.** Used by
  every I/O and cast path; rejects typmod > MAX_TIMESTAMP_PRECISION
  with a WARNING and a downgrade to 6 (`:115-134`
  [verified-by-code]).
- **`PgStartTime` set once at postmaster start;** `PgReloadTime`
  reset on `SIGHUP`. Both module-level `TimestampTz` globals (`:43-46`).

## Functions of note

- **`timestamp_in`** (`:157`) — runs `ParseDateTime` +
  `DecodeDateTime`, dispatches on `dtype`. For TZ-bearing input,
  `tm2timestamp(..., &tz, ...)` lifts to UTC; the no-TZ
  `timestamp_in` ignores any zone token (`tzp = NULL`).
- **`timestamptz_in`** (`:340`) — same but always honors session
  timezone (`session_timezone`) when none specified.
- **`timestamp_part_common`** (`:5515`) — shared between
  `timestamp_part` and `extract_timestamp`. Massive switch over
  `DTK_*` field codes. Tolerates ±infinity by routing through
  `NonFiniteTimestampTzPart` (`:5448`).
- **`timestamp_pl_interval`** (`:3104`) — adds month, day, time
  components in that order so that "2000-01-31 + 1 month + 1 day"
  is well-defined as 2000-02-29. Each step calls `j2date`/`date2j`
  to renormalize.
- **`interval_um_internal`** (`:3445`) — interval unary minus.
  Negates each of `month`, `day`, `time` independently with overflow
  checks; used as the building block for `interval_mi` etc.
- **`now`** (`:2158`) — returns `GetCurrentTransactionStartTimestamp`,
  so it's stable within a transaction; `statement_timestamp`
  (`:2166`) returns `GetCurrentStatementStartTimestamp`;
  `clock_timestamp` (`:2227`) calls `GetCurrentTimestamp` —
  not stable, wall-clock now.
- **`generate_series_timestamp`** (`:5500+`) — uses `SRF_*` macros;
  per-call state tracks current and finish + interval step + sign,
  walks via `timestamp_pl_interval`.

## Cross-references

- `source/src/backend/utils/adt/datetime.c` — `ParseDateTime`,
  `DecodeDateTime`, `EncodeDateTime[Only]`, `j2date`, `date2j`.
- `source/src/backend/utils/adt/date.c` — DATE/TIME types; cross-type
  comparators come back here for the timestamp side.
- `source/src/backend/utils/adt/formatting.c` — `to_char`/`to_timestamp`.
- `source/src/timezone/` — IANA tz data, accessed via `pg_tz` handles.
- `source/src/include/datatype/timestamp.h` — `USECS_PER_*` and epoch
  macros shared with frontend.

## Open questions

- `extract(epoch from timestamptz 'infinity')` — `[unverified]` whether
  it returns `'Infinity'::numeric` or errors.
- `IntervalAggState` precision: comment notes `pInfcount` / `nInfcount`
  are kept separate from `N`; what's the policy if BOTH counts are
  positive during finalfn? `[inferred]` it raises "interval out of
  range" but worth confirming.
- The 30-day, 24-hour normalization in `interval_cmp_value` means
  `'1 month'::interval = '30 days'::interval` for `=` but NOT for
  `timestamp + …`. Could trip up indexes on interval columns.
  `[verified-by-code]` from comment but worth a dedicated note.

## Confidence tag tally

- `[verified-by-code]` × 2
- `[from-comment]` × 3
- `[inferred]` × 2
- `[unverified]` × 2
