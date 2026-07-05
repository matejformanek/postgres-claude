---
source_url: https://www.postgresql.org/docs/current/plpgsql-statements.html
fetched_at: 2026-07-05T20:47:00Z
anchor_sha: e0ff7fd9aa2e
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# PL/pgSQL basic statements (internals §43.5 — page body says §41.5)

The SPI-plumbing chapter: how assignment, `SELECT ... INTO`, `PERFORM`, dynamic
`EXECUTE`, and result-status (`GET DIAGNOSTICS` / `FOUND`) map onto the SPI
manager. The single most operationally important fact here is **`EXECUTE`
bypasses the plan cache entirely** — the exact opposite of every other statement
form. Subsections: §43.5.1 Assignment, .2 Executing a Command With No Result,
.3 Single-Row Result, .4 Dynamic Commands, .5 Result Status, .6 Doing Nothing.

## Non-obvious claims

- **Assignment is a `SELECT`, with an assignment cast on the result.** `var :=
  expr` evaluates `expr` as a `SELECT` (per §43.4), then coerces via the
  assignment cast rules (§10.4); if no cast exists, it falls back to
  **output-function → input-function textual conversion**, which can throw at
  runtime if the input function rejects the string. [from-docs]
- **Optimizable vs utility commands split on parameterizability.** `SELECT /
  INSERT / UPDATE / DELETE / MERGE` (+ `EXPLAIN`, `CREATE TABLE AS SELECT`) take
  PARAM substitution and get a cached plan; **utility commands cannot accept
  query parameters** and so must be built as strings and run via `EXECUTE`.
  [from-docs]
- **`PERFORM query`** runs an optimizable command and discards its result, but
  **sets `FOUND`** to whether ≥1 row was produced. It's the way to call a
  side-effect `SELECT`/function without an `INTO` target. [from-docs]
- **`INTO STRICT` enforces exactly-one-row with named errors.** Without `STRICT`,
  `SELECT ... INTO` takes the first row (NULLs if none) and silently discards the
  rest. With `STRICT`, "the command must return exactly one row or a run-time
  error will be reported, either `NO_DATA_FOUND` (no rows) or `TOO_MANY_ROWS`
  (more than one row)." [from-docs]
- **`RETURNING ... INTO` is implicitly strict-ish.** An `INSERT/UPDATE/DELETE/
  MERGE ... RETURNING ... INTO` errors on >1 row **even without `STRICT`**,
  because there's no ordering to pick a "first" row from. [from-docs]
- **`EXECUTE` has NO plan caching — by design.** "there is no plan caching for
  commands executed via `EXECUTE`. Instead, the command is always planned each
  time the statement is run." That is the whole point: the string can name
  different tables/columns each call. The flip side is you pay parse+plan every
  execution. [from-docs]
- **`EXECUTE` does no variable substitution; parameters go through `USING`.**
  PL/pgSQL variable names are *not* substituted into the command string; pass
  data via `$1,$2,... USING ...` (optimizable commands only). Identifiers must be
  interpolated safely with `quote_ident()` / `format('%I')`; values with
  `quote_literal` / `quote_nullable` / `format('%L')`. `%L` and `quote_nullable`
  render SQL `NULL` for a NULL input, where `quote_literal` returns SQL NULL
  (the value), a classic dynamic-SQL NULL footgun. [from-docs]
- **`GET DIAGNOSTICS` vs `FOUND` diverge on `EXECUTE`.** `GET [CURRENT]
  DIAGNOSTICS var = ROW_COUNT | PG_CONTEXT | PG_ROUTINE_OID` reflects the most
  recent command *including* `EXECUTE`, but **`EXECUTE` does not change
  `FOUND`.** `FOUND` starts false per call and is set by `SELECT INTO`,
  `PERFORM`, DML, `FETCH`, `MOVE`, `FOR`/`FOREACH`, and `RETURN QUERY` — but not
  by bare `EXECUTE`. `FOUND` is local to each function and does not propagate to
  callers. [from-docs]
- **`NULL;` is a real no-op statement**, kept for PL/SQL compatibility and as a
  placeholder in empty branches. [from-docs]

## Why this matters for a hacker

The `EXECUTE`-doesn't-cache rule is the lever for every "why is my dynamic-SQL
function slow / why does my table-name parameter not work" question: parameters
are data-only PARAM slots, identifiers need `format('%I')`, and each `EXECUTE`
re-plans. It is also the safe workaround whenever a record's column types vary
across calls (§43.11's stable-type requirement). [inferred]

## Links into corpus

- [[knowledge/docs-distilled/plpgsql-implementation.md]] — §43.11: the plan cache
  `EXECUTE` deliberately opts out of.
- [[knowledge/docs-distilled/plpgsql-expressions.md]] — §43.4: assignment RHS is
  one of these SELECT-expressions.
- [[knowledge/docs-distilled/spi.md]] / [[knowledge/docs-distilled/spi-memory.md]]
  — `SPI_execute` / `SPI_execute_with_args` behind these statements.
- [[knowledge/docs-distilled/error-message-reporting.md]] — `NO_DATA_FOUND` /
  `TOO_MANY_ROWS` are trappable SQLSTATEs.

## Open questions

- Whether `EXECUTE ... USING` uses a one-shot unsaved plan (`SPI_execute_with_args`)
  vs a saved plan — confirm in `pl_exec.c` `exec_stmt_dynexecute` at anchor
  `e0ff7fd9aa2e`.
