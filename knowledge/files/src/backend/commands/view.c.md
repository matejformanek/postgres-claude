# view.c

- **Source path:** `source/src/backend/commands/view.c`
- **Lines:** 519
- **Last verified commit:** `ef6a95c7c64`

## Purpose

"Use rewrite rules to construct views." [from-comment, view.c:3-4] CREATE VIEW = create a pg_class entry with `relkind = RELKIND_VIEW` + zero data files + an `ON SELECT` rule in pg_rewrite that substitutes the view's defining query whenever the view is referenced.

## Public surface

- `DefineView` — parse `ViewStmt`, call `DefineVirtualRelation` to make the pg_class+pg_attribute rows, then `StoreViewQuery` to put the query into pg_rewrite as `RULE_ON_SELECT`.
- `DefineVirtualRelation` — make the view relation; on CREATE OR REPLACE VIEW, verify that the new column list is a *superset* (compatible types) of the old — `checkViewColumns`.
- `StoreViewQuery` — write/replace the rewrite rule.
- `UpdateRangeTableOfViewParse` — used by `CREATE OR REPLACE VIEW` to update the stored rule's RT.

## Updatable views

A view is **automatically updatable** if it's a simple SELECT from one table without aggregates/DISTINCT/etc.; the rewriter handles INSERT/UPDATE/DELETE on it by substituting the underlying relation. Non-trivial views require INSTEAD OF triggers (`commands/trigger.c`) or INSTEAD rules. WITH CHECK OPTION is enforced by the rewriter (`rewrite/rewriteHandler.c`).

## Confidence tag tally

`[verified-by-code]=3 [from-comment]=1`

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
