# parse_oper.c

- **Source:** `source/src/backend/parser/parse_oper.c` (1105 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## Purpose

Resolve binary / prefix operators by name and operand types, returning the
corresponding `pg_operator` row (and ultimately a `FuncExpr` /
`OpExpr`-shaped result).

## Entries

- `oper(pstate, opname, ltypeId, rtypeId, noError, location)` — binary op
  lookup; `noError` controls whether failure raises or returns NULL.
- `right_oper` — prefix op lookup. (Postfix ops were removed in PG 14.)
- `compatible_oper_opid` — like `oper` but tolerates "no exact match, try
  implicit coercion".
- `make_op` / `make_scalar_array_op` — build the final `OpExpr` /
  `ScalarArrayOpExpr` node with coerced args.

## Operator candidate caching

`OprCacheKey` / `OprCacheEntry` (defined at top of file) implement a small
process-local hash to avoid re-running `oper_select_candidate` for every
repeated operator+types triple. Invalidated by `syscache` flushes via the
`InvalidateOprCacheCallBack` callback.

## Select-candidate algorithm

Same shape as `parse_func.c`'s function overload resolution: candidates
from the syscache, filter by exact matches first, then by promotable
matches, then by implicit-coercion matches. SQL spec §9.5 priority.

## Related

- `parse_coerce.c` — the actual coercion of operands once candidates are
  filtered.
- `parse_func.c` — sibling resolution logic for named function calls.
- `pg_operator` system catalog — backing store.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
- [subsystems/parser-and-rewrite.md](../../../../subsystems/parser-and-rewrite.md)
