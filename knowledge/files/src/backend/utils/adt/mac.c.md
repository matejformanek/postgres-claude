# `src/backend/utils/adt/mac.c`

- **File:** `source/src/backend/utils/adt/mac.c` (430 lines)
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422` (2026-06-03)

## Purpose

The `macaddr` type — 6-byte EUI-48 MAC addresses. I/O, comparison,
abbreviated-key SortSupport, and bitwise NOT/AND/OR/truncation.
(`mac.c:1-12` [from-comment])

## Type role

- **Input:** `macaddr_in` (`:44`) — accepts seven notations via cascading
  `sscanf` formats: `xx:xx:..`, `xx-xx-..`, `xxxxxx:xxxxxx`,
  `xxxxxx-xxxxxx`, `xxxx.xxxx.xxxx`, `xxxx-xxxx-xxxx`, plain `xxxxxxxxxxxx`
  (`:60-79`). `%1s` trailing-garbage trap, then per-octet `0..255` range
  check (`:86-91`).
- **Output:** `macaddr_out` (`:110`) — always canonical `xx:xx:xx:xx:xx:xx`.
- **Binary I/O:** `macaddr_recv`/`macaddr_send` — six raw bytes.
- **Comparison:** `macaddr_cmp_internal` (`:171`) — two 24-bit halves
  via the `hibits`/`lobits` macros.
- **Sort support:** `macaddr_sortsupport` (`:352`) installs
  `ssup_datum_unsigned_cmp` and the abbreviated-key converter
  `macaddr_abbrev_convert` (`:404`). **Abbreviation is never aborted**
  because 6 bytes fits entirely in 8-byte Datum — the abbreviated key is
  authoritative (`:384-392` [from-comment]).
- **Arithmetic:** `macaddr_not`, `_and`, `_or`, `_trunc` (zero out the
  manufacturer-specific lower 3 bytes).

## Phase D notes

- **`sscanf` with `%x` accepts signed input.** That's why the explicit
  range check `(a < 0) || (a > 255)` exists at `:86-91` — `sscanf("%x")`
  parses into `int`, so `-1` becomes a valid scanf match but is rejected
  here. [verified-by-code]
- **The cascading sscanf is O(7) per input.** Each `sscanf` rescans the
  whole string up to 17 chars; not a DoS surface. No backtracking.
- **`hibits`/`lobits` macros** are written with implicit-int promotion
  (`(addr)->a << 16` where `a` is unsigned char). On a system where
  `unsigned long` is 32 bits, this is fine; on a 64-bit `unsigned long`,
  the upper bits are zero and comparison still works. No bug.
- The abbreviated-key path big-endian-izes via `DatumBigEndianToNative`
  (`:427`) so `ssup_datum_unsigned_cmp` (which compares Datums as native
  ints) yields the correct collation order on little-endian.

## Potential issues

- `[ISSUE-correctness: macaddr_in accepts e.g. "12345678901234567890" as
  the 7th sscanf fallback would not match (it expects 12 chars exactly),
  but very long inputs are silently truncated past 12 chars? Need to
  verify the %2x%2x%2x%2x%2x%2x format rejects extras via %1s. (low)]`
- `[ISSUE-undocumented-invariant: which of 7 input notations is canonical
  is not specified; output is always colon-form (low).]`
- `[ISSUE-info-disclosure: errmsg echoes raw input (:83, :91). (info)]`

## Cross-references

- `source/src/include/utils/inet.h` — `macaddr` struct.
- `source/src/backend/utils/sort/sortsupport.c` —
  `ssup_datum_unsigned_cmp`.
- `source/src/backend/utils/adt/mac8.c` — EUI-64 sibling.

## Confidence tag tally

- `[verified-by-code]` × 3
- `[from-comment]` × 2
- `[inferred]` × 1
