---
source_url: https://www.postgresql.org/docs/current/xfunc-sql.html
chapter: "38.5 Query Language (SQL) Functions (xfunc-sql)"
fetched_at: 2026-06-17
anchor_sha: e5f94c4808fe88c170840ac3a24cdfa423b404fc
---

# SQL (`LANGUAGE sql`) functions — xfunc-sql

The semantics of `LANGUAGE sql` function bodies: how arguments resolve, how the
result is taken from the last statement, SETOF/TABLE forms, and the
string-body vs `BEGIN ATOMIC` split. Executed by `executor/functions.c`;
inlined (when simple) by `optimizer/util/clauses.c`.

## Non-obvious claims

- **The result is the last statement's output, full stop.** Unless the
  function returns `void`, the last statement must be a `SELECT`, or an
  `INSERT`/`UPDATE`/`DELETE`/`MERGE` carrying a `RETURNING` clause; only that
  final query's result is returned. [from-docs xfunc-sql]
- **Two body forms with different parse timing.** The classic string-constant
  body (dollar-quoted or single-quoted) is **not parsed at definition time**;
  the newer `BEGIN ATOMIC ... END` form *is* parsed and dependency-tracked at
  definition time (so it survives `search_path` games and records dependencies
  — a meaningful robustness/security difference). [from-docs + inferred]
- **Argument-name vs column-name precedence:** if an argument name collides
  with a column name in the function's SQL, **the column wins**. Disambiguate
  by qualifying with the function name: `funcname.argname`. [from-docs]
- **`$n` and named references are interchangeable** regardless of how the arg
  was declared — `$1` works even for a named parameter, and vice versa.
  [from-docs]
- **Arguments are values, never identifiers.** `INSERT INTO $1 VALUES (42)`
  cannot work — you can't parameterize a table/column name in a SQL function.
  [from-docs]
- **Composite args use dotted access:** `argname.field` or `$1.field`.
  [from-docs]
- **Composite results match by *position*, not name.** The select-list order
  must exactly match the composite type's column order; column naming is
  irrelevant to the system. Return values are implicitly/assignment-cast to the
  declared type when possible, else you must cast explicitly. [from-docs]
- **`OUT` params build an anonymous composite result** whose column names come
  from the OUT-param names. Crucially, **only input params form the calling
  signature** — OUT params don't participate in overload resolution or in
  `DROP FUNCTION`. [from-docs]
- **`SETOF`: the final query runs to completion**, each output row becoming a
  result-set element. [from-docs]
- **Non-SETOF + `RETURNING` silently drops extra rows.** A last-statement
  `INSERT/UPDATE/DELETE/MERGE ... RETURNING` always runs to completion even
  without `SETOF`; rows beyond the first are silently discarded. [from-docs]
- **`RETURNS TABLE(cols)` ≡ OUT params + `SETOF record`**, and you may **not**
  mix explicit `OUT`/`INOUT` params with `RETURNS TABLE`. [from-docs]
- **Polymorphism follows the simple/common split** (see
  [[knowledge/docs-distilled/extend-type-system.md]]): `anyelement` won't
  reconcile differing inputs (`make_array(1, 2.5)` fails); `anycompatible`
  will pick a common type. A polymorphic return requires a polymorphic
  argument. [from-docs]

## Links into corpus

- The runtime that executes a SQL-function body and streams its rows:
  [[knowledge/files/src/backend/executor/functions.c.md]].
- The inliner that folds a simple SQL function into the calling query's plan:
  [[knowledge/files/src/backend/optimizer/util/clauses.c.md]]
  (`inline_function` / `inline_set_returning_function`).
- The type-resolution rules these signatures obey:
  [[knowledge/docs-distilled/extend-type-system.md]].
- Volatility marking (affects inlining + caching):
  [[knowledge/docs-distilled/xfunc-volatility.md]].

## Caveats / verification

- All claims `[from-docs xfunc-sql]` except the `BEGIN ATOMIC` parse-timing
  note tagged `[inferred]` (verifiable via `prosqlbody` handling in
  `pg_proc.c` / `functioncmds.c`). Execution + inlining behavior is in
  `source/src/backend/executor/functions.c` and
  `source/src/backend/optimizer/util/clauses.c` at anchor
  `e5f94c4808fe88c170840ac3a24cdfa423b404fc`.
