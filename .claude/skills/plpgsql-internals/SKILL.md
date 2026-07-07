---
name: plpgsql-internals
description: PostgreSQL's PL/pgSQL procedural-language implementation — `src/pl/plpgsql/src/` — the parser (`pl_gram.y` + `pl_scanner.c`), compiler (`pl_comp.c` — turns source text into `PLpgSQL_function` struct), executor (`pl_exec.c` — the interpreter with 268 KB of statement handlers), function/DO/procedure dispatch (`pl_handler.c`), and the trusted-language sandbox boundary. Loads when the user asks about PL/pgSQL semantics not obvious from SQL (nested exceptions, RAISE / GET STACKED DIAGNOSTICS, cursor lifecycle, RECORD variables, EXECUTE dynamic SQL, GET DIAGNOSTICS, transaction control from within a procedure, plan caching for expressions, or the trusted-vs-untrusted distinction), when investigating "why is my PL/pgSQL slower than raw SQL" (typically plan-cache or exception-block reasons), when adding a new PL/pgSQL feature (has scenario `integrate-with-plpgsql`), or when working with PL/pgSQL security (recall from `2026-06-04-a9-plpgsql` session that trusted-PL gate is enforced exactly twice in `pl_handler.c`, EXECUTE has zero injection defenses, WHEN OTHERS swallows almost everything). Skip when the ask is about PL/Python / PL/Perl / PL/Tcl (see the sibling `src/pl/plpython/` etc.), or about SPI (a shared API — see `fmgr-and-spi`).
when_to_load: Debug PL/pgSQL semantics or performance; extend the language; audit PL/pgSQL security (COMMIT-in-procedure snapshot invariant, cache invalidation gaps, EXECUTE injection); work with plpgsql-specific error handling.
companion_skills:
  - fmgr-and-spi
  - error-handling
  - executor-and-planner
---

# plpgsql-internals — the SQL procedural language

PL/pgSQL is PG's most-used procedural language: functions, procedures, DO blocks, triggers. Under the hood it's a **parser + compiler + interpreter** living in a self-contained subdirectory. The interpreter (`pl_exec.c`) is 268 KB — the biggest source file in PG core after `postmaster.c`.

## The file map

| File | KB | Role |
|---|---:|---|
| `pl_handler.c` | 15 | The `PL_handler_*` fmgr entry points. Compiles + caches + executes. **This is where the trusted-language sandbox gate lives — enforced exactly twice.** |
| `pl_gram.y` | 119 | Bison grammar — PL/pgSQL statement syntax (IF / LOOP / WHILE / FOR / DECLARE / RAISE / GET DIAGNOSTICS / etc.). |
| `pl_scanner.c` | 19 | Tokenizer that feeds the grammar. Wraps `core_yylex` — shares tokens with the main SQL parser. |
| `pl_comp.c` | 66 | Compiler — takes the parsed AST + turns it into `PLpgSQL_function` struct with `PLpgSQL_stmt`s + datum types + variable slots. |
| `pl_exec.c` | **268** | Interpreter. `exec_stmt_block`, `exec_stmt_execsql`, `exec_stmt_return`, `exec_stmt_raise`, EXCEPTION handling. Every statement type has its own `exec_stmt_*` handler. |
| `pl_funcs.c` | 39 | Utility functions — data structures, formatting, err-context callback, dumping compiled functions. |
| `plpgsql.h` | 37 | Public API + PLpgSQL_* struct definitions. |
| `pl_reserved_kwlist.h` + `pl_unreserved_kwlist.h` | — | Keyword tables. PL/pgSQL has its own reserved-word set separate from SQL. |

## The 3-stage flow: parse → compile → execute

### 1. Parse

- SQL parser hands off the function body when `LANGUAGE plpgsql` is detected.
- `pl_gram.y` parses the body producing `PLpgSQL_stmt` AST nodes.
- Grammar interleaves with SQL — nested `EXECUTE 'SQL text'` re-invokes SQL parser via SPI.

### 2. Compile

