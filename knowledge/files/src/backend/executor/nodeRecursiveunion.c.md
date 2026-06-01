# nodeRecursiveunion.c

- **Source:** `source/src/backend/executor/nodeRecursiveunion.c` (≈300 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## Purpose

Drives a `WITH RECURSIVE` CTE. Iterative semi-naive evaluation:

1. Run the **non-recursive** term (leftPlan); push results to the
   `intermediate_table` and (for UNION DISTINCT) into a hash table for dup
   detection.
2. Repeat:
   - Swap `intermediate_table` ↔ `working_table`.
   - Reset/rescan the **recursive** term (rightPlan), whose WorkTableScan
     reads from `working_table`.
   - Drain rightPlan into `intermediate_table` (dedup via hash if UNION).
   - Stop when intermediate is empty.

[from-comment file head + interface notes]

## UNION vs UNION ALL

- `UNION` (DISTINCT): `build_hash_table` allocates a TupleHashTable; only
  rows not already present in any previous iteration are added.
- `UNION ALL`: no dedup; trivially append.

## Termination

If the recursive term keeps producing new rows, the loop runs forever —
this is by design (the user is expected to write a terminating condition).
PG can hit out-of-disk-space on the tuplestore eventually, but does not
otherwise constrain iteration count (no `max_recursion` GUC like SQL Server).

## Tags

- [verified-by-code] semi-naive loop structure + dedup.
- [from-comment] file-level intent.
