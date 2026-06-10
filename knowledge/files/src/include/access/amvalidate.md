# `access/amvalidate.h` — opclass / opfamily validation helpers

**Verified against source pin `4b0bf0788b0`** (path: `source/src/include/access/amvalidate.h`)

## Role
Helpers shared by every index AM's `amvalidate` and `amadjustmembers`
callbacks. Validates that opclass / opfamily entries have the right
signatures and provides grouping helpers for opclass population.

## Public API
- `OpFamilyOpFuncGroup` struct (`amvalidate.h:20`) — left/right type pair
  plus bitmasks of operator and support-func numbers present for that pair.
- `identify_opfamily_groups(oprlist, proclist)` (`amvalidate.h:30`) — returns
  `List *` of `OpFamilyOpFuncGroup` from CatCList results.
- `check_amproc_signature(funcid, restype, exact, minargs, maxargs, …)`
  (`amvalidate.h:31`) — variadic check of support-proc input/output types.
- `check_amoptsproc_signature(funcid)` (`amvalidate.h:33`).
- `check_amop_signature(opno, restype, lefttype, righttype)`
  (`amvalidate.h:34`).
- `opclass_for_family_datatype(amoid, opfamilyoid, datatypeoid)`
  (`amvalidate.h:36`).
- `opfamily_can_sort_type(opfamilyoid, datatypeoid)` (`amvalidate.h:38`).

## Invariants
- Bitmasks `operatorset` / `functionset` are `uint64` — caps total operator
  count and total support-func count per `(lefttype, righttype)` pair at
  **64**. `[verified-by-code]` (`amvalidate.h:24`-`25`).
- `check_amproc_signature` and `check_amop_signature` emit `WARNING` (not
  `ERROR`) on a mismatch so the validator can keep accumulating findings
  and report multiple issues; the caller decides whether overall validation
  fails. `[inferred]` (verified by reading impl in `amvalidate.c`).

## Notable internals
- 64-bit bitmask hard-caps the strategy + procnum dimension per type pair.
  BTMaxStrategyNumber=5, RTMaxStrategyNumber=30 — well under 64.
- `exact=true` in `check_amproc_signature` means "argument types must match
  exactly"; `exact=false` allows binary-coercible matches.

## Trust-boundary / Phase D surface

This is a *static-validation* surface — invoked by `amvalidate` /
`amadjustmembers` during CREATE OPERATOR CLASS / ALTER OPERATOR FAMILY.
It checks that pg_amop and pg_amproc entries are well-typed but does NOT
verify runtime behavior (no "the operator is actually transitive" check).

**[ISSUE-defense-in-depth: 64-entry bitmask cap silently truncates (low)]** —
If a future AM ever declares >64 strategies or >64 support funcs per type
pair, `operatorset`/`functionset` overflow silently. No assertion catches
this. `amvalidate.h:24`-`25`.

**[ISSUE-audit-gap: validation is structural, not semantic (informational)]** —
`amvalidate` cannot detect operator-semantics mismatches (e.g., a "less than"
operator that's not transitive, or that disagrees with the AM's sort order).
This is the well-known root cause behind A13/A14 collation pin and NaN
clustering issues. `[from-comment]` `amapi.h:178`.

## Cross-refs
- `knowledge/files/src/include/access/amapi.h` — `amvalidate_function`
  and `amadjustmembers_function` consumers.
- A13/A14 corpus: collation pin / NaN cluster — semantic mismatches that
  static `amvalidate` cannot catch.

## Issues
1. **[ISSUE-defense-in-depth: 64-bit bitmask caps strategy/procnum count (low)]**
   — `amvalidate.h:24`-`25`.
2. **[ISSUE-audit-gap: validation is structural only, not semantic (informational)]**
   — `amvalidate.h:30`-`38`.
