# `src/backend/statistics/dependencies.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** ~1800
- **Source:** `source/src/backend/statistics/dependencies.c`

## Purpose

Soft functional dependencies (kind `STATS_EXT_DEPENDENCIES`). For each
subset of declared columns, computes a **degree** `f ∈ [0,1]` of "knowing
the LHS determines the RHS". `f=1` is a hard FK; `f=0` is independence;
in practice this captures correlations like (zip → city) where the LHS
mostly determines the RHS.

## Building (`statext_dependencies_build`, `:341`)

- Enumerates every subset `{A1..Ak} → B` with `k ≥ 1` and `B ∉ A`s,
  up to `STATS_MAX_DIMENSIONS = 8`.
- `dependency_degree` (`dependencies.c:215`): for each row, count how
  many rows agree on `(A1..Ak)`; among those, count how many also agree
  on `B`. `f = (consistent rows) / (rows in non-singleton groups)`.
- Only dependencies with `f >= MIN_DEPENDENCY_DEGREE = 0.3` are kept;
  weaker than that and the planner doesn't trust them.

## Selectivity (`dependencies_clauselist_selectivity`, `:1354`)

The core formula for an `a → b` dependency [from-comment]:
```
P(a,b) = f * P(a) + (1-f) * P(a) * P(b)
```
The first term is "if we believe in the dependency, knowing a forces
b". The second is the independence assumption residual.

- For >2 columns the dependencies apply recursively, starting with the
  widest/strongest. `P(a,b,c) = f * P(a,b) + (1-f) * P(a,b) * P(c)`.
- `clauselist_apply_dependencies` (called from
  `dependencies_clauselist_selectivity`) actually applies the formula
  using a slight modification of the textbook version that handles
  per-clause-overlap edge cases.
- Only equality / IS NULL clauses get the dependency treatment (other
  clauses left to per-column).
- Marks consumed clause indexes in `estimatedclauses` bitmap so MCV's
  pass before us and the rest of the planner don't double-count.

## Catalog & serialization

- Stored in `pg_statistic_ext_data.stxddependencies` as a bytea blob.
- `statext_dependencies_serialize` / `_deserialize` (`:437`, `:492`) —
  custom format: header + `(degree, lhs_attnum_list, rhs_attnum)`
  triples sorted by `(narrest, strongest first)` so the planner can
  early-out.
- `statext_dependencies_load(mvoid, inh)` (`:687`) reads via
  `STATEXTDATASTXOID` syscache; one entry per (statoid, inh).

## Notable

- Sample size driven by `statext_compute_stattarget` — typically
  `300 * default_statistics_target` rows.
- Comparator uses ordering operators from each attribute's typcache;
  attributes without `<` get skipped (can't define group equality).
- Expression columns participate the same way after analyze materializes
  `exprvals`.

## Tag tally

`[verified-by-code]` 3 / `[from-comment]` 5
