# `src/backend/utils/adt/bytea.c`

- **File:** `source/src/backend/utils/adt/bytea.c` (1367 lines)
- **Source pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`

## Purpose

I/O and operators for the **`bytea`** type — raw byte arrays as a
varlena. Was split out of `varlena.c` to isolate the bit-/byte-oriented
operators (`get_byte`, `get_bit`, `set_byte`, `set_bit`, `XOR`,
`bitwise_count`, etc.) plus string-agg for byteas. The varlena
sort-support for bytea also lives here.

## I/O

- `byteain` (`:200`) — accepts **two formats**:
  - **Hex** (`\x` prefix): delegates to `hex_decode_safe` from
    `encode.c` (`:212-220`).
  - **Escape**: `\\` for backslash, `\nnn` for octal byte, else
    pass-through (`:228-260`). Invalid escape → `ereturn` with
    `ERRCODE_INVALID_TEXT_REPRESENTATION` (soft-error friendly).
- `byteaout` (`:274`) — output format selected by GUC `bytea_output`:
  - `BYTEA_OUTPUT_HEX` (default): `\x` prefix + hex_encode.
  - `BYTEA_OUTPUT_ESCAPE`: octal for non-printable, doubled backslash.
- `bytearecv` (`:357`), `byteasend` (`:376`) — binary protocol: just
  copies bytes verbatim (no encoding conversion).

## Operators

- `byteacmp`, `byteaeq`, `byteane`, `bytealt`, `bytea_larger`, etc. —
  byte-wise `memcmp` semantics.
- `bytea_substring` / `bytea_overlay` / `byteacat` — slice and combine
  (use TOAST slice helpers from varlena when input is TOASTed).
- `get_byte(bytea, int)` / `set_byte(bytea, int, int)` / `get_bit` /
  `set_bit` — random access, with range checks emitting precise
  `errmsg("index %d out of valid range, 0..%d", ...)` (`:651, :682,
  :718, :754`).
- `bitwise_count` (`:580`) — `SELECT count_ones(bytea)`; uses
  `pg_popcount`.
- Bitwise binary ops: AND/OR/XOR, with `errmsg("byte data length
  mismatch")` when sizes differ.
- `string_agg(bytea, bytea)` — `bytea_string_agg_transfn` (`:384`),
  `_finalfn` — internal-type state via `makeStringInfo`.

## Phase D notes — input bombs

- `byteain` with hex input: max input is 1 GB text (text varlena limit),
  decodes to ~0.5 GB binary. `hex_decode_safe` does the work; no
  separate cap here. The `palloc(bc)` (`:215`) is at most input/2 +
  VARHDRSZ.
- `byteaout` (escape format) explicitly checks `len > MaxAllocSize`
  (`:313-316`) — guards against the worst case where every byte is
  non-printable (4× expansion).
- `bytearecv` (`:357`) — wire-protocol receive. **No cap beyond the
  protocol's own per-message limit.** Each byte is copied verbatim
  via `pq_copymsgbytes`. If `nbytes + VARHDRSZ > MaxAllocSize`, palloc
  will reject (`:365`). [verified-by-code]
- Embedded NUL handling: bytea is binary, NUL is fine. The escape
  output format prints NUL as `\000` (4 chars).

## Potential issues

- [ISSUE-dos: `byteain` escape-format path (`:228-260`) is a tight C
  loop with no CFI; a multi-MB escape-format string takes real CPU.
  Bounded by the text input limit (1 GB) but no periodic
  CHECK_FOR_INTERRUPTS. (low)]
- [ISSUE-wire-protocol: `bytearecv` accepts up to ~1 GB of bytes
  verbatim from the wire. No format validation possible (it's raw
  bytes). Expected; documented. (informational)]
- [ISSUE-info-disclosure: error `"invalid input syntax for type bytea"`
  (`:258`) does NOT echo the offending byte position — good (cf
  numeric input errors which sometimes leak input fragments). (low)]

## Cross-references

- `source/src/backend/utils/adt/encode.c` — `hex_decode_safe`,
  `hex_encode`, used by I/O.
- `source/src/backend/utils/adt/varlena.c` — many bytea operators
  share helpers with text operators there.
- `source/src/include/utils/builtins.h` — declarations.

## Confidence tag tally

- `[verified-by-code]` × 8
- `[from-comment]` × 1