- `plpgsql_compile` (in `pl_comp.c`) — turns AST + function catalog metadata into `PLpgSQL_function`:
  - `datums[]` array — one entry per variable, cursor, or reference.
  - `action` — the top-level `PLpgSQL_stmt_block`.
  - `fn_oid`, `fn_hashkey`, `resowner_for_use_stack` — bookkeeping.
- `PLpgSQL_function` is CACHED in a hash keyed by (fn_oid, argument types) — so a function compiled once serves many calls.
- **Cache invalidation via `plpgsql_HashTableDelete`** — fires on `pg_proc` invalidation. Historical bug source: some catalog changes don't invalidate this cache correctly (see 2026-06-04 session).

### 3. Execute

- `plpgsql_exec_function` (in `pl_exec.c`) — walks the `PLpgSQL_stmt` tree:
  - For each statement, dispatches to `exec_stmt_<kind>` (there are ~30 kinds).
  - Expressions (assignments, conditions) go through SPI — `SPI_execute_snapshot` — with a **per-expression plan cache** (`PLpgSQL_expr.plan`).
  - EXCEPTION blocks use PG_TRY/CATCH at the C level; every EXCEPTION handler enters a subtransaction.

## The trusted-language boundary

PL/pgSQL registers TWO handlers:

- `plpgsql_call_handler` — **untrusted**. Used when the function is declared `LANGUAGE plpgsql` with owner=superuser.
- `plpgsql_call_handler` also serves the **trusted** variant when checked. Trusted PL/pgSQL is (from a security-review standpoint) SAME as untrusted — the "trust" claim is that PL/pgSQL doesn't have `COPY FROM PROGRAM` / `EXECUTE FILE ...` primitives. Every SQL a PL/pgSQL function runs still has the SQL-level GRANT/REVOKE + RLS gates.

Real security issues:

- **`EXECUTE format('...')` is injection-prone** — no sanitizing. Use `quote_ident`, `quote_literal`, `format('%L', ...)`.
- **`WHEN OTHERS` swallows almost everything**, including `query_canceled`. A misbehaving procedure can be hard to kill.
- **`COMMIT` in a procedure ends the current snapshot** — a procedure that reads x, COMMITs, then reads x may see different data. Snapshot invariant intentionally broken.

See `2026-06-04-a9-plpgsql.md` session log for the specific findings.

## Plan cache in PL/pgSQL

Each `EXECUTE` / `SELECT ... INTO` / expression in a function gets its own `PLpgSQL_expr` struct with a cached `SPIPlanPtr`. On first call → prepare + save; subsequent calls reuse.

Cache is invalidated when:
- Underlying object (table, function) changes catalogversion.
- Search path or role changes (for generic plans).
- Explicit `DEALLOCATE ALL`.

But NOT invalidated when:
- A GUC that affects planning changes (mostly).
- A comment on the referenced object changes (correct — no plan impact).

## Common patch shapes

### Add a new PL/pgSQL statement kind

Scenario: `integrate-with-plpgsql`. Sequence:
- Extend grammar in `pl_gram.y` — parser action produces the new AST node.
- Extend `PLpgSQL_stmt_type` enum in `plpgsql.h` + AST struct.
- Add `exec_stmt_<kind>` in `pl_exec.c`.
- Add support in `pl_funcs.c` for dumping / freeing the new node.
- Regression tests in `src/pl/plpgsql/src/expected/plpgsql_*.out`.

### Add a new EXCEPTION reason code

- Extend `errcodes.txt` (in `src/backend/utils/errcodes.txt`).
- Regenerate `plerrcodes.h` via `generate-plerrcodes.pl`.
- Documentation.

### Debug "PL/pgSQL is 10x slower than raw SQL"

- Check if the plan-cache is warm — first call always compiles + prepares plans.
- Check if EXCEPTION blocks are hot — each entry creates a subtransaction (expensive).
- Use `plpgsql.extra_warnings = 'strict_multi_assignment'` etc. to catch common footguns.
- `EXPLAIN (ANALYZE, BUFFERS)` inside the function via `RAISE INFO '%', ...`.

### Extend GET DIAGNOSTICS

