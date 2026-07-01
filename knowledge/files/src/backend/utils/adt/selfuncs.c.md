# `src/backend/utils/adt/selfuncs.c`

- **File:** `source/src/backend/utils/adt/selfuncs.c` (9250 lines —
  one of the top-5 biggest files in `utils/adt/`)
- **Header:** `source/src/include/utils/selfuncs.h`
- **Last verified commit:** `b7e4e3e7fa73` (2026-07-01; re-pinned from
  `ef6a95c7c64`. Cites ≤ line 2385 hold; +2 through the mid-file and
  +10 from `examine_variable` onward after b574fec00f27 char-collation
  fix. `selfuncs.h` header cites unchanged.)

## Purpose

The standard library of **selectivity estimators** (`oprrest` and
`oprjoin` functions registered in `pg_operator`) and **index cost
estimators** (`amcostestimate` functions per AM). This is where the
planner asks "what fraction of rows pass `col = const`", "how many
distinct groups in `GROUP BY a, b`", "what does a btree scan of this
index cost", etc. Wrong answers here are the single most common
source of bad plans — see the long top-of-file comment block at
`:23-92` [from-comment] for the call-convention contract.

## Top of file (verbatim opening)

```
 * selfuncs.c
 *    Selectivity functions and index cost estimation functions for
 *    standard operators and index access methods.
 *
 *    Selectivity routines are registered in the pg_operator catalog
 *    in the "oprrest" and "oprjoin" attributes.
 *
 *    Index cost functions are located via the index AM's API struct,
 *    which is obtained from the handler function registered in pg_am.
```
(`:1-21` [from-comment])

## Public surface (the load-bearing entries)

### Operator-level estimators

- `eqsel` / `neqsel` (`:300, 630`) — `=` / `<>`; both call
  `eqsel_internal`.
- `scalarltsel` / `scalarlesel` / `scalargtsel` / `scalargesel`
  (`:1544, 1553, 1562, 1571`) — `<`, `<=`, `>`, `>=`; all call
  `scalarineqsel_wrapper` → `scalarineqsel`.
- `eqjoinsel` / `neqjoinsel` (`:2385, 3183`) — join versions.
- `scalarltjoinsel` etc. (`:3261-3288`) — ordered-comparison joins;
  currently all return `DEFAULT_INEQ_SEL`. Yes, really.
- `matchingsel` / `matchingjoinsel` (`:3633, 3651`) — generic estimator
  for pattern-match operators (`~`, `~~*`, `@@`, …). Returns
  `DEFAULT_MATCHING_SEL` (0.010).
- `boolvarsel`, `booltestsel`, `nulltestsel`, `scalararraysel`,
  `rowcomparesel` (`:1585, 1624, 1782, 1900, 2318`) — for the special
  expression node types.

### Building blocks the above call (also exported)

- `var_eq_const` (`:368`), `var_eq_non_const` (`:539`) — exported so
  estimators in other ADT modules (rangetypes, jsonb) can reuse the
  MCV-list lookup logic.
- `mcv_selectivity` (`:805`) and `histogram_selectivity` (`:896`) —
  walk the MCV array / equi-depth histogram for any
  caller-supplied opproc.
- `ineq_histogram_selectivity` (`:1114`) — binary-search-the-histogram,
  with **endpoint refresh from a live index** (see Surprise §3 below).
- `generic_restriction_selectivity` (`:987`) — the "I have a statistic
  for this operator family, use it" fallback shared by many extension
  types.

### Index cost estimators

- `genericcostestimate` (`:7420`) — shared base for all built-in AM
  cost functions.
- `btcostestimate` (`:7713`), `hashcostestimate` (`:8185`),
  `gistcostestimate` (`:8230`), plus SP-GiST, GIN, BRIN further down.

### Group / hash estimators (called by planner directly, not via
catalog)

- `estimate_num_groups` (`:3802`) — for `GROUP BY` / `DISTINCT` /
  sort-merge cardinality.
- `estimate_hash_bucket_stats` (`:4422`),
  `estimate_hashagg_tablesize` (`:4528`),
  `estimate_multivariate_bucketsize` (`:4154`),
  `estimate_multivariate_ndistinct` (`:4569`).

### Variable-statistics fetch layer

- `examine_variable` (`:5651`), `examine_simple_variable` (`:6047`),
  `examine_indexcol_variable` (`:6518`) — produce a
  `VariableStatData` with the `pg_statistic` tuple, the source
  RelOptInfo, type info, and uniqueness/ACL flags.
