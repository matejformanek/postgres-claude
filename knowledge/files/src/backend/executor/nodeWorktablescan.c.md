# nodeWorktablescan.c

- **Source:** `source/src/backend/executor/nodeWorktablescan.c` (≈170 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## Purpose

Scans the **working table** inside the recursive part of a recursive CTE.
Companion to `nodeRecursiveunion.c`: each iteration of the recursive
union, the WorkTableScan reads from the tuplestore that holds the previous
iteration's results.

## Mechanics

WorkTableScan finds its driving RecursiveUnionState via the EState
(`es_param_exec_vals` PARAM_EXEC slot indexes set by the planner). Pulls
rows from `ru_->working_table` (a Tuplestorestate) one at a time.

A WorkTableScan resets its read pointer at every rescan, so RecursiveUnion
just resets+swaps the working table and the scan re-reads from start.

## Tags

- [verified-by-code] linkage through PARAM_EXEC slot.
- [from-comment] WorkTableScanNext docstring.
