---
path: src/interfaces/ecpg/pgtypeslib/timestamp.c
anchor_sha: e18b0cb7344cb4bd28468f6c0aeeb9b9241d30aa
loc: 921
depth: deep
---

# `timestamp.c` — ecpg client-side `timestamp` type (parse, format, arithmetic)

## Purpose
Implements the `PGTYPEStimestamp_*` family for the ecpg `pgtypeslib`
client library: the in-application timestamp data type used by embedded-SQL
programs. It mirrors the backend's `timestamp` semantics (int64 microseconds
since the J2000 epoch) but lives entirely in libpq-land. Functions cover
ASCII parse (`PGTYPEStimestamp_from_asc` via the shared `ParseDateTime` /
`DecodeDateTime` machinery), ASCII output (`PGTYPEStimestamp_to_asc` via
`EncodeDateTime`), a `strftime`-style formatter (`PGTYPEStimestamp_fmt_asc`
→ the big `dttofmtasc_replace` dispatcher), a `strptime`-style parser
(`PGTYPEStimestamp_defmt_asc` → `PGTYPEStimestamp_defmt_scan`, defined in
`dt_common.c`), current-time fetch, subtraction to an `interval`, and
interval add/subtract. The internal `tm2timestamp` / `timestamp2tm`
converters are private copies of the backend routines of the same names.
`[verified-by-code]` timestamp.c:1-921

## Public symbols
| Symbol | Site | Notes |
|---|---|---|
| `int tm2timestamp(struct tm *tm, fsec_t fsec, int *tzp, timestamp *result)` | timestamp.c:38 | tm → timestamp; year is full (not 1900-based), month 1-based; returns -1 on overflow/out-of-range. Non-`static` — also used by `interval.c`/`datetime.c` in pgtypeslib. |
| `timestamp PGTYPEStimestamp_from_asc(char *str, char **endptr)` | timestamp.c:201 | Parse ASCII to timestamp; sets `errno` and returns 0 on failure. |
| `char *PGTYPEStimestamp_to_asc(timestamp tstamp)` | timestamp.c:267 | Format to ISO string; `pgtypes_strdup` result (caller frees). |
| `void PGTYPEStimestamp_current(timestamp *ts)` | timestamp.c:289 | Fill `*ts` with current local datetime. |
| `int PGTYPEStimestamp_fmt_asc(timestamp *ts, char *output, int str_len, const char *fmtstr)` | timestamp.c:777 | strftime-like format into caller buffer of size `str_len`. |
| `int PGTYPEStimestamp_sub(timestamp *ts1, timestamp *ts2, interval *iv)` | timestamp.c:792 | `iv = ts1 - ts2` (microsecond delta, month=0); rejects non-finite. |
| `int PGTYPEStimestamp_defmt_asc(const char *str, const char *fmt, timestamp *d)` | timestamp.c:805 | strptime-like parse; default fmt `"%Y-%m-%d %H:%M:%S"`. |
| `int PGTYPEStimestamp_add_interval(timestamp *tin, interval *span, timestamp *tout)` | timestamp.c:857 | `tout = tin + span`; handles month carry + end-of-month clamp. |
| `int PGTYPEStimestamp_sub_interval(timestamp *tin, interval *span, timestamp *tout)` | timestamp.c:912 | Negates span, delegates to add. |

## Internal landmarks
- `time2t` (timestamp.c:16) packs h/m/s/fsec into int64 microseconds;
  `dt2local` (timestamp.c:22) applies a tz offset. `[verified-by-code]`
- `tm2timestamp` (timestamp.c:38) is the tm→timestamp client copy: it computes
  `dDate = date2j(...) - date2j(2000,1,1)` (J2000 base), then
  `*result = dDate*USECS_PER_DAY + time` guarded by `pg_mul_s64_overflow` /
  `pg_add_s64_overflow` (timestamp.c:49-50) and a final `IS_VALID_TIMESTAMP`
  check (timestamp.c:56). `[verified-by-code]`
- `timestamp2tm` (timestamp.c:89, `static`) is the reverse client copy; uses
  `TMODULO` to split into date/time, rotates into local zone via
  `localtime_r` under `HAVE_STRUCT_TM_TM_ZONE` / `HAVE_INT_TIMEZONE`
  (timestamp.c:129-162). `[verified-by-code]`
- `SetEpochTimestamp` (timestamp.c:62) materializes the Unix-epoch timestamp
  via `GetEpochTime`; called per-`%s` inside the formatter. `[verified-by-code]`
- `EncodeSpecialTimestamp` (timestamp.c:190) handles `-infinity`/`+infinity`,
  `abort()`s on anything else. `[verified-by-code]`
