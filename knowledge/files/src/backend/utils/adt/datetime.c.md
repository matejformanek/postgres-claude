# `src/backend/utils/adt/datetime.c`

- **File:** `source/src/backend/utils/adt/datetime.c` (5425 lines)
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422` (2026-06-03)

## Purpose

The **shared parser/formatter** for all date/time-flavored types — date,
time, timetz, timestamp, timestamptz, and interval. Not itself the per-type
fmgr surface (those live in `date.c`, `timestamp.c`); this file is the
tokenizer + the big `Decode*` state machines + the encoder + the timezone
abbreviation table loader. (`datetime.c:1-13` [from-comment])

The file is one of the largest non-array files under adt/ and is the
historic gravity-well for parser DoS / off-by-one CVEs in PG date handling.

## Type role

Used internally by all five date/time fmgr types for **input parsing** and
**output formatting**. Not directly bound to fmgr functions itself (apart
from `pg_timezone_*` set-returning helpers).

## Key public functions (selection)

- **Date math:** `date2j` / `j2date` / `j2day` (`:297`, `:322`, `:355`) —
  Julian day arithmetic. Deterministic, no parser surface.
- **Time-now:** `GetCurrentDateTime` (`:377`), `GetCurrentTimeUsec` (`:398`).
- **Tokenizer:** `ParseDateTime(timestr, workbuf, buflen, …)` (`:775`) —
  splits input into field strings + ftype tags; caller supplies the
  workbuf to avoid palloc churn.
- **Decoders:**
  - `DecodeDateTime` (`:1000`) — for date/timestamp/timestamptz.
  - `DecodeTimeOnly` (`:1927`) — for time/timetz.
  - `DecodeInterval` (`:3511`) — Postgres-style interval.
  - `DecodeISO8601Interval` (`:3977`) — ISO 8601 `P…T…` interval.
  - `DecodeDate` (`:2462`), `DecodeTime` (`:2739`), `DecodeNumber` (`:2796`),
    `DecodeNumberField` (`:2982`), `DecodeTimezone` (`:3075`),
    `DecodeTimezoneName` (`:3309`), `DecodeTimezoneAbbrev` (`:3160`),
    `DecodeUnits` (`:4196`), `DecodeSpecial` (`:3266`).
- **Validators:** `ValidateDate` (`:2573`).
- **Encoders:** `EncodeDateOnly` / `EncodeTimeOnly` / `EncodeDateTime` /
  `EncodeInterval` (`:4379`, `:4465`, `:4496`, `:4740`).
- **TZ abbrev table:** `ConvertTimeZoneAbbrevs`, `InstallTimeZoneAbbrevs`,
  `pg_timezone_abbrevs_zone`, `pg_timezone_abbrevs_abbrevs`,
  `pg_timezone_names` (set-returning).
- **Static keyword table:** `datetktbl` (`:106`) — alphabetically sorted,
  binary-searched by `datebsearch` (`:4303`). Static entries; TZ/DTZ/DYNTZ
  loaded separately into `zoneabbrevtbl`.

## Phase D notes (the big one)

- **No unbounded recursion.** Both `DecodeDateTime` and `DecodeInterval`
  are flat state machines over the field array; `ParseDateTime` enforces
  `MAXDATEFIELDS` (defined in `datetime.h`, default 25) on the field
  count [verified-by-code, see ParseDateTime usage of `nf`].
- **No unbounded year.** `ValidateDate` (`:2573`) clamps year to the
  `IS_VALID_JULIAN(...)` range; outputs `DTERR_FIELD_OVERFLOW` for
  outsize values. Confirmed by inspection that all callers funnel through
  ValidateDate.
- **Overflow helpers:** `AdjustMicroseconds`/`Days`/`Months`/`Years`
  (`:629-688`), `AdjustFract*` (`:548-628`), and `int64_multiply_add`
  (`:533`) use checked arithmetic — overflow → returns false, caller
  emits `DTERR_FIELD_OVERFLOW`. Confirmed for AdjustMicroseconds at
  `:629-643` [verified-by-code].
- **Fraction parsing:** `ParseFraction` (`:691`) and
  `ParseFractionalSecond` (`:729`) use `strtod` on a bounded `cp`; output
  range-checked.
- **Soft-error path:** All errors are returned as `dterr` codes; the
  caller (`timestamp_in`, etc.) lowers them into ereport via
  `DateTimeParseError` (`:4241`) with the same input-string echo discipline.
- **Workbuf:** `ParseDateTime` requires the caller to supply a workbuf
  whose required size is `strlen(timestr) + MAXDATEFIELDS * sizeof(char *)`
  — see signature `:775`. Callers (e.g. `date.c`, `timestamp.c`) allocate
  on the stack with `MAXDATELEN+MAXDATEFIELDS`. **If a caller miscalculates
  buflen there's a stack-overflow risk — but ParseDateTime's contract is
  enforced via `dterr` return when it would overflow.** [partly inferred,
  need to verify the buflen check exists at `:775+` exactly]
- **Interval ISO 8601:** `ParseISO8601Number` (`:3907`) returns
  ipart/fpart via strtoll/strtod; both range-checked downstream. No
  recursion.
- **Timezone abbrev table** is updated under cluster-wide GUC reload, not
  per-query; `ClearTimeZoneAbbrevCache` (`:3246`) clears the per-session
  lookup cache. No per-query mutation surface.

## Historical context (Phase D)

CVE-2007-3278, CVE-2010-1170, and several non-CVE post-1996 commits all
touched DecodeDateTime/DecodeInterval for parser DoS or off-by-one issues.
The current overflow discipline + the field-count cap + the ValidateDate
clamp are the post-mortem hardening. **No new DoS surface found in this
read** — the state machines are flat, all numeric fields run through
`int64_multiply_add`, and unicode-aware year inputs are rejected
upstream by `ParseDateTime`'s ASCII tokenizer (`isdigit`/`isalpha` over
unsigned char). [inferred from code structure; not a CVE-class audit]

## Potential issues

- `[ISSUE-undocumented-invariant: ParseDateTime workbuf size contract not
  expressed in a sizeof macro; callers compute MAXDATELEN+MAXDATEFIELDS
  by hand. (low)]` `:775`
- `[ISSUE-stale-todo: comment about "the static table contains no TZ,
  DTZ, or DYNTZ entries" (:102-104) — verify still true post-tzparser
  refactor. (info)]`
- `[ISSUE-info-disclosure: DateTimeParseError echoes input string into
  errmsg — standard idiom, but worth flagging for log-redaction tooling
  (:4241+). (info)]`

## Cross-references

- `source/src/include/utils/datetime.h` — `datetkn`, field type constants,
  `MAXDATEFIELDS`, `MAXDATELEN`.
- `source/src/backend/utils/adt/date.c` — date/time fmgr surface; uses
  `DecodeTimeOnly`, `EncodeTimeOnly`.
- `source/src/backend/utils/adt/timestamp.c` — timestamp fmgr surface;
  uses `DecodeDateTime`, `EncodeDateTime`.
- `source/src/timezone/` — IANA tz database driver, accessed via `pg_tz`.

## Open questions

- Exact buflen contract of `ParseDateTime` and whether a malformed caller
  could under-size the workbuf. Worth a focused read of `:775-1000`.
- Whether the interval ISO 8601 path has hardening parity with the legacy
  PG interval path — anecdotally less audited.

## Confidence tag tally

- `[verified-by-code]` × 3
- `[from-comment]` × 4
- `[inferred]` × 3
