# _int_selfuncs.c

`source/contrib/intarray/_int_selfuncs.c` (355 lines).

## One-line summary

Selectivity functions for intarray operators: wrappers that redirect `@>`/`<@`/`&&` to the built-in `arraycontsel`/`arraycontjoinsel` with the right built-in operator OID, plus a real `_int_matchsel` for `@@` (query_int match) that walks the parsed query tree against the column's MCE statistics.

## Public API / entry points

- `_int_overlap_sel`, `_int_contains_sel`, `_int_contained_sel` (restriction) — `source/contrib/intarray/_int_selfuncs.c:28-30,55-83` [verified-by-code]
- `_int_overlap_joinsel`, `_int_contains_joinsel`, `_int_contained_joinsel` — `_int_selfuncs.c:31-33,85-116`
- `_int_matchsel(root, oid, args, varRelid)` — for `@@` — `_int_selfuncs.c:34,119-253`
- internal `int_query_opr_selec(item, mcelems, mcefreqs, nmcelems, minfreq)` — recursive selectivity walker — `_int_selfuncs.c:255-338`
- internal `compare_val_int4` — `bsearch` comparator — `_int_selfuncs.c:341-355`

## Key invariants

- The simple wrappers exist because `arraycontsel` looks at the operator OID to recognise `&&`/`@>`/`<@`; intarray's user-defined operators have different OIDs so the wrappers substitute `OID_ARRAY_OVERLAP_OP` / `OID_ARRAY_CONTAINS_OP` / `OID_ARRAY_CONTAINED_OP` — `_int_selfuncs.c:42-53,57-115` [from-comment]
- `_int_matchsel` returns `DEFAULT_EQ_SEL` if: not "var @@ const" or "const @@ var", var is not `INT4ARRAYOID`, RHS isn't a Const, or RHS const-type isn't `query_int` — `_int_selfuncs.c:145-187` [verified-by-code]
- Strict operator → returns `0.0` if Const is NULL — `_int_selfuncs.c:170-175`
- Reads `STATISTIC_KIND_MCELEM` slot from `pg_statistic`; the MCE slot for int4 arrays has `nnumbers == nvalues + 3` (3 extra: minimal MCE freq, maximal freq, null fraction). If layout doesn't match, returns `DEFAULT_EQ_SEL` for unknown VALs — `_int_selfuncs.c:215-235`
- `int_query_opr_selec` calls `check_stack_depth()` — `_int_selfuncs.c:265` [verified-by-code]
- Selectivity combination: `!s → 1 - s`; `&` (AND) → `s1 * s2`; `|` (OR) → `s1 + s2 - s1*s2` — `_int_selfuncs.c:304-320`
- All intermediate results `CLAMP_PROBABILITY`'d (0 ≤ s ≤ 1) — `_int_selfuncs.c:250,335`
- For VAL not in MCE: estimated as `Min(DEFAULT_EQ_SEL, minfreq/2)` — `_int_selfuncs.c:285-294`

## Notable internals

- `get_function_sibling_type(fcinfo->flinfo->fn_oid, "query_int")` — clever way to look up the `query_int` OID without hard-coding it: looks at the function's own pg_proc entry and finds a peer type in the same extension — `_int_selfuncs.c:183`
- MCE search uses `bsearch` over an array of `Datum` (each holding an int4 by value), via a `Datum → int32` comparator — `_int_selfuncs.c:274-275,341-355`
- For unsupported tree nodes (neither VAL nor OPR) → `elog(ERROR, "unrecognized int query item type: %u", ...)` — should never happen given the parser; defensive — `_int_selfuncs.c:328-332`
- Selectivity is scaled by `(1 - nullfrac)` to account for NULL rows in MCE stats which only cover non-null rows — `_int_selfuncs.c:244-245`

## Trust boundary / Phase D surface

- **READS `pg_statistic`, attacker controls MCE entries** — an unprivileged user who can `INSERT` into an analyzed table can plant specific int4 values in the column. After ANALYZE, those become MCEs visible in `pg_statistic`, and `int_query_opr_selec` will read them via `get_attstatsslot`. The READ itself is safe (no syscalls, no string compare, plain int4 lookup), but **planner can be misled into bad plans** — e.g. flood a column with one value so `@@ '<that_val>'` looks like 90% selectivity, then the planner picks seqscan even though the index would be better. Inverse: a malicious actor pre-poisons stats to make `@@` *under*-estimate, leading to nested-loop blowups. [verified-by-code] `_int_selfuncs.c:215-235` [ISSUE-STATS]
- **Cross-link to A7 `pg_locale_icu`** — A7 found similar stats-deserialization issues where attacker-supplied string MCEs could affect collation handling. Here it's pure integer — no string-decoding bug surface — but the *planner trust* of pg_statistic is the same architectural pattern.
- **`check_stack_depth()` in `int_query_opr_selec`** — recursive walk over the same tree the `bqarr_in` parser produced; depth bounded by parser at input time. Belt-and-braces. — `_int_selfuncs.c:265`
- **`_int_matchsel` `query` not copied** — uses `DatumGetQueryTypeP` (NOT `…PCopy`), reading the Const's varlena in-place. Safe because Const datums are immutable for the lifetime of planning. — `_int_selfuncs.c:189`
- **`sslot` cleanup in error paths** — `free_attstatsslot(&sslot)` is reached only on the success path; the early-return paths use the un-init'd `sslot` (zeroed on lines 237-238 only in the no-statsTuple case). If `get_attstatsslot` returns false, `sslot.values` is NULL — `free_attstatsslot` handles that. — `_int_selfuncs.c:237-247` [verified-by-code]
- **Operator-OID substitution can be wrong if extension version mismatches** — `OID_ARRAY_OVERLAP_OP` etc. are built-in array operators. If a future PG redefines those operators or the intarray operators diverge semantically from built-in array overlap/contain, the wrappers would silently produce wrong selectivities. [from-comment] [ISSUE-COUPLING] — `_int_selfuncs.c:42-53`

## Cross-references

- `utils/selfuncs.h` — `arraycontsel`, `arraycontjoinsel`, `VariableStatData`, `AttStatsSlot`
- `catalog/pg_statistic.h` — `STATISTIC_KIND_MCELEM`
- `commands/extension.h` — `get_function_sibling_type`
- A7 `pg_locale_icu` — stats-deserialization issues found there
- `_int_bool.c` — same tree walker shape

## Issues spotted

- [ISSUE-STATS: attacker-controlled MCE entries in pg_statistic can mislead the planner into bad plans for `@@` (Low — affects all opclasses that read stats; not intarray-specific)]
- [ISSUE-COUPLING: selectivity wrappers hardcode `OID_ARRAY_*_OP` substitution; semantic drift between intarray and core array operators would silently produce wrong estimates (Low)]
- [ISSUE-DOC: the `nnumbers == nvalues + 3` magic number for intarray MCE layout is comment-only — easy to break with future ANALYZE changes (Low)]

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/contrib-intarray.md](../../../subsystems/contrib-intarray.md)
