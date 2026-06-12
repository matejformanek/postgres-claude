---
path: src/interfaces/ecpg/pgtypeslib/dt_common.c
anchor_sha: e18b0cb7344cb4bd28468f6c0aeeb9b9241d30aa
loc: 3027
depth: deep
---

# `dt_common.c` — client-side date/time token tables + decode/encode workhorse for pgtypeslib

## Purpose
This is the shared date/time engine for the ECPG `pgtypes` library — the
client-side date, timestamp, and interval types used by embedded-SQL programs.
It carries a self-contained copy of the backend's datetime parsing and
formatting machinery so that ECPG programs can interpret and render
date/time values without a server round-trip. It defines the two big lexical
token tables (`datetktbl[]` for absolute dates/timezones, `deltatktbl[]` for
interval units), the month/day name arrays, the Julian-day conversion
primitives (`date2j`/`j2date`), the field decoders (`DecodeDateTime`,
`DecodeDate`, `DecodeTime`, `DecodeNumber`, `DecodeNumberField`,
`DecodeTimezone`), the tokenizer `ParseDateTime`, and the encoders
(`EncodeDateOnly`, `EncodeDateTime`). It also implements a `strptime`-style
format scanner `PGTYPEStimestamp_defmt_scan` used by the timestamp parse-from-
format path [verified-by-code dt_common.c:2534].

This file is, by design, a near-verbatim fork of backend
`src/backend/utils/adt/datetime.c` logic, simplified for the client (no
GUC-driven session timezone, no full TZ database, `errno`-based error
reporting instead of `ereport`). That duplication is its dominant maintenance
hazard — see Invariants & gotchas [inferred].

## Public symbols
| Symbol | Site | Notes |
|---|---|---|
| `const int day_tab[2][13]` | dt_common.c:14 | Days-per-month, [0]=common [1]=leap; trailing 0 sentinel. Used for day-of-month range checks. |
| `int date2j(int y, int m, int d)` | dt_common.c:581 | Gregorian (y,m,d) → Julian day number; overflow-safe to 2^31-1. |
| `void j2date(int jd, int *year, int *month, int *day)` | dt_common.c:606 | Inverse of `date2j`. |
| `int DecodeUnits(int field, char *lowtoken, int *val)` | dt_common.c:536 | Binary-searches `deltatktbl[]` (interval units), per-field cache. |
| `void EncodeDateOnly(struct tm *, int style, char *str, bool EuroDates)` | dt_common.c:671 | Date-only formatting in ISO/SQL/German/Postgres styles. |
| `void TrimTrailingZeros(char *str)` | dt_common.c:724 | Strips trailing fractional-second zeros, keeping >=2 frac digits. |
| `void EncodeDateTime(struct tm *, fsec_t, bool print_tz, int tz, const char *tzn, int style, char *str, bool EuroDates)` | dt_common.c:756 | Full date+time formatter, four styles. |
| `int GetEpochTime(struct tm *tm)` | dt_common.c:952 | Fills tm with Unix epoch via `gmtime_r`. |
| `void GetCurrentDateTime(struct tm *tm)` | dt_common.c:1063 | Current local time via static `abstime2tm`. |
| `void dt2time(double jd, int *hour,*min,*sec, fsec_t *fsec)` | dt_common.c:1071 | Splits a microsecond count into h/m/s/fsec. |
| `int DecodeTime(char *str, int *tmask, struct tm *, fsec_t *fsec)` | dt_common.c:1444 | Parses `hh:mm[:ss[.ffffff]]`; range-checks min/sec. |
| `int ParseDateTime(char *timestr, char *lowstr, char **field, int *ftype, int *numfields, char **endstr)` | dt_common.c:1610 | Tokenizer: splits input into typed fields into caller-supplied `lowstr` buffer. |
| `int DecodeDateTime(char **field, int *ftype, int nf, int *dtype, struct tm *, fsec_t *fsec, bool EuroDates)` | dt_common.c:1793 | Master field interpreter; returns 0 full date, 1 time-only, -1 error. |
| `int PGTYPEStimestamp_defmt_scan(char **str, char *fmt, timestamp *d, int *year,*month,*day,*hour,*minute,*second,*tz)` | dt_common.c:2534 | `strptime`-style parse of a timestamp from a format string. |
| `char *months[]`, `char *days[]`, `char *pgtypes_date_weekdays_short[]`, `char *pgtypes_date_months[]` | dt_common.c:493-499 | Public English name arrays (short month, full weekday, short weekday, full month), NULL-terminated. |

