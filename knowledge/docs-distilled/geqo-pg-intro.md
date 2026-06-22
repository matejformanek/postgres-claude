---
source_url: https://www.postgresql.org/docs/current/geqo-pg-intro.html
fetched_at: 2026-06-21T00:00:00Z
anchor_sha: f25a07b2d94c
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: false
---

# Docs distilled — §61.3: Genetic Query Optimization (GEQO) in PostgreSQL

The implementation half of the GEQO chapter: how PG actually maps the
join-order search onto a genetic algorithm. The parent `geqo.html`
([docs-distilled/geqo.md](../docs-distilled/geqo.md)) covers the GUC surface
and *when* GEQO fires; this leaf covers the *encoding* and the genetic
machinery, plus the limitations the docs themselves admit.

## The TSP framing (non-obvious)

- GEQO recasts join-order optimization as a **Traveling Salesman Problem
  (TSP)**: find the lowest-cost ordering in which to visit (join) the base
  relations. `[from-docs]`
- A candidate join order is encoded as a **string of integer relation IDs** —
  a chromosome. The docs' worked example: the join tree with leaves 4,1,3,2
  encodes as `'4-1-3-2'`, read as "join rel 4 to rel 1, then join rel 3, then
  join rel 2." `[from-docs]` Each integer is a *gene*; the whole string is the
  *chromosome* (terms from §61.2, [geqo-intro2.md](./geqo-intro2.md)).
- Crucial: GEQO only searches the **join order** (the shape/sequence). The
  per-step cost — and the choice among the three join *strategies*
  (nestloop / merge / hash) at each join — is still delegated to the **standard
  planner's cost estimator**, run once per candidate sequence. GEQO is a search
  heuristic *wrapped around* the normal costing machinery, not a replacement
  for it. `[from-docs]`

## The genetic machinery PG actually uses

- **Steady-state GA**, not generational: each "generation" replaces only the
  *least-fit* individuals in the pool rather than the whole population. The
  docs cite this as the reason for faster convergence. `[from-docs]`
  Implemented in the pool-management code
  ([files/.../geqo_pool.c.md](../files/src/backend/optimizer/geqo/geqo_pool.c.md),
  [geqo_selection.c.md](../files/src/backend/optimizer/geqo/geqo_selection.c.md)).
- **Edge-recombination crossover (ERX)** is the recombination operator,
  chosen specifically to minimize "edge losses" when splicing two parent tours
  — a TSP-aware crossover. `[from-docs]` (Source: `geqo_erx.c`; PG also ships
  several *alternative* recombination operators — cx/ox1/ox2/pmx/px — selectable
  at build time, see the `geqo_recombination.c` dispatcher and the per-operator
  files under `src/backend/optimizer/geqo/`.) `[verified-by-code]`
- **No mutation operator** in the default path: mutation is deliberately
  omitted because a random swap would usually produce an *illegal* TSP tour
  (a relation visited twice / not at all), which would then need a repair pass.
  ERX alone keeps every child a legal permutation. `[from-docs]` (`geqo_mutation.c`
  exists but is only wired in for recombination operators that can produce
  illegal tours.) `[verified-by-code]`
- The whole approach is **adapted from D. Whitley's Genitor algorithm**. `[from-docs]`

## The planning loop

1. The standard planner first builds scan paths for each individual base
   relation (GEQO does not touch scan-level planning). `[from-docs]`
2. GEQO seeds a **pool** of random initial join sequences (legal permutations). `[from-docs]`
3. For each sequence, the standard planner estimates total cost — this is the
   **fitness** (lower cost = more fit). The fitness evaluation lives in
   `geqo_eval.c`
   ([geqo_eval.c.md](../files/src/backend/optimizer/geqo/geqo_eval.c.md)). `[from-docs]`
4. Least-fit candidates are discarded; new candidates are bred by ERX from fit
   parents. `[from-docs]`
5. Loop until a preset number of sequences has been evaluated; the best ever
   seen is returned as the chosen join order. `[from-docs]`

The driver for all of this is `geqo()` in `geqo_main.c`
([geqo_main.c.md](../files/src/backend/optimizer/geqo/geqo_main.c.md)). The docs
name `gimme_pool_size` and `gimme_number_generations` (in `geqo_main.c`) as the
two tuning routines that trade plan optimality against planning time. `[from-docs]`

## Determinism — same query, same plan (with a caveat)

- GEQO is **stochastic but reproducible**: at the start of each run it reseeds
  its RNG from the **`geqo_seed`** GUC (a float in [0,1]). Same query + same
  `geqo_seed` + same other GEQO params ⇒ **identical plan**. `[from-docs]`
- This is the lever for experimentation: nudge `geqo_seed` to explore a
  different region of the search space if the current plan looks bad. `[from-docs]`
- Practical consequence (ties back to the parent doc's warning): because the
  search is non-exhaustive, two *different* `geqo_seed` values can yield
  *different* plans for the *same* query — GEQO gives up the planner's usual
  "deterministic best plan" guarantee. `[from-docs]`

## Limitations the docs openly admit (future-work bullets)

- **Redundant recomputation**: distinct candidates that share a sub-sequence
  re-cost that shared join from scratch; caching sub-join cost estimates would
  save time at the price of memory. `[from-docs]`
- **The TSP analogy is imperfect**: in a true TSP the cost of a substring is
  independent of the rest of the tour, but in join optimization the cost of a
  join sub-sequence **depends on context** (what's already been joined, row
  estimates, available indexes). ERX optimizes for a property the real problem
  doesn't have. `[from-docs]`
- Consequently the **choice of ERX is itself questionable**, and the GA
  parameter settings remain admittedly suboptimal. `[from-docs]`

## Links into corpus

- Parent chapter (GUC surface, when-it-fires): [docs-distilled/geqo.md](./geqo.md) `primary`
- GA vocabulary this page reuses: [docs-distilled/geqo-intro2.md](./geqo-intro2.md)
- Driver / fitness / pool source docs:
  [geqo_main.c.md](../files/src/backend/optimizer/geqo/geqo_main.c.md),
  [geqo_eval.c.md](../files/src/backend/optimizer/geqo/geqo_eval.c.md),
  [geqo_pool.c.md](../files/src/backend/optimizer/geqo/geqo_pool.c.md),
  [geqo_recombination.c.md](../files/src/backend/optimizer/geqo/geqo_recombination.c.md),
  [geqo_erx.c.md](../files/src/backend/optimizer/geqo/geqo_erx.c.md)
- Optimizer subsystem (the standard DP join search GEQO replaces):
  [docs-distilled/planner-optimizer.md](./planner-optimizer.md)
