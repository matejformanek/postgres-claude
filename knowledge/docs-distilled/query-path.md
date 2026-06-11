---
source_url: https://www.postgresql.org/docs/current/query-path.html
fetched_at: 2026-06-10T20:55:00Z
anchor_sha: 4b0bf0788b066a4ca1d4f959566678e44ec93422
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# The Path of a Query (internals ch. 51.1)

The five-stage spine of backend query processing. This is the canonical map the
`parser-and-nodes` and `executor-and-planner` skills hang off; worth having
distilled even though it's prose-light, because it fixes the *vocabulary* (query
tree vs plan tree vs path) the rest of the corpus uses.

## Non-obvious claims

- **Five stages, in order:** (1) connection establishment, (2) parser, (3) rewrite
  system, (4) planner/optimizer, (5) executor. The client-server boundary is at
  stage 1; everything after is one forked backend. [from-docs]
- **Parser output is a *query tree*.** The docs page collapses raw-parse and
  semantic-analysis into "the parser stage creates a query tree"; it does *not*
  name gram.y/scan.l or the raw parse tree → query tree distinction (that detail
  lives in the parser chapter, not here). Treat the two-step (raw parse, then
  parse-analysis) as `[from-comment]`/`[verified-by-code]` knowledge from
  `parser-and-nodes`, not from this page. [from-docs]
- **Rewrite runs on the query tree, driven by catalog rules.** It looks up *rules*
  in the system catalogs and applies the transformations in their *rule bodies*.
  The headline application: **views are realized here** — a query against a view is
  rewritten to hit the base tables per the view definition. So views are a
  rewrite-stage construct, not a planner or executor one. [from-docs]
- **Planner consumes the *rewritten* query tree** and emits a *query plan* (plan
  tree). Its method: enumerate all *paths* that yield the same result, cost each,
  pick the cheapest, then expand that path into a complete plan. [from-docs]
- **Executor is demand-pull over the plan tree.** It recursively walks plan nodes,
  pulling rows, scanning relations through the storage system, doing sorts/joins,
  evaluating qualifications, and returning result rows. [from-docs]

## Links into corpus

- Stage 2 detail: `parser-and-nodes` skill + `knowledge/docs-distilled/querytree.md`.
- Stage 3 detail: `knowledge/docs-distilled/rules-views.md` (views-as-rewrite) and
  `knowledge/docs-distilled/querytree.md`.
- Stage 4 detail: `knowledge/docs-distilled/planner-optimizer.md` (this run),
  `geqo.md`, `planner-stats.md`; `executor-and-planner` skill.
- Stage 5 detail: `executor-and-planner` skill (`ExecInitNode`/`ExecProcNode`
  dispatch).
- Sibling overview leaves of ch. 51: `parser-stage`, `planner-optimizer` (this
  run), `executor` — candidates for future docs-miner runs.