## Internal landmarks
- **`datetktbl[]`** (dt_common.c:20) — the master absolute-token table:
  ~400 entries of `{text, token, lexval}` covering reserved words
  (`epoch`, `now`, `today`, `infinity`), month names, weekday names, AM/PM,
  units, and a very large timezone-abbreviation set. `#if 0` blocks mark
  removed/ambiguous abbreviations.
- **`deltatktbl[]`** (dt_common.c:421) — interval-unit token table
  (century/decade/year/.../microsecond and the `ago` modifier).
- **`szdatetktbl` / `szdeltatktbl`** (dt_common.c:486-487) — `lengthof` of each.
- **`datecache[]` / `deltacache[]`** (dt_common.c:489-491) — per-field
  one-slot lookup caches, indexed by field position, exploiting the fact that
  successive dates tend to share a format.
- **`datebsearch`** (dt_common.c:501) — the binary search both
  `DecodeSpecial`/`DecodeUnits` rely on; prechecks first char, then `strncmp`
  to `TOKMAXLEN` so truncated tokens match.
- **Static decoders:** `DecodeSpecial` (636), `DecodeNumberField` (1093),
  `DecodeNumber` (1204), `DecodeDate` (1314), `DecodeTimezone` (1510),
  `DecodePosixTimezone` (1556).
- **Static time helpers:** `abstime2tm` (976), with three platform branches
  (`HAVE_STRUCT_TM_TM_ZONE` / `HAVE_INT_TIMEZONE` / neither → UTC).
- **Format-scan helpers:** `find_end_token` (2367) and `pgtypes_defmt_scan`
  (2472) underpin `PGTYPEStimestamp_defmt_scan`; the big `switch (*pfmt)` at
  dt_common.c:2577 implements the strftime-letter vocabulary, with `%D %r %R %T`
  recursing by rewriting into a sub-format string (e.g. dt_common.c:2677).

## Invariants & gotchas
- **Token tables MUST stay sorted by `token` (ASCII, lowercase).**
  Both `datetktbl[]` and `deltatktbl[]` are consumed only via
  `datebsearch` (dt_common.c:501), which assumes ascending order. An
  out-of-order insertion silently makes that token (and possibly neighbours)
  un-findable — the classic datetime-table bug. [verified-by-code dt_common.c:510-526]
- **`datebsearch` matches on `TOKMAXLEN`-truncated tokens** (dt_common.c:518):
  table text is stored truncated to `TOKMAXLEN`, so longer input words match
  their prefix. Adding a token longer than `TOKMAXLEN` that collides on its
  prefix with an existing one is a silent hazard. [verified-by-code]
- **Field-mask discipline:** decoders accumulate a `fmask` of which fields are
  set and reject duplicates (`if (tmask & fmask) return -1;`,
  dt_common.c:2307). `DTK_DATE_M` / `DTK_TIME_M` are the "complete set" masks;
  the final completeness/validity gate is dt_common.c:2336-2355.
- **2-digit-year windowing is hard-coded:** `< 70 → +2000`, else `< 100 →
  +1900`. This appears in *three* places that must agree —
  `DecodeDate` (dt_common.c:1426-1432), `DecodeDateTime`
  (dt_common.c:2320-2326), and (with a different `< 100 → +1900`-only rule)
  the format scanner at dt_common.c:2703. [verified-by-code]
