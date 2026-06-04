---
path: src/backend/utils/adt/numutils.c
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
loc: 1311
depth: deep
---

# numutils.c

- **Source path:** `source/src/backend/utils/adt/numutils.c`
- **Lines:** 1311
- **Depth:** deep
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
- **Companion files:** `src/include/utils/builtins.h` (declares `pg_strtoint*`/`pg_*toa`/`pg_ultostr*`/`uint*in_subr`), `src/include/common/int.h` (`pg_neg_u16/32/64_overflow`, `pg_add/sub/mul_s64_overflow`, `strtou64`), `src/include/port/pg_bitutils.h` (`pg_leftmost_one_pos32/64`). Callers: int2.c/int4.c/int8.c, oid.c, timestamp/date code (`pg_ultostr_zeropad`), and most numeric I/O.

## Purpose
The integer<->string conversion core for the backend: string-to-int parsing with overflow detection (`pg_strtoint16/32/64` + their `_safe` variants and `uint32in_subr`/`uint64in_subr`), and int-to-string formatting (`pg_itoa`/`pg_ltoa`/`pg_lltoa`, the no-NUL `pg_ultoa_n`/`pg_ulltoa_n`, and `pg_ultostr`/`pg_ultostr_zeropad`). [from-comment] `numutils.c:3-4`. These are plain exported C helpers (not fmgr functions) used pervasively across the backend; the type I/O wrappers that call them live elsewhere. Formatting uses a two-digit lookup table and a base-10-length precomputation for speed `numutils.c:28-85`.

## Public symbols
| Symbol | file:line | Role |
| --- | --- | --- |
| `pg_strtoint16` | `numutils.c:120` | Hard-error wrapper -> `pg_strtoint16_safe(s, NULL)`. |
| `pg_strtoint16_safe` | `numutils.c:127` | smallint parse; base 10/16/8/2, underscores, escontext-aware. |
| `pg_strtoint32` | `numutils.c:382` | Hard-error wrapper. |
| `pg_strtoint32_safe` | `numutils.c:388` | integer parse. |
| `pg_strtoint64` | `numutils.c:643` | Hard-error wrapper. |
| `pg_strtoint64_safe` | `numutils.c:649` | bigint parse. |
| `uint32in_subr` | `numutils.c:896` | unsigned 32-bit parse via `strtoul`, with `endloc` continuation + width recheck. |
| `uint64in_subr` | `numutils.c:983` | unsigned 64-bit parse via `strtou64`, with `endloc`. |
| `pg_itoa` | `numutils.c:1040` | int16 -> string (delegates to `pg_ltoa`), returns strlen. |
| `pg_ultoa_n` | `numutils.c:1053` | uint32 -> string, NOT NUL-terminated, returns length. |
| `pg_ltoa` | `numutils.c:1118` | int32 -> NUL-terminated string, returns strlen. |
| `pg_ulltoa_n` | `numutils.c:1138` | uint64 -> string, NOT NUL-terminated, returns length. |
| `pg_lltoa` | `numutils.c:1225` | int64 -> NUL-terminated string, returns strlen. |
| `pg_ultostr_zeropad` | `numutils.c:1265` | uint32 -> zero-padded to minwidth; returns end ptr, no NUL. |
| `pg_ultostr` | `numutils.c:1305` | uint32 -> string; returns end ptr, no NUL. |

No SQL-callable (`PG_FUNCTION_ARGS`) entry points live in this file — it is entirely plain C helpers.

## Internal landmarks
- **Two-digit lookup table** `DIGIT_TABLE[200]` `numutils.c:28-38`: 100 ASCII digit pairs; formatting copies 2 bytes at a time.
- **Base-10 length precompute** `decimalLength32`/`decimalLength64` `numutils.c:43-85`: `(leftmost_one_pos+1) * 1233 / 4096` approximates log10 from log2, then a `PowersOfTen` table corrects off-by-one `numutils.c:58-59,83-84`. Drives right-to-left digit placement so the writer knows the output width up front.
- **Hex lookup** `hexlookup[128]` `numutils.c:87-96`: maps ASCII to 0-15, -1 for non-hex; indexed by `(unsigned char)*ptr` (so 128 entries cover the 7-bit ASCII range used after `isxdigit`).
- **Two-pass parse strategy** (all three `pg_strtoint*_safe`): a branch-light fast path assuming base-10 ASCII digits, optional leading `-`, no spaces/underscores `numutils.c:136-202`; on any deviation it `goto slow` and re-parses from the start handling sign, `0x`/`0o`/`0b` prefixes, underscores, and surrounding whitespace `numutils.c:204-344`.
- **Overflow-detection strategy (the high-value part):** accumulation is done in the *unsigned* counterpart (`uint16`/`uint32`/`uint64`) `numutils.c:116-118,131`. Before each multiply-add the code checks `tmp > -(PG_INTnn_MIN / base)` `numutils.c:182,231,255,279,303` — i.e. the magnitude limit derived from the most-negative value, so both signs are covered by one test. Final sign application: negatives go through `pg_neg_uNN_overflow` `numutils.c:194,336`; positives are bounded by `tmp > PG_INTnn_MAX` `numutils.c:199,341`. This is why the most-negative int (whose magnitude exceeds `PG_INTnn_MAX`) parses correctly — see the "NB: Accumulate input as an unsigned number" header comment `numutils.c:116-118`.
- **uint*in_subr ERANGE/EINVAL handling** `numutils.c:904-923,990-1009`: `errno`-based; treats EINVAL like a parse failure (endptr==s) and normalizes ERANGE to the out-of-range message. `uint32in_subr` additionally rechecks width when `unsigned long` is wider than uint32 and accepts both signed- and unsigned-extended matches for back-compat with minus-signed input `numutils.c:944-963`.
- **Formatting fast paths:** `pg_ultostr_zeropad` short-cuts the 2-digit/minwidth==2 case with a single `memcpy` `numutils.c:1272-1276`; the `pg_ulltoa_n` loop strips 8 digits per iteration while >= 1e8, then drops to 32-bit math `numutils.c:1155-1179`.

