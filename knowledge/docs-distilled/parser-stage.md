---
source_url: https://www.postgresql.org/docs/current/parser-stage.html
fetched_at: 2026-06-11T00:00:00Z
anchor_sha: e18b0cb7344cb4bd28468f6c0aeeb9b9241d30aa
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# Docs distilled — §52.3: The Parser Stage

Why PostgreSQL splits parsing into a **raw parser** (pure syntax, no catalog) and
a **transformation** stage (semantics, catalog lookups). The reason `gram.y` knows
nothing about types, and the parse-tree → query-tree boundary.

## Two components [from-docs]

1. **Raw parser** — syntax only. `scan.l` (flex → `scan.c`) tokenizes identifiers
   and keywords; `gram.y` (bison → `gram.c`) is grammar rules + C actions that
   build a **raw parse tree**. On a syntax error it returns the error; on success
   it hands back the parse tree. **No catalog access, no type info.** [from-docs]
   [verified-by-code, source/src/backend/parser/gram.y + scan.l; via
   knowledge/idioms/parser-pipeline.md]
2. **Transformation process** — semantic analysis. Takes the raw parse tree and
   *"does the semantic interpretation needed to understand which tables,
   functions, and operators are referenced"*, producing the **query tree**
   (a `Query` node). [from-docs]
   [verified-by-code, source/src/backend/parser/analyze.c — `parse_analyze_*`]

## Why the split exists — the transaction argument [from-docs]

The non-obvious design reason: **system-catalog lookups can only happen inside a
transaction.** But some commands (`BEGIN`, `ROLLBACK`, …) must run *without* a
transaction already open and without semantic analysis. So:

- Raw parsing alone is enough to recognize transaction-control statements and
  dispatch them.
- Only once a statement is confirmed to be a real query (`SELECT`, `UPDATE`, …)
  does the transformation stage run its catalog-dependent analysis. [from-docs]

This is why you cannot fold catalog lookups into `gram.y`: the grammar runs before
there's necessarily a transaction to look things up in.

## Parse tree vs query tree [from-docs]

| | Raw parse tree | Query tree (`Query`) |
|---|---|---|
| Built by | `gram.y` actions | transformation (analyze.c) |
| Catalog resolved | No | Yes |
| Types known | No | Yes (column + expression result types) |
| Example node | `FuncCall` (any `name(args)` syntax) | `FuncExpr` *or* `Aggref`, by what the name resolves to |

The structures *look* similar but differ in detail: a syntactic `FuncCall` becomes
a `FuncExpr` (ordinary function) or an `Aggref` (aggregate) only after the
transformation stage resolves the name against the catalog. [from-docs]
[verified-by-code, source/src/include/nodes/parsenodes.h (`FuncCall`) vs
primnodes.h (`FuncExpr`, `Aggref`); via knowledge/idioms/node-types-and-lists.md]

## Links into corpus

- [[knowledge/idioms/parser-pipeline.md]] — the full parse→analyze→rewrite→plan
  pipeline with the file:line cites.
- [[knowledge/docs-distilled/querytree.md]] — the structure of the `Query` node
  this stage emits.
- [[knowledge/docs-distilled/query-path.md]] — where parsing sits in the whole
  query path.
- [[knowledge/idioms/node-types-and-lists.md]] — `FuncCall`/`FuncExpr`/`Aggref`
  and the Node taxonomy.

## Gaps / follow-ups

- The chapter does not name `raw_parser()` / `parse_analyze_fixedparams()`
  entry points or the `kwlist.h` keyword table; those are in the parser-pipeline
  idiom doc. The `BEGIN`/`ROLLBACK` "no analysis" path detail lives in `tcop`.
