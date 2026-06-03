# src/common/digit_table.h

## Purpose
A 200-byte static const lookup table: every two-digit decimal number "00"
through "99" laid out as adjacent ASCII characters. Lets Ryu's `to_chars`
emit two decimal digits per loop iteration via a single 16-bit memcpy.

## Role in PG
Internal to Ryu. Included by `d2s.c` and `f2s.c`. Not used elsewhere in
the tree.

## Layout
```c
static const char DIGIT_TABLE[200] = {
    '0','0','0','1', ..., '9','8','9','9'
};
```
Indexing convention: to write the decimal representation of value `v`
(where `v < 100`), copy two bytes starting at `DIGIT_TABLE[v * 2]`.

## State / globals
The table itself is `static const` — one private copy per translation
unit (d2s and f2s each get one). Compiler may dedup with LTO; without
LTO the binary carries 400 bytes of redundancy. Not a concern.

## Phase D notes
- **Read-only constant.** No mutation, no untrusted input.
- The `static const` means it lives in `.rodata`, which is shared
  between forked backends — no per-backend memory cost.

## Potential issues
None.
