---
source_url: https://www.postgresql.org/docs/current/overview.html
also_referenced:
  - https://www.postgresql.org/docs/current/query-path.html
  - https://www.postgresql.org/docs/current/connect-estab.html
  - https://www.postgresql.org/docs/current/parser-stage.html
  - https://www.postgresql.org/docs/current/planner-optimizer.html
  - https://www.postgresql.org/docs/current/executor.html
fetched_at: 2026-06-06T00:00:00Z
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Docs distilled — Chapter 51: Overview of PostgreSQL Internals

The "path of a query" chapter — the canonical map of what happens between a
backend receiving SQL text and returning rows. It is the orientation document
the whole `knowledge/subsystems/*` set decomposes; this distillation pins the
stage boundaries and the exact terminology so the per-subsystem docs can be
read against a shared spine. (Chapter derives from Stefan Simkovics' MSc
thesis; the prose is old but the stage decomposition is unchanged through PG18.)

## The five stages, in order

1. **Connection establishment (51.2).** The **postmaster** listens on a port;
   on each client connection it **forks a dedicated backend process** — one
   backend per connection, no threading. The postmaster does not handle the
   query itself, it only sets up the connection and gets out of the way. After
   the fork, client and backend talk directly without postmaster intervention.
   [from-docs] [via knowledge/subsystems/tcop.md, knowledge/subsystems/main.md]
2. **Parser stage (51.3).** Two distinct sub-steps the chapter is careful to
   separate:
   - **Parser** (raw parsing): a deliberately **simple** flex/bison grammar that
     only checks SQL *syntax* and builds a **raw parse tree**. It does **no**
     catalog access — it cannot, because it must run before semantic knowledge
     is available, and keeping it dumb keeps the grammar tractable. [from-docs]
   - **Transformation / analysis**: walks the raw parse tree, resolves table and
     column names against the catalogs, expands `*`, type-checks, and produces a
     **query tree** (a `Query` node). This is where semantic meaning enters.
     [from-docs] [via knowledge/subsystems/parser-and-rewrite.md,
     knowledge/idioms/parser-pipeline.md]
3. **Rewrite system (51.4).** The **rule system** rewrites the query tree per
   rules stored in `pg_rewrite`. **Views are implemented here**: a `SELECT` on a
   view is rewritten by substituting the view's underlying query (a rule named
   `_RETURN`). Output is still a (possibly expanded into several) query tree.
   [from-docs] [via knowledge/subsystems/parser-and-rewrite.md]
4. **Planner / optimizer (51.5).** Takes the rewritten query tree and **generates
   candidate Paths**, costs them, and selects the **cheapest** one, then turns it
   into a finished **plan tree** (`PlannedStmt` of `Plan` nodes). For joins it
   enumerates orderings; when the join count is high it switches to **GEQO**
   (genetic optimizer) rather than exhaustive search. The planner is cost-based,
   not rule-based. [from-docs] [via knowledge/subsystems/optimizer.md]
5. **Executor (51.6).** Walks the plan tree in a **demand-pull (Volcano /
   iterator) model**: each node pulls tuples from its children one at a time on
   request. The executor recursively processes the tree, applying the operations
   (joins, sorts, aggregates) the plan prescribes, and hands result rows back to
   the client. [from-docs] [via knowledge/subsystems/executor.md]

## Non-obvious points worth keeping

- **Raw parse tree ≠ query tree.** The two-phase parser is a recurring source of
  confusion: "the parser" produces a syntax-only raw tree with zero catalog
  lookups; only *analysis/transformation* yields the semantically-resolved
  `Query`. Code that needs name resolution lives in the second phase
  (`parse_analyze*`), not the grammar. [from-docs]
- **One backend per connection** is the architectural fact that makes a fresh
  process (and thus cold caches, `InitPostgres`, fork cost) appear on every
  `psql` connect — the thing the CLAUDE.md "per-connection fork model" warning
  is about. [from-docs]
- **The optimizer is path-based before it is plan-based.** Candidate enumeration
  works on `Path` nodes (cheap to create/discard); only the winner is expanded to
  a `Plan`. This Path→Plan split is the load-bearing design the `executor-and-planner`
  skill and `optimizer.md` document. [from-docs]
- **The rewrite system sits *between* analysis and planning**, not inside either.
  Views, `DO INSTEAD` rules, and `RETURNING`-bearing rules are all this stage.
  [from-docs]

## The query's data-structure spine (terminology to plan tree)

| Stage | Input | Output | Node/struct |
|---|---|---|---|
| Raw parse | SQL text | raw parse tree | `RawStmt` / grammar nodes |
| Analysis | raw parse tree | query tree | `Query` |
| Rewrite | `Query` | 0..n `Query` | `Query` (rules from `pg_rewrite`) |
| Plan | `Query` | plan tree | `Path` → `Plan` / `PlannedStmt` |
| Execute | `PlannedStmt` | tuples | `PlanState` tree |

## Links into corpus

- [[knowledge/subsystems/tcop.md]] — the `postgres.c` main loop that drives
  exactly this stage sequence (`exec_simple_query`).
- [[knowledge/subsystems/parser-and-rewrite.md]] — stages 2–3 in depth.
- [[knowledge/idioms/parser-pipeline.md]] — raw-parse → analyze → rewrite idiom.
- [[knowledge/subsystems/optimizer.md]] — stage 4 (Path→Plan, add_path).
- [[knowledge/subsystems/executor.md]] — stage 5 (ExecInitNode/ExecProcNode).
- [[knowledge/idioms/node-types-and-lists.md]] — the `Node`/`List` machinery the
  trees above are built from.

## Gaps / follow-ups

- The five sub-pages (query-path, connect-estab, parser-stage, planner-optimizer,
  executor) were read for their claims but only the chapter-level prose is
  quoted here; each subsystem doc already carries the file:line depth, so no
  separate per-subpage distillation is queued.
