# rewriteSupport.h

- **Source:** `source/src/include/rewrite/rewriteSupport.h` (~30 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## Purpose

Small set of catalog-side helpers and one important constant.

## Constants

```c
#define ViewSelectRuleName  "_RETURN"
```

The fixed name of the ON SELECT rule that every view's body is stored
under. Hardcoded across the codebase — see `commands/view.c`,
`rewriteHandler.c`, `ruleutils.c`.

## Functions

```c
extern bool IsDefinedRewriteRule(Oid owningRel, const char *ruleName);
extern void SetRelationRuleStatus(Oid relationId, bool relHasRules);
extern Oid  get_rewrite_oid(Oid relid, const char *rulename,
                            bool missing_ok);
```

All three are catalog-level helpers shared by `rewriteDefine.c` /
`rewriteRemove.c` and by some `commands/` paths that need to know whether
a rule exists.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/parser-and-rewrite.md](../../../../subsystems/parser-and-rewrite.md)
