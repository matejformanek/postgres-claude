# `src/backend/utils/adt/int.c`

- **File:** `source/src/backend/utils/adt/int.c` (1679 lines)
- **Last verified commit:** `ef6a95c7c64de07dff4dd1f1da88ffae7b086ef3` (2026-06-01)

## Purpose

Fmgr-callable functions for the 16-bit (`int2` / `smallint`) and
32-bit (`int4` / `integer`) integer types, plus the `int2vector`
helper used by `pg_index.indkey`. `int8` (`bigint`) lives in `int8.c`
because of the 64-bit-specific path. Includes I/O, arithmetic with
overflow checks, all cross-width comparators (`int24eq`, `int42lt`,
etc.), `in_range` window-frame helpers, and the planner support
function for `generate_series(int4, int4)`.

## Top of file (verbatim)

```
 * int.c
 *    Functions for the built-in integer types (except int8).
 *
 * OLD COMMENTS
 *    I/O routines: int2in, int2out, int2recv, int2send
 *                  int4in, int4out, int4recv, int4send
 *                  int2vectorin, int2vectorout, int2vectorrecv, int2vectorsend
 *    Boolean operators: inteq, intne, intlt, intle, intgt, intge
 *    Arithmetic operators: intpl, intmi, int4mul, intdiv
 *    Arithmetic operators: intmod
```
(`:1-28` [from-comment])

## Public surface (selected)

- **int2/int4 I/O:** `int2in/_out/_recv/_send`,
  `int4in/_out/_recv/_send`. Input delegates to
  `pg_strtoint16_safe` / `pg_strtoint32_safe` (`common/int.c`) with
  soft-error support.
- **Cross-width casts:** `i2toi4` (`:339`), `i4toi2` (`:355` with
  overflow check), `int4_bool` / `bool_int4` (`:376, 384`).
- **Same-width comparison:** `int4eq/.../ge`, `int2eq/.../ge`
  (`:391–520`).
- **Cross-width comparison:** `int24eq/ne/lt/le/gt/ge` (int2 vs int4)
  and `int42*` mirror set. These exist so btree opclasses can avoid
  forcing a cast that would block index use.
- **Arithmetic:** `int4mul` (`:848`, with overflow check via
  `pg_mul_s32_overflow`), `int4pl`, `int4mi`, `int4div`, `int4mod`,
  `int4abs`, `int4um`, `int4inc`, plus `int2*` mirrors and cross-width
  `int24pl`, `int42mul`, etc.
- **in_range:** `in_range_int4_int4` (`:652`), `in_range_int4_int2`
  (`:686`), `in_range_int4_int8` (`:698`), and `in_range_int2_*`
  variants — used by `RANGE BETWEEN ... PRECEDING/FOLLOWING` window
  frames.
- **int2vector:** `int2vectorin/_out/_recv/_send`,
  `buildint2vector` (extern).
- **generate_series:** `generate_series_int4` (`:1533`),
  `generate_series_step_int4` (`:1539`),
  `generate_series_int4_support` (`:1615`) — planner hook for row
  estimates.

## Key invariants

- **All arithmetic uses overflow-checked primitives.** From
  `common/int.h` (`pg_add_s32_overflow`, etc.). Overflow ⇒
  `ereport(ERROR, ERRCODE_NUMERIC_VALUE_OUT_OF_RANGE)` —
  no silent wrap (`:848+` int4mul [verified-by-code]).
- **Soft-error parsing.** `pg_strtoint16/32_safe(num, fcinfo->context)`
  lets COPY / `CAST x AS int` route into the error-saving path
  instead of throwing.
- **`int2vector` mirrors `oidvector` conventions:** 1-D, lower bound
  0, no nulls (`Int2VectorSize` `:44` and analogous checks).
- **No `int4mod(INT_MIN, -1)` divide-by-zero trap.** The
  divide-by-zero / overflow corner of `INT_MIN / -1` is handled
  explicitly to avoid SIGFPE on x86 (`[inferred]` — pattern
  documented in `int8.c` and same one applies; worth verifying).
- **Cross-width comparisons promote int2 → int4** before comparing,
  not via casting back; `int24lt(a,b)` reads as `((int32)a) < b`
  (`[verified-by-code]`).

## Functions of note

- **`int4mul`** (`:848`) — uses `pg_mul_s32_overflow` and reports
  via the canonical `ERRCODE_NUMERIC_VALUE_OUT_OF_RANGE` ereport.
  Same pattern repeated for every arithmetic op.
- **`in_range_int4_int4`** (`:652`) — implements RANGE-frame
  boundary test. Returns bool: `(val - base) <= offset` in the
  ascending case (or `>=` descending), with overflow→
  unbounded handling. The wider-rhs forms (`int4_int8`) promote
  via `pg_add_s64_overflow`.
- **`generate_series_int4_support`** (`:1615`) — implements
  `SupportRequestRows`; estimates output row count as
  `(finish - start) / step + 1`, used by the planner to size
  hash tables and parallel plans.

## Cross-references

- `source/src/backend/utils/adt/int8.c` — sibling 64-bit
  implementation and the cross-width `int48*`, `int84*`, `int82*`,
  `int28*` operators.
- `source/src/common/int.c` — `pg_strtoint*_safe`.
- `source/src/include/common/int.h` — overflow-checked arithmetic
  primitives.

## Open questions

- The "OLD COMMENTS" section header is stale; not all listed ops
  match modern names (e.g. `intpl` is now `int4pl`). `[inferred]`
- Are all in_range variants UB-safe for `offset = INT64_MIN`?
  `[unverified]`

## Confidence tag tally

- `[verified-by-code]` × 2
- `[from-comment]` × 1
- `[inferred]` × 2
- `[unverified]` × 1
