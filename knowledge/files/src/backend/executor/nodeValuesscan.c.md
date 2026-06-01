# nodeValuesscan.c

- **Source:** `source/src/backend/executor/nodeValuesscan.c` (≈300 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Code paths covered:** init + per-row evaluation + JIT trigger
- **Depth:** read

## Purpose

Scans a `VALUES (...), (...), (...)` clause. Each row is a List of Exprs
compiled into an ExprState at init time; per call we evaluate the next
row's ExprState into the result slot.

## Mechanics

- Init: walks `valuesLists` and either compiles per-row ExprStates eagerly
  (small lists) or stores raw Expr trees for lazy compilation. JIT (when
  enabled and `jit_above_cost` exceeded) is invoked here for hot VALUES
  scans inside larger plans.
- Per call: `node->curr_idx++`; compile (if needed) and evaluate the row.

## VALUES vs INSERT … VALUES

For `INSERT INTO t VALUES (...)`, the planner builds a `ValuesScan` below
the ModifyTable to deliver rows. Same code path applies.

## Tags

- [verified-by-code] per-row eager-vs-lazy compilation logic.
- [from-comment] interface list at top.
