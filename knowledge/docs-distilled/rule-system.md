---
source_url: https://www.postgresql.org/docs/current/rule-system.html
fetched_at: 2026-06-14T19:58:00Z
anchor_sha: e18b0cb7344
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Docs distilled — The PostgreSQL Rule System (§51.4)

The one-paragraph internals-overview placement of the rewriter in the query
pipeline. This is the §51 "Overview of Internals" stub; the full treatment is
the separate Chapter 39 rules family (already partly distilled as `rules-views`
/ `querytree`). Use this only for "where does rewriting sit".

## The rewriter sits between parser and planner

- The rule system is implemented by **query rewriting**, a module **between the
  parser stage and the planner/optimizer**: [from-docs]
  ```
  Parser → Rewriter → Planner/Optimizer → Executor
  ```
- **Both input and output of the rewriter are query trees** — "there is no change
  in the representation or level of semantic detail in the trees." Unlike
  parse-analysis (raw → Query) or planning (Query → Plan), rewriting is
  **Query → Query**: a structure-preserving transform. [from-docs]
  [cross: knowledge/docs-distilled/query-path.md]

## Rewriting is macro expansion on the parse tree

- The docs frame rewriting as **"a form of macro expansion"** — a rule's action
  query tree is spliced into the user's query tree. This is how views
  (ON SELECT DO INSTEAD rules) and user-defined rules both work. [from-docs]
  [cross: knowledge/docs-distilled/rules-views.md]

## Historical note

- PostgreSQL originally had a **row-level rule implementation executed deep in the
  executor**; that was **removed in 1995** during the Postgres95 transition, and
  the parse-tree-rewriting design is what survives. Useful context for why the
  rule system is a rewriter and not an executor feature. [from-docs]

## Where the full story lives

- This section explicitly punts to **Chapter 39 "The Rule System"** (`rules.html`)
  for detail — the `pg_rewrite` catalog, ON SELECT/INSERT/UPDATE/DELETE rule
  forms, and the view-implementation mechanics are there, not here. [from-docs]

## Links into corpus
- [[knowledge/docs-distilled/rules-views.md]] — how views become ON SELECT DO INSTEAD rules (the Chapter 39 detail).
- [[knowledge/docs-distilled/querytree.md]] — the Query-tree structure the rewriter consumes and produces.
- [[knowledge/docs-distilled/query-path.md]] — the full parser→rewriter→planner→executor pipeline this section places the rewriter in.
- [[knowledge/docs-distilled/parser-stage.md]] — the stage immediately upstream.
- Skill: `parser-and-nodes` — for editing the rewriter / Query node machinery.

## Gaps / follow-ups
- Deliberately thin (it's the overview stub). The `pg_rewrite` catalog and the
  rule-action splicing detail are corpus/Chapter-39 territory — cite
  `rules-views.md`, not this doc, for anything load-bearing about rule storage.
