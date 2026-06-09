# utils/varbit.h — BIT() / BIT VARYING() varlena

Source: `source/src/include/utils/varbit.h` (89 lines)
Source pin: `4b0bf0788b066a4ca1d4f959566678e44ec93422`

## Role

VarBit varlena layout and access macros for SQL BIT/VARBIT types.

## Public API / on-disk format

```
int32 vl_len_;          /* varlena header */
int32 bit_len;          /* number of valid bits */
uint8 bit_dat[];        /* most-sig byte first */
```

(`varbit.h:30-36`).

## Invariants

- **INV-varbit-trailing-zeros** [from-comment, `varbit.h:25-28`]: "if `bit_len` is not a multiple of BITS_PER_BYTE, the low-order bits of the last byte of `bit_dat[]` are unused and MUST be zeroes." This lets `bit_cmp` skip masking. Any code that constructs a VarBit must zero the pad bits.
- **INV-varbit-no-excess-bytes** [from-comment, `varbit.h:27-28`]: header VARSIZE must match `ceil(bit_len/8) + VARHDRSZ + VARBITHDRSZ` exactly — no excess.
- **INV-varbit-MSB-first** [from-comment, `varbit.h:35`]: most significant byte first; opposite of inet's network byte order convention used in some places.
- **INV-varbit-MAXLEN-overflow-safe** [verified-by-code, `varbit.h:80-83`]: `VARBITMAXLEN = INT_MAX - BITS_PER_BYTE + 1`. Comment: "Several code sites assume no overflow from computing bitlen + X; VARBITTOTALLEN() has the largest such X."

## Notable internals

- `VARBITPAD(PTR)` (`varbit.h:75`): number of pad bits in the last byte; useful when constructing/extending.
- `BITMASK = 0xFF` (`varbit.h:87`) — full-byte mask constant.

## Trust-boundary / Phase-D surface

- **varbit_recv** [inferred — header silent]: must validate (a) `bit_len ≥ 0`, (b) `bit_len ≤ VARBITMAXLEN`, (c) VARSIZE matches `VARBITTOTALLEN(bit_len)` exactly, (d) the pad bits in the last byte are zero. The last check is the security-relevant one: non-zero pad bits would break `bit_cmp` equality.
- The `bit_len + X` overflow comment (`varbit.h:80-83`) is the kind of caveat that's easy to miss when refactoring sizing math; should be a `StaticAssert`.

## Cross-refs

- `source/src/backend/utils/adt/varbit.c` — implementation.

## Issues

- `[ISSUE-DOC: varbit_recv pad-bit-zero contract is hidden (medium)]` — non-zero pad bits would let two distinct binary inputs compare equal/unequal inconsistently. Header doesn't surface this as a recv-time check requirement.
