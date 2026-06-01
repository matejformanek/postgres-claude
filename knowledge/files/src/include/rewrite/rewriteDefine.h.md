# rewriteDefine.h

- **Source:** `source/src/include/rewrite/rewriteDefine.h` (~30 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## Purpose

API of `rewriteDefine.c` — CREATE RULE + view-rule installation.

## Exported entries

- `DefineRule(RuleStmt *, const char *queryString)` — top entry, returns
  `ObjectAddress`.
- `DefineQueryRewrite(rulename, event_relid, event_qual, event_type,
   is_instead, replace, action)` — used by `commands/view.c` for view
  installation (and internally by `DefineRule`).
- `EnableDisableRule` — used by `ALTER TABLE ... ENABLE/DISABLE RULE`.
- Constants: `ViewSelectRuleName` (`"_RETURN"`) is in `rewriteSupport.h`,
  not here.
