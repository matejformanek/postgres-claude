# lsyscache.c

- **Source path:** `source/src/backend/utils/cache/lsyscache.c`
- **Lines:** 4030
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `lsyscache.h`, `syscache.c`/`catcache.c` (does all the real work).

## Purpose

A grab-bag of convenience wrappers — "Convenience routines for common queries in the system catalog cache." [from-comment, lsyscache.c:3-4]. Each `get_*` function does a single `SearchSysCache*` against the relevant cache, extracts one or a few fields, releases the tuple, and returns the result. About 131 such functions, organized by catalog (AMOP / AMPROC / ATTRIBUTE / CAST / COLLATION / CONSTRAINT / LANGUAGE / NAMESPACE / OPCLASS / OPERATOR / PROC / RANGE / TYPE / STATISTIC, etc.).

## Top-of-file comment

> "Convenience routines for common queries in the system catalog cache. … NOTES: Eventually, the index information should go through here, too." [lsyscache.c:3-13]

## Public surface (selected)

Too many to enumerate; representative examples:

- AMOP: `get_opfamily_member`, `get_ordering_op_properties`, `get_mergejoin_opfamilies`, `get_compatible_hash_operators`.
- AMPROC: `get_opfamily_proc`.
- ATTRIBUTE: `get_attname`, `get_attnum`, `get_atttype`, `get_atttypetypmodcoll`, `get_attstatsslot`/`free_attstatsslot`.
- OPCLASS / OPFAMILY: `get_opclass_family`, `get_opclass_input_type`, `get_opclass_method`.
- OPERATOR: `op_in_opfamily`, `get_op_btree_interpretation`, `get_commutator`, `get_negator`, `get_oprjoin`, `get_oprrest`.
- PROC: `get_func_name`, `get_func_namespace`, `get_func_rettype`, `get_func_strict`, `get_func_leakproof`, `get_func_arg_info`.
- TYPE: `get_typtype`, `get_typbyval`, `get_typlen`, `get_typdefault`, `get_typdefault_typid`, `getTypeIOParam`, `get_type_io_data`, `getTypeInputInfo`, `getTypeOutputInfo`.
- STATISTIC: `get_attavgwidth` (with hook), `get_attstatsslot`.
- Hook: `get_attavgwidth_hook` (lsyscache.c:57).

## Key types / structs

Defines no new types. Operates on syscache tuples, returning C scalars or palloc'd copies.

## Key invariants and locking

- **Stateless wrappers.** Every function follows the pattern: `SearchSysCacheN → HeapTupleIsValid? → extract → ReleaseSysCache → return`. No caching of its own; relies entirely on syscache/catcache for memoization. [verified-by-code, lsyscache.c throughout]
- **NULL/InvalidOid on miss.** Most functions silently return InvalidOid / 0 / NULL when the row isn't found; a few `elog(ERROR)` (the rule is documented per-function in lsyscache.h).
- **Hook surface.** `get_attavgwidth_hook` (57) lets extensions override the stats-collected avg-width estimate (used by the planner). Only this single hook exists in the file.
- **No mutation.** Despite being in `utils/cache`, this file does NOT write or invalidate anything; it is read-only on the syscache layer.

## Functions of note

1. **`get_attstatsslot` / `free_attstatsslot`** — fetch one slot of `pg_statistic`'s polymorphic `stavalues`/`stanumbers` and free the resulting array memory. The mate function exists because the array contents may be palloc'd separately from the tuple. The planner uses these heavily.
2. **`get_func_*` family** — every plpgsql / SPI / planner site that asks "what's this function's strictness/volatility/rettype" goes through one of these one-liners. They are how the rest of the backend stays decoupled from `Form_pg_proc` layout.
3. **`getTypeIOParam`, `getTypeInputInfo`, `getTypeOutputInfo`** — pulled out specifically for the I/O conversion paths (`pq_getmsgtext`, COPY, etc.); typmod handling is inside.

## Cross-references

- **Called from**: parser, rewriter, planner, executor, COPY, plpgsql, extensions. Essentially every catalog-aware code path uses these to avoid hand-coding the SearchSysCache → extract → release dance.
- **Calls into**: syscache (`SearchSysCache*`, `SysCacheGetAttr*`), occasionally typcache (e.g. for range types).

## Open questions

- The "Eventually, the index information should go through here, too" comment dates from at least 2000; the relevant `get_index_*` accessors instead live on the relcache (`RelationGetIndex*`). Probably a stale aspiration. [from-comment, but the aspiration is itself unfulfilled]

## Confidence tag tally

verified-by-code: 5 — from-comment: 2 — from-readme: 0 — inferred: 0 — unverified: 0

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
- [subsystems/utils-cache.md](../../../../../subsystems/utils-cache.md)
