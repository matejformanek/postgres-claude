---
source_url: https://www.postgresql.org/docs/current/geqo.html
fetched_at: 2026-06-07T00:00:00Z
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Docs distilled — Chapter 62: Genetic Query Optimizer

The planner's escape hatch for large join problems. The exhaustive
(`dynamic-programming`) join-order search in `make_one_rel` is super-linear in
the number of base relations; past a threshold it becomes infeasible, so the
planner switches to a **genetic algorithm** that treats join orders as
chromosomes and evolves a good-enough plan in bounded time. This doc captures
the GUC surface, the encoding, and the *cost* of using it (non-deterministic
plans), and links to the optimizer subsystem doc.

## When GEQO fires

- **Trigger = number of FROM-list items ≥ `geqo_threshold`** (default 12). Below
  that, the standard near-exhaustive `dynamic-programming` search runs. [from-docs]
  [verified-by-code, source/src/backend/optimizer/path/allpaths.c — `make_rel_from_joinlist`
  checks `enable_geqo && levels_needed >= geqo_threshold`; via
  knowledge/subsystems/optimizer.md]
- The exhaustive search is what `add_path` cost-dominance pruning feeds; GEQO
  *replaces* the join-order search only — base-rel path generation, costing, and
  the final `RelOptInfo` are shared. The genetic part is purely "in what order do
  we join". [inferred, from-docs]

## The encoding (why it's "genetic")

- **A chromosome is an integer string; each gene is a base-relation index.** A
  candidate join order is a permutation of the relation ids. [from-docs]
  [verified-by-code, source/src/backend/optimizer/geqo/geqo_recombination.c +
  geqo_pool.c — `Gene` is the relid type, `Chromosome` carries the `string` of genes]
- **`gimme_tree` (geqo_eval.c) decodes a chromosome into a join tree** by greedily
  merging "clumps" (`merge_clump`); the resulting tree is costed via the normal
  path machinery and that cost is the chromosome's *fitness*. [from-docs]
  [verified-by-code, source/src/backend/optimizer/geqo/geqo_eval.c — `gimme_tree`,
  `merge_clump`]
- **Crossover = edge recombination** (`geqo_recombination.c`): children inherit
  *adjacencies* (which relation is joined next to which) rather than absolute
  positions, because for join ordering the neighbor relationship is what carries
  cost signal, not the slot index. [from-docs] [from-comment]

## The GUCs (all `geqo_*`)

| GUC | Default | Role |
|---|---|---|
| `geqo` | on | master switch for GEQO |
| `geqo_threshold` | 12 | FROM-item count at/above which GEQO is used |
| `geqo_effort` | 5 | 1–10 dial; derives pool_size/generations when those are 0 |
| `geqo_pool_size` | 0 (=auto from effort) | population per generation |
| `geqo_generations` | 0 (=auto from effort) | number of evolution rounds |
| `geqo_selection_bias` | 2.0 | selective pressure (1.5–2.0) |
| `geqo_seed` | 0.0 | PRNG seed (0–1) for the random path choices |

[from-docs] — defaults cross-checked against the GUC table; treat the numeric
defaults as `[from-docs]` since they can change between majors.

## The cost you accept by using it

- **Plans are non-deterministic across runs** unless `geqo_seed` is pinned: the
  same query can get different join orders (hence different EXPLAIN, different
  runtime) on repeated planning. This is the headline gotcha for anyone debugging
  "why did this query get slow today" on a wide join. [from-docs]
- **No cross-call memory.** GEQO does **not** cache the best chromosome it found
  for a query shape; every planning invocation re-runs the GA from a fresh random
  pool. The chapter explicitly lists "remembering the best plan across calls" as
  unimplemented future work. [from-docs]
- `geqo_seed` makes a single backend reproducible, but does **not** make the plan
  *good* — it only makes it *stable*. Raising `geqo_threshold` above the real
  join count is the usual fix when a wide query needs the exhaustive search.
  [inferred, from-docs]

## Links into corpus

- [[knowledge/subsystems/optimizer.md]] — the exhaustive `dynamic-programming`
  join search GEQO substitutes for, plus `add_path` cost-dominance.
- [[knowledge/architecture/planner.md]] — where join-order search sits in the
  Path → Plan pipeline.
- [[knowledge/docs-distilled/planner-stats.md]] — the row-count estimates that
  feed the fitness function GEQO optimizes against.
- executor-and-planner skill — for code-level work in `optimizer/path/` and
  `optimizer/geqo/`.

## Gaps / follow-ups

- No per-file corpus doc yet for `src/backend/optimizer/geqo/*.c`
  (`geqo_main.c`, `geqo_eval.c`, `geqo_pool.c`, `geqo_recombination.c`,
  `geqo_selection.c`). A focused read would let the optimizer subsystem doc cite
  `gimme_tree`/`merge_clump` at file:line instead of the `[verified-by-code]`
  pointers above.
