# `src/backend/utils/adt/varbit.c`

- **File:** `source/src/backend/utils/adt/varbit.c` (1894 lines)
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422` (2026-06-03)

## Purpose

I/O, casts, comparison, and bitwise/arithmetic operators for the SQL
types `BIT(n)` (fixed-length bit string) and `BIT VARYING(n)` (varbit).
The on-disk layout is a varlena header + `int32 bit_len` + the bit
payload, MSB-first per byte, with the low-order pad bits of the last
byte required to be zero. (`varbit.c:1-30` [from-comment])

## Type role

- **Input:**
  - `bit_in` (`:147`) — handles three prefix forms: `B'...'`,
    `X'...'`, or bare `'010101'`. Hex strings have an upfront length
    cap at `VARBITMAXLEN / 4` (`:195-199`); regular strings rely on
    `MaxAllocSize`. Length must match `atttypmod` exactly for fixed BIT
    (`:209-213`).
  - `varbit_in` (`:452`) — analogous to bit_in but for VARBIT (uses
    typmod as upper bound).
- **Output:** `bit_out` (`:280`) — same as `varbit_out` (`:587`),
  always emits the bit representation (the alternate hex output is
  `#if 1`-d out at `:282-324`).
- **Binary I/O:** `bit_recv` (`:331`) / `bit_send` (`:376`) — int32
  bitlength + raw bytes; explicitly re-applies `VARBIT_PAD` to ensure
  the last-byte pad bits are zero on receive (`:367`).
- **Typmod:** `bittypmodin`/`out`, `varbittypmodin`/`out`,
  `varbit_support` — typmod is the bit length.
- **Comparison:** `bit_cmp` (`:818`) — bytewise then length tiebreak.
- **Operators:** `bitcat`, `bitsubstr`, `bitoverlay`, `bit_bit_count`,
  `bitlength`, `bitoctetlength`, `bit_and`/`or`/`xor`/`not`,
  `bitshiftleft`/`right`, `bitfromint4`/`int8`, `bittoint4`/`int8`,
  `bitposition`, `bitsetbit`, `bitgetbit`.

## Phase D notes

- **Padding invariant: VARBIT_PAD.** Every operation that writes a
  varbit must zero the low-order pad bits of the last byte; comparison
  and hash rely on this. The `VARBIT_CORRECTLY_PADDED` assert (`:68-78`)
  catches violations in cassert builds. **`bit_recv` is the
  user-facing entry that could ingest a non-padded buffer; it calls
  VARBIT_PAD defensively (`:367`).** [verified-by-code]
- **VARBITMAXLEN length cap on hex input** at `bit_in:195-199` is
  load-bearing: a user-supplied hex string is otherwise `slen * 4`
  bits, which without the check could overflow `int32` for
  `slen > INT_MAX/4`. The bound `VARBITMAXLEN / 4` (where
  `VARBITMAXLEN ≈ INT_MAX - VARHDRSZ`, see varbit.h) prevents that.
  [verified-by-code]
- **Length-mismatch ereturn for fixed BIT** at `:209-213` — uses
  ERRCODE_STRING_DATA_LENGTH_MISMATCH, which is what other fixed-length
  string types emit.
- **Soft-error path:** `bit_in` uses `ereturn(escontext, ...)`
  throughout (`:196, 210, 232, 257`). VARBIT same. [verified-by-code]
- **Bit shifts:** `bitshiftleft` (`:1392`) and `bitshiftright` (`:1459`)
  handle the byte-and-bit case via memmove + bit blend, and check
  shifts ≥ bitlen → zero result. The exact shift code is fiddly but
  has been stable since 9.x.
- **`bitfromint4` / `bitfromint8`** — convert an integer to a fixed-bit
  representation. **Big-endian conversion in code** (`:1531+, 1611+`)
  uses byte-by-byte placement; off-by-one would be visible immediately.

## Potential issues

- `[ISSUE-undocumented-invariant: all operations MUST preserve the
  zero-pad on the last byte (VARBIT_PAD); failure is silently visible
  as compare/hash mismatch (medium). Cassert build catches it.]`
- `[ISSUE-correctness: bit_in's "bare" form (no B/X prefix) treats
  input as binary by default (:178-184); this is convenient but means
  `cast('hello' as bit)` would error per-character at `:232`. (info)]`
- `[ISSUE-info-disclosure: errmsg uses `%.*s` with `pg_mblen_cstr` for
  the offending character (:234, :260); multibyte-safe (info).]`
- `[ISSUE-stale-todo: bit_out's hex alternate code is `#if 1`-d out
  (:282-324). Dead code in disguise. (info)]`

## Cross-references

- `source/src/include/utils/varbit.h` — `VarBit`, `VARBITLEN`,
  `VARBITS`, `VARBITBYTES`, `VARBITTOTALLEN`, `VARBITPAD`,
  `VARBITMAXLEN`, `HIGHBIT`, `BITMASK`, `BITS_PER_BYTE`.
- `source/src/backend/utils/adt/varlena.c` — varlena infrastructure.

<!-- issues:auto:begin -->
- [Issue register — `utils-adt`](../../../../../issues/utils-adt.md)
<!-- issues:auto:end -->

## Confidence tag tally

- `[verified-by-code]` × 4
- `[from-comment]` × 2
