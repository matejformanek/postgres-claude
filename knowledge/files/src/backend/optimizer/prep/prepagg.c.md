# prepagg.c — Aggref / transition-state preprocessing

- **Source:** `source/src/backend/optimizer/prep/prepagg.c` (695 lines)
- **Last verified commit:** `ef6a95c7c64`
- **Depth:** read

## Purpose

Two optimizations applied to all Aggrefs in a query:
1. **Identical Aggrefs** are computed only once (CSE on aggregates).
2. **Compatible aggregates share a transition state** (e.g. `sum(x)` +
   `avg(x)` both reuse the running sum/count); only the final functions
   run separately. [from-comment:6-10]

Polymorphic transition types are resolved here too. [from-comment:15-16]

## Validity preconditions for sharing

All aggregate properties used during transition must be equal: ORDER BY,
DISTINCT, FILTER, and the arguments must be non-volatile. [from-comment:104-108]

## Public entries

- `void preprocess_aggrefs(PlannerInfo *root, Node *clause)` (line 109) —
  creates `AggInfo` and `AggTransInfo` lists on root; sets per-Aggref
  `aggno` / `transno` / `aggtranstype` fields.
- `void get_agg_clause_costs(PlannerInfo *root, AggSplit aggsplit, AggClauseCosts *costs)`
  (line 558) — sum costs for the discovered transitions/finals; estimates
  hashagg memory as if every state was concurrent.
  [from-comment:548-555]

## Wart

`AggInfo` / `AggTransInfo` are thrown away after planning, so executor
startup duplicates some of these lookups. Acknowledged by a comment as
"one day, fix this". [from-comment:18-22]

## Tags
`[verified-by-code]` ×1, `[from-comment]` ×6

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
