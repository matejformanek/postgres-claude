---
source_url: https://www.postgresql.org/docs/current/planner-optimizer.html
fetched_at: 2026-06-10T20:55:00Z
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Planner/Optimizer (internals ch. 51.5)

The overview of how PG turns a rewritten query tree into a plan tree. Pairs with
the `executor-and-planner` skill (which covers the `add_path` cost-dominance
pruning and `createplan.c` Path→Plan mechanics at code level).

## Non-obvious claims

- **Path = cut-down plan.** The planner reasons over *paths* — "cut-down
  representations of plans containing only as much information as the planner needs
  to make its decisions." Only after the cheapest path is chosen is a full plan
  tree built for the executor. This is the central data-structure split of the
  optimizer. [from-docs]
- **Sequential scan is always a baseline path** for every relation; index scan
  paths are added only when a restriction `relation.attribute OPR constant` matches
  an index key *and* the operator belongs to the index's operator class. [from-docs]
- **Indexes also win for ordering, not just filtering** — an index whose sort order
  matches `ORDER BY` (or is useful as a merge-join input) generates a path even
  without an equality predicate. [from-docs]
- **Three join methods, each with a distinct cost profile:**
  - *Nested loop* — right relation scanned once per left row; cheap to implement,
    can be costly unless the right side has an index.
  - *Merge join* — both inputs sorted on join keys, then scanned in parallel; each
    relation scanned only once.
  - *Hash join* — right relation loaded into a hash table keyed on join attrs, then
    left relation probed. [from-docs]
- **🔑 Join-order search is threshold-gated by `geqo_threshold`.** Below the
  threshold (fewer relations): near-**exhaustive** bottom-up search, preferentially
  joining relation pairs that have a join clause (`WHERE rel1.a=rel2.b`), falling
  back to clause-less (Cartesian) pairs only when forced. At/above the threshold:
  the **Genetic Query Optimizer** (GEQO, ch. 61) replaces exhaustive search with
  heuristics — explicitly because exhaustive search "would take an excessive amount
  of time and memory." [from-docs]
- **Selection and projection are distributed, not centralized.** Most plan node
  types can themselves discard rows (selection) and compute derived columns
  (projection); the planner attaches these to "the most appropriate nodes" rather
  than adding dedicated nodes. [from-docs]
- **Finished plan tree node inventory:** seq/index scans of base rels;
  nested-loop / merge / hash join nodes; auxiliary sort and aggregate nodes.
  [from-docs]

## Links into corpus

- Code-level companion: `executor-and-planner` skill (RelOptInfo lifecycle,
  `add_path` dominance pruning, `cost_*` units, `createplan.c`).
- GEQO detail: `knowledge/docs-distilled/geqo.md`.
- Costing inputs: `knowledge/docs-distilled/planner-stats.md` and
  `knowledge/docs-distilled/row-estimation-examples.md` (this run).
- Upstream stage: `knowledge/docs-distilled/query-path.md` (this run).
- Code: `source/src/backend/optimizer/path/allpaths.c`,
  `source/src/backend/optimizer/plan/createplan.c`,
  `source/src/backend/optimizer/path/joinpath.c`. [unverified — not line-pinned]
