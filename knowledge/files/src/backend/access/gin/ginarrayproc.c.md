# `src/backend/access/gin/ginarrayproc.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~311
- **Source:** `source/src/backend/access/gin/ginarrayproc.c`

Provides the four GIN opclass support functions used by the built-in
`array_ops` opclass (any array type indexed via GIN): `extractValue`,
`extractQuery`, `consistent`, and `triconsistent`. Each function
implements the strategy semantics for the four supported array
operators: overlap (`&&`, strategy 1), contains (`@>`, strategy 2),
contained-by (`<@`, strategy 3), equal (`=`, strategy 4).
[verified-by-code]

## API / entry points

- `ginarrayextract(PG_FUNCTION_ARGS)` — `extractValue` support; deconstructs
  input array into `(elems[], nulls[])` and returns the element array.
  Note `PG_GETARG_ARRAYTYPE_P_COPY(0)` deliberately makes a copy because
  the returned `elems[]` point into the array body. [verified-by-code]
- `ginarrayextract_2args(PG_FUNCTION_ARGS)` — legacy two-arg pg_proc
  entry kept for reloading pre-9.1 `contrib/intarray` opclass
  declarations; trampolines to `ginarrayextract`. Comment at line 62-66
  says "should go away eventually" — a ~15-year-old stale TODO.
  [from-comment] [ISSUE-stale-todo: 15-year-old eventual-removal
  comment (nit)]
- `ginqueryarrayextract(PG_FUNCTION_ARGS)` — `extractQuery` support.
  Sets `searchMode` per strategy. Notable special cases (lines 109-133):
  - `GinContainsStrategy` with empty array → `GIN_SEARCH_MODE_ALL`
    ("everything contains the empty set").
  - `GinContainedStrategy` → always `GIN_SEARCH_MODE_INCLUDE_EMPTY`
    ("empty set is contained in everything").
  - `GinEqualStrategy` with empty array → `INCLUDE_EMPTY`.
  - `GinOverlapStrategy` → `DEFAULT` even for empty (empty overlap
    nothing, so no items can match). [verified-by-code]
- `ginarrayconsistent(PG_FUNCTION_ARGS)` — boolean `consistent` support.
  Overlap and contains are exact (`*recheck = false`); contained and
  equal always set `*recheck = true`. [verified-by-code]
- `ginarraytriconsistent(PG_FUNCTION_ARGS)` — ternary version. Returns
  `GIN_TRUE`/`GIN_FALSE`/`GIN_MAYBE`; lifts the boolean logic to
  three-valued. Contained strategy collapses to `GIN_MAYBE` always.
  [verified-by-code]

## Notable invariants / details

- `extractValue` and `extractQuery` both take the array by `_P_COPY` and
  then pass `elems` to the caller without freeing the array — the
  returned datum array points into the copied array body, so freeing it
  would be a use-after-free. Comment at line 57 and 135 calls this out.
  [from-comment]
- Strategy numbers are local `#define`s (lines 23-26) and not pulled from
  `stratnum.h` — they shadow the conceptual `RTOverlapStrategyNumber`
  etc. but are independent. The header `stratnum.h` is included but only
  used implicitly via `StrategyNumber` typedef. [verified-by-code]
- Equal-strategy `consistent` deliberately ignores `nullFlags` (lines
  202-206 and 289-293) "because `array_contain_compare` and `array_eq`
  handle nulls differently" — a deliberate behavioural compromise
  documented in the comment but with no exact spec of which behaviour
  wins. [from-comment]
- `triconsistent` overlap (lines 248-266): if any element is firm
  `GIN_TRUE` and not null, immediately returns `GIN_TRUE`; otherwise
  collapses `GIN_MAYBE` results into a `MAYBE` overall. The `else if
  (check[i] == GIN_MAYBE && res == GIN_FALSE)` guard ensures a single
  TRUE wins over later MAYBEs. [verified-by-code]
- Default case in `ginarraytriconsistent` (line 305-307) reports
  `"ginarrayconsistent"` in the elog (copy-paste from the boolean
  sibling); message mismatch is minor. [verified-by-code]
  [ISSUE-doc-drift: triconsistent error reports the wrong function
  name "ginarrayconsistent" in elog at line 305 (nit)]

## Potential issues

- Line 62-66. `ginarrayextract_2args` was added when the signature
  changed in 9.1 and the comment says "should go away eventually" — but
  it's still here at e18b0cb. Removal is still gated by pg_dump output
  from pre-9.1 databases. [ISSUE-stale-todo: long-pending compatibility
  shim (nit)]
- Line 305. The `default` branch in `ginarraytriconsistent` errors with
  the string `"ginarrayconsistent"` (the boolean sibling's name); a
  copy-paste from above. Cosmetic only — the branch is unreachable in
  practice because GIN core validates the strategy number before
  dispatch. [ISSUE-doc-drift: elog mentions wrong function name (nit)]
- Line 220, 307. Both `default` branches set `res = false` after
  `elog(ERROR, …)` purely to silence the compiler ("res may be used
  uninitialized") despite `elog(ERROR)` not returning — the typedef
  changes (`bool` vs `GinTernaryValue`) mean the second one writes a
  type-mismatched value. Cosmetic. [verified-by-code]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `access`](../../../../../issues/access.md)
<!-- issues:auto:end -->
