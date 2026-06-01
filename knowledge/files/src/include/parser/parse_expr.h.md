# parse_expr.h

- **Source:** `source/src/include/parser/parse_expr.h` (~25 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## Purpose

Minimal API surface for the giant `parse_expr.c`. Only two functions and a
GUC.

```c
extern PGDLLIMPORT bool Transform_null_equals;

extern Node *transformExpr(ParseState *, Node *expr, ParseExprKind);
extern const char *ParseExprKindName(ParseExprKind);
```

All per-node-kind transformers are `static` inside `parse_expr.c`. The
public contract is just "give me a raw expression + a kind, get back a
typed one."
