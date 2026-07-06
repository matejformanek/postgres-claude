---
source_url: https://www.postgresql.org/docs/current/plpgsql-implementation.html
fetched_at: 2026-07-05T20:47:00Z
anchor_sha: e0ff7fd9aa2e
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: true
---

# PL/pgSQL under the hood (internals §43.11 — page body still says §41.11)

**The load-bearing internals leaf of the whole PL/pgSQL chapter.** Two
subsections: §43.11.1 Variable Substitution and §43.11.2 Plan Caching. This is
the page that explains *why* PL/pgSQL variables behave like they do — they are
**query parameters (`PARAM` nodes), never textual substitution** — and how the
per-session compiled tree + SPI-prepared plans are cached. Directly relevant to
the sesvars PARAM-reuse work (CLAUDE.md R15: the reference implementation reused
existing PARAM infrastructure) and to the `fmgr-and-spi` / `plhandler` skills.

> Chapter renumbered to §43 in the current ToC but the page body text still
> reads "41.11" (docs lag, same class as the §31→§29 logical-replication and
> §21 auth renumbers). Cite by slug, not by number.

## Non-obvious claims

- **Variable substitution is parameter substitution, not text.** "PL/pgSQL
  substitutes query parameters for such references." A variable reference becomes
  a `$n` parameter, so **"variable substitution can only insert data values into
  an SQL command; it cannot dynamically change which database objects are
  referenced by the command."** You cannot parameterize a table/column name this
  way — that's what `EXECUTE` + `format('%I')` is for. [from-docs] Verified: the
  interpreter builds a `ParamListInfo` per expression via `setup_param_list()`
  (`source/src/pl/plpgsql/src/pl_exec.c:6351`) with a lazy `plpgsql_param_fetch`
  callback (`pl_exec.c:6399`); the expr executes as a parameterized plan
  (`paramLI = setup_param_list(estate, expr)` at `pl_exec.c:2256`). [verified-by-code @e0ff7fd9aa2e]
- **Parameters are only substituted where syntactically legal.** "Query
  parameters will only be substituted in places where they are syntactically
  permissible." A name in an identifier position is left alone (and then usually
  errors as an unknown column). [from-docs]
- **Variable-vs-column ambiguity is an error by default.** "PL/pgSQL will report
  an error if a name in an SQL statement could refer to either a variable or a
  table column." Resolution knobs: qualify (`block.foo` for the variable,
  `tbl.foo` for the column), the per-function `#variable_conflict use_variable |
  use_column | error` pragma, or the system GUC `plpgsql.variable_conflict`
  (superuser-only; default `error`). [from-docs]
- **The binary instruction tree is built lazily, once per session.** "The
  PL/pgSQL interpreter parses the function's source text and produces an internal
  binary instruction tree the first time the function is called (within each
  session)." Individual SQL commands inside are **not** translated at that point.
  [from-docs]
- **Each SQL expr/command is `SPI_prepare`'d on first reach, then reused.** "As
  each expression and SQL command is first executed in the function, the PL/pgSQL
  interpreter parses and analyzes the command to create a prepared statement,
  using the SPI manager's `SPI_prepare` function." Subsequent visits reuse it.
  So the compile is two-stage: eager tree, lazy per-statement plans. [from-docs]
- **Generic-vs-custom plan choice is delegated to SPI.** "PL/pgSQL (or more
  precisely, the SPI manager) can furthermore attempt to cache the execution
  plan." If the plan is value-independent or has run many times, a **generic
  plan** is cached; if it's sensitive to variable values, a fresh **custom plan**
  is built each visit so the planner can use the live values. This is the same
  custom/generic machinery `plancache.c` drives for client-side PREPARE.
  [from-docs]
- **The plan cache key is (function, argument-type combo, trigger-table), not
  just the function.** Polymorphic functions get "a separate statement cache for
  each combination of actual argument types," and a trigger function used on N
  tables caches "for each trigger function and table combination, not just for
  each function." [from-docs]
- **`'now'`-as-literal footgun is a direct consequence of plan caching.**
  `INSERT ... VALUES (logtxt, 'now')` freezes the `now` string into a
  `timestamp` constant at first-plan time, so every later call logs the *first*
  call's time. Assigning `curtime := 'now'` into a variable re-casts per call;
  using `now()` / `current_timestamp` is the correct fix. [from-docs]
- **Record-field types must be stable across calls.** "the data types of the
  fields must not change from one call of the function to the next, since each
  expression will be analyzed using the data type that is present when the
  expression is first reached." Use `EXECUTE` to dodge if a record's shape
  genuinely varies. [from-docs]

## Why this design

The two-stage compile (eager instruction tree + lazy per-statement SPI plans) is
what makes PL/pgSQL fast on the hot path: the loop body is walked as a compiled
tree, and each embedded query rides the same generic/custom plan cache the rest
of the backend uses, so a function called thousands of times per session pays
parse+plan cost roughly once. The price is the semantic surprises above — frozen
`'now'`, stable record types, no identifier parameterization — all of which fall
straight out of "a variable is a `$n`, and the plan is cached." [inferred]

## Links into corpus

- [[knowledge/docs-distilled/plpgsql-overview.md]] — the §43.1 architecture leaf
  (loadable handler, SPI-batching advantages) this page implements.
- [[knowledge/docs-distilled/plpgsql-expressions.md]] — §43.4: every expr is a
  cached `SELECT`; this page is the caching mechanism behind it.
- [[knowledge/docs-distilled/plpgsql-statements.md]] — §43.5: `EXECUTE` is the
  explicit escape from this plan cache.
- [[knowledge/docs-distilled/spi.md]] / [[knowledge/docs-distilled/spi-memory.md]]
  — the `SPI_prepare` / plan-caching ABI this page names.
- [[knowledge/docs-distilled/plhandler.md]] — the PL handler ABI PL/pgSQL is the
  reference implementation of.
- [[knowledge/idioms/fmgr.md]] / the `fmgr-and-spi` skill — PARAM + SPI plumbing.

## Open questions

- Exact `plancache.c` entry (`GetCachedPlan` custom-vs-generic decision) reached
  from `pl_exec.c` — trace on a future deep read at anchor `e0ff7fd9aa2e`.
