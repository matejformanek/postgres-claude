# rewriteSupport.c

- **Source:** `source/src/backend/rewrite/rewriteSupport.c` (116 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## Purpose

Catalog-level support helpers shared by `rewriteDefine.c` and
`rewriteRemove.c`.

## Functions

- `IsDefinedRewriteRule(relname, rulename)` — predicate, used by
  `DefineQueryRewrite` to reject duplicate rule names.
- `SetRelationRuleStatus(relationOid, relHasRules)` — flips
  `pg_class.relhasrules` and invalidates the relcache. Called when the
  first rule is added to a relation, or the last one is dropped.
- `get_rewrite_oid(relname, rulename, missing_ok)` — Oid lookup for
  ALTER RULE / drop paths.

## Why split out

`relhasrules` toggling and rulename lookup are the only two operations
that both Define and Remove paths need; collecting them here keeps the
catalog-touch logic in one place.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
