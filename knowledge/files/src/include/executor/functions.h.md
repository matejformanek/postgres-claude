# functions.h

- **Source:** `source/src/include/executor/functions.h` (55 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read (whole file)

## Purpose

Public API for `LANGUAGE sql` function execution. Used by `fmgr.c` (to find
`fmgr_sql`), `parser/parse_func.c` (to set up `SQLFunctionParseInfo` for
argument-name resolution during body parse), and `commands/proclang.c`.

## Key types

- `SQLFunctionParseInfo` — parser-callback context: `fname`, `nargs`,
  `argtypes[]`, `argnames[]`, function's namespace, collation. Resolves
  `arg_$1` style and named-parameter references inside the body.
- `SQLFunctionCachePtr` (opaque; defined in functions.c) — per-function
  cached state; held in `fn_extra` of FmgrInfo for SQL functions.

## Functions

- `prepare_sql_fn_parse_info(procedureTuple, call_expr, inputCollation)`
  — used by parser callback hooks during parse of function body.
- `sql_fn_parser_setup(pstate, pinfo)` — register the parser hooks.
- `check_sql_fn_retval(...)` — type-checks final tlist vs. declared
  rettype; returns the resolved TupleDesc and possibly modifies the final
  query's tlist.
- `fmgr_sql(PG_FUNCTION_ARGS)` — fmgr entry, exposed for direct invocation.

## Tags

- [verified-by-code] type/function declarations.
- [from-comment] header docstring at top.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/executor.md](../../../../subsystems/executor.md)
