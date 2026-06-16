# `src/backend/utils/adt/numutils.c`

- **File:** `source/src/backend/utils/adt/numutils.c` (1311 lines)
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422` (2026-06-03)

## Purpose

The **canonical integer parser and formatter** for the backend. Every
int2/int4/int8 input function and every oid input ultimately funnels
through one of these. Also exports the fast int-to-string converters used
by `printf`-free hot paths. (`numutils.c:1-13` [from-comment])

## Type role

Infrastructure for primitive integer types. Not bound to a single fmgr
function.

## Public API

- `pg_strtoint16(s)` / `_safe(s, escontext)` (`:121`, `:127`).
- `pg_strtoint32(s)` / `_safe(s, escontext)` (`:382`, `:388`).
- `pg_strtoint64(s)` / `_safe(s, escontext)` (`:643`, `:649`).
- `uint32in_subr(s, endloc, typname, escontext)` (`:897`) — uses
  `strtoul` for legacy compat; required by `oidin`, `tidin`'s block
  parse, and other unsigned paths.
- `uint64in_subr` (`:984`) — uses `strtou64`; required by `oid8in`.
- `pg_itoa(int16, char *)` (`:1041`).
- `pg_ltoa(int32, char *)` (`:1119`).
- `pg_lltoa(int64, char *)` and `pg_ulltoa_n(uint64, char *)` (`:1139`)
  — the latter is what oid8out and many JSON paths use.
- The 200-byte `DIGIT_TABLE` (`:28-38`) and `decimalLength32` /
  `decimalLength64` (`:43`, `:62`) helpers for the
  4-digit-per-iteration ryu-style formatter.

## Input-format support

`pg_strtoint{16,32,64}_safe` accept:

1. Optional leading `+` or `-`.
2. Decimal (default), hexadecimal (`0x` / `0X`), octal (`0o` / `0O`),
   or binary (`0b` / `0B`) prefix.
3. Optional `_` separator between digits (must be flanked by digits on
   both sides) (`:308-317, :569-578, :830-839`).
4. Leading and trailing whitespace.

## Phase D notes (the hot zone)

- **`INT_MIN` negation is handled correctly** by accumulating into an
  `uint{16,32,64}` and using `pg_neg_u{16,32,64}_overflow` (`:194,
  336, 455, 597, 716, 858`) [verified-by-code]. No `(int)-x` where
  `x == INT_MIN` UB.
- **Overflow check during accumulation:** `tmp > -(PG_INTNN_MIN / 10)`
  before each multiply-add (`:182, 303, 443, 564, 704, 825`). This
  bounds `tmp` against the MAX-magnitude of the negative side; since
  the accumulator is unsigned and `PG_INTNN_MIN` has larger magnitude
  than `PG_INTNN_MAX`, this is the tighter bound and ensures
  post-loop `tmp` fits when negated. [verified-by-code]
- **Fast path** for the common case (base-10, no separators, no
  leading `+`, no leading whitespace) at the top of each function
  (`:142-202, 405-464, 666-725`). Falls back to the labeled
  `slow:` block on any non-digit at the first position, on a leading
  `+`, or on non-numeric trailing chars. [verified-by-code]
- **Underscore validation:** must NOT be first (`firstdigit` check at
  `:311, 572, 833`) and MUST be followed by a digit (`:240-241,
  264-265, 288-289, 314-316, 501-502, 525-526, 549-550, 576-577, etc.`).
  This is the canonical PG-17 numeric literal underscore feature; no
  arithmetic surface.
- **`uint32in_subr` quirk:** for backwards compatibility, accepts a
  leading `-` as long as the value matches after either signed or
  unsigned extension (`:947-963` [from-comment]). I.e. `'-1'::oid` =
  4294967295. This is the **oid-cast-from-text wrap-around** behavior
  that surprises many users. [verified-by-code]
- **`uint64in_subr`** does NOT have the matching backwards-compat
  branch — it's used by oid8 which is a newer type. So `oid8in('-1')`
  rejects, but `oidin('-1')` accepts and wraps. [verified-by-code via
  absence at :983-1029]
- All `goto out_of_range` / `goto invalid_syntax` paths use `ereturn`
  with soft-error context (`:347, 608, 869, 914, etc.`), so all six
  parsers are SAFE for use under `escontext`/`SOFT_ERROR_OCCURRED`.

## Output path

`pg_ultoa_n` / `pg_ulltoa_n` write digits **back-to-front** via the
2-digit `DIGIT_TABLE` (`:1054`, `:1139`). Caller must pre-allocate the
right buffer size (10 bytes for u32, MAXINT8LEN for u64). Length
returned, no NUL terminator.

## Potential issues

- `[ISSUE-correctness: uint32in_subr accepts negative sign as wrap-around
  to uint32 for legacy reasons (:947-963); uint64in_subr does not
  (:983-1029). Cross-type asymmetry. (medium) — documented but
  surprising]`
- `[ISSUE-undocumented-invariant: the `tmp > -(PG_INTNN_MIN / 10)` bound
  is correct but subtle; comment at `:158-160, 419-421, 680-682` only
  partially explains. A future cleanup that "simplifies" to MAX/10
  would be wrong. (medium)]`
- `[ISSUE-info-disclosure: invalid-syntax errmsg echoes input verbatim
  (:355, 615, 877). (info) — standard idiom]`
- `[ISSUE-stale-todo: none observed. (info)]`

## Cross-references

- `source/src/common/int.h` — `pg_neg_u{16,32,64}_overflow`,
  `pg_add/sub/mul_s{16,32,64}_overflow` (A5 layer).
- `source/src/port/strtou64.c` (or wrapper) — `strtou64`.
- `source/src/backend/utils/adt/int.c`, `int8.c` — primary callers.
- `source/src/backend/utils/adt/oid.c` — uint32in_subr consumer.
- `source/src/backend/utils/adt/oid8.c` — uint64in_subr consumer.

<!-- issues:auto:begin -->
- [Issue register — `utils-adt`](../../../../../issues/utils-adt.md)
<!-- issues:auto:end -->

## Confidence tag tally

- `[verified-by-code]` × 6
- `[from-comment]` × 2
