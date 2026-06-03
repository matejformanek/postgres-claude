# `src/backend/utils/adt/char.c`

- **File:** `source/src/backend/utils/adt/char.c` (254 lines)
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422` (2026-06-03)

## Purpose

The internal single-byte `"char"` type (not `SQL CHAR(n)` — that is bpchar in
varchar.c). One byte of payload, used heavily in system catalogs for
single-letter codes (`relkind`, `typtype`, etc.). (`char.c:1-15` [from-comment])

## Type role

- **Input:** `charin` (`:41`) — accepts `\ooo` 3-octal-digit escapes
  (e.g. `\200`); else takes the first byte and silently discards the rest
  (backwards-compat for accidental multibyte input, `:36-39` [from-comment]).
- **Output:** `charout` (`:64`) — emits `\ooo` for high-bit bytes (0x80-0xFF),
  empty string for 0x00, raw byte otherwise.
- **Binary I/O:** `charrecv`/`charsend` — one byte, **no character set
  conversion** — comment notes "somewhat dubious, but in many cases people
  use char for a 1-byte binary type" (`:88-91` [from-comment]).
- **Cast:** `text_char`/`char_text` (`:204`, `:228`) — same escape rules as
  charin/out but honest about empty string ↔ 0x00.

## Phase D notes

- **Comparisons are done UNSIGNED, casts to int are SIGNED.** This dichotomy is
  explicit at `:120-124` ("You wanted consistency?") and is preserved across
  the whole file — `chartoi4`/`i4tochar` reinterpret via `int8`, while
  `charlt`/`charle`/`chargt`/`charge` cast to `uint8` (`:150,159,168,177`
  [verified-by-code]). Catalog comparisons rely on the unsigned ordering, so
  values 0x80-0xFF sort *after* 0x7F — consistent with bytea-like ordering.
- `i4tochar` range-checks against `SCHAR_MIN`/`SCHAR_MAX` (`:194-198`) — so
  `(-128..127)` are valid `int4` round-trips. To set the high-bit values via
  int4 you'd need a negative int. [verified-by-code]
- No locale dependency at all — `"char"` is byte-only by design.

## Potential issues

- `[ISSUE-correctness: charin silently truncates multibyte to first byte
  (:46-51). (low)]` — documented behavior, but means CAST('日'::"char")
  returns something locale/encoding-implicit. Already flagged in code
  comments.
- `[ISSUE-undocumented-invariant: signed/unsigned split between comparison
  ops and int casts is by-design but easy to forget. (info)]`

## Cross-references

- `source/src/include/utils/fmgrprotos.h` — PG_GETARG_CHAR / PG_RETURN_CHAR.
- `source/src/include/c.h` — `IS_HIGHBIT_SET` macro.
- `source/src/backend/utils/adt/varchar.c` — the bpchar/varchar(SQL CHAR/VARCHAR)
  type that is NOT this type.

## Confidence tag tally

- `[verified-by-code]` × 2
- `[from-comment]` × 3
