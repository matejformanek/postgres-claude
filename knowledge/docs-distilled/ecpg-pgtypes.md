---
source_url: https://www.postgresql.org/docs/current/ecpg-pgtypes.html
fetched_at: 2026-07-21T18:50:00Z
anchor_sha: 0da71d90d623
title: "ECPG — pgtypes Library (§36 leaf): the libpgtypes C API for numeric/decimal/date/timestamp/interval, DECSIZE 30 vs NUMERIC_MAX_PRECISION 1000"
maps_to_skill: wire-protocol
---

# ECPG — pgtypes Library (server-type arithmetic in the client)

`libpgtypes` is a standalone C library (linked `-lpgtypes`, separate from
`libecpg`) that reimplements PostgreSQL's `numeric`/`date`/`timestamp`/
`interval` semantics *client-side*, so an embedded-SQL program can parse,
format, and compute on those types without a server round-trip. It is the
client mirror of the backend's `numeric.c`/`date.c`/`timestamp.c` ADTs.

## Non-obvious claims

- **`numeric` and `decimal` are two structs with a deliberate size trade-off.**
  `numeric` holds `NumericDigit *buf; NumericDigit *digits;` — heap pointers,
  unbounded, with `NUMERIC_MAX_PRECISION 1000`
  (`source/src/interfaces/ecpg/include/pgtypes_numeric.h:10,18-27`). `decimal`
  is the same header fields but `NumericDigit digits[DECSIZE]` **inline**, with
  `#define DECSIZE 30` (`pgtypes_numeric.h:15,29-37`). So `decimal` is
  fixed at 30 digits and **stack-allocatable**, while `numeric` is
  heap-only and effectively unbounded. That is exactly why the docs say
  "decimal … limited to 30 significant digits". [verified-by-code]

- **Sign is a sentinel, not a bit.** `sign` is one of `NUMERIC_POS 0x0000`,
  `NUMERIC_NEG 0x4000`, `NUMERIC_NAN 0xC000`, `NUMERIC_NULL 0xF000`
  (`pgtypes_numeric.h:6-9`) — mirroring the backend numeric header flags.
  [verified-by-code]

- **Arithmetic functions return an int status and write through a result
  pointer.** `PGTYPESnumeric_add/_sub/_mul/_div(numeric *v1, numeric *v2,
  numeric *result)` return `int` (`pgtypes_numeric.h:50-53`); the caller owns
  `result` (must be `PGTYPESnumeric_new()`'d). `PGTYPESnumeric_cmp` returns
  `1/-1/0` and **`INT_MAX` on error** — so a naive `cmp()>0` test misreads an
  error as "greater". [verified-by-code][from-docs]

- **There is no `decimal` arithmetic API — convert to `numeric` first.** Only
  `PGTYPESdecimal_new`/`_free` plus the bridges
  `PGTYPESnumeric_to_decimal`/`PGTYPESnumeric_from_decimal`
  (`pgtypes_numeric.h:62-63`) exist. To add two `decimal`s you convert both to
  `numeric`, add, convert back. [verified-by-code][from-docs]

- **`errno` carries the pgtypes error class, not the return value.** Parse
  failures set `PGTYPES_NUM_BAD_NUMERIC` / `_OVERFLOW` / `_UNDERFLOW` /
  `_DIVIDE_ZERO`, dates set `PGTYPES_DATE_BAD_DATE` / `_ERR_ENOTDMY` / `…`,
  timestamps `PGTYPES_TS_BAD_TIMESTAMP` / `_ERR_EINFTIME`. Because
  `PGTYPEStimestamp_from_asc` returns `PGTYPESInvalidTimestamp`
  (documented as 1899-12-31 23:59:59) on failure — a *valid-looking* value —
  the docs insist you check `errno != 0`, not the return, to detect a bad
  parse. [from-docs]

- **`date`/`timestamp` are value typedefs; `interval` is a heap struct.**
  `date` and `timestamp` can be declared inline and passed by value
  (`PGTYPESdate_from_asc` returns a `date`); `interval` follows the
  new/free pattern like `numeric`. `PGTYPESdate_from_asc` assumes **MDY**
  ordering for ambiguous input and accepts Julian (`J2451187`) and ISO-8601
  compact (`19990108`) forms. `PGTYPESdate_dayofweek` returns 0=Sunday..6=Saturday.
  [from-docs]

- **Strings returned by pgtypes must be freed with `PGTYPESchar_free`, not
  `free`.** `PGTYPES*_to_asc` return `malloc`'d strings; on Windows freeing them
  with the app's `free()` crosses the CRT heap boundary, so `PGTYPESchar_free`
  exists specifically to free them on the library's heap — same DLL-heap rule
  as libpq's `PQfreemem`. [from-docs]

## Links into corpus

- Backend implementations this library mirrors: the `numeric`/`date`/`timestamp`
  ADTs — `knowledge/docs-distilled/datetime-input-rules.md`,
  `knowledge/docs-distilled/datetime-julian-dates.md` (the DetermineTimeZone /
  date2j machinery), and `source/src/backend/utils/adt/numeric.c`.
- The host-variable declarations that use these types:
  `knowledge/docs-distilled/ecpg-variables.md`.
- The DLL-heap free rule shared with libpq:
  `knowledge/docs-distilled/libpq-misc.md` (`PQfreemem`).
- Why `-lpgtypes` is a separate link: `knowledge/docs-distilled/ecpg-process.md`.
- Skill: `wire-protocol`.
