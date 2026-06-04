# network_selfuncs.c — selectivity estimators for inet operators

## Purpose

Unlike `geo_selfuncs.c`, this file does real statistics-based estimation for inet operators (`<<`, `<<=`, `>>`, `>>=`, `&&`). Uses the column's MCV list and histogram from `pg_statistic` to estimate how many tuples satisfy a network containment / overlap predicate.

Source: `source/src/backend/utils/adt/network_selfuncs.c` (990 lines).

## Key functions

- `networksel` (line 78) — single-column selectivity. Dispatches by operator strategy; loads MCV + histogram; estimates via `inet_mcv_join_sel` / `inet_hist_inclusion_selectivity`. [verified-by-code]
- `networkjoinsel` (line 203) — two-column join selectivity. Builds two MCVs and computes overlap. [verified-by-code]

Plus extensive private helpers (`inet_hist_value_sel`, `inet_mcv_join_sel`, `inet_inclusion_selectivity`, `inet_semi_join_selectivity`, `inet_opr_codenum`) — the file is a self-contained estimator.

## Phase D notes

- **Real statistics-driven estimation** — substantially smarter than `geo_selfuncs`.
- **Family-aware**: MCV entries of one family are not matched against histogram bins of the other.
- **Histogram-based inclusion** uses the assumption that addresses within a histogram bin are uniformly distributed across the bin's CIDR range — defensible but optimistic for clustered data.
- No security surface: pure statistics.

## Potential issues

- `[ISSUE-correctness: histogram-based estimation assumes uniform distribution within a bin; for sparse address spaces (e.g. IPv6 with a few /48s) the assumption is wildly off (low — known stats limitation)]`.
- `[ISSUE-undocumented-invariant: the join estimator assumes the two columns have stats from the SAME population sampling; cross-database joins via FDW with stale stats can produce nonsense estimates (low)]`.

Confidence: `[verified-by-code]` for entry points.
