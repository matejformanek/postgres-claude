# src/include/rewrite/rewriteGraphTable.h

**Source pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
**Lines:** 21 [verified-by-code]

## Role

PG18 SQL/PGQ rewriter — lowers `GRAPH_TABLE(...)` references in a
`Query` into relational join/union expansions over the constituent
tables of the property graph. Runs after parse-analysis (which
filled in label / property bindings) and before planning.

## Public API

- `rewriteGraphTable(Query *parsetree, int rt_index) -> Query *`
  (`:19`) — rewrite a specific rangetable entry that is a
  `RTE_GROUP`-style graph reference. Returns a new Query with
  that entry replaced by the lowered form.

## Invariants

- INV-PGQ-REWRITE-IDEMPOTENT: applying `rewriteGraphTable`
  twice on the same Query should be a no-op on the second
  call (after rangetable entry is replaced, the marker is
  gone). Verify against `rewriteGraphTable.c`.
- INV-PGQ-NO-RULES: graph-table rewrite happens INSIDE the
  rewrite phase but is NOT itself a pg_rewrite rule; it's
  hard-coded lowering.

## Trust boundary / Phase D surface

- **PG18 NEW SURFACE.** Top risks:
  - The lowered join tree must preserve all ACL/RLS quals
    from the constituent tables. The property graph object
    has its own ACL; the *underlying* tables have separate
    ACL. Bypass risk if the rewriter applies graph-level
    permission only.
  - Pattern lowering can produce large UNION ALL trees
    (one branch per edge label); a pathological label
    cardinality is a planner DoS vector.
  - The output Query passes through readfuncs/outfuncs for
    plan caching — any new node-tree fields must be
    serializable.
- **A7 echo (RLS qual loss).** Same risk profile as view
  expansion — if the rewriter drops a RLS qual when lowering,
  the property graph becomes an RLS bypass.
- **A8 echo (replication).** A subscriber running a published
  GRAPH_TABLE query against a different set of constituent
  tables (same names, different schemas) gets different
  results.

## Cross-references

- `commands/propgraphcmds.h` — DDL: CREATE/ALTER PROPERTY
  GRAPH.
- `parser/parse_graphtable.h` — parse-analysis precursor.
- `nodes/parsenodes.h` — `Query`, `GraphPattern`,
  `GraphElementPattern`.
- `rewrite/rewriteHandler.h` — top-level rewriter entry that
  calls into here.

## Issues / drift

- `[ISSUE-TRUST: PG18 new — header doesn't document ACL/RLS propagation contract for graph-vs-constituent-tables (high)] — source/src/include/rewrite/rewriteGraphTable.h:19`
- `[ISSUE-DOC: single prototype, zero context — bare header (medium)] — source/src/include/rewrite/rewriteGraphTable.h:1-22`
