# rewriteRemove.c

- **Source:** `source/src/backend/rewrite/rewriteRemove.c` (94 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## Purpose

`DROP RULE` implementation — delete a `pg_rewrite` row and invalidate the
host relation's relcache entry so other backends pick up the change.

## Functions

- `RemoveRewriteRuleById(ruleOid)` — by Oid; the path used by
  `dependency.c` when a dependent object's drop cascades to the rule.
- Helpers to locate the rule's host class Oid before deletion (needed
  for the relcache invalidation).

## Side effects

- Calls `CacheInvalidateRelcacheByRelid` on the host relation.
- Removes `pg_depend` entries.
- Does NOT undo the relkind change made by `DefineQueryRewrite` — dropping
  a view's `_RETURN` rule is rejected separately by view-drop code.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
