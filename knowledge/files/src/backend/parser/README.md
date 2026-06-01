# parser/README

- **Source:** `source/src/backend/parser/README` (36 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** deep-read

## Purpose

Authoritative one-screen map of the parser directory. Establishes that this
directory does more than tokenize/parse SQL — it also builds the analyzed
`Query` trees passed to the optimizer. [from-README] `:5-8`

## The layered design (the load-bearing claim)

The README orders the files by pipeline stage and is the canonical source for
what each `parse_*.c` is responsible for. [from-README] `:10-31`

```
parser.c     → entry point; raw_parser() wraps flex + bison
scan.l       → flex tokenizer (must stay no-backtrack)
scansup.c    → escape handling in literals
gram.y       → bison grammar; emits a "raw" parse tree
analyze.c    → top of parse analysis for optimizable queries
parse_clause.c   WHERE/ORDER/GROUP/HAVING/FROM
parse_expr.c     general expressions
parse_relation.c relation + column resolution, RTE construction
parse_target.c   target list (SELECT-list / RETURNING / SET clause)
parse_func.c     function calls + table.column dispatch
parse_oper.c     operator resolution
parse_type.c     type-name resolution
parse_coerce.c   type coercion / cast insertion
parse_agg.c      aggregates + window functions
parse_collate.c  collation assignment post-pass
parse_cte.c      WITH (CTE) handling
parse_merge.c    MERGE
parse_param.c    $n Param refs
parse_node.c     ParseState ctor + node-builder helpers
parse_enr.c      ephemeral named rels (trigger transition tables)
parse_jsontable.c JSON_TABLE
parse_utilcmd.c  parse analysis for DDL (CREATE TABLE etc.) — RUN AT EXECUTION TIME
```

## Why parse_utilcmd.c is special

Utility commands (DDL) are not analyzed at the same time as DML. They get
wrapped in `Query{commandType=CMD_UTILITY, utilityStmt=<raw>}` and only
re-examined by `parse_utilcmd.c` when `ProcessUtility` runs them — because
locks acquired at parse-analyze time cannot be relied on across plan-cache
boundaries. [from-comment] `analyze.c:8-14`, [from-comment] `parse_utilcmd.c:6-12`

## Keyword table lives elsewhere

`src/common/keywords.c` (+ `src/common/kwlookup.c`) hold the standard keyword
table and the lookup function. Split out so frontend code (psql, ecpg, libpq)
can use the same table. [from-README] `:33-35`

## Related idiom

See `knowledge/idioms/parser-pipeline.md` for the end-to-end walk-through of
how raw text becomes a `Query` becomes a rewritten `List<Query>`.