- **Client-side fork of backend `datetime.c` — drift risk.** The fsec handling
  comment explicitly notes a behavior divergence: this code *truncates* the
  seventh fractional digit where "the backend does" rounding
  (dt_common.c:1115, dt_common.c:1481). Any fix or new abbreviation in backend
  `datetime.c` does NOT propagate here automatically. [from-comment]
- **`EncodeDateOnly`/`EncodeDateTime` write into a caller buffer with no length
  argument** and build the string with chained `sprintf`/`sprintf(str+offset)`
  / `sprintf(str+strlen(str))` (e.g. dt_common.c:681, 695, 784). Correctness
  depends entirely on the caller sizing `str` for the worst case (BC suffix +
  6-digit fsec + timezone name up to `MAXTZLEN`). No bounds check exists here. [verified-by-code]
- **`ParseDateTime` requires `lowstr` of at least `strlen(timestr) +
  MAXDATEFIELDS` bytes** and writes a NUL after each field (dt_common.c:1606,
  dt_common.c:1762); under-sizing overflows silently. `field[]`/`ftype[]` must
  hold `MAXDATEFIELDS`. [from-comment / verified-by-code]
- **`%z` / `%Z` timezone scan** (dt_common.c:2915, 2925): `%Z` does a *linear*
  scan over `datetktbl` matching only `TZ`/`DTZ` entries via `pg_strcasecmp`
  (not the binary search), so it tolerates the table's sort order but is O(n).

## Cross-refs
- [[datetime.c]] — the backend original this file forks; primary drift source.
- [[timestamp.c]] — pgtypeslib timestamp type; calls `EncodeDateTime`,
  `tm2timestamp`, `PGTYPEStimestamp_defmt_scan`.
- [[interval.c]] — pgtypeslib interval type; consumer of `DecodeUnits` /
  `deltatktbl`.
- [[numeric.c]] — sibling pgtypeslib type module.
- `dt.h`, `pgtypeslib_extern.h` — token/mask macros (`DTK_*`, `TOKMAXLEN`,
  `MAXDATEFIELDS`) and `pgtypes_alloc`/`pgtypes_strdup`.

## Potential issues
- **[ISSUE-bounds: unbounded sprintf into caller buffer]** `dt_common.c:756`
  (and `dt_common.c:671`) — `EncodeDateTime`/`EncodeDateOnly` take a `char *str`
  with no size and emit via chained `sprintf`. Safe only if every caller sizes
  the buffer for the maximal output (BC + full fsec + `MAXTZLEN` tzn). A
  caller passing an undersized buffer overflows with no diagnostic. Medium
  severity (callers are in-tree, but the contract is implicit). [verified-by-code]
- **[ISSUE-correctness: fsec truncation vs backend rounding]**
  `dt_common.c:1115` / `dt_common.c:1481` — sub-second parsing truncates the
  7th fractional digit whereas backend `datetime.c` rounds. ECPG clients can
  thus disagree with the server by 1 microsecond on the same literal. Low
  severity but a genuine client/server divergence, called out in-code as `XXX`. [from-comment]
- **[ISSUE-maintainability: silent table-sort invariant]**
  `dt_common.c:20` / `dt_common.c:421` — the two large token tables have no
  build-time sortedness assertion; correctness of every `datebsearch` lookup
  rests on hand-maintained ASCII order. A mis-ordered insert fails silently
  (token simply not found). Low-to-medium severity given the size of
  `datetktbl[]` (~400 entries). [verified-by-code]
- **[ISSUE-drift: divergent client copy of datetime.c]**
  whole file — this is a long-lived fork of backend datetime logic; new
  reserved words, timezone abbreviations, or parsing fixes landing in
  `datetime.c` will not reach ECPG clients unless manually mirrored here. Low
  severity per-change but cumulative. [inferred]
