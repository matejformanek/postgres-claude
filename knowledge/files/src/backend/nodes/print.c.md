# print.c

- **Source:** `source/src/backend/nodes/print.c` (515 lines)
- **Last verified commit:** `ef6a95c7c64`
- **Depth:** skim

## Purpose

Debug pretty-printers — wrappers around `nodeToString` plus indenting
formatters, plus hand-rolled printers for a few planner-internal
structures that don't have great `_OUT` forms.

## API

| Line | Function | Notes |
|---|---|---|
| 36 | `print(obj)` | `nodeToStringWithLocations` → `format_node_dump` → printf |
| 54 | `pprint(obj)` | same but `pretty_format_node_dump` |
| 72 | `elog_node_display(lev, title, obj, pretty)` | sends pretty-printed dump to log via `ereport`/`errdetail_internal` |
| 96 | `format_node_dump(dump)` | wraps long output at 78 cols on whitespace |
| 150 | `pretty_format_node_dump(dump)` | indent by tracking `{}` `:` `()` nesting; LINELEN=78, INDENTSTOP=3, MAXINDENT=60 |
| 254 | `print_rt(rtable)` | tabular print of `RangeTblEntry` list with rtekind |
| 329 | `print_expr(expr, rtable)` | recursive print for Var/Const/OpExpr/FuncExpr (others print "unknown expr") |
| 434 | `print_pathkeys(pathkeys, rtable)` | walks PathKey list → EquivalenceClass members → `print_expr` |
| 474 | `print_tl(tlist, rtable)` | TargetEntry list — resno, resname, expr |
| 500 | `print_slot(slot)` | TupleTableSlot via `debugtup` |

## Notes

- The `dump`-formatting functions are pure text transforms; they don't
  understand node semantics, just balance `{` `}` and break lines on
  whitespace.
- `print_expr` is intentionally limited — only Var/Const/OpExpr/FuncExpr
  — which means dumping a complex expression often shows
  "unknown expr" for sub-nodes. Intended for `gdb` / `elog` debugging,
  not user-facing output.
- `nodeDisplay(x)` macro in the header just calls `pprint`.

## Cross-references

- Header: `source/src/include/nodes/print.h`
- Companion underlying machinery: `outfuncs.c` (`nodeToStringWithLocations`).
- Heavy users: planner debug builds (`debug_print_plan`,
  `debug_print_parse`, `debug_print_rewritten` GUCs).
