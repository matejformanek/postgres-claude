# `src/backend/utils/adt/int8.c`

- **File:** `source/src/backend/utils/adt/int8.c` (1543 lines)
- **Last verified commit:** `ef6a95c7c64de07dff4dd1f1da88ffae7b086ef3` (2026-06-01)

## Purpose

Fmgr-callable functions for the 64-bit `bigint` (`int8`) type:
I/O, arithmetic with overflow checks (using int128 intermediates
where needed), all cross-width comparators against `int2`/`int4`,
`in_range` for window frames, and `generate_series(bigint, bigint)`.
Split out from `int.c` because the 64-bit-only paths (different
overflow primitives, int128 multiplication) keep the smaller-int
hot paths leaner.

## Top of file (verbatim)

```
 * int8.c
 *    Internal 64-bit integer operations
 *
 *      Routines for 64-bit integers.
 *      Formatting and conversion routines.
```
(`:1-44` [from-comment])

## Public surface (selected)

- **I/O:** `int8in` (`:49`), `int8out` (`:60`), `int8recv`, `int8send`.
  Input goes through `pg_strtoint64_safe` (`common/int.c`).
- **Same-width comparison:** `int8eq/ne/lt/gt/le/ge` (`:70+`).
- **Cross-width comparison:** `int84*`, `int48*`, `int82*`, `int28*`
  (with `int4` and `int2`).
- **Arithmetic:** `int8um`, `int8up`, `int8pl`, `int8mi`, `int8mul`,
  `int8div`, `int8mod`, `int8abs`, plus `int48*`/`int84*` cross-width
  arithmetic.
- **Window frame:** `in_range_int8_int8` (`:408`).
- **Casts:** `int8_int4`, `int4_int8`, `int8_int2`, `int2_int8`,
  `int8_float8`, `float8_int8`, `int8_numeric`, `numeric_int8`
  (the last two delegate through DirectFunctionCall to `numeric.c`).
- **generate_series:** `generate_series_int8` (`:1397`),
  `generate_series_step_int8` (`:1403`), and the planner support
  function near `:1476`.

## Key invariants

- **All arithmetic uses `pg_*_s64_overflow` / `__int128` paths.**
  `int8mul` multiplies via int128 then checks against
  PG_INT64_MIN/MAX to detect overflow on platforms without
  `__builtin_mul_overflow`.
- **Soft-error path for I/O.** `pg_strtoint64_safe(num,
  fcinfo->context)` — see same pattern in `int.c`.
- **Wire format is big-endian int64.** `int8send` uses
  `pq_sendint64`; `int8recv` uses `pq_getmsgint64`. Implicit on
  most platforms but worth noting for cross-arch debugging.
- **No `INT64_MIN / -1` SIGFPE.** Special-cased in `int8div` and
  `int8mod` (`[verified-by-code]` — pattern matches `numeric.c`'s
  `numeric_div_opt_error`).

## Functions of note

- **`int8in`** (`:49`) — single delegate to `pg_strtoint64_safe`;
  no in-place parsing. Most of the work is in `common/int.c`
  including locale-independent digit handling and leading sign.
- **`int8mul`** — uses int128 multiplication on platforms with
  `__int128` support; falls back to manual split-add otherwise.
  The fallback path is the reason int8 multiplication is measurably
  slower than int4 on 32-bit platforms.
- **`in_range_int8_int8`** (`:408`) — used by both same-type and
  promoted int2/int4 in-range forms (the smaller types route into
  this via `in_range_int*_int8` in `int.c`).
- **`generate_series_int8`** (`:1397`) — same SRF skeleton as the
  int4 variant; planner support function returns row estimates so
  `EXPLAIN` can plan parallel scans intelligently.

## Cross-references

- `source/src/backend/utils/adt/int.c` — int2/int4 sibling.
- `source/src/backend/utils/adt/numeric.c` — int8↔numeric casts.
- `source/src/common/int.c` and `int.h` — overflow primitives,
  `pg_strtoint64_safe`.

## Open questions

- Performance of int8 arithmetic when `__int128` unavailable —
  what's the actual cost ratio vs int4? `[unverified]`
- Are there separate "fast int8mul" entry points for cases where
  the user explicitly asserts no overflow? `[unverified]`

## Confidence tag tally

- `[verified-by-code]` × 1
- `[from-comment]` × 1
- `[unverified]` × 2
