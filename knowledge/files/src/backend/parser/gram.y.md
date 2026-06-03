# gram.y

- **Source:** `source/src/backend/parser/gram.y` (524 KB; generated to `gram.c` at build time)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** skim (top + design notes only — not parsed rule-by-rule)

## Purpose

Bison grammar that turns the flex token stream into the **raw parse tree**
(rooted in `RawStmt`). Every SQL statement form (SELECT, INSERT, ALTER
TABLE, CREATE INDEX, …) has rules here that allocate parse nodes from
`src/include/nodes/parsenodes.h` via `makeNode(FooStmt)` and fill them with
`$N` values.

## What it covers

Effectively the full SQL surface area PostgreSQL supports: DML, DDL,
transaction control, cursors, prepared statements, EXPLAIN, VACUUM/ANALYZE,
COPY, RULE, SECURITY LABEL, CALL/DO, set ops, MERGE, JSON_TABLE,
GRAPH_TABLE, etc. The `stmtmulti` / `toplevel_stmt` rules at the top are
the dispatch.

## What it does NOT do

> "nothing in this file should initiate database accesses" — `gram.y:23-25`
> (HISTORY/NOTES block in the prologue).

No catalog lookup, no type checking, no operator resolution, no locking.
The grammar must be able to run inside an aborted transaction.

## Why we don't parse it here

`gram.y` is the largest hand-written file in the backend by a wide margin.
The README + the canonical idiom in
`knowledge/idioms/parser-pipeline.md` already establishes the layered
design (raw → analyzed → rewritten → planned) and shows the
`SelectStmt` / `select_no_parens` / `simple_select` decomposition pattern
that every other statement type follows. Drilling into specific rules is
done on-demand when adding or modifying a statement; we don't catalog them
here.

## Generated outputs

- `gram.c` — the parser tables and `base_yyparse()` entry point. Produced
  by `bison -d` during build (see `Makefile` and `meson.build` in the same
  directory). Not checked in.
- `gram.h` — the token enum (`IDENT`, `SELECT_LA`, …). Included by
  `scan.l`, `parser.c`, and a handful of other places.

## Entry from outside

The only public symbol is `base_yyparse(yyscanner)`, called by
`raw_parser()` in `parser.c:77`. Output lands in
`yyextra->parsetree` and is returned by `raw_parser` as a `List<RawStmt>`.

## Related

- `parser.c` — driver + `base_yylex` filter for multi-token lookahead.
- `scan.l` — the lexer side of the same pipeline.
- `gramparse.h` — `base_yy_extra_type`, `core_yyalloc`, etc., shared
  between scanner and parser.
- `knowledge/idioms/parser-pipeline.md` — for the design framing.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
- [subsystems/parser-and-rewrite.md](../../../../subsystems/parser-and-rewrite.md)
