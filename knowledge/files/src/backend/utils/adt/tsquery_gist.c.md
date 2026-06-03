# `src/backend/utils/adt/tsquery_gist.c`

## Purpose

GiST opclass for `tsquery` columns (much less common than
tsvector GiST — but supports `@>` / `<@` between tsqueries).
Uses a fixed-size `TSQuerySign` (uint64 bitmap, defined in
`ts_type.h`) — a Bloom filter over the query's operand CRCs.
277 lines.

## Key functions

- `gtsquery_compress` — `tsquery_gist.c:27`. Build a TSQuerySign
  from a tsquery via `makeTSQuerySign` (sets bit `crc % 64` per
  operand).
- `gtsquery_consistent` — Match tsquery against tsquery using the
  sign-bitmap; returns `recheck = true`.
- `gtsquery_union` — Bitwise OR.
- `gtsquery_penalty`, `gtsquery_picksplit`, `gtsquery_same` —
  Standard GiST opclass methods.

## Phase D notes

64-bit sign is tiny — high false-positive rate is acceptable
because tsquery columns are typically small. Recheck does the real
work.

No user-tunable siglen here, unlike `tsgistidx.c`.

## Potential issues

- [ISSUE-correctness: Consistent must set `recheck = true` (lossy
  sign). Forgetting is a silent bug. (medium)] — applies throughout
  `gtsquery_consistent`
- [ISSUE-dead-code: Decompress is intentionally absent (comment at
  `:47-49` explains other support functions work on compressed
  form). Easy to misread as missing-function bug. (low)]
