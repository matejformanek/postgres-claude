# nodeCustom.c

- **Source:** `source/src/backend/executor/nodeCustom.c` (≈200 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## Purpose

Extension hook: `CustomScan` plan nodes dispatch to a registered
`CustomScanMethods` (`nodes/extensible.h`) and `CustomExecMethods`. Used
by external code like Citus / TimescaleDB to inject node types the core
planner doesn't know about.

## Mechanics

`ExecInitCustomScan`:
- Allocates a `CustomScanState`; the extension provider's `CreateCustomScanState`
  may upcast to a larger struct.
- If `scanrelid > 0` (custom replacement of a base scan), opens the scan
  relation.
- Sets up TupleTableSlots with the provider-chosen slot ops.
- Calls provider's `BeginCustomScan`.

`ExecCustomScan` defers to provider's `ExecCustomScan` callback.

Other callbacks: ReScan, MarkPos, RestrPos, End, EstimateDSM,
InitializeDSMCustomScan, InitializeWorkerCustomScan, ReInitializeDSM,
ShutdownCustomScan, ExplainCustomScan.

## Tags

- [verified-by-code] CustomExecMethods dispatch + provider hooks.
- [from-comment] node-level header.
