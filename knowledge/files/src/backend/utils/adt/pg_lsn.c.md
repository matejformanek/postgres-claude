# `src/backend/utils/adt/pg_lsn.c`

- **File:** `source/src/backend/utils/adt/pg_lsn.c` (307 lines)
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422` (2026-06-03)

## Purpose

The `pg_lsn` type — WAL position (`XLogRecPtr`, i.e. uint64). I/O,
comparison, hash, and pg_lsn ± numeric arithmetic.

## Type role

- **Input:** `pg_lsn_in` / `pg_lsn_in_safe` (`:64`, `:32`) — parses
  `X/Y` where each side is 1–8 hex digits (`MAXPG_LSNCOMPONENT = 8`,
  `MAXPG_LSNLEN = 17`). Uses `strspn(str, "0123456789abcdefABCDEF")`
  to bound each side (`:41-47`).
- **Output:** `pg_lsn_out` (`:75`) — `snprintf("%X/%08X", ...)` via
  `LSN_FORMAT_ARGS(lsn)`. Note the **zero-padded low half**: high half
  may be 1-8 hex digits, low half is always 8.
- **Binary I/O:** raw int64.
- **Comparison:** standard, plus `pg_lsn_larger`/`pg_lsn_smaller`.
- **Hash:** delegates to `hashint8`/`hashint8extended`.
- **Arithmetic:**
  - `pg_lsn_mi` (`:219`) — LSN − LSN → numeric (via a snprintf round-trip
    through `numeric_in` because the difference can exceed int64 range
    when signed: `±2^63 - 1`).
  - `pg_lsn_pli` / `pg_lsn_mii` (`:246`, `:280`) — LSN ± numeric → LSN,
    via numeric_add/sub on a numeric-converted LSN. Reject NaN
    explicitly (`:254-257, :288-291`).

## Phase D notes

- **`strspn` bounding ensures no integer-overflow** during parse: each
  side is at most 8 hex digits → fits in uint32 → combined into a
  uint64 via `((uint64) id << 32) | off` (`:50-52` [verified-by-code]).
- **No null check on `str`** — caller guarantees via PG_GETARG_CSTRING.
- The arithmetic path **funnels through numeric**, not raw int64 ops,
  because adding e.g. a numeric `1e30` to an LSN can't naively
  saturate. Result then passes through `numeric_pg_lsn` (defined
  elsewhere) which performs the final range check. [verified-by-code,
  partially]
- `pg_lsn_out` format note: with high-half ≥ `0x100000000` the output
  width grows, so `MAXPG_LSNLEN = 17` is the *worst-case* with a
  ≤ 8-digit high half. **`MAXPG_LSNLEN + 1 = 18` buf is sufficient**
  (`:78-81`). Verified by the snprintf format string.

## Potential issues

- `[ISSUE-undocumented-invariant: pg_lsn_in requires EXACTLY one '/'
  with 1-8 hex digits each side; whitespace is NOT trimmed (:42,46).
  (low) — minor surprise vs other type input functions]`
- `[ISSUE-info-disclosure: errmsg echoes raw input (:59). (info)]`
- `[ISSUE-correctness: pg_lsn_mi returns numeric, breaking the
  type-symmetric expectation that LSN-LSN = LSN-offset (int8). This is
  by design because the difference can exceed int64 sign range, but
  surprises users (info).]`

## Cross-references

- `source/src/include/access/xlogdefs.h` — `XLogRecPtr`,
  `InvalidXLogRecPtr`, `LSN_FORMAT_ARGS`.
- `source/src/backend/utils/adt/numeric.c` — `numeric_in`,
  `numeric_add`, `numeric_sub`, `numeric_pg_lsn`.

## Confidence tag tally

- `[verified-by-code]` × 3
- `[inferred]` × 1