- New `GD_*` enum in `pl_exec.c`.
- Handler in `exec_stmt_getdiag`.
- Grammar rule in `pl_gram.y` for the syntax.

## Pitfalls

- **`FOR rec IN SELECT ...` is a Portal, not a materialized list** — the loop iterates lazily. Modifying the underlying table during the loop may or may not affect what the loop sees (depends on isolation level).
- **`RETURNS TABLE` vs `RETURNS SETOF composite`** — both work; the compiler generates different output-slot handling. Common source of "wrong-column-order" bugs when mixing them.
- **`RAISE ...` without SQLSTATE** — defaults to `P0001` (raise_exception). Explicit SQLSTATE (`RAISE USING ERRCODE = ...`) needed for finer-grained handlers.
- **EXCEPTION handlers can't COMMIT** — subtransactions inside them get rolled back on exit; trying to commit will error.
- **`GET DIAGNOSTICS row_count = ...`** applies to the LAST executed statement, not the surrounding block.
- **`PERFORM x` vs `SELECT x`** — PERFORM discards the result; SELECT into a variable requires the INTO clause. `SELECT foo()` without INTO in PL/pgSQL is a compile error.
- **`FOUND` variable is not always what you expect** — set by SELECT (was there a row?), UPDATE / DELETE / INSERT / MERGE (any rows affected?), EXECUTE (last row's presence). It's transactional per-block.
- **COMMIT-in-procedure loses the snapshot** — the transactional context inside the procedure changes; assumptions about "same snapshot throughout" are wrong.
- **`RETURN NEXT` vs `RETURN QUERY`** — the former accumulates in a tuplestore per-call; the latter iterates. RETURN QUERY of a large result set is much better than looping with RETURN NEXT.
- **Trusted PL/pgSQL isn't really sandboxed** — every SQL statement respects the calling user's SQL-level privileges. If you thought "trusted" meant "isolated", you're wrong.

## Related corpus

- **Idiom**: `fmgr` (the entry point via fmgr's PG_FUNCTION_INFO_V1 machinery), `syscache-invalidation-flow` (relates to plpgsql cache invalidation).
- **Subsystems**: `parser-and-rewrite` (SQL parser recursively invoked via EXECUTE), `executor` (SPI dispatch executes SQL statements plpgsql produces), `catalog-conventions` (pg_proc / pg_language rows for LANGUAGE plpgsql).
- **Scenario**: `integrate-with-plpgsql` (adding a new PL/pgSQL statement/feature).
- **Sessions**: `2026-06-04-a9-plpgsql.md` (deep-read of the whole `pl/plpgsql/` directory — security-boundary summary, 87 issues surfaced).
- **File docs**: `knowledge/files/src/pl/plpgsql/src/pl_*.md` — one doc per file.

## Corpus-chain shortcut

```
python3 scripts/corpus-chain.py --scenario integrate-with-plpgsql
python3 scripts/corpus-chain.py --file src/pl/plpgsql/src/pl_exec.c
```

Second surfaces the 268 KB interpreter's neighborhood.

## Boundary

**Use this skill** for `src/pl/plpgsql/src/` — the PL/pgSQL implementation.

**Don't use** for:
- **Other PLs** — `plpython` / `plperl` / `pltcl` live in sibling subdirs. Each has its own boundary + trust model. Notable: PL/Perl uses opcode-mask (not Safe.pm); PL/Python is untrusted-only by design; PL/Tcl uses Tcl safe interp (structurally strongest). See sessions `2026-06-04-a10-*.md` for cross-PL comparison.
- **SPI** — the Server Programming Interface that PL/pgSQL and every other PL uses to run SQL. See `fmgr-and-spi` skill.
- **`CREATE FUNCTION` for LANGUAGE C** — that's fmgr territory, not PL/pgSQL.
- **`CREATE FUNCTION` for LANGUAGE sql** — different implementation (function inlining), lives in `src/backend/optimizer/util/`.
- **`DO` blocks in languages OTHER than plpgsql** — same DO statement, per-language dispatch. This skill covers the plpgsql case only.
