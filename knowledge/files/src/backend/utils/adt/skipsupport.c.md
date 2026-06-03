# `src/backend/utils/adt/skipsupport.c`

- **File:** `source/src/backend/utils/adt/skipsupport.c` (61 lines)
- **Header:** `source/src/include/utils/skipsupport.h`
- **Source pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`

## Purpose

A single helper, `PrepareSkipSupportFromOpclass`, used by the B-tree
**skip-scan** machinery (PG 18+) to fetch and (optionally) reverse the
`BTSKIPSUPPORT_PROC` for a given opclass. (`skipsupport.c:1-13`,
`:22-28` [from-comment])

## Key functions

- `PrepareSkipSupportFromOpclass(opfamily, opcintype, reverse)` (`:29`):
  1. Looks up the `BTSKIPSUPPORT_PROC` (proc number) in the opfamily via
     `get_opfamily_proc` (`:36`).
  2. If absent, returns NULL — opclass has no skip support.
  3. Otherwise allocates a `SkipSupportData`, calls the support function
     via `OidFunctionCall1` (`:42`).
  4. For `reverse == true` (DESC), swaps `low_elem ↔ high_elem` and
     `decrement ↔ increment` (`:44-58`).

## Phase D notes

- Tiny, no user-facing input handling. Not a Phase D surface.
- The reverse swap is purely on already-populated SkipSupport fields;
  no allocation, no untrusted input.

## Potential issues

- None of concern.

## Cross-references

- `source/src/include/access/nbtree.h` — `BTSKIPSUPPORT_PROC` proc
  number, `SkipSupportData`/`SkipSupportIncDec` typedefs.
- `source/src/backend/access/nbtree/nbtutils.c` — the skip-scan loop
  that consumes `SkipSupport`.

## Confidence tag tally

- `[verified-by-code]` × 2
- `[from-comment]` × 1
