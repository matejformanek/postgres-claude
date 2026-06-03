# rewriteManip.c

- **Source:** `source/src/backend/rewrite/rewriteManip.c` (1975 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## Purpose

Library of tree-manipulation helpers used by both `rewriteHandler.c` and
non-rewriter callers (planner, parser, partitioning). All operate on the
parser-produced `Query` / expression tree shape.

## Notable helpers

| Symbol | Use |
|---|---|
| `OffsetVarNodes(node, offset, sublevels_up)` | shift `varno` indices in an expression — used when concatenating rangetables (e.g. rule action's RT entries are appended to original Query's rtable) |
| `ChangeVarNodes` | renumber a specific old_varno → new_varno |
| `IncrementVarSublevelsUp` / `DecrementVarSublevelsUp` | adjust `varlevelsup` when moving an expression between nesting levels |
| `rangeTableEntry_used` | walker: is rt_index referenced anywhere in this query? (used by `fireRIRrules` `:2148` to skip irrelevant RTEs) |
| `attribute_used` | is `relid.attno` referenced? |
| `AddInvertedQual` | add `qual` as `NOT (qual)` to a Query's WHERE — the engine for "conditional INSTEAD" rule splitting |
| `AddQual` | append a qual via `AND` |
| `ReplaceVarsFromTargetList` | substitute Vars whose varno matches a given RTE with expressions from a target list — the substitution engine behind view expansion |
| `getInsertSelectQuery` | for an INSERT...SELECT, fetch the underlying SELECT Query (the rule action introspection helpers use this) |
| `acquireLocksOnSubLinks` (referenced by `rewriteHandler.c:68`) | local to handler but uses helpers from here |

## Var renumbering pattern

The rewriter's primary trick — "splice a rule action's tree into the
original query" — boils down to: append the action's `rtable` to the
original's, shift the action's `Var.varno`s by the old `rtable` length
(`OffsetVarNodes`), shift `varlevelsup` if crossing a subquery boundary,
substitute references to the rule's pseudo-RTE (NEW/OLD) with the actual
expressions (`ReplaceVarsFromTargetList`).

## Caveats

- These helpers walk *mutably* in some cases (the function name spells
  it out). Always copy first when the original tree must be preserved.
- The walker functions follow the standard `query_tree_walker` /
  `expression_tree_walker` idiom from `nodeFuncs.c`; bugs here often
  manifest as "node type T_X not supported" failures after a parsenode
  is added without updating the walkers.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
- [subsystems/parser-and-rewrite.md](../../../../subsystems/parser-and-rewrite.md)
