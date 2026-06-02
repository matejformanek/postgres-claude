# rewriteDefine.c

- **Source:** `source/src/backend/rewrite/rewriteDefine.c` (871 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## Purpose

Implement `CREATE RULE` (the DDL side of the rewrite system) and the
`_RETURN` rule that internally backs every view. Stores rule definitions
in `pg_rewrite` and updates relcache invalidation so other backends notice.

## Public entry points

| Line | Symbol | Role |
|---|---|---|
| 52  | `InsertRule` | low-level `pg_rewrite` insert + dependency registration |
| 190 | `DefineRule` | parse the user-facing `CreateRuleStmt`, then call `DefineQueryRewrite` |
| 224 | `DefineQueryRewrite` | the meat: validate the rule action queries, check permissions, mutate the host relation if turning it into a view, finally `InsertRule` |

`DefineQueryRewrite` is also called by `commands/view.c` when creating a
view — every view is implemented as an unconditional INSTEAD ON SELECT
rule named `_RETURN` whose action is the view's query.

## What gets stored

`pg_rewrite` columns: `ev_class` (host rel Oid), `rulename`, `ev_type`
(SELECT/UPDATE/INSERT/DELETE), `ev_enabled`, `is_instead`, `ev_qual` (the
WHERE clause, nodeToString'd), `ev_action` (the rule's action queries,
nodeToString'd). `RewriteRule` (the in-memory form, in
`utils/rel.h`) is what the rewriter consumes.

## Constraints enforced at definition

- ON SELECT rules must be unconditional INSTEAD (the `_RETURN` shape).
- Multiple ON SELECT rules per relation are disallowed.
- RETURNING is only allowed in unconditional INSTEAD rules
  (referenced at `rewriteHandler.c:4533`).
- Rules can't refer to ENRs (transition tables).
- Various permission checks via `aclcheck`.

## Side effects

- Marks dependencies in `pg_depend` (rule → tables it references).
- If creating the `_RETURN` rule on a heap table, converts it in place
  to a view (changes `pg_class.relkind`, drops heap files).

## Related

- `rewriteRemove.c` — `DROP RULE`.
- `rewriteSupport.c` — small shared helpers (`IsDefinedRewriteRule`,
  `SetRelationRuleStatus`).
- `commands/view.c` — wrapper for view creation.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
- [subsystems/parser-and-rewrite.md](../../../../subsystems/parser-and-rewrite.md)
