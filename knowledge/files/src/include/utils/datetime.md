# utils/datetime.h — date/time parsing + decoding shared infrastructure

Source: `source/src/include/utils/datetime.h` (371 lines)
Source pin: `4b0bf0788b066a4ca1d4f959566678e44ec93422`

## Role

Shared by date, time, timestamp, timestamptz, interval: token tables, field-type and DTK_* token codes, bitmask helpers, the `ParseDateTime` / `DecodeDateTime` / `DecodeTimeOnly` / `DecodeInterval` / `DecodeISO8601Interval` API, `DateTimeParseError` and DTERR_* error codes, time zone abbreviation table machinery, encoding (`EncodeDateOnly` etc.), and the Gregorian-rules `isleap` macro.

## Public API

- **Constants**: `MAXDATELEN=128`, `MAXDATEFIELDS=25`, `TOKMAXLEN=10` (`datetime.h:200-204`).
- **Field type codes** (`datetime.h:90-124`): `RESERV/MONTH/YEAR/DAY/JULIAN/TZ/DTZ/DYNTZ/IGNORE_DTF/AMPM/HOUR/MINUTE/SECOND/MILLISECOND/MICROSECOND/DOY/DOW/UNITS/ADBC/AGO/ABS_BEFORE/ABS_AFTER/ISODATE/ISOTIME/WEEK/DECADE/CENTURY/MILLENNIUM/DTZMOD/UNKNOWN_FIELD`.
- **DTK_* token codes** (`datetime.h:141-181`): for `datetktbl` entries.
- **`datetkn`** struct (`datetime.h:207-212`): `{ char token[11]; char type; int32 value; }` — the static token table layout.
- **`TimeZoneAbbrevTable`** (`datetime.h:215-221`): flexible-array installable abbrev table.
- **`DynamicZoneAbbrev`** (`datetime.h:224-228`).
- **DTERR_*** error codes (`datetime.h:284-290`): `BAD_FORMAT`, `FIELD_OVERFLOW`, `MD_FIELD_OVERFLOW`, `INTERVAL_OVERFLOW`, `TZDISP_OVERFLOW`, `BAD_TIMEZONE`, `BAD_ZONE_ABBREV`.
- **`DateTimeErrorExtra`** (`datetime.h:292-298`).
- **Parse/decode API** (`datetime.h:306-353`): `GetCurrentDateTime`, `GetCurrentTimeUsec`, `j2date`, `date2j`, `ParseDateTime`, `DecodeDateTime`, `DecodeTimezone`, `DecodeTimeOnly`, `DecodeInterval`, `DecodeISO8601Interval`, `DateTimeParseError`, `DetermineTimeZoneOffset/Abbrev*`, `EncodeDateOnly/TimeOnly/DateTime/Interval/SpecialTimestamp`, `ValidateDate`, `DecodeTimezoneAbbrev/Special/Units/Name/NameToTz/AbbrevPrefix`, `ClearTimeZoneAbbrevCache`, `j2day`, `TemporalSimplify`, `CheckDateTokenTables`, `ConvertTimeZoneAbbrevs`, `InstallTimeZoneAbbrevs`, `AdjustTimestampForTypmod`.
- **`isleap(y)`** macro (`datetime.h:273`).
- **`FMODULO`/`TMODULO`** macros (`datetime.h:238-254`).

## Invariants

- **INV-datetime-bitmask-fits-int** [from-comment, `datetime.h:81-87`]: "Can't have more of these than there are bits in an unsigned int." YEAR/MONTH/DAY/HOUR/MINUTE/SECOND must be in [0, 14] so they fit in the left half of INTERVAL's typmod — "you can't change them without initdb!"
- **INV-datetktbl-restrict-to-31** [from-comment, `datetime.h:131-133`]: most DTK_* values used in bitmasks must be in [0, 31]; some are allowed higher because they're never used as masks.
- **INV-MAXDATELEN-sufficient** [from-comment, `datetime.h:194-198`]: 128 must suffice for all possible output (interval_out is ~90 bytes worst case). Longer outputs overrun.
- **INV-Gregorian-only** [from-comment, `datetime.h:265-272`]: ALL years use Gregorian rules per SQL standard — even pre-1582. Date 1500-02-29 is REJECTED (Julian-valid but not Gregorian).
- **INV-int64-C99-division** [from-comment, `datetime.h:247-249`]: `TMODULO` assumes C99 semantics (negative quotients truncate toward zero). PG abandons pre-C99 compilers.
- **INV-FMODULO-floating-broken-modf** [from-comment, `datetime.h:233-237`]: `modf` was broken on some platforms historically; FMODULO replaces it.

## Trust-boundary / Phase-D surface

- **A7 datetime.c parser-DoS defenses** [from-corpus, CVE-2007-3278 + CVE-2010-1170 lineage]: `ParseDateTime` operates on a fixed-size `workbuf` (`datetime.h:311-313`) of `buflen` bytes; if a caller under-allocates, the parser writes past it. The header doesn't restate the "must be at least `strlen(timestr) + MAXDATEFIELDS` bytes" rule that the implementation requires.
- **`MAXDATELEN=128` is a CALLER buffer-size contract** (`datetime.h:200`): every `Encode*` function expects a 128-byte buffer at minimum. Callers passing smaller buffers overrun silently.
- **DTERR_* must be passed through `DateTimeParseError`** (`datetime.h:326-328`) — calling ereport directly with a DTERR_* value bypasses the BAD_TIMEZONE / BAD_ZONE_ABBREV extra-info path and produces a misleading message.
- **`InstallTimeZoneAbbrevs`** (`datetime.h:366`): replaces a shared-memory table; not safe to call from a non-primary backend without external sync (only one path, in postmaster startup).

## Cross-refs

- `source/src/backend/utils/adt/datetime.c` — implementation; the A7 DoS history lives there.
- `source/src/backend/utils/adt/timestamp.c`, `date.c`, `time.c` — consumers.
- `source/src/timezone/` — zic-format tz database.

## Issues

- `[ISSUE-DOC: workbuf sizing contract not surfaced (high)]` — `ParseDateTime` requires the caller's `workbuf` to be `>= strlen(timestr) + MAXDATEFIELDS*K` bytes; the header just says "workbuf" with no size discipline. Mis-sized buffers were a 2007/2010 CVE family.
- `[ISSUE-INVARIANT: bitmask field-code range tied to typmod (high)]` — `datetime.h:81-87` says you can't change YEAR/MONTH/DAY/HOUR/MINUTE/SECOND ordering without initdb. Worth an explicit `StaticAssert` somewhere.
- `[ISSUE-DOC: MAXDATELEN as caller-buffer-size (medium)]` — `EncodeDateOnly/TimeOnly/DateTime/Interval` expect ≥128-byte buffers; not stated in the prototype comments.
