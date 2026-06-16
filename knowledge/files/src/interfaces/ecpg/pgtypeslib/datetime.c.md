---
path: src/interfaces/ecpg/pgtypeslib/datetime.c
anchor_sha: e18b0cb7344cb4bd28468f6c0aeeb9b9241d30aa
loc: 713
depth: deep
---

# `datetime.c` — client-side `date` type for ECPG pgtypeslib

## Purpose

Implements the `PGTYPESdate_*` API for the standalone `date` type used by ECPG
client programs (the `pgtypes` library), independent of any server connection.
`date` is a plain `int` holding days relative to the year-2000 epoch
(`date2j(2000,1,1)`) `[verified-by-code datetime.c:95,109]`. The file provides:
allocation (`PGTYPESdate_new`/`_free`); ascii parsing via the shared backend
datetime scanner (`PGTYPESdate_from_asc` uses `ParseDateTime`/`DecodeDateTime`,
datetime.c:70-71); ascii formatting (`PGTYPESdate_to_asc` via `EncodeDateOnly`,
datetime.c:110); conversion to/from the client `timestamp` type
(`PGTYPESdate_from_timestamp`, datetime.c:30); Julian/MDY helpers
(`PGTYPESdate_julmdy`, `PGTYPESdate_mdyjul`, datetime.c:114-135); current date
(`PGTYPESdate_today`, datetime.c:147); day-of-week (`PGTYPESdate_dayofweek`,
datetime.c:137); and the two custom format engines `PGTYPESdate_fmt_asc`
(datetime.c:167) and `PGTYPESdate_defmt_asc` (datetime.c:329) that handle
Informix-style `dd`/`mm`/`yy` format strings. It leans heavily on the
`date2j`/`j2date` Julian conversions and the month/weekday name tables from
`dt_common.c`.

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `date *PGTYPESdate_new(void)` | datetime.c:14 | `pgtypes_alloc(sizeof(date))`; may return NULL on OOM |
| `void PGTYPESdate_free(date *d)` | datetime.c:24 | plain `free` |
| `date PGTYPESdate_from_timestamp(timestamp dt)` | datetime.c:30 | microseconds→days; returns 0 for non-finite input |
| `date PGTYPESdate_from_asc(char *str, char **endptr)` | datetime.c:46 | parse via backend scanner; on error `errno=PGTYPES_DATE_BAD_DATE`, returns `INT_MIN` |
| `char *PGTYPESdate_to_asc(date dDate)` | datetime.c:100 | `j2date`+`EncodeDateOnly`; `pgtypes_strdup` result |
| `void PGTYPESdate_julmdy(date jd, int *mdy)` | datetime.c:114 | fills mdy[0]=month, mdy[1]=day, mdy[2]=year |
| `void PGTYPESdate_mdyjul(int *mdy, date *jdate)` | datetime.c:127 | inverse of julmdy |
| `int PGTYPESdate_dayofweek(date dDate)` | datetime.c:137 | 0=Sunday … 6=Saturday |
| `void PGTYPESdate_today(date *d)` | datetime.c:147 | `GetCurrentDateTime`; only writes `*d` if `errno==0` |
| `int PGTYPESdate_fmt_asc(date dDate, const char *fmtstring, char *outbuf)` | datetime.c:167 | format date into caller buffer; returns 0 / -1 (OOM) |
| `int PGTYPESdate_defmt_asc(date *d, const char *fmt, const char *str)` | datetime.c:329 | parse date per fmt; returns 0 / -1 (errno set) |

## Internal landmarks

- **Epoch offset convention**: every public conversion adds/subtracts
  `date2j(2000,1,1)` to translate between the stored day-count and a true Julian
  day number understood by `date2j`/`j2date` `[verified-by-code datetime.c:95,
  109,121,134,144,154,215,710]`.
- **`from_asc` reuses backend scanner**: `ParseDateTime` + `DecodeDateTime`
  (from `dt_common.c`/backend datetime code) tokenize the string; only
  `DTK_DATE` and `DTK_EPOCH` dtypes are accepted, everything else is a bad date
  (datetime.c:77-93). `EuroDates` is hardcoded `false` (datetime.c:61).
- **`fmt_asc` dispatcher** (datetime.c:218): walks a length-sorted `mapping[]`
  table (`ddd`,`dd`,`mmm`,`mm`,`yyyy`,`yy`) and repeatedly `strstr`-replaces
  each token in `outbuf` with the computed component, formatted via a
  `replace_type` switch (string-constant vs leading-zero uint). Weekday/month
  literals come from `pgtypes_date_weekdays_short` and `months` tables in
  `dt_common.c` (datetime.c:225,233).
