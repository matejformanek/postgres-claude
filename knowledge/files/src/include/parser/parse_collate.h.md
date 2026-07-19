# parse_collate.h

- **Source:** `source/src/include/parser/parse_collate.h` (~27 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## Purpose

Tiny header — 4 functions.

```c
extern void assign_query_collations  (ParseState *, Query *);
extern void assign_list_collations   (ParseState *, List *exprs);
extern void assign_expr_collations   (ParseState *, Node *expr);
extern Oid  select_common_collation  (ParseState *, List *exprs, bool none_ok);
```

`assign_query_collations` is the public top-level call, used by every
per-statement transform in `analyze.c` after the rest of the analysis is
complete. The other three are for callers that need finer-grained
collation work (planner sometimes, DDL constraint expressions).

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/parser-and-rewrite.md](../../../../subsystems/parser-and-rewrite.md)