- `get_variable_numdistinct` (`:6621`) — interprets `stadistinct`
  (negative = fraction of rel, positive = absolute count).
- `get_variable_range` / `get_actual_variable_range` /
  `get_actual_variable_endpoint` (`:6754, 6944, 7133`) — fetch min/max
  from histograms *or* an index.
- `statistic_proc_security_check` (`:6592`) — the gate that demands
  leakproof comparison when the user lacks SELECT on all rows. **This
  is what makes RLS / column-level security safe against statistics
  leakage.**

## Key types

- **`VariableStatData`** (`selfuncs.h:87-101`) — the per-Var bundle:
  `Node *var`, `RelOptInfo *rel`, `HeapTuple statsTuple` (with
  `freefunc`), `vartype` / `atttype` / `atttypmod`, `isunique`,
  `acl_ok`. Caller pattern is `examine_variable(...); ...;
  ReleaseVariableStats(vardata)` (macro at `:103-107`).
- **`GenericCosts`** (`selfuncs.h:132-146`) — out-parameter struct for
  `genericcostestimate`. Holds `indexStartupCost`, `indexTotalCost`,
  `indexSelectivity`, `indexCorrelation`, plus intermediates
  (numIndexPages/Tuples, spc_random_page_cost, num_sa_scans). AM
  wrappers fill some fields, call generic, then adjust.
- **`MCVHashEntry` / `MCVHashContext`** (`selfuncs.c:160-177`) — used
  by the hash-based fast path in `eqjoinsel_inner` when both sides
  have MCV lists totaling ≥ `EQJOINSEL_MCV_HASH_THRESHOLD` (200 in
  production builds, 20 with assertions) — see `:146-157`
  [from-comment].
- **`EstimationInfo` + `SELFLAG_USED_DEFAULT`** (`selfuncs.h:75-84`)
  — flags returned to caller noting that a `DEFAULT_*_SEL` fell-back
  estimate was used; planner uses this to display
  `EXPLAIN (... GENERIC_PLAN)` warnings and similar.

## Key invariants and gotchas

- **Default selectivities** are deliberately small (`selfuncs.h:24-31`
  [from-comment]): `DEFAULT_EQ_SEL=0.005`, `DEFAULT_INEQ_SEL=0.3333`,
  `DEFAULT_RANGE_INEQ_SEL=0.005`, `DEFAULT_MATCH_SEL=0.005`,
  `DEFAULT_NUM_DISTINCT=200`. "Small enough to ensure that indexscans
  will be used if available, for typical table densities of ~100
  tuples/page" — i.e. **the planner is biased toward indexes when
  ignorant**, which is the right pessimism for the default case.
- **MCV vs histogram split.** Every estimator computes selectivity
  in three buckets — NULLs (from `stanullfrac`), MCVs (from
  `most_common_vals` + `most_common_freqs`), and the remainder
  (treated as uniform-over-distinct or interpolated via histogram).
  This is the universal idiom; see `var_eq_const` (`:368`) for the
  canonical implementation [verified-by-code].
- **Cross-type operator handling.** Histograms are stored with one
  specific `staop`; the lookup via `comparison_ops_are_compatible`
  (`:1135-1145`) handles cross-type and `<=` vs `<` (`:1129-1136`
  [from-comment]).
- **Security check is mandatory before invoking the op.** Every
  selectivity helper that *calls* a stats-consuming operator must
  guard with `statistic_proc_security_check(&vardata, opfunc)` —
  `var_eq_const` at `:408`, `ineq_histogram_selectivity` at `:1138`,
  etc. `stanullfrac` is the only field freely available regardless
  of security (`:386-387, 2449` [from-comment]).
- **Unique-index optimization.** If `vardata->isunique && tuples ≥ 1`,
  `var_eq_const` short-circuits to `1.0 / tuples` regardless of MCVs
  (`:403-406` [verified-by-code]).

## Functions of note

- **`eqsel_internal` → `var_eq_const` / `var_eq_non_const`**
  (`:308, 368, 539`). The textbook implementation. For const: try
  unique-index shortcut → walk MCVs with the op as predicate → if
  no match, use `(1 − sumcommon − nullfrac) / (ndistinct − nmcvs)`
  for the "other" mass (`:485-505`). For non-const: assume the rhs is
  one of the column's distinct values, so selectivity ≈
  `(1 − nullfrac) / ndistinct`.
