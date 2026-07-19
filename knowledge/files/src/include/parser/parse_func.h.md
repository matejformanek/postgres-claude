# parse_func.h

- **Source:** `source/src/include/parser/parse_func.h` (~75 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## Purpose

Prototypes for function/operator resolution from `parse_func.c`.

## Key types

- `FuncDetailCode` enum — outcome of `func_get_detail`: `FUNCDETAIL_NORMAL`,
  `FUNCDETAIL_AGGREGATE`, `FUNCDETAIL_WINDOWFUNC`, `FUNCDETAIL_PROCEDURE`,
  `FUNCDETAIL_COERCION`, `FUNCDETAIL_NOTFOUND`, `FUNCDETAIL_MULTIPLE`.

## Exported entries

- `ParseFuncOrColumn` — the main entry.
- `func_get_detail` — overload resolution.
- `func_select_candidate` — type-preference ranking.
- `make_fn_arguments` — coerce args to declared param types.
- `LookupFuncName` / `LookupFuncNameTypeNames` /
  `LookupFuncWithArgs` — name-only / by-typename lookups used by DDL
  (`COMMENT ON FUNCTION ...`, `ALTER FUNCTION ...`).
- `LookupAggWithArgs` / `LookupOperWithArgs` — same for aggs / ops.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/parser-and-rewrite.md](../../../../subsystems/parser-and-rewrite.md)