- `dttofmtasc_replace` (timestamp.c:299-774) is the strftime dispatcher: a
  per-conversion `switch (*p)` filling a `union un_fmt_comb replace_val` +
  `replace_type`, then calling `pgtypes_fmt_replace` (timestamp.c:755). Many
  conversions (`%E %G %g %U %V %W %x %X %z %Z`) delegate to libc `strftime`,
  temporarily decrementing `tm->tm_mon` to libc's 0-based convention around
  each call (e.g. timestamp.c:399/408). Recursive composites: `%D`→`"%m/%d/%y"`,
  `%r`→`"%I:%M:%S %p"`, `%R`, `%T`. `[verified-by-code]`
- `PGTYPEStimestamp_defmt_asc` (timestamp.c:805) seeds out-params with
  impossible sentinels (year/month/day = -1, etc.) and hands off to
  `PGTYPEStimestamp_defmt_scan` (declared elsewhere; the actual scanner lives
  in `dt_common.c`). `[verified-by-code]` timestamp.c:841

## Invariants & gotchas
- **int64 microsecond representation, J2000 epoch.** `timestamp` is int64 µs
  relative to 2000-01-01 (`date2j(2000,1,1)`, timestamp.c:47,100). The legacy
  float8/`HAVE_INT64_TIMESTAMP` dual-representation era is gone here: all paths
  use `int64`/`USECS_PER_*`. Do not reintroduce float timestamp assumptions.
  `[verified-by-code]` timestamp.c:16-27,47-48
- **Client copy of backend `timestamp.c` — drift risk.** `tm2timestamp` and
  `timestamp2tm` duplicate backend `src/backend/utils/adt/timestamp.c` logic.
  Fixes to overflow handling, epoch math, or tz rotation in the backend must be
  manually mirrored here; the two can silently diverge. `[inferred]`
  timestamp.c:29-183
- **Overflow guards are present in `tm2timestamp` but not in arithmetic.**
  `tm2timestamp` uses `pg_mul_s64_overflow`/`pg_add_s64_overflow`
  (timestamp.c:49-50). However `PGTYPEStimestamp_sub` (timestamp.c:798,
  `iv->time = *ts1 - *ts2`) and `PGTYPEStimestamp_add_interval`
  (timestamp.c:894, `*tin += span->time`) do plain int64 +/- with no overflow
  check. `[verified-by-code]`
- **strftime buffer accounting.** Each direct write decrements `*pstr_len`
  and advances `q`, always keeping at least 1 byte for `'\0'` (the
  `*pstr_len > 1` guards, e.g. timestamp.c:733-752,761-769). The libc
  `strftime` branches pass the *remaining* `*pstr_len` and treat a 0 return as
  overflow → `-1`. The literal-`%`-at-end case returns -1 (timestamp.c:721-727).
  `[verified-by-code]`
- **tm_mon convention juggling.** Internally `tm->tm_mon` is 1-based; every
  libc-`strftime` delegation temporarily does `tm->tm_mon -= 1` then restores
  `+= 1`. A delegation that returns early without restoring would corrupt the
  month for later conversions (none currently do). `[verified-by-code]`
  timestamp.c:399-408 et al.
- **`%I`/`%l` 12-hour bug class.** `tm->tm_hour % 12` (timestamp.c:465,492)
  yields 0 for both noon and midnight rather than 12 — a known
  strftime-fidelity wart, not corrected here. `[verified-by-code]`

## Cross-refs
- [[dt_common.c]], [[interval.c]], [[datetime.c]]

## Potential issues
- **[ISSUE-overflow: unchecked int64 subtraction in `PGTYPEStimestamp_sub`]**
  `timestamp.c:798` — `iv->time = (*ts1 - *ts2)` over two finite int64
  timestamps can overflow int64 (e.g. far-future minus far-past) without
  detection, producing a wrong interval; severity low-moderate (client-side,
  inputs already range-checked at parse so practical range is bounded by
  `IS_VALID_TIMESTAMP`, but the difference can still exceed that bound).
- **[ISSUE-overflow: unchecked int64 add in `PGTYPEStimestamp_add_interval`]**
  `timestamp.c:894` — `*tin += span->time` adds the interval's microsecond
  field with no `pg_add_s64_overflow` guard and no post-add
  `IS_VALID_TIMESTAMP` recheck, so adding a large interval can wrap silently;
  contrast the careful guards in `tm2timestamp` (timestamp.c:49-50). Severity
  low-moderate.
- **[ISSUE-correctness: `%s` epoch uses float division]**
  `timestamp.c:547` — `replace_val.int64_val = (*ts - SetEpochTimestamp()) / 1000000.0`
  divides via `double`, losing precision for large second counts before
  truncating back to int64; severity low (cosmetic for the formatter).
