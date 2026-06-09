# `src/include/executor/execScan.h`

**Pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`

## Role

Inlineable scan-tuple machinery shared by all scan-style nodes
(`SeqScan`, `IndexScan`, `BitmapHeapScan`, `ForeignScan`,
`CustomScan`, …) [from-comment: lines 1-2]. Two
`pg_attribute_always_inline` static functions: `ExecScanFetch` and
`ExecScanExtended`.

## Public API

### `ExecScanFetch(node, epqstate, accessMtd, recheckMtd)`
[verified-by-code: lines 32-136]

Check CFI, then either:
1. **EvalPlanQual recheck path** [lines 40-130]: if `epqstate !=
   NULL`, return the test tuple supplied by the EPQ caller, after
   running `recheckMtd` to validate access-method quals.
2. **Normal path** [lines 132-135]: call `accessMtd(node)`.

EPQ branches:
- `scanrelid == 0` (foreign or custom pushed-down join): if this
  node is a descendant in the EPQ tree (its extParam contains the
  EPQ param), run recheck; else fall through to access method.
- `relsubs_done[scanrelid-1]`: return empty slot (already
  delivered).
- `relsubs_slot[scanrelid-1] != NULL`: return that replacement
  tuple, mark done.
- `relsubs_rowmark[scanrelid-1] != NULL`: fetch via non-locking
  rowmark (`EvalPlanQualFetchRowMark`).

### `ExecScanExtended(node, accessMtd, recheckMtd, epqstate, qual,
                     projInfo)` [verified-by-code: lines 160-253]

Driver loop:
- Fast path [lines 174-180]: if neither `qual` nor `projInfo`,
  reset expr context and return raw scan tuple.
- Else loop: fetch via `ExecScanFetch`, check `qual` via
  `ExecQual`, apply `ExecProject` if needed. On qual failure,
  increment `InstrCountFiltered1` and continue.

Designed so the compiler eliminates branches when arguments are
NULL [from-comment: lines 148-151].

## Invariants

- **INV-CFI** [verified-by-code: line 38] `CHECK_FOR_INTERRUPTS()`
  is called once per fetched tuple — cancellation latency tied to
  scan tuple rate.
- **INV-EXPRCTX-RESET** [verified-by-code: lines 178, 186, 251]
  Per-tuple expr context reset on every fetch and after each qual
  failure.
- **INV-EPQ-ROW-AT-MOST-ONCE** [verified-by-code: lines 72-82,
  93-104, 114-116] EPQ replacement tuples are delivered at most
  once per relsubs slot.
- **INV-EMPTY-SLOT-TYPE** [verified-by-code: lines 204-209] When
  returning empty due to scan end, use `projInfo->pi_state.resultslot`
  if projecting — so the caller sees a slot with the correct
  TupleDesc.

## Trust boundary

No direct Phase D surface — this is per-tuple plumbing. Quals and
projections invoke user-defined functions, but those run under
existing executor fmgr/SQL function gates (`fmgr-and-spi`,
`memory-contexts`).

## Cross-refs

- `executor/executor.h` — main executor API.
- `executor/instrument.h` — `InstrCountFiltered1`.
- `nodes/execnodes.h` — `ScanState`, `EPQState`,
  `ExecScanAccessMtd`, `ExecScanRecheckMtd`.
- `executor/nodeSeqscan.h` et al — callers.

## Issues

None.
