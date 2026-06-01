# nodeSubqueryscan.c

- **Source:** `source/src/backend/executor/nodeSubqueryscan.c` (≈190 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## Purpose

A scan-shaped wrapper around a **subquery in FROM** that the planner could
not flatten into the parent query. The subplan executes as a separate plan
tree (built by `set_subqueryscan_references` in setrefs.c).

`ExecSubqueryScan` just delegates to `subplanstate` and returns its rows.
Mostly exists to provide a node type whose `scanrelid > 0` so the executor
can hang RTE info on it; the subplan itself does all the work.

## Tags

- [verified-by-code] dispatch to subplanstate.
- [from-comment] interface list at top.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/executor.md](../../../../subsystems/executor.md)
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
