---
source_url: https://www.postgresql.org/docs/current/plpgsql-structure.html
fetched_at: 2026-07-05T20:47:00Z
anchor_sha: e0ff7fd9aa2e
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# PL/pgSQL block structure (internals §43.2 — page body says §41.2)

Small but load-bearing for one reason: it nails the **block-`BEGIN` is not a
transaction-`BEGIN`** distinction that trips up everyone reading PL/pgSQL for the
first time, and it describes the implicit outer block that holds parameters +
`FOUND`. Pairs with `plpgsql-transactions.md` (the real transaction-control
leaf).

## Non-obvious claims

- **The function body is a string literal handed to the handler.** The body
  between `AS $$ ... $$` is opaque text to `CREATE FUNCTION`; the plpgsql handler
  parses it on first call (§43.11). Dollar-quoting is the idiom precisely because
  the body is a string. [from-docs]
- **Block grammar is `[<<label>>] [DECLARE decls] BEGIN stmts END [label];`.**
  Every declaration and statement is semicolon-terminated; a *nested* block's
  `END` needs a trailing semicolon, but the function's final `END` does not.
  [from-docs]
- **Subblock variables shadow outer ones; qualify by block label to reach the
  outer.** `outerblock.quantity` reaches the outer variable even when an inner
  `DECLARE quantity` masks the name. Name resolution is lexical by block. [from-docs]
- **There is an implicit outer block labeled with the function name.** It holds
  the function's parameter declarations and the special variables (e.g.
  `FOUND`); you can qualify with the function name to disambiguate a parameter
  from a same-named column. [from-docs]
- **`BEGIN`/`END` are pure grouping — NOT transaction control.** The exact
  wording: *"It is important not to confuse the use of `BEGIN`/`END` for grouping
  statements in PL/pgSQL with the similarly-named SQL commands for transaction
  control. PL/pgSQL's `BEGIN`/`END` are only for grouping; they do not start or
  end a transaction."* Transaction control (COMMIT/ROLLBACK) is §43.8, and a
  block with an `EXCEPTION` clause opens a *subtransaction* (savepoint), not a
  top-level transaction. [from-docs]

## Why this matters

The block-BEGIN ≠ transaction-BEGIN rule is the root of a whole class of
misconceptions: an `EXCEPTION` block does *not* commit anything, it rolls back to
an internal savepoint; and you cannot "BEGIN a transaction" inside a function.
The implicit outer block is where `FOUND` and parameters live, which is why they
survive across inner blocks. [inferred]

## Links into corpus

- [[knowledge/docs-distilled/plpgsql-transactions.md]] — §43.8: the actual
  COMMIT/ROLLBACK rules (and the atomic-context restriction).
- [[knowledge/docs-distilled/plpgsql-implementation.md]] — §43.11: how the body
  string becomes a compiled tree.
- [[knowledge/docs-distilled/subxacts.md]] — the subtransaction/savepoint an
  `EXCEPTION` block opens.

## Open questions

- Where `pl_exec.c` establishes the internal savepoint for an `EXCEPTION` block
  (`exec_stmt_block` `BeginInternalSubTransaction`) — pin at anchor
  `e0ff7fd9aa2e`.
