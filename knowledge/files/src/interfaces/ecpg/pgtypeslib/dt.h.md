---
path: src/interfaces/ecpg/pgtypeslib/dt.h
anchor_sha: e18b0cb7344cb4bd28468f6c0aeeb9b9241d30aa
loc: 343
depth: read
---

# `dt.h` — date/time macro + token-type header for ECPG pgtypeslib

## Purpose
The shared date/time constant/macro header for the client-side `pgtypeslib`.
It is a deliberate, hand-copied subset of the backend's
`src/include/utils/datetime.h`: the field-type codes (`RESERV`, `MONTH`,
`YEAR`, …), the token-type codes (`DTK_*`), the parse bit-mask macros
(`DTK_M`, `DTK_DATE_M`, …), the unit-per-day/hour/sec constants, the
`FMODULO`/`TMODULO` arithmetic macros, the Julian-date and timestamp validity
macros, and the `datetkn` lookup-table struct. It also prototypes the whole
internal date/time decode/encode API (`DecodeDateTime`, `EncodeDateTime`,
`date2j`, `j2date`, …) that the pgtypeslib `.c` files implement. Pure
declarations — no code. `[verified-by-code]`

## Public symbols
(all file-internal to pgtypeslib; this header is **not installed**)

| Symbol group | Site | Notes |
|---|---|---|
| `MAXTZLEN`, `fsec_t` | dt.h:10-12 | `fsec_t` is `int32` (fractional seconds, usec) `[verified-by-code]` |
| `USE_*_DATES` | dt.h:14-17 | DateStyle output selectors (POSTGRES/ISO/SQL/GERMAN) |
| `INTSTYLE_*` | dt.h:19-22 | IntervalStyle selectors |
| `INTERVAL_FULL_RANGE`, `INTERVAL_MASK`, `MAX_INTERVAL_PRECISION` | dt.h:24-26 | interval typmod helpers |
| `DTERR_*` | dt.h:28-32 | decode error returns; `DTERR_MD_FIELD_OVERFLOW` triggers a DateStyle hint `[from-comment]` |
| String tokens `DAGO`/`EPOCH`/`NOW`/… | dt.h:35-45 | special date words |
| Unit-name tokens `DMICROSEC`…`DTIMEZONE` | dt.h:47-62 | field unit names |
| Meridian/era: `AM`/`PM`/`HR24`, `AD`/`BC` | dt.h:71-76 | |
| **Field-type codes** `RESERV`…`UNKNOWN_FIELD` | dt.h:92-121 | meaning of a token; values 0..14 reserved for YEAR/MONTH/… so masks fit an interval typmod `[from-comment]` (dt.h:84-90) |
| **Token-type codes** `DTK_NUMBER`…`DTK_ISODOW` | dt.h:139-178 | the "value" stored in `datetktbl[]` entries |
| **Mask macros** `DTK_M`, `DTK_ALL_SECS_M`, `DTK_DATE_M`, `DTK_TIME_M` | dt.h:185-188 | `0x01 << t` bit masks |
| Buffer sizes `MAXDATELEN`(128), `MAXDATEFIELDS`(25), `TOKMAXLEN`(10) | dt.h:196-200 | working-buffer caps; oversize input rejected early `[from-comment]` |
| `datetkn` struct | dt.h:203-208 | `{char token[11]; char type; int32 value;}` lookup-table row |
| `FMODULO`, `TMODULO` | dt.h:218-234 | modf replacement / int64 timestamp split `[from-comment]` |
| Unit constants `DAYS_PER_YEAR`…`USECS_PER_SEC` | dt.h:237-263 | calendar/usec conversion factors |
| `isleap` | dt.h:269 | leap-year predicate |
| Julian macros `JULIAN_MINYEAR`…`IS_VALID_JULIAN` | dt.h:275-286 | |
| `MIN_TIMESTAMP`/`END_TIMESTAMP`/`IS_VALID_TIMESTAMP` | dt.h:288-291 | int64 timestamp range |
| `UTIME_*` / `IS_VALID_UTIME` | dt.h:293-305 | Unix-time validity window (1901..2038) |
| `DT_NOBEGIN`/`DT_NOEND` + `TIMESTAMP_*` macros | dt.h:307-314 | -infinity/infinity sentinels |
| API prototypes `DecodeInterval`…`PGTYPEStimestamp_defmt_scan` | dt.h:316-335 | implemented in pgtypeslib `.c` files |
| `extern` tables: `pgtypes_date_weekdays_short`, `pgtypes_date_months`, `months`, `days`, `day_tab` | dt.h:337-341 | shared name/length tables |

## Invariants & gotchas
- **Field-type ordering is load-bearing.** Per the comment (dt.h:84-90),
  YEAR/MONTH/DAY/HOUR/MINUTE/SECOND must stay in 0..14 so their bit masks fit
  the left half of an interval typmod. The token-type list (dt.h:134-137)
  carries an explicit warning that "most of these values are not equal to
  IGNORE_DTF nor RESERV" — renumbering either independent list silently breaks
  decode logic. `[from-comment]`
- `TMODULO` (dt.h:230) assumes C99 truncate-toward-zero integer division; only
  valid because timestamps are now always int64. `[from-comment]`
- `MAXDATELEN` is 128 and is the contract for every output buffer fed to the
  encoders and to `pgtypes_fmt_replace`; the comment (dt.h:190-194) notes
  `PGTYPESinterval_to_asc()` is the worst case at ~90 bytes. `[from-comment]`
- `datetkn.token` is `TOKMAXLEN + 1` = 11 bytes, always NUL-terminated; only
  the first `TOKMAXLEN` chars of a token are stored. `[from-comment]` (dt.h:199-205)

## Cross-refs
- [[pgtypeslib_extern.h]] — sibling internal header (alloc + fmt-replace side).
- [[dt_common.c]] — implements `DecodeDateTime`/`EncodeDateTime`/`date2j` and
  defines the `datetktbl[]` keyed by these codes.
- [[timestamp.c]], [[interval.c]], [[datetime.c]] — consumers of these macros.
- Backend [[datetime.h]] (`src/include/utils/datetime.h`) — the master copy
  this header was hand-cloned from.

## Potential issues
This header is a **manual copy** of backend `utils/datetime.h` (stated at
dt.h:88 and dt.h:184). It is a standing drift risk: any renumbering or addition
of `DTK_*` / field-type codes upstream is not propagated automatically, and the
in-file warnings about renumbering apply across the copy boundary too. Worth
re-verifying against `source/src/include/utils/datetime.h` when that file moves.
