# cost.h — costsize.c + clausesel.c prototypes

- **Source:** 226 lines · **Last verified commit:** `ef6a95c7c64`

Public cost-model constants (`DEFAULT_SEQ_PAGE_COST=1.0`,
`DEFAULT_RANDOM_PAGE_COST=4.0`) and prototypes for every `cost_*`
estimator (cost_seqscan, cost_index, cost_bitmap_heap_scan, cost_sort,
cost_hashjoin, cost_mergejoin, cost_agg, cost_windowagg, …) plus the
selectivity entry points (`clauselist_selectivity*`, `clause_selectivity*`).

Module-wide GUCs declared: `seq_page_cost`, `random_page_cost`,
`cpu_*_cost`, `effective_cache_size`, `enable_seqscan`, `enable_hashagg`,
the whole `enable_*` family.

Caveat in source: "cost-estimation code should use the variables, not
these constants" — DEFAULTS are for postgresql.conf seeding only.
[from-comment:21-23]

## Appears in scenarios

<!-- scenarios:auto:begin -->

- [Scenario — Add a new cost-model constant (and optional GUC)](../../../../scenarios/add-new-cost-model-knob.md)
- [Scenario — Add a new plan node](../../../../scenarios/add-new-plan-node.md)

<!-- scenarios:auto:end -->

## Synthesized by
<!-- backlinks:auto -->
- [idioms/cost-units-gucs.md](../../../../idioms/cost-units-gucs.md)
