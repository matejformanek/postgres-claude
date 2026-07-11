# `src/backend/statistics/extended_stats.c`

- **Last verified commit:** `c1702cb51363` (re-pinned 2026-07-11 from `ef6a95c7c64`; `bms_offset_members` commit `bb7ded1eebed` and neighbours shifted the selectivity entry points by −6)
- **Lines:** 2666
- **Source:** `source/src/backend/statistics/extended_stats.c`

## Purpose

Driver layer for `CREATE STATISTICS` objects (functional dependencies,
mvdistinct, MCV lists, and expression stats). Builds extended stats during
`ANALYZE`, then answers the planner during selectivity estimation by
combining MCV + dependencies on top of per-column stats.

## Key entry points

- `BuildRelationExtStatistics` (`extended_stats.c:112-`) — invoked from
  `commands/analyze.c` after per-column stats are computed; iterates each
  `pg_statistic_ext` row for the relation and builds the requested
  ndistinct / dependencies / MCV / expr stats from the same sampled rows
  used for per-column stats. Each kind gets a memory context that is reset
  per object.
- `ComputeExtStatisticsRows` — computes how many rows to sample
  (`statext_compute_stattarget`-driven from per-object STATISTICS targets,
  per-column targets, and `default_statistics_target`).
- `statext_clauselist_selectivity` (`extended_stats.c:2024`) — planner
  entry. Two-step: MCV first, then functional dependencies on the
  remainder. For OR clauses, only MCV applies (dependencies are AND-only).
  Dependencies run last because they're coarser than MCV. [from-comment]
  (`extended_stats.c:2035-2059`)
- `statext_mcv_clauselist_selectivity` (`extended_stats.c:1737`) — greedy
  per round: pick the best stats object (`choose_best_statistics`), apply
  it, mark those clauses in `estimatedclauses` bitmap, repeat.
- `choose_best_statistics` (`extended_stats.c:1256`) — pick the object
  that (1) covers the most clause attnums+exprs, (2) breaks ties by
  fewest total keys (narrowest stats wins). XXX comment notes
  insertion-order tiebreak as a known weakness. [from-comment]
  (`extended_stats.c:1250-1254`)

## Clause-compatibility rules (the gatekeeper)

`statext_is_compatible_clause_internal` (`extended_stats.c:1378`) accepts:
- `Var op Const` or `Const op Var` with operator restriction-selectivity
  function in `{F_EQSEL, F_NEQSEL, F_SCALARLTSEL/LESEL/GTSEL/GESEL}`.
  Same set for `ScalarArrayOpExpr` (Var only on left). [verified-by-code]
  (`extended_stats.c:1433-1447`, `:1490-1504`)
- `IS NULL` / `IS NOT NULL`.
- AND / OR / NOT compositions (all children must be compatible).
- System columns and `varlevelsup>0` rejected. (`extended_stats.c:1396-1404`)
- Leakproof bookkeeping: any non-leakproof operator forces a permissions
  check that the user can select **all rows** (no security barrier / RLS)
  for the referenced columns, otherwise the clause is rejected. This
  prevents MCV/dependencies from leaking values the user couldn't read.
  [verified-by-code] (`extended_stats.c:1660-1702`)

## MCV combining ("base / simple / total")

For each MCV object we compute three selectivities (`extended_stats.c:1720-`):
- **simple**: column-independent product (the standard estimator's answer).
- **base**: sum of MCV item base-frequencies (product of per-column
  frequencies) of items matching the clauses — the MCV's own "independence
  assumption" answer for the MCV-covered portion.
- **total**: total MCV coverage (sum of all MCV item frequencies).

Then `mcv_combine_selectivities` mixes them so that MCV provides the
"correlated" answer on the MCV-covered portion and per-column stats handle
the long tail. (See `knowledge/files/src/backend/statistics/mcv.c.md`.)

## Building expression stats (`compute_expr_stats`, `:2135`)

- Creates an `EState` + per-tuple `ExprContext` in a dedicated
  `"Analyze Expression"` AllocSet.
- For each sampled tuple: `ExecEvalExprSwitchContext`, then `datumCopy`
  the result into `expr_context` so it survives `ResetExprContext`.
- Drives `stats->compute_stats(stats, expr_fetch_func, tcnt, tcnt)` —
  reuses the standard per-column stat builders, just with a synthetic
  fetch callback over the materialized `exprvals[]`. `n_distinct`
  attoption override applies as for regular columns.

## How extended stats merge into rel cardinality

Note for the curious: `extended_stats.c` itself only adjusts **clause
selectivities** (the per-clause / per-pair multipliers). Total row
cardinality at `RelOptInfo` level is `rel->rows = rel->tuples * sel`,
where `sel` is the product of clauselist selectivities. The extended-
stats hook is called inside `clauselist_selectivity_ext` so its corrected
selectivity is naturally used by the planner without any special-cased
cardinality patching. The `estimatedclauses` bitmap is the contract:
clauses marked as estimated get `selectivity = 1.0` in the standard
fallback loop, so the corrected value is not double-counted. [verified-by-code]
(see `optimizer/path/clausesel.c`)

## Notable invariants

- Inheritance flag (`inh`) must match between stats object and request —
  separate stats are built per inheritance flavor. (`extended_stats.c:1278-1280`)
- WIDTH_THRESHOLD = 1024 bytes: wider varlena values are ignored for MCV /
  ndistinct purposes — they're unlikely to be MCV anyway. [from-comment]
  (`extended_stats.c:50-59`)
- `STATS_MAX_DIMENSIONS` caps stats object width (8 by default — see
  `statistics.h`).
- Expression stats are stored as a serialized `pg_statistic`-shaped
  pseudo-rel in `pg_statistic_ext_data.stxdexpr` (one element per
  declared expression). `serialize_expr_stats` / `statext_expressions_load`.

## Cross-refs

- Inbound: `commands/analyze.c`, `optimizer/path/clausesel.c` (planner).
- Outbound: `dependencies.c`, `mvdistinct.c`, `mcv.c` for per-kind logic;
  `statistics/extended_stats_internal.h` for shared types.

## Tag tally

`[verified-by-code]` 4 / `[from-comment]` 5

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
- [idioms/extended-statistics-statext.md](../../../../idioms/extended-statistics-statext.md)

