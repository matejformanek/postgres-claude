# parse_graphtable.c

- **Source:** `source/src/backend/parser/parse_graphtable.c` (394 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** skim

## Purpose

Parse analysis for `GRAPH_TABLE(graph_name, MATCH ... COLUMNS (...))` — the
SQL/PGQ property-graph query feature. Produces a `RangeGraphTable`-rooted
`ParseNamespaceItem` that the rewriter later expands into a regular
relational subquery (see `rewriteGraphTable.c`).

## Entry

- `transformGraphTable` — called from
  `parse_clause.c:transformRangeGraphTable`. Resolves the property-graph
  Oid from `pg_propgraph_label` / `pg_propgraph_property`, parses MATCH
  pattern elements (vertex / edge / label expressions, length quantifiers),
  resolves the COLUMNS expressions against the matched bindings.

## Note

GRAPH_TABLE is a newer feature (PG 18); the lowering happens in
`rewrite/rewriteGraphTable.c` during `fireRIRrules` (see
`rewriteHandler.c:2088`). At parse-analyze time we only build the
syntactic + catalog-resolved description.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
- [subsystems/parser-and-rewrite.md](../../../../subsystems/parser-and-rewrite.md)
