# execScan.c

- **Source:** `source/src/backend/executor/execScan.c` (156 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** deep-read

## Purpose

Tiny but central: provides `ExecScan(ScanState *, ExecScanAccessMtd accessMtd,
ExecScanRecheckMtd recheckMtd)` — the generic "fetch next tuple from the AM,
apply qual, project" loop shared by every relation/scan node (SeqScan,
IndexScan, FunctionScan, ValuesScan, ForeignScan, CustomScan, etc.).
[from-comment] `:3-10`

## Why this matters

By centralizing qual + projection here, individual scan nodes only have to
provide:

- an **access method** callback that returns the next raw tuple in the scan
  slot (or `NULL` for EOS),
- a **recheck method** that re-evaluates internal pushed-down quals when
  EvalPlanQual hands the node a different row.

This is the core of PG's "every scan node looks the same to its parent"
abstraction. ExecScan handles `EvalPlanQual` replays transparently: if
`estate->es_epq_active` is in play, ExecScan diverts to `EvalPlanQualNext`
which yields the replayed row, then ExecScan re-runs qual+projection +
calls the supplied `recheckMtd` to verify access-method-internal predicates.

## Glue helpers in the matching header

`execScan.h` defines `ExecScanReScan(ScanState*)` which is the boilerplate
ReScan companion — clears the scan slot, resets EPQ state, and bumps the
node's tuple counters. Headers also wire up TupleTableSlot allocation for
scan/result slots via `ExecInitScanTupleSlot` and `ExecAssignScanProjectionInfo`
(in execTuples.c / execUtils.c).

## Tags

- [verified-by-code] role of ExecScan + the access/recheck callback contract.
- [from-comment] top-of-file purpose statement.