- **`ineq_histogram_selectivity`** (`:1114`) — binary-search the
  histogram, then interpolate within the bin via
  `convert_to_scalar`. Crucially, if it hits the first or last
  histogram entry it calls `get_actual_variable_range` to refresh
  via a live index scan, so estimates don't go badly wrong when the
  min/max has drifted since the last ANALYZE (`:1157-1163`
  [from-comment]).
- **`eqjoinsel_inner`** (`:2590`) — the classic algorithm: probabilistic
  match between two MCV lists (count how much mass on each side
  matches the other), plus a `(1 − match) × (1 − match) / max(nd1, nd2)`
  term for the unmatched remainder. Uses `MCVHashTable` (simplehash
  template instantiation at `:277-288`) when both lists are large.
- **`estimate_num_groups`** (`:3802`) — heart of GROUP BY cost
  estimation. For each grouping expression: try `examine_variable`,
  if statistics-bearing → use ndistinct; if boolean → factor 2; SRFs
  → multiply at the end (the largest SRF expansion). Multivariate
  ndistinct via `estimate_multivariate_ndistinct` is consulted to
  reduce overcounting when correlated columns are grouped together.
- **`get_actual_variable_range`** (`:6944`) — the "go look at the
  index" escape hatch. Finds an ordering index, opens it with
  `index_open(... NoLock)` (assumes caller already holds a lock),
  builds a 1-key `SK_ISNULL | SK_SEARCHNOTNULL` scankey, runs
  `get_actual_variable_endpoint` to grab the literal min or max.
  Skips partial indexes, partitioned tables, hypothetical indexes,
  and indexes that can't return the column (`:6972-6994`
  [verified-by-code]). Bounded by `effort` cap inside the endpoint
  helper.
- **`statistic_proc_security_check`** (`:6592`) — returns true if (a)
  `vardata->acl_ok` is already true (user can see all rows), or
  (b) the function in question is marked LEAKPROOF. Combined with
  `all_rows_selectable` (`:6323`) this is the defense against RLS /
  per-column-privilege bypass via selectivity estimation.
- **`btcostestimate` + `btcost_correlation`** (`:7713, 7676`) — adds
  the btree-specific physical-vs-logical-order correlation factor
  on top of `genericcostestimate`. Pulls
  `STATISTIC_KIND_CORRELATION` from pg_statistic.

## Cross-references

- `source/src/backend/optimizer/path/clausesel.c` — the *clause*-level
  selectivity dispatcher; calls `clause_selectivity` → eventually
  `eqsel` etc. via fmgr.
- `source/src/backend/optimizer/path/costsize.c` — uses
  `GenericCosts`, `estimate_num_groups`, `estimate_hash_bucket_stats`.
- `source/src/backend/statistics/` — extended-statistics multivariate
  MCV / ndistinct / dependencies (consulted by
  `estimate_multivariate_ndistinct`, etc.).
- `source/src/backend/utils/adt/array_selfuncs.c` —
  `scalararraysel_containment` (declared in `selfuncs.h:253`).
- `source/src/backend/utils/adt/rangetypes_selfuncs.c`,
  `network_selfuncs.c`, `tsvector_op.c` — per-type selectivity
  modules that reuse `var_eq_const` / `histogram_selectivity` etc.

## Open questions

- `scalarltjoinsel` and family currently return only the default
  inequality selectivity (`:3261+`). Is there an active TODO upstream
  to use histogram joins for ordered comparisons? `[unverified]`
- `EQJOINSEL_MCV_HASH_THRESHOLD = 200` is "simplistic but seems to
  work" (`:148-152` [from-comment]) — no calibration data referenced.
- `get_actual_variable_range`'s `effort` cap (in
  `get_actual_variable_endpoint`) — what is the actual budget?
  `[unverified]`

## Confidence tag tally

- `[verified-by-code]` × 8
- `[from-comment]` × 7
- `[unverified]` × 3

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
- [idioms/analyze-mcv-histogram-correlation.md](../../../../../idioms/analyze-mcv-histogram-correlation.md)

## Appears in scenarios

<!-- scenarios:auto:begin -->

- [Scenario — Add a new index access method](../../../../../scenarios/add-new-index-am.md)

<!-- scenarios:auto:end -->

