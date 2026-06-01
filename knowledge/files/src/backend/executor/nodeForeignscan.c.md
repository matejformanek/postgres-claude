# nodeForeignscan.c

- **Source:** `source/src/backend/executor/nodeForeignscan.c` (≈480 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## Purpose

Thin shim that hosts a Foreign Data Wrapper's `FdwRoutine` callbacks.
The FDW (postgres_fdw, file_fdw, third-party) does all real work; this node
provides the executor-side scaffolding. [from-comment INTERFACE]

## Required FDW callbacks

- `BeginForeignScan(node, eflags)` — open the foreign connection / cursor.
- `IterateForeignScan(node)` — return next slot or NULL (used by
  `ForeignNext` → ExecScan).
- `EndForeignScan(node)` — close it down.
- `ReScanForeignScan(node)` — rewind.
- `RecheckForeignScan(node, slot)` — used by ExecScan recheck path.

## Async-capable FDWs (PG 14+)

Optional callbacks `ForeignAsyncRequest`, `ForeignAsyncConfigureWait`,
`ForeignAsyncNotify` plug into execAsync.c so a Foreign Scan under Append
participates in the leader's WaitEventSet (overlapping network round trips
across multiple remote shards).

## EPQ

For `FOR UPDATE` over a foreign table, the FDW provides
`RecheckForeignScan` to re-fetch the locked row from the remote side during
EvalPlanQual.

## Tags

- [verified-by-code] FdwRoutine callbacks used by the shim.
- [from-comment] interface list.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/executor.md](../../../../subsystems/executor.md)
- [subsystems/optimizer.md](../../../../subsystems/optimizer.md)
