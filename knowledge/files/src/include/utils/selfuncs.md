# `src/include/utils/selfuncs.h`

**Pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`

## Role

Selectivity / cost-estimation building blocks for the planner.
Exposes default selectivity constants, the `VariableStatData` cache,
hooks for plugins, and per-shape selectivity functions
(`boolvarsel`, `nulltestsel`, `scalararraysel`, `rowcomparesel`,
`mergejoinscansel`, `estimate_num_groups`, hash-bucket / hash-agg
estimators).

## Public API

### Default constants [verified-by-code: lines 33-56]

- `DEFAULT_EQ_SEL = 0.005`
- `DEFAULT_INEQ_SEL = 1/3`
- `DEFAULT_RANGE_INEQ_SEL = 0.005`
- `DEFAULT_MULTIRANGE_INEQ_SEL = 0.005`
- `DEFAULT_MATCH_SEL = 0.005` (LIKE etc.)
- `DEFAULT_MATCHING_SEL = 0.010`
- `DEFAULT_NUM_DISTINCT = 200`
- `DEFAULT_UNK_SEL = 0.005`
- `DEFAULT_NOT_UNK_SEL = 1 - DEFAULT_UNK_SEL`

Rationale [from-comment: lines 24-31]: tuned so that indexscans win
when usable; 1/DEFAULT_EQ_SEL = DEFAULT_NUM_DISTINCT by design.

### Macro [verified-by-code: lines 63-69]

`CLAMP_PROBABILITY(p)` clamps to `[0, 1]`.

### Estimation-info flag [lines 76-84]

`SELFLAG_USED_DEFAULT` set when an estimator fell back to a default.

### `VariableStatData` [verified-by-code: lines 87-101]

`{var, rel, statsTuple (pg_statistic HeapTuple), freefunc, vartype,
atttype, atttypmod, isunique, acl_ok}`. `acl_ok` records whether
caller has SELECT on the column — gates whether
`statistic_proc_security_check` will let MCV/histogram values flow
into user-visible side-channels [line 99-100].

`ReleaseVariableStats(vardata)` frees the stats tuple via freefunc.

### `GenericCosts` [verified-by-code: lines 132-146]

Cost estimator return + intermediate values: `indexStartupCost`,
`indexTotalCost`, `indexSelectivity`, `indexCorrelation`,
`numIndexPages`, `numIndexTuples`, `spc_random_page_cost`,
`num_sa_scans`, `numNonLeafPages`.

### Hooks [verified-by-code: lines 149-158]

- `get_relation_stats_hook` (extension override for `pg_statistic`
  fetch).
- `get_index_stats_hook`.

### Functions [verified-by-code: lines 162-249]

- `examine_variable`, `all_rows_selectable`,
  `statistic_proc_security_check` — variable lookup + ACL gate.
- `get_restriction_variable`, `get_join_variables`,
  `get_variable_numdistinct`.
- `mcv_selectivity`, `histogram_selectivity`,
  `generic_restriction_selectivity`, `ineq_histogram_selectivity`.
- `var_eq_const`, `var_eq_non_const`.
- `boolvarsel`, `booltestsel`, `nulltestsel`, `scalararraysel`,
  `rowcomparesel`, `estimate_array_length`, `mergejoinscansel`.
- `estimate_num_groups`, `estimate_multivariate_bucketsize`,
  `estimate_hash_bucket_stats`, `estimate_hashagg_tablesize`.
- Index helpers: `get_quals_from_indexclauses`,
  `index_other_operands_eval_cost`, `add_predicate_to_index_quals`,
  `genericcostestimate`.
- Array containment: `scalararraysel_containment`.

## Invariants

- **INV-ACL-GATE** [verified-by-code: lines 99-100, 165] Selectivity
  paths that would invoke a user-defined comparator on an MCV value
  must check `vardata.acl_ok` (the user has SELECT on the column)
  AND `statistic_proc_security_check(vardata, func_oid)` (the
  operator's underlying function is leakproof or the user has
  privilege to invoke it). Otherwise an attacker could write a
  side-channel `=` operator that exfiltrates MCV contents.
- **INV-CLAMP** [verified-by-code: lines 63-69] Probability outputs
  must be clamped to [0, 1] before return.
- **INV-DEFAULT-FLAG** [from-comment: lines 73-79] Estimators that
  fall back set `SELFLAG_USED_DEFAULT` so callers can avoid
  cascading defaults.

## Trust boundary (Phase D)

This is the **MCV-leak / stats-poisoning surface** — central A11
cross-link.

- **Leaky operator attack**: a low-privilege user runs `SELECT *
  FROM tbl WHERE secret_col = my_op('payload')` where `my_op` is a
  non-leakproof function they defined. Without the leakproof gate,
  the planner's `mcv_selectivity` would invoke `my_op` against each
  MCV value of `secret_col`, leaking those values to the function.
  This is exactly what `statistic_proc_security_check` prevents.
- **Stats poisoning (A11 link)**: postgres_fdw stats import / PG17+
  user-callable stats import means stats can come from a less-
  trusted source. A poisoned histogram can drive the planner to a
  bad plan or to an expensive parameter-dependent invocation.
- **`get_relation_stats_hook` / `get_index_stats_hook`** [lines
  153-158]: an extension owning these hooks can synthesize arbitrary
  stats per query. Same trust as a planner_hook — module-author
  level.

## Cross-refs

- `utils/index_selfuncs.h` — index AM estimator entry points.
- `nodes/pathnodes.h` — `PlannerInfo`, `RelOptInfo`, `IndexOptInfo`.
- `catalog/pg_statistic.h` — backing storage.
- A11 postgres_fdw stats-import, A12 amcheck/pgstattuple, A14 stats
  surface.

## Issues

- [ISSUE-PHASE-D: ACL gate (`acl_ok` + `statistic_proc_security_check`)
  is enforced at each estimator's discretion — there's no single
  enforcement point. Missing the check in a new estimator opens the
  MCV-leak channel (high, well-known historical CVE class)] —
  lines 99-100, 165.
- [ISSUE-DEFAULT: defaults at lines 33-56 are tuned to make
  indexscans win; they're effectively a planner policy with no
  cassert-time tunability and only loose links to actual stats
  shapes (low)] — lines 33-56.
- [ISSUE-A11: `get_relation_stats_hook` lets an FDW-driven module
  silently override stats per query without an audit trail —
  combined with cost-based plan choice, this is the lever for
  poisoned cross-cluster stats (medium)] — lines 149-158.
