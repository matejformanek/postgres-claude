# parse_merge.h

- **Source:** `source/src/include/parser/parse_merge.h` (~22 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## Purpose

Single-function header.

```c
extern Query *transformMergeStmt(ParseState *, MergeStmt *);
```

Called from `analyze.c:transformStmt` on `T_MergeStmt`. Everything else is
internal to `parse_merge.c`.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/parser-and-rewrite.md](../../../../subsystems/parser-and-rewrite.md)
