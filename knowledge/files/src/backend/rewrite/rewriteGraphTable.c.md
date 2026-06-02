# rewriteGraphTable.c

- **Source:** `source/src/backend/rewrite/rewriteGraphTable.c` (1334 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** skim

## Purpose

Lower a `RTE_GRAPH_TABLE` (produced by `parser/parse_graphtable.c`) into a
plain relational subquery. Runs once per GRAPH_TABLE RTE during
`fireRIRrules`, before any other RIR/RLS processing on that RTE.
[verified-by-code] `rewriteHandler.c:2088-2091`.

## Entry

- `rewriteGraphTable(parsetree, rt_index)` — replaces the GRAPH_TABLE RTE
  with an `RTE_SUBQUERY` whose subquery joins the property-graph element /
  label / property catalog tables according to the MATCH pattern.

## What gets emitted

For a GRAPH_TABLE pattern like `(v) -[e]-> (w)`, the lowering builds:

- a SELECT from `pg_propgraph_element` joined to itself for vertex/edge
  matching,
- joins to `pg_propgraph_label` / `pg_propgraph_property` for label
  filtering,
- WHERE clauses for label-expression / quantifier / cycle constraints.

## Why a rewrite (not a planner) step

The lowering produces a *Query* tree, so it has to happen before
planning. Hooking into `fireRIRrules` is convenient because that walker
already visits every RTE.

## Related

- `parse_graphtable.c` — produces the input.
- `pg_propgraph_*` system catalogs.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
- [subsystems/parser-and-rewrite.md](../../../../subsystems/parser-and-rewrite.md)
