---
source_url: https://www.postgresql.org/docs/current/geqo-intro.html
fetched_at: 2026-06-19T18:50:00Z
anchor_sha: bdae2c20e88d
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# GEQO Introduction (genetic-query-optimizer ch. 61.1)

The "why a genetic algorithm at all" leaf of §61 — the combinatorial-explosion
argument behind GEQO, distinct from the already-distilled `geqo.md` parent.
Note: the GUC parameters (`geqo_threshold` et al.) and the explicit
gene/chromosome/population/fitness vocabulary live in §61.2+, **not** in this
§61.1 introduction.

## The problem GEQO exists to dodge

- **Join-order plan space grows exponentially with the number of joins.** The
  number of possible query plans grows exponentially in the join count.
  [from-docs]
- PostgreSQL's **standard** optimizer does a *near-exhaustive search* over join
  strategies, based on the **IBM System R** dynamic-programming algorithm.
  [from-docs]
- That near-exhaustive search "can take an enormous amount of time and memory
  space when the number of joins in the query grows large" — making the ordinary
  optimizer **inappropriate for queries joining a large number of tables.**
  [from-docs]

## What GEQO does instead

- GEQO implements a **genetic algorithm** to solve the join-ordering problem
  "in a manner that is efficient for queries involving large numbers of joins."
  [from-docs]
- Implication (not stated as such in §61.1): GEQO trades the standard
  optimizer's near-optimality for **bounded planning time** — a heuristic search
  rather than an exhaustive one. [inferred]
- The genetic-algorithm framing (treating join order as a combinatorial
  optimization problem modeled on biological evolution; the TSP analogy; the
  gene/chromosome/fitness terms) is developed in **later §61 sections**, not the
  introduction. [from-docs — explicit "see Chapter 61" forward reference]

## Where it kicks in (pointer)

- The activation threshold is the **`geqo_threshold`** GUC (and GEQO itself is
  gated by the **`geqo`** boolean) — documented in §61.2 / runtime-config, *not*
  this intro page. [from-docs — deferred] → see `geqo.md`.

## Links into corpus

- [[knowledge/docs-distilled/geqo.md]] — the §61 parent (algorithm + GUCs).
- [[knowledge/docs-distilled/planner-optimizer.md]] — where the System R
  near-exhaustive search sits in the planner pipeline.
- [[knowledge/subsystems/optimizer.md]] — join-order enumeration
  (`join_search_one_level` / standard_join_search vs. geqo).
- [[knowledge/idioms/cost-join-paths.md]] — the cost model GEQO's fitness
  function ultimately calls.
- [[knowledge/data-structures/reloptinfo.md]] / [[knowledge/data-structures/plannerinfo.md]]
  — the rel/join structures the search permutes.

## Open questions

- Confirm the current default `geqo_threshold` (historically 12) and the
  `join_search_hook` path that swaps in `geqo()` at anchor `bdae2c20e88d` —
  belongs in `geqo.md`, not here.