- **`defmt_asc` order analysis** (datetime.c:356-405): locates `yy`/`mm`/`dd`
  in the fmt string to derive a 3-char `fmt_token_order` permutation. Has a
  no-delimiter special case for pure-digit 6- or 8-byte inputs (datetime.c:
  427-502) that re-inserts spaces; otherwise lowercases a strdup'd copy and
  tokenizes digit runs. Falls back to month-name / abbreviation matching
  (`pgtypes_date_months` then `months`, the "evil[tm] hack" at datetime.c:
  628-635) when fewer than 3 numeric tokens are found.

## Invariants & gotchas

- **Stored representation is days since 2000-01-01**, a signed `int`. Do not
  change the epoch base without touching every `date2j(2000,1,1)` site
  `[verified-by-code]`. `INT_MIN` is the sentinel "bad date" return for
  `from_asc` (datetime.c:67,74,86,92).
- **Error discipline is errno-based**: `from_asc` sets `PGTYPES_DATE_BAD_DATE`;
  `defmt_asc` sets `PGTYPES_DATE_ERR_EARGS`, `_ENOSHORTDATE`, `_ENOTDMY`,
  `_BAD_DAY`, `_BAD_MONTH`. Callers must check `errno`, since the in-band return
  (`INT_MIN` / `-1`) overlaps valid-looking values in some APIs
  `[verified-by-code datetime.c:64-708]`.
- **`from_asc` length guard**: rejects `strlen(str) > MAXDATELEN` before parsing
  (datetime.c:64). The `lowstr` scratch buffer is `MAXDATELEN + MAXDATEFIELDS`
  (datetime.c:57), matching backend `datetime.c` sizing.
- **`fmt_asc` writes into a caller-supplied `outbuf` with no length argument**:
  it `strcpy`s `fmtstring` into `outbuf` (datetime.c:212) then grows it as tokens
  expand (e.g. `yyyy`→4 digits is same width, but `mmm`/`ddd`→3-char names, and
  numeric replacements are bounded by `PGTYPES_DATE_NUM_MAX_DIGITS`=20). Buffer
  sizing is entirely the caller's responsibility — see Potential issues.
- **`defmt_asc` range validation** is partial: it checks `tm_mday` in 1..31,
  `tm_mon` in 1..MONTHS_PER_YEAR, rejects day 31 in 30-day months, and rejects
  Feb > 29 (datetime.c:686-708) — but it does **not** validate Feb 29 against
  leap years, nor does it validate the parsed year. `date2j` is then trusted to
  produce a value (datetime.c:710).
- **`today` leaves `*d` unwritten on error** (datetime.c:153): if
  `GetCurrentDateTime` sets errno, the caller's `date` is untouched (possibly
  uninitialized). [inferred] callers should pre-zero or check errno.
- **`from_timestamp` returns 0 for non-finite input** with only a "suppress
  compiler warning" comment (datetime.c:35-43); no error is signaled, so a
  `+/-infinity` timestamp silently maps to the 2000-01-01 epoch date
  `[verified-by-code]`.

## Cross-refs

- [[dt_common.c]] — `date2j`/`j2date`, `ParseDateTime`, `DecodeDateTime`,
  `EncodeDateOnly`, `GetCurrentDateTime`, and the `months` /
  `pgtypes_date_months` / `pgtypes_date_weekdays_short` name tables this file
  consumes.
- [[timestamp.c]] — client `timestamp` type bridged by `from_timestamp`.
- [[interval.c]] — sibling pgtypeslib client type.

<!-- issues:auto:begin -->
- [Issue register — `ecpg`](../../../../../issues/ecpg.md)
<!-- issues:auto:end -->

## Potential issues

- **[ISSUE-overflow: unbounded `outbuf` in `fmt_asc`]** `datetime.c:168,212` —
  `PGTYPESdate_fmt_asc` takes no buffer-size argument; it `strcpy`s the format
  string into `outbuf` and expands tokens in place. A caller who sizes `outbuf`
  to `strlen(fmtstring)` will overflow whenever a token expands (`mmm`/`ddd`
  literal, `yyyy` from a `yy` pattern is fine, but month/weekday names and the
  digit replacements via `memcpy(start_pattern, t, strlen(t))` at datetime.c:
  260,273,285,297 can grow the string). Severity: medium — documented API
  contract (callers must oversize), but easy to misuse; no internal bound check.
- **[ISSUE-correctness: missing leap-year check in `defmt_asc`]**
  `datetime.c:704-708` — Feb is only rejected for day > 29, so `Feb 29` in a
  non-leap year is accepted and passed to `date2j`, yielding a normalized
  (rolled-over, Mar 1) date rather than an error. Severity: low — backend
  `date_in` would reject this; client-side `defmt_asc` silently normalizes.
- **[ISSUE-style: `defmt_asc` does not validate year range]**
  `datetime.c:681-682,710` — `tm_year` is taken from `strtol` (or left 0 if the
  token failed) with no bounds check before `date2j`; a 2-digit-year input is
  taken literally (e.g. `yy=99` → year 99, not 1999). Severity: low —
  behavioral, matches Informix legacy semantics [inferred].
