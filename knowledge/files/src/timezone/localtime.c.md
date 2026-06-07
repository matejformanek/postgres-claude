---
path: src/timezone/localtime.c
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
loc: 2023
depth: deep
---

# src/timezone/localtime.c

## Purpose

The runtime half of PostgreSQL's bundled IANA tzcode: it **loads** a compiled
TZif binary (or parses a POSIX `TZ` string) into an in-memory `struct state`,
and **converts** a `pg_time_t` instant to a broken-down `struct pg_tm` honoring
that zone's UTC offsets, DST transitions, and abbreviations. This is what backs
every timestamp-with-time-zone computation: `pgtz.c::pg_tzset` calls `tzload`
here, and `datetime.c` / `timestamp.c` call `pg_localtime` / `pg_gmtime` here.
A heavily-PG-annotated copy of upstream tzcode `localtime.c`; the file builds in
**both frontend and backend** (`#include "c.h"`, not `postgres.h` —
`localtime.c:16-17`). `[verified-by-code]`

## Public symbols

| Symbol | Site | Role |
|---|---|---|
| `int tzload(char const *name, char *canonname, struct state *sp, bool doextend)` | `localtime.c:588` | Load TZif file `name` into `*sp`; return 0 or an errno; report canonical spelling in `canonname` |
| `bool tzparse(const char *name, struct state *sp, bool lastditch)` | `localtime.c:938` | Parse a POSIX `TZ` string (`EST5EDT,M3.2.0,...`) into `*sp` |
| `struct pg_tm *pg_localtime(const pg_time_t *timep, const pg_tz *tz)` | `localtime.c:1346` | Broken-down local time in zone `tz` |
| `struct pg_tm *pg_gmtime(const pg_time_t *timep)` | `localtime.c:1391` | Broken-down UTC time |
| `int pg_next_dst_boundary(...)` | `localtime.c:1612` | Find the next DST transition after `*timep`; return offsets/isdst before & after |
| `bool pg_interpret_timezone_abbrev(const char *abbrev, ..., const pg_tz *tz)` | `localtime.c:1745` | Resolve an abbreviation's gmtoff/isdst at/near a given time |
| `bool pg_timezone_abbrev_is_known(const char *abbrev, bool *isfixed, ...)` | `localtime.c:1863` | Is the abbrev defined in this zone; single meaning or several |
| `const char *pg_get_next_timezone_abbrev(int *indx, const pg_tz *tz)` | `localtime.c:1938` | Iterate all abbreviations in a zone |
| `bool pg_get_timezone_offset(const pg_tz *tz, long int *gmtoff)` | `localtime.c:1967` | True (+offset) iff the zone uses exactly one GMT offset |
| `const char *pg_get_timezone_name(pg_tz *tz)` | `localtime.c:1991` | The zone's `TZname` |
| `bool pg_tz_acceptable(pg_tz *tz)` | `localtime.c:2006` | Reject leap-second-aware zones |

## Internal landmarks

- `tzloadbody` (`localtime.c:211-580`) — the actual TZif parser, called by
  `tzload` with a `malloc`'d scratch `union local_storage`. Reads the header,
  then loops `stored = 4` then `8` to read the legacy 32-bit block and then the
  64-bit block (`:248`). Decodes big-endian fields via `detzcode`/`detzcode64`
  (`:117,143`). After the binary data, if `doextend`, it parses the trailing
  newline-wrapped POSIX TZ string via `tzparse` and splices its future
  transitions on (`:416-495`), reusing existing abbreviations to stay under
  `TZ_MAX_CHARS` (the America/Anchorage example, `:427-433`).
- `tzparse` (`localtime.c:938`) — POSIX `TZ` grammar parser:
  `std offset[dst[offset][,start[/time],end[/time]]]`. Synthesizes two
  transitions per year across a `YEARSPERREPEAT` (400-year) window
  (`:1063-1128`), or marks the zone perpetual-DST / single-type.
- `localsub` (`localtime.c:1261`) — the conversion core behind `pg_localtime`;
  binary-searches `sp->ats[]` for the active transition (`:1315-1327`), then
  calls `timesub`.
- `timesub` (`localtime.c:1416`) — converts seconds-since-epoch + offset to
  Y/M/D/h/m/s, applying leap-second correction and the `+ hit` second-60
  representation (`:1519-1523`).
- `gmtsub` / `gmtload` (`localtime.c:1359,1247`) — a private always-available GMT
  `struct state`, `malloc`'d once on first use.
- `differ_by_repeat` / `goback`/`goahead` (`localtime.c:169,498-516`) — detect
  that the transition table is periodic so `localsub` can **extrapolate** beyond
  the table's ends by shifting whole 400-year cycles (`:1272-1308`).
- Range-discard during load (`localtime.c:288-315`) — transitions outside
  `[TIME_T_MIN, TIME_T_MAX]` are dropped; the last pre-`TIME_T_MIN` transition is
  pretended to occur exactly at `TIME_T_MIN`.
