---
source_url: https://www.postgresql.org/docs/current/plpgsql-expressions.html
fetched_at: 2026-07-05T20:47:00Z
anchor_sha: e0ff7fd9aa2e
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# PL/pgSQL expressions (internals §43.4 — page body says §41.4)

Short page, one big idea with sharp corollaries: **every PL/pgSQL expression is
evaluated by the main SQL executor as if it were `SELECT expression`** — there is
no separate PL/pgSQL expression engine. This is *the* reason PL/pgSQL expression
semantics exactly match SQL, and why `x < y` in an `IF` is a cached prepared
plan. Pairs with `plpgsql-implementation.md` (the caching side) and
`executor-and-planner`.

## Non-obvious claims

- **An expression is literally a one-column `SELECT`.** "All expressions used in
  PL/pgSQL statements are processed using the server's main SQL executor." `IF
  expression THEN` is evaluated by feeding `SELECT expression` to the main SQL
  engine. There is no PL/pgSQL-specific operator evaluation. [from-docs]
- **Variables become `$n` parameters in that SELECT.** For integer `x`, `y`,
  `IF x < y THEN` is equivalent to `PREPARE stmt(integer, integer) AS SELECT $1 <
  $2` then `EXECUTE` with the live values. Same PARAM substitution as
  §43.11.1. [from-docs] → `setup_param_list()`
  (`source/src/pl/plpgsql/src/pl_exec.c:6351`), evaluated through
  `exec_eval_expr` (`pl_exec.c:5766`). [verified-by-code @e0ff7fd9aa2e]
- **The plan is prepared once and reused.** "The query plan for the `SELECT` is
  prepared just once and then reused" across evaluations with different variable
  values — the caching from §43.11.2 applies to plain expressions too, not just
  full SQL statements. [from-docs]
- **Expression = SELECT constraints leak through.** Because it becomes a
  `SELECT`, an expression may carry the same clauses (even `FROM`/`WHERE`), but
  **cannot** have a top-level `UNION`/`INTERSECT`/`EXCEPT`, must produce a single
  column, and must not return more than one row. Zero rows → the result is
  `NULL`. [from-docs]
- **`FROM` inside an expression is legal.** `IF count(*) > 0 FROM my_table THEN`
  works — a direct consequence of "it's a SELECT." Surprising to readers who
  think of an expression as a scalar. [from-docs]

## Why this design

Reusing the main executor means PL/pgSQL never has to reimplement operator
resolution, type coercion, function calls, or NULL semantics — an expression's
behavior is identical to the same text in SQL, for free. The cost is that every
expression carries a prepared-plan and a `SELECT`'s constraints (single column,
single row), which is why tight inner-loop arithmetic in PL/pgSQL is slower than
in a compiled language: each `:=` is a cached SPI plan execution. [inferred]

## Links into corpus

- [[knowledge/docs-distilled/plpgsql-implementation.md]] — §43.11: the caching
  and PARAM mechanism this page relies on.
- [[knowledge/docs-distilled/plpgsql-statements.md]] — §43.5: assignment / SELECT
  INTO are these expressions in statement position.
- [[knowledge/docs-distilled/executor.md]] — the "main SQL executor" doing the
  evaluation.
- [[knowledge/docs-distilled/spi.md]] — the prepared-statement path.

## Open questions

- Whether a simple scalar expr takes the `exec_eval_simple_expr` fast path
  (bypassing full SPI) vs the general path — confirm in `pl_exec.c` at anchor
  `e0ff7fd9aa2e`.
