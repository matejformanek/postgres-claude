# functions.c

- **Source:** `source/src/backend/executor/functions.c` (2696 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** deep-read (the SQL-language function executor)

## Purpose

Implements `language sql` functions: parse/analyze/plan/execute the function
body as a sequence of queries, returning the result of the last one. Uses
plancache + funccache (`utils/cache/funccache.c`) to cache per-function
state across calls. [from-comment] `:3-7`

## Lifecycle

### Plumbing: `fmgr_sql(PG_FUNCTION_ARGS)` `:1577`

The fmgr handler entry. On first call for a given function-OID:

1. `init_sql_fcache` `:537` — fetches `pg_proc` row, parses + analyzes
   prosrc as a SQL statement list using `prepare_sql_fn_parse_info` `:252`
   to bind function args. Compiles each query (raw → analyzed → planned)
   via the plancache.
2. `check_sql_fn_retval` `:2117` — validates that the last query's TLIST
   matches the function's declared return type, possibly injecting a
   final tlist projection / row-type cast.
3. `init_execution_state` `:654` — builds the `execution_state` list
   (one per command) that we'll iterate through.

Subsequent calls reuse the cached fcache. funccache callbacks
`sql_compile_callback` `:1041` and `sql_delete_callback` `:1214` are
registered for plan-invalidation and shutdown respectively.

### Per-call driver

- `postquel_start` `:1277` — start one query: create QueryDesc, ExecutorStart,
  install a tuplestore DestReceiver for non-final queries (they're side-effect
  only) and a special "lazyEval" receiver for the final SELECT (so we can
  stream results without buffering everything).
- `postquel_getnext` `:1401` — drive ExecutorRun until a row is available
  (or the query exits), then either return it to fmgr_sql's caller (when
  it's the final query of a `RETURNS SETOF`) or discard (intermediate
  queries).

## Lazy vs. eager evaluation

- **Lazy** (the default for `SETOF`): final query is run row-by-row through
  fmgr's ValuePerCall mechanism — driven by repeated `fmgr_sql` calls,
  each yielding one row.
- **Eager**: the function is `RETURNS one row`, or context disallows lazy
  (`returnsTuple`-only callers). The final query is run to completion and
  the result tuplestore is returned via Materialize mode.

The choice is controlled by `lazyEvalOK` param passed to `init_sql_fcache`.

## RETURNS TABLE / OUT params

`check_sql_fn_retval` handles three rettype shapes — scalar, named-composite,
and `RETURNS TABLE(col1 t1, col2 t2)`. For the last, it constructs an
implicit composite type and possibly inserts a final ROW() projection
around the last query.

## Cross-version notable behavior

- **Transactional side-effects**: a SQL function's intermediate queries do
  modify the database; failures inside trigger normal subtransaction-style
  rollback if invoked from a context that supports it (e.g. PL/pgSQL
  EXCEPTION block). Otherwise the surrounding xact is aborted.
- **Snapshot management**: each query in the function body gets a fresh
  snapshot under default settings; this is what makes
  `SELECT now(); SELECT pg_sleep(1); SELECT now();` inside a SQL function
  potentially see different statement_timestamps.
- **Inlining**: a simple-enough `LANGUAGE sql` function (single SELECT, no
  side effects, immutable/stable) is often **inlined by the planner** in
  `optimizer/util/clauses.c` (`inline_function`) and this code path is
  never reached — that's why most performance-sensitive sql functions
  appear in EXPLAIN output as their inlined expression.

## Tags

- [verified-by-code] entry points + lifecycle ordering.
- [from-comment] file header + per-function docs.
- [inferred] inlining bypass detail (clear from optimizer code; here only
  for reader orientation).
