# parse_merge.c

- **Source:** `source/src/backend/parser/parse_merge.c` (427 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## Purpose

Parse analysis for `MERGE INTO ... USING ... ON ... WHEN MATCHED THEN ...
WHEN NOT MATCHED THEN ...`. Builds a `Query{commandType=CMD_MERGE}` with
the target relation, the source (a relation or subquery), the join
condition, and a list of `MergeAction` nodes — one per `WHEN` branch.

## Entry

- `transformMergeStmt(pstate, stmt)` — called from
  `analyze.c:transformStmt` for `T_MergeStmt`. Steps:

  1. Add the target RTE (target-table, marked for `RowExclusiveLock`).
  2. Add the source RTE (via `transformFromClauseItem`-style helpers).
  3. Type-check the `ON` join condition (`EXPR_KIND_MERGE_WHEN`).
  4. For each `WHEN` clause: parse the `MergeWhenClause` action
     (`MERGE_WHEN_MATCHED` / `MERGE_WHEN_NOT_MATCHED_BY_SOURCE` /
     `MERGE_WHEN_NOT_MATCHED_BY_TARGET`), build the target list for
     UPDATE/INSERT actions, type-check the optional AND condition.
  5. Process RETURNING via the shared target-list machinery.

## Caveats

- The "match" condition is a join — a row not in the source can still
  fire a `WHEN NOT MATCHED BY SOURCE` action (PG 17 feature). The
  three-way enum is what the executor switches on.
- `MergeSupportFunc` nodes (`MERGE_ACTION()`) are produced here; their
  expression-side resolution sits in `parse_expr.c:transformMergeSupportFunc`.
- MERGE on partitioned tables uses the normal result-relation
  partitioning logic, but the rewriter (in `rewriteHandler.c`) has
  special handling for views — updatable views via MERGE were added in
  PG 17.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
