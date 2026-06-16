# `src/backend/utils/adt/mac8.c`

- **File:** `source/src/backend/utils/adt/mac8.c` (569 lines)
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422` (2026-06-03)

## Purpose

The `macaddr8` type — 8-byte EUI-64 MAC addresses. **Accepts both EUI-48
(6-byte) and EUI-64 input**, stores internally as EUI-64, output always
EUI-64. EUI-48 → EUI-64 promotion inserts `FF:FE` between OUI and NIC.
(`mac8.c:1-19` [from-comment])

## Type role

- **Input:** `macaddr8_in` (`:97`) — hand-written byte-pair loop (no
  `sscanf` here, unlike mac.c) with a 128-entry `hexlookup[]` table
  (`:41-50`). Spacer (`:`, `-`, `.`) must be **consistent throughout** the
  input — mixing is rejected (`:172-177` [verified-by-code]). 6-byte
  input is promoted via OUI/NIC reshuffle + `0xFF:0xFE` injection
  (`:197-206`).
- **Output:** `macaddr8_out` (`:234`) — always canonical 8-byte
  colon-form.
- **Binary I/O:** `macaddr8_recv` (`:254`) — special-cases `buf->len == 6`
  to accept EUI-48 on the wire and promote (`:265-274`).
- **Comparison/hash:** standard, via `macaddr8_cmp_internal` (`:310`).
- **Arithmetic:** `_not`, `_and`, `_or`, `_trunc`, plus `_set7bit` which
  ORs `0x02` into the first byte — the universal/local bit flip for
  modified EUI-64 (IPv6 SLAAC) (`:497-517`).
- **Conversion:** `macaddrtomacaddr8` (`:524`) inserts `FF:FE`;
  `macaddr8tomacaddr` (`:545`) refuses to convert if bytes 4-5 ≠ `FF:FE`
  (range error with hint, `:552-559`).

## Phase D notes

- `hex2_to_uchar` (`:59`) tests `*ptr > 127` BEFORE indexing `hexlookup`
  (`:65-67, :77-79`) — explicit guard against the lookup-table OOB read
  that would otherwise occur with high-bit input bytes. [verified-by-code]
- The `palloc0_object` calls (`:210`, `:259`, `:420`, etc.) ensure
  zero-padding in the (unused) struct slots. Not strictly necessary but
  defensive.
- `macaddr8_recv` quietly accepts 6-byte payloads — a client that
  generated an EUI-48 binary representation will be promoted to EUI-64
  without comment. That's documented at `:249-251` [from-comment] and is
  the same semantics as `macaddr8_in`.
- `isspace((unsigned char) *ptr)` is used (`:116`, `:186`, `:188`); but
  oddly the code at `:116` doesn't cast — `isspace(*ptr)` where
  `*ptr` is `const unsigned char` already (line 99 casts the cstring to
  `const unsigned char *`). Safe but slightly unusual style.

## Potential issues

- `[ISSUE-undocumented-invariant: macaddr8_recv accepts 6-byte payloads
  and promotes (:265-274). (low) — documented in comment but worth
  noting for wire-format compat]`
- `[ISSUE-correctness: macaddr8tomacaddr refuses conversion if bytes 4-5
  != FF:FE; round-trip is lossy for non-SLAAC addresses (:552-559). (info,
  by design)]`
- `[ISSUE-info-disclosure: errmsg echoes raw input (:227). (info)]`

## Cross-references

- `source/src/include/utils/inet.h` — `macaddr8` struct.
- `source/src/backend/utils/adt/mac.c` — EUI-48 sibling.

<!-- issues:auto:begin -->
- [Issue register — `utils-adt`](../../../../../issues/utils-adt.md)
<!-- issues:auto:end -->

## Confidence tag tally

- `[verified-by-code]` × 3
- `[from-comment]` × 2
