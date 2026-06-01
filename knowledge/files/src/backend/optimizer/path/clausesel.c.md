# clausesel.c — selectivity combination

- **Source:** `source/src/backend/optimizer/path/clausesel.c` (977 lines)
- **Last verified commit:** `ef6a95c7c64`
- **Depth:** read

## 1. Purpose

Given a list of qual clauses, compute the *combined* selectivity. The
per-operator selectivity estimators (eqsel, scalarltsel, …) live in
`utils/adt/selfuncs.c`; clausesel.c is the *combiner* layer above them.
[verified-by-code]

## 2. Public entries

| Line | Function | Notes |
|---|---|---|
| 99 | `clauselist_selectivity` | Implicitly-ANDed list. Empty → 1.0. List elements may be `RestrictInfo` (preferred; allows caching) or bare exprs. Thin wrapper over `_ext`. [from-comment:56-62] |
| 116 | `clauselist_selectivity_ext` | Extra `use_extended_stats` flag. Extended stats applied first, on as many clauses as possible (captures cross-column deps); leftover clauses multiplied (assumes independence). [from-comment:66-72] |
| 666 | `clause_selectivity` | Single clause. With nonzero `varRelid` set jointype=JOIN_INNER, sjinfo=NULL even if it's a join clause being treated as restriction. [from-comment:660-664] |
| 683 | `clause_selectivity_ext` | extended-stats-disabled variant |

## 3. Key trick — range query pairing

Range queries (`x > 34 AND x < 42`) are detected when both clauses use
scalarltsel-family estimators on the same variable. Selectivity is then
`hisel + losel + null_frac - 1` instead of `hisel * losel`, because the
two halves are *not* independent. Falls back to DEFAULT_RANGE_INEQ_SEL
if either is DEFAULT_INEQ_SEL or result is negative. [from-comment:73-92]

Side benefit: redundant inequalities (`x < 4 AND x < 5`) collapse to the
tighter one. [from-comment:93-95]

## 4. Mental model

`clauselist_selectivity` does *two* passes:
1. Group clauses, call `statext_clauselist_selectivity` for any that map
   to MV stats objects.
2. Loop over remaining clauses calling `clause_selectivity_ext`,
   collecting `RangeQueryClause` candidates and multiplying everything
   else. [verified-by-code]

## 5. Tags
`[verified-by-code]` ×2, `[from-comment]` ×8
