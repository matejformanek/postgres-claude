# rewriteManip.h

- **Source:** `source/src/include/rewrite/rewriteManip.h` (~120 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## Purpose

Public surface of the tree-manipulation library in `rewriteManip.c`. Used
widely outside the rewriter — by planner, parser, partitioning, RLS,
ruleutils, FDW pushdown.

## Context structs

- `replace_rte_variables_context` — passed to `replace_rte_variables`
  callbacks (the generic var-substitution engine).
- `ChangeVarNodes_context` — for the rt_index-renumbering walk.

## Exported entries (selection)

- `OffsetVarNodes`, `ChangeVarNodes` — rangetable renumbering.
- `IncrementVarSublevelsUp`, `IncrementVarSublevelsUp_rtable`,
  `DecrementVarSublevelsUp` — nesting-level adjustment.
- `rangeTableEntry_used` — predicate walker.
- `attribute_used`, `find_attr_recursive_in_jointree` —
  attribute-reference predicates.
- `AddQual`, `AddInvertedQual` — qual splicing for rule application.
- `ReplaceVarsFromTargetList` — the substitution engine behind view
  expansion.
- `getInsertSelectQuery` — strip the layer between INSERT-SELECT and the
  SELECT body.
- `acquireLocksOnSubLinks` is referenced from the impl but not exported.

## Why it's used outside rewrite/

These walkers are "anything that needs to splice or renumber pieces of a
Query." Many callers therefore depend on this header without being
rule-related.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/parser-and-rewrite.md](../../../../subsystems/parser-and-rewrite.md)