## Invariants & gotchas
- **Overflow must be detected pre-store, not post.** The `-(PG_INTnn_MIN / base)` guard runs *before* `tmp = tmp*base + digit` `numutils.c:182-185,303-306`, so the unsigned accumulator never wraps silently. Changing the comparison to `>=` or moving it after the multiply would corrupt boundary values.
- **`_safe` vs non-`_safe` is the soft-error contract.** The bare `pg_strtointNN(s)` pass `NULL` escontext `numutils.c:123,384,645`, so `ereturn` degrades to a hard `ereport(ERROR)`. The `_safe(s, escontext)` form fills an `ErrorSaveContext` if given one; callers MUST then check `SOFT_ERROR_OCCURRED()` `numutils.c:112-114,373-375,634-636`. Same for `uint*in_subr` `numutils.c:892-894,979-981`.
- **Underscore rules:** a single `_` is allowed only *between* digits, never leading/trailing/doubled; each branch enforces "must be followed by more digits" `numutils.c:236-242,308-317`, and the decimal branch additionally forbids a leading underscore `numutils.c:310-312`. The fast path bails to slow on any `_`.
- **Out-of-range vs invalid-syntax are distinct SQLSTATEs.** `ERRCODE_NUMERIC_VALUE_OUT_OF_RANGE` for overflow `numutils.c:347-350` vs `ERRCODE_INVALID_TEXT_REPRESENTATION` for bad syntax `numutils.c:353-356`; the type name in the message is hardcoded per function ("smallint"/"integer"/"bigint").
- **No-NUL functions need exact buffer sizing.** `pg_ultoa_n` requires >= 10 bytes `numutils.c:1050-1051`, `pg_ulltoa_n` >= MAXINT8LEN `numutils.c:1135-1136`, `pg_ltoa` >= 12 `numutils.c:1113-1116`, `pg_lltoa` >= MAXINT8LEN+1 `numutils.c:1222-1223`. `pg_ultostr`/`pg_ultostr_zeropad` write no terminator and return the end pointer for chaining `numutils.c:1249-1250,1291-1292`.
- **`pg_ltoa`/`pg_lltoa` negate via unsigned** `numutils.c:1126,1233`: `uvalue = (uintNN) 0 - uvalue` to handle INT_MIN without signed-overflow UB.
- **`pg_ultostr_zeropad` asserts minwidth > 0** `numutils.c:1270`; the `memmove`+`memset` left-pads in place after `pg_ultoa_n` `numutils.c:1282-1284`.
- **decimalLength tables must stay in sync with the type width:** `decimalLength64`'s `PowersOfTen` runs to 1e19 `numutils.c:76`; an undersized table would index out of bounds for large values.

## Cross-references
- [[knowledge/files/src/backend/utils/adt/cash.c]], [[knowledge/files/src/backend/utils/adt/enum.c]] — sibling adt files.
- [[knowledge/idioms/error-handling]] — `ereturn`/`escontext`/`SOFT_ERROR_OCCURRED`, the OUT_OF_RANGE vs INVALID_TEXT_REPRESENTATION split.
- `source/src/include/common/int.h` — `pg_neg_uNN_overflow`, `strtou64`, the s64 overflow helpers reused by cash.c.
- `source/src/include/port/pg_bitutils.h` — `pg_leftmost_one_pos32/64` behind `decimalLength*`.
- `source/src/backend/utils/adt/int8.c`, `int.c` — primary fmgr callers wrapping these helpers.

## Potential issues
- None surfaced. The overflow paths are guarded pre-store and the soft/hard error split is consistent and documented in each function header.

## Confidence tag tally
- [verified-by-code]: 9
- [from-comment]: 3
- [from-README]: 0
- [inferred]: 0
- [unverified]: 0
