# src/include/commands/propgraphcmds.h

**Source pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
**Lines:** 23 [verified-by-code]

## Role

PG18 DDL entry points for **property graphs** (SQL/PGQ, ISO/IEC 9075-16).
Property graphs are a catalog-level "view-of-views" that maps relational
tables onto a graph of nodes and edges queryable via `GRAPH_TABLE`.

## Public API

- `CreatePropGraph(ParseState *pstate, const CreatePropGraphStmt *stmt)
  -> ObjectAddress` (`:20`).
- `AlterPropGraph(ParseState *pstate, const AlterPropGraphStmt *stmt)
  -> ObjectAddress` (`:21`).

## Invariants

- Property graphs are first-class catalog objects (`pg_propgraph_*`
  catalogs introduced in PG18). The `ObjectAddress` returned is the
  pg_class entry of the graph (graphs share `pg_class` relkind 'g'
  conceptually — verify via catalog/genbki when implementing).
- Both signatures take `const` Stmt — i.e. parse analysis does NOT
  mutate the node. Required because the cached-plan path may re-execute
  the same parsetree.

## Trust boundary / Phase D surface

- **PG18 NEW ATTACK SURFACE.** Property graph DDL was first committed in
  PG18; the parser path through `parse_graphtable.h`, the rewriter via
  `rewriteGraphTable.h`, and the executor wiring through
  `rewriteGraphTable` are all new code that has NOT had the multi-year
  fuzz exposure of legacy SQL paths. Likely sources of bugs:
  - graph-pattern qual elision (rewriter strips a qual that wasn't
    redundant).
  - element-label cycle in `MATCH` patterns triggering planner infinite
    recursion.
  - permission checks at graph level vs underlying table level.
- **NAME-vs-OID echo (A8 logical-replication).** Property graphs name
  their constituent tables by **identifier** at CREATE time and resolve
  to OID at use time. A drop-and-recreate of the underlying table is
  likely to make the graph reference dangle or silently re-bind to a
  new table of the same name — needs verification in `propgraphcmds.c`.

## Cross-references

- `parser/parse_graphtable.h` — parse-analysis entry for `GRAPH_TABLE`
  references in SELECTs.
- `rewrite/rewriteGraphTable.h` — rewriter converts `GRAPH_TABLE` into
  a join/union tree over the constituent tables.
- `nodes/parsenodes.h` — `CreatePropGraphStmt`, `AlterPropGraphStmt`,
  `GraphPattern`.
- `tcop/cmdtaglist.h` — `CMDTAG_CREATE_PROPERTY_GRAPH`,
  `CMDTAG_ALTER_PROPERTY_GRAPH`, `CMDTAG_DROP_PROPERTY_GRAPH`.

## Issues / drift

- `[ISSUE-TRUST: PG18 SQL/PGQ — entirely new attack surface; no security review documented in header; permission model for graph vs constituent tables unclear (high)] — source/src/include/commands/propgraphcmds.h:20-21`
- `[ISSUE-DOC: no comment explains the relationship to pg_class entries or how DROP propagates; minimal header (medium)] — source/src/include/commands/propgraphcmds.h:1-23`
