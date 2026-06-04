---
path: src/backend/utils/adt/char.c
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
loc: 254
depth: deep
---

# char.c

- **Source path:** `source/src/backend/utils/adt/char.c`
- **Lines:** 254
- **Depth:** deep
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
- **Companion files:** `src/include/utils/fmgrprotos.h` (prototypes), `src/include/varatt.h` (VARDATA/SET_VARSIZE macros), `src/include/catalog/pg_proc.dat` (charin/charout/chareq/chartoi4/i4tochar/text_char/char_text entries), `src/include/catalog/pg_type.dat` (`"char"` type), `src/include/libpq/pqformat.h`

## Purpose

Implements the built-in single-byte `"char"` type — explicitly NOT the SQL `CHAR(n)` (bpchar) type [from-comment `char.c:3-5`]. Provides I/O (`charin`/`charout`/`charrecv`/`charsend`), six btree comparisons, conversions to/from int4, and casts to/from `text`. The header comment block at `char.c:119-124` documents the deliberate asymmetry: comparisons treat the byte as unsigned (uint8) while integer conversions treat it as signed (int8) [from-comment `char.c:120-123`].

## Public symbols

| Symbol | file:line | Role |
| --- | --- | --- |
| `charin` | `char.c:40` | Input; decodes `\ooo` octal escape or takes first byte |
| `charout` | `char.c:63` | Output; emits empty/ASCII/`\ooo` per high-bit |
| `charrecv` | `char.c:93` | Binary recv; one raw byte, no charset conversion |
| `charsend` | `char.c:104` | Binary send; one raw byte |
| `chareq` | `char.c:126` | Equality |
| `charne` | `char.c:135` | Inequality |
| `charlt` | `char.c:144` | Less-than (unsigned compare) |
| `charle` | `char.c:153` | Less-or-equal (unsigned) |
| `chargt` | `char.c:162` | Greater-than (unsigned) |
| `charge` | `char.c:171` | Greater-or-equal (unsigned) |
| `chartoi4` | `char.c:181` | Cast "char" => int4 (signed interpretation) |
| `i4tochar` | `char.c:189` | Cast int4 => "char" (range-checked SCHAR_MIN..SCHAR_MAX) |
| `text_char` | `char.c:203` | Cast text => "char" |
| `char_text` | `char.c:227` | Cast "char" => text |

## Internal landmarks

- Octal helper macros (`char.c:24-26`): `ISOCTAL` (is `0`-`7`), `TOOCTAL` (digit -> ASCII), `FROMOCTAL` (ASCII -> value, casting through `unsigned char`).
- `charin` escape recognition (`char.c:45-49`): exactly 4 chars, leading backslash, three octal digits => one byte; otherwise first byte (or 0 for empty input) [from-comment `char.c:50`].
- `charout` three output cases (`char.c:69-82`): high-bit set => `\ooo`; otherwise raw single byte (which also handles `0x00` as a 1-char string containing NUL... — see gotchas) [from-comment `char.c:57-61`].
- `text_char`/`char_text` mirror `charin`/`charout` but handle the empty-string/0x00 mapping "honestly" (`char.c:210-213`, `char.c:233-236`).

## Invariants & gotchas

- **Signed/unsigned asymmetry is intentional.** Comparisons cast to `(uint8)` (`char.c:150`, `char.c:159`, `char.c:168`, `char.c:177`); int conversions cast through `(int8)` (`char.c:186`, `char.c:199`). Do not "fix" one to match the other — the comment `char.c:120-123` ("You wanted consistency?") flags this as deliberate.
- **`charout` allocates 5 bytes** (`char.c:67`): max output is `\ooo\0`. `char_text` allocates `VARHDRSZ + 4` (`char.c:231`) for the same reason.
- **0x00 round-trip asymmetry between charout and char_text.** `charout` for a non-high-bit byte writes `result[0] = ch; result[1] = '\0'` unconditionally (`char.c:80-81`), so 0x00 becomes a CSTRING whose first byte is NUL — i.e. an effectively empty C string [from-comment `char.c:79` "produces acceptable results for 0x00"]. `char_text`, by contrast, explicitly maps 0x00 to a zero-length text (`char.c:250-251`) because it cannot rely on NUL termination. The documented output spec (`char.c:57-58`) says 0x00 is the empty string; `charout` achieves that only by virtue of CSTRING NUL semantics.
- **`i4tochar` range check.** Rejects values outside `SCHAR_MIN..SCHAR_MAX` with a soft `ereturn` (`char.c:194-197`), then casts via `(int8)` — so the stored byte preserves sign. `chartoi4` is the inverse signed read (`char.c:186`).
- **Soft-error paths.** `i4tochar` uses `ereturn(fcinfo->context, ...)` (`char.c:195`) for soft input-error support.
- **`text_char` reads via `VARDATA_ANY`/`VARSIZE_ANY_EXHDR`** (`char.c:207`, `char.c:214`) so it correctly handles short/compressed/toasted text headers; argument fetched with `PG_GETARG_TEXT_PP` (the "PP" un-detoasted-pointer form).
- **`charrecv` does NO encoding conversion** (`char.c:89-91`) — one raw wire byte. This is documented as "somewhat dubious" but supported because people use "char" as a 1-byte binary type.

## Cross-references

- [[knowledge/idioms/fmgr-and-spi]] — PG_GETARG/PG_RETURN conventions, `PG_GETARG_TEXT_PP`.
- [[knowledge/idioms/error-handling]] — `ereturn` soft-error contract in `i4tochar`.
- bytea "escape" format that case 3 of `charout` mirrors: `src/backend/utils/adt/varlena.c`.
- Sibling adt type files: [[knowledge/files/src/backend/utils/adt/bool.c]], [[knowledge/files/src/backend/utils/adt/name.c]].
- The SQL `CHAR(n)` type (bpchar), which this is NOT: `src/backend/utils/adt/varchar.c`.

## Confidence tag tally

- [verified-by-code]: 0
- [from-comment]: 7
- [inferred]: 0
- [unverified]: 0
