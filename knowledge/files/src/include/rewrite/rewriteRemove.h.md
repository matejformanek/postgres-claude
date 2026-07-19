# rewriteRemove.h

- **Source:** `source/src/include/rewrite/rewriteRemove.h` (~20 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## Purpose

One function:

```c
extern void RemoveRewriteRuleById(Oid ruleOid);
```

The path used by `dependency.c` to drop a rule when a containing object's
DROP cascades.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/parser-and-rewrite.md](../../../../subsystems/parser-and-rewrite.md)