- `defaulttype` inference (`localtime.c:518-577`) — heuristics to pick the time
  type for instants before the first transition, working around bugs in 32-bit
  data from tzdb ≤ 2018e (Australia/Macquarie, EST5EDT).

## Invariants & gotchas

- **`pg_localtime`/`pg_gmtime` return a pointer to a single file-static
  `struct pg_tm tm`** (`localtime.c:104`, returned at `:1349,1394`). They are
  **not reentrant**: a second call overwrites the first result. Callers must
  consume or copy the `struct pg_tm` before the next call. This is per the C
  standard's "two static objects" rule (`:96-102`), but the contract is not
  restated at the `pgtime.h` declarations — see Potential issues.
- **Leap-second-aware zones are rejected** by `pg_tz_acceptable`
  (`localtime.c:2006-2023`): it runs `pg_localtime` for GMT-midnight 2000-01-01
  and insists `tm_sec == 0`; any nonzero result means leap-second timekeeping,
  which "would wreak havoc with our date/time arithmetic". `pgtz.c`'s zone
  enumeration uses this to skip the `right/` (leap-second) tzdata subtree.
- **Hard input validation in the loader.** `tzloadbody` rejects out-of-range
  counts (`leapcnt/typecnt/timecnt/charcnt` vs the `TZ_MAX_*` ceilings,
  `:265-271`), short reads (`:272-281`), non-monotonic / duplicate transition
  times (`:305-311`), out-of-range type/desig indices (`:322,338,342`), and
  malformed leap-second spacing (`:369-371`). A corrupt TZif yields `EINVAL`,
  not a crash — important because the zone name is attacker-influenceable
  (any role can `SET timezone`), even though the *file set* is trusted.
- **`malloc`/`free`, not `palloc`.** `tzload` allocates its scratch via raw
  `malloc` (`:591`) and `gmtsub` `malloc`s the GMT state once (`:1371`),
  precisely because this file links into frontend tools too. Don't "fix" these
  to `palloc` — see Potential issues.
- **`detzcode` does manual two's-complement negation** (`:131-139`) to stay
  correct on (now hypothetical) non-two's-complement hosts; the `+ hit` leap
  representation in `timesub` (`:1523`) is the only place a `tm_sec` of 60 is
  produced.
- Overflow discipline: nearly all arithmetic on years/seconds goes through
  `increment_overflow` / `increment_overflow_time` / `oadd`-style guards
  (`:1541-1574`), returning `EOVERFLOW` rather than wrapping. Preserve this when
  touching the conversion math.
- `pg_interpret_timezone_abbrev` / `pg_timezone_abbrev_is_known` match
  abbreviations **case-sensitively** and assume the all-upper-case form
  (`:1743,1861`); they also assume no duplicate abbrev strings in `sp->chars`.

## Potential issues

- **[ISSUE-undocumented-invariant: pg_localtime/pg_gmtime share one static
  result buffer]** `localtime.c:104` — both return `&tm`, a single file-static
  `struct pg_tm`. The non-reentrancy / consume-before-next-call contract is
  documented only in the in-file comment (`:96-102`), not at the `pgtime.h`
  prototypes that backend callers see. A future caller stashing two
  `pg_localtime` results and comparing them would silently read the same struct
  twice. Long-standing upstream design (matches libc `localtime`), so almost
  certainly wontfix — worth a one-line note at the header. Severity: nit.
- **[ISSUE-undocumented-invariant: tzload uses raw malloc/free deliberately
  (frontend+backend)]** `localtime.c:591,1371` — the scratch `local_storage`
  and the GMT `struct state` use `malloc`/`free` rather than the backend
  `palloc`, because the file compiles into frontend binaries via `c.h`. Not a
  bug, but a trap for a backend hacker "tidying" allocations into memory
  contexts; the rationale isn't stated at the allocation sites. Severity: nit.

## Cross-refs

- `knowledge/files/src/timezone/pgtz.c.md` — calls `tzload`/`tzparse`; owns the
  loaded-zone cache and `pg_open_tzfile` (the case-insensitive, `.`-skipping
  file opener that bounds the attacker-influenceable zone name).
- `knowledge/files/src/timezone/tzfile.h.md` — the TZif on-disk layout and the
  `TZ_MAX_*` ceilings `tzloadbody` enforces.
- `knowledge/files/src/timezone/private.h.md` — `TIME_T_MIN/MAX`, `isleap`,
  `SECSPERREPEAT`, the overflow-arithmetic constants.
- `knowledge/files/src/backend/utils/adt/datetime.c.md` — the primary backend
  consumer of `pg_localtime`/`pg_next_dst_boundary`.
- `knowledge/idioms/guc-variables.md` — `TimeZone`/`log_timezone` GUC wiring
  that drives which `pg_tz` is active.
