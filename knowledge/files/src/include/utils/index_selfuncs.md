# `src/include/utils/index_selfuncs.h`

**Pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`

## Role

Index cost-estimator entry points, one per built-in index AM
[from-comment: lines 3-4]. Split out of `selfuncs.h` specifically
to avoid pulling planner internals into the AMs [from-comment:
lines 7-9].

## Public API

[verified-by-code: lines 25-72] Each AM exposes one function with
identical signature:

```c
void <am>costestimate(PlannerInfo *root, IndexPath *path,
                      double loop_count,
                      Cost *indexStartupCost, Cost *indexTotalCost,
                      Selectivity *indexSelectivity,
                      double *indexCorrelation,
                      double *indexPages);
```

Functions: `btcostestimate` (B-tree), `hashcostestimate`,
`gistcostestimate`, `spgcostestimate`, `gincostestimate`,
`brincostestimate`.

The structs `PlannerInfo` and `IndexPath` are referenced via `struct`
without including the full headers — only `access/amapi.h` is pulled
in [from-comment: lines 9-10].

## Invariants

- **INV-MIN-DEPENDENCY** [from-comment: lines 7-10] This header
  must depend on nothing beyond `access/amapi.h`. Adding a new
  include is treated as a mistake.
- **INV-SIG** [inferred] All six estimators share the same signature
  because `amapi.h` `amcostestimate` field points to one of them.

## Trust boundary (Phase D)

- Cost estimators read `pg_statistic` MCV/histogram entries
  (indirectly via `selfuncs.h` helpers). They run under the planner
  in the user's privilege context — stats poisoning by an attacker
  with INSERT to `pg_statistic` (superuser-only by default; FDW
  stats-import in PG17+ widens this surface) can mislead the cost
  estimator into picking a bad plan or running an expensive
  parameter-dependent function via mcv_selectivity. A11
  cross-finding.

## Cross-refs

- `utils/selfuncs.h` — `genericcostestimate`, shared helpers.
- `access/amapi.h` — `amcostestimate` AM slot.
- A11 postgres_fdw stats-import angle.

## Issues

None at header level.
