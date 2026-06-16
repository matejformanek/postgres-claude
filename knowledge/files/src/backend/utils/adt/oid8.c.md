# `src/backend/utils/adt/oid8.c`

- **File:** `source/src/backend/utils/adt/oid8.c` (168 lines)
- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422` (2026-06-03)

## Purpose

The `oid8` (`Oid8`) **scalar** type — a 64-bit OID. NOT an array of OIDs
despite the suggestive name. Companion to the 32-bit `Oid` in `oid.c`.
Used for 64-bit object identifiers in newer catalog contexts.
(`oid8.c:1-13` [from-comment])

## Type role

- **Input:** `oid8in` (`:28`) — delegates to `uint64in_subr` (numutils.c),
  with typname `"oid8"` so error messages say "value out of range for
  type oid8" rather than "bigint".
- **Output:** `oid8out` (`:38`) — uses `pg_ulltoa_n` for fast formatting,
  manual palloc+memcpy to skip the `pstrdup` strlen (`:48-53`
  [from-comment]).
- **Binary I/O:** `oid8recv` (`:61`) / `oid8send` (`:72`) — raw int64.
- **Comparison:** `oid8eq/ne/lt/le/gt/ge`, `oid8larger`/`oid8smaller`.
  Unlike the `oid` type, no `oid8cmp` exists in this file — comparison
  is unsigned via direct `<`/`>` on `Oid8` (which is unsigned 64-bit).
- **Hash:** `hashoid8` / `hashoid8extended` — delegate to `hashint8`.

## Phase D notes

- **Unlike `oidin('-1')` which wraps to MAXUINT32 (uint32in_subr
  legacy compat), `oid8in('-1')` rejects** — `uint64in_subr` does not
  have the cross-extension fallback (see numutils.c notes).
  [verified-by-code]
- No additional input syntax beyond what `uint64in_subr` provides
  (whitespace, decimal/hex/octal/binary via `strtou64(s, &endptr, 0)`).
- `oid8out` skips a strlen by tracking length explicitly — modest
  perf win on hot catalog paths.
- All comparison ops use direct `Oid8` operators; no signed/unsigned
  confusion possible because `Oid8` is unambiguously `uint64`.

## Potential issues

- `[ISSUE-correctness: oid8 has no "vector" sibling like oidvector for
  oid; if a 64-bit-OID-array type is needed, the absence of oid8vector
  is a future-feature gap. (info)]`
- `[ISSUE-undocumented-invariant: oid8in('-1') rejects but oidin('-1')
  wraps; this cross-type behavior asymmetry is not flagged in user
  docs. (low)]`

## Cross-references

- `source/src/backend/utils/adt/numutils.c` — `uint64in_subr`,
  `pg_ulltoa_n`.
- `source/src/backend/utils/adt/oid.c` — 32-bit sibling.

<!-- issues:auto:begin -->
- [Issue register — `utils-adt`](../../../../../issues/utils-adt.md)
<!-- issues:auto:end -->

## Confidence tag tally

- `[verified-by-code]` × 2
- `[from-comment]` × 1
