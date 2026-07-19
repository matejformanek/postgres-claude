# src/include/parser/parse_graphtable.h

**Source pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
**Lines:** 24 [verified-by-code]

## Role

Parse-analysis hooks for PG18 SQL/PGQ `GRAPH_TABLE(...)` clauses in
FROM. Tiny header — the entry points are the bridge between the
grammar (which produces raw `GraphPattern` parsenodes) and the
rewriter that lowers `GRAPH_TABLE` to relational joins.

## Public API

- `transformGraphTablePropertyRef(ParseState *pstate, ColumnRef
  *cref) -> Node *` (`:20`) — resolves a property-style column
  reference like `n.name` inside a graph-table.
- `transformGraphPattern(ParseState *pstate, GraphPattern
  *graph_pattern) -> Node *` (`:22`) — full pattern analysis;
  produces the transformed expression tree.

## Invariants

- INV-PGQ-SCOPE: graph-pattern transform runs in the
  ParseState scope of the enclosing FROM clause; element labels
  must be in scope at the call site.
- INV-PGQ-PROPERTY-RESOLUTION: `ColumnRef` against a graph
  element variable resolves via property graph metadata (from
  `pg_propgraph_*` catalogs), NOT via standard column lookup.

## Trust boundary / Phase D surface

- **PG18 NEW SURFACE.** All of SQL/PGQ is new; minimal fuzz
  exposure. Top risks:
  - Property-name resolution oracle: a `transformGraphTablePropertyRef`
    leak could let a user probe whether a labeled element has a
    given property, even when SELECT on the underlying table
    would be denied. **Verify in propgraphcmds.c** how ACL is
    enforced.
  - Pattern transform can recursively expand label aliases —
    pathological patterns could trigger O(n^2) or worse
    expansion (planner DoS).
  - `GraphPattern` parse node is freshly designed; readfuncs/
    outfuncs round-trip via `gen_node_support.pl` — any
    omitted field is a silent data-loss bug for cached plans.
- **Cross-cluster query trust echo (A11).** Standard parser
  invariants (parse-then-rewrite) hold; pattern transforms
  must not invoke user-controllable functions (no GraphPattern
  contains free-form expressions today — verify).

## Cross-references

- `commands/propgraphcmds.h` — DDL.
- `rewrite/rewriteGraphTable.h` — post-parse rewrite.
- `nodes/parsenodes.h` — `GraphPattern`,
  `GraphElementPattern`, et al.
- `parser/parse_clause.h` — FROM-clause entry that invokes
  this.

## Issues / drift

- `[ISSUE-TRUST: PG18 new surface — property-ref resolution may bypass underlying-table ACL; needs verification (high)] — source/src/include/parser/parse_graphtable.h:20`
- `[ISSUE-DOC: zero comments on what GraphPattern even is; first-time reader is lost (medium)] — source/src/include/parser/parse_graphtable.h:1-24`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/parser-and-rewrite.md](../../../../subsystems/parser-and-rewrite.md)
