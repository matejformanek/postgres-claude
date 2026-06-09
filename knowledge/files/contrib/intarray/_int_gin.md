# _int_gin.c

`source/contrib/intarray/_int_gin.c` (181 lines).

## One-line summary

GIN opclass support for `int4[]`: `ginint4_queryextract` extracts indexable VAL items from a `query_int` or array query and selects the right `GIN_SEARCH_MODE_*`; `ginint4_consistent` evaluates the GIN bitmap result against the original strategy.

## Public API / entry points

- `ginint4_queryextract(query, *nentries, strategy, ..., *searchMode)` — `source/contrib/intarray/_int_gin.c:10,12-105` [verified-by-code]
- `ginint4_consistent(check, strategy, query, nkeys, extra, recheck)` — `source/contrib/intarray/_int_gin.c:107,109-181`

## Key invariants

- Strategies handled: `RTOverlapStrategyNumber` (`&&`), `RTContainsStrategyNumber`/`RTOldContains` (`@>`), `RTContainedByStrategyNumber`/`RTOldContainedBy` (`<@`), `RTSameStrategyNumber` (`=`), `BooleanSearchStrategy` (`@@`) — `source/contrib/intarray/_int_gin.c:75-101,122-178` [verified-by-code]
- `BooleanSearchStrategy` with **no required VAL** (e.g. `!42`) forces `GIN_SEARCH_MODE_ALL` (full index scan) — `source/contrib/intarray/_int_gin.c:32-40` [verified-by-code]
- `@>` (contains) with empty query array → `GIN_SEARCH_MODE_ALL` (everything contains the empty set) — `source/contrib/intarray/_int_gin.c:91-96`
- `<@` (contained-by) → always `GIN_SEARCH_MODE_INCLUDE_EMPTY` (empty set is contained in everything) — `source/contrib/intarray/_int_gin.c:80-84`
- `RTOverlap`/`RTContains` → `recheck = false` (GIN result is exact for those); `RTContainedBy`/`RTSame` → `recheck = true` — `source/contrib/intarray/_int_gin.c:124-165` [verified-by-code]

## Notable internals

- For `BooleanSearchStrategy`, walks the `QUERYTYPE.items` array and `res[*nentries++] = Int32GetDatum(item->val)` for each VAL — the ITEM ordering in the resulting Datum array MUST match the ordering that `gin_bool_consistent` (in `_int_bool.c`) expects when re-mapping `check[]` back onto the tree. The two scans use the same `i++` over `items[i].type == VAL`. — `source/contrib/intarray/_int_gin.c:46-55` vs `source/contrib/intarray/_int_bool.c:350-354` [verified-by-code]
- Unknown strategy → `elog(ERROR, "ginint4_queryextract: unknown strategy number: %d", strategy)` — `source/contrib/intarray/_int_gin.c:99-100`

## Trust boundary / Phase D surface

- **Index-scan amplification via `! 42`** — a query like `! 42` against a GIN-indexed `int4[]` column forces `GIN_SEARCH_MODE_ALL`, i.e. a sequential scan of all entries through the GIN posting tree. Attacker who can inject `query_int` literals can trigger O(N) work on indexes that look O(log N) from the SQL — clear DoS amplifier for any app that exposes `@@` to user-provided query strings. [verified-by-code] `source/contrib/intarray/_int_gin.c:37-40` [ISSUE-AMPLIFY]
- **`palloc_array(Datum, query->size)`** with `query->size` already capped by `bqarr_in` at `QUERYTYPEMAXITEMS`, so DoS reachable through input but not through this allocation specifically — `source/contrib/intarray/_int_gin.c:45`
- **The "ITEM order matches between queryextract and consistent" invariant is unwritten** — anyone refactoring `_int_bool.c` `gin_bool_consistent` without also touching `_int_gin.c` `ginint4_queryextract` will silently mis-evaluate queries. There's a comment at `_int_gin.c:46-48` noting the contract; not enforced by code. [verified-by-code] [ISSUE-CONTRACT]

## Cross-references

- `_int_bool.c` (`gin_bool_consistent`, `query_has_required_values`)
- `access/gin/*` — generic GIN framework + `GIN_SEARCH_MODE_*` semantics
- `access/stratnum.h` — `RT*StrategyNumber` definitions

## Issues spotted

- [ISSUE-AMPLIFY: `! 42` style queries force full GIN scan; reachable via any app exposing `@@` query strings (Med)]
- [ISSUE-CONTRACT: VAL-order coupling between `ginint4_queryextract` and `gin_bool_consistent` is comment-only, not enforced (Low)]
