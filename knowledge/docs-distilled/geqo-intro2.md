---
source_url: https://www.postgresql.org/docs/current/geqo-intro2.html
fetched_at: 2026-06-21T00:00:00Z
anchor_sha: f25a07b2d94c
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: false
---

# Docs distilled — §61.2: Genetic Algorithms (GEQO background)

The vocabulary chapter. It defines the genetic-algorithm terms PG's GEQO
implementation ([geqo-pg-intro.md](./geqo-pg-intro.md)) then reuses. Almost all
of this is **general GA theory, not PG-specific** — flagged as such per bullet
so a reader doesn't mistake the analogy for an implementation claim.

## The vocabulary (general GA theory)

- **Population** — the set of all candidate solutions currently under
  consideration. `[from-docs]`
- **Individual** — one candidate solution within the population. `[from-docs]`
- **Fitness** — a scalar metric for how well an individual solves the problem
  ("degree of adaptation to its environment"). In GEQO, fitness = the standard
  planner's estimated total cost of the encoded join order (lower is fitter).
  `[from-docs]` (The cost↔fitness mapping itself is the PG-specific part,
  defined in §61.3, not here.)
- **Chromosome** — a string encoding an individual's coordinates in the search
  space. `[from-docs]`
- **Gene** — a sub-section of a chromosome encoding one parameter; typical
  encodings are **binary** or **integer**. GEQO uses the integer encoding (relation
  IDs). `[from-docs]`

## The evolutionary operators (general GA theory)

A GA improves the population by iterating three operations to produce successive
generations of higher average fitness: `[from-docs]`

1. **Recombination** — splice genetic material from multiple parent individuals
   into a child. (GEQO's recombination = edge-recombination crossover, §61.3.)
2. **Mutation** — random alteration of a chromosome. (GEQO **omits** mutation in
   its default operator path — see §61.3 for why: it would break TSP-tour
   legality.)
3. **Selection** — preferentially retain high-fitness individuals across
   generations.

## The one claim worth remembering

- **A GA is NOT a random search.** The page explicitly quotes the
  comp.ai.genetic FAQ: a GA "uses stochastic processes, but the result is
  distinctly non-random (better than random)." `[from-docs]` This is the
  conceptual justification for GEQO returning usable plans far faster than the
  exhaustive dynamic-programming search, despite sampling only a slice of the
  join-order space.
- §61.2 stops at vocabulary; the actual analogy to query optimization (TSP
  framing, integer relation-ID encoding, the Genitor-derived steady-state GA) is
  deferred to §61.3. Don't look for PG specifics here. `[from-docs]`

## Links into corpus

- The PG-specific implementation that uses this vocabulary:
  [docs-distilled/geqo-pg-intro.md](./geqo-pg-intro.md)
- Parent chapter (GUC surface, when-it-fires): [docs-distilled/geqo.md](./geqo.md) `primary`
- §61.1 (query optimization as a hard problem): [docs-distilled/geqo-intro.md](./geqo-intro.md)
