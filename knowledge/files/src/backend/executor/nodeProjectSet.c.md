# nodeProjectSet.c

- **Source:** `source/src/backend/executor/nodeProjectSet.c` (≈300 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## Purpose

Implements the legacy "set-returning function in the targetlist" semantics.
Where the planner cannot eliminate the SRF in the TLIST, it inserts a
`ProjectSet` node whose job is to call each TLIST SRF and emit one combined
output row per (input row × LCM of SRF cardinalities).

The PG10 SRF refactor moved most SRFs out of the TLIST (they now live in
FROM via LATERAL), but ProjectSet still drives ones that remain.

## Mechanics

`ExecProjectSet`:

- Hold the current input row in scan slot.
- Each `pset->elems[]` is either an Expr (non-SRF) or a SetExprState (SRF).
- On each output call, advance every SRF via `ExecMakeFunctionResultSet`
  (execSRF.c). If any SRF reports `ExprMultipleResult`, more rows are
  coming for this input — emit one combined row and stay on the same input.
- When all SRFs report `ExprEndResult`, pull the next input row.

## LCM semantics

If multiple SRFs in the TLIST produce different counts (e.g.
`SELECT generate_series(1,2), generate_series(1,3)`), output rows = LCM(2,3)
= 6 rows where shorter SRFs cycle. (This historical behavior is deprecated
and tagged so by warning in some cases.)

## Tags

- [verified-by-code] dispatch through SetExprState.
- [from-comment] file-level intent.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/executor.md](../../../../subsystems/executor.md)
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
