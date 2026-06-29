# nodeAgg.h

- **Source:** `source/src/include/executor/nodeAgg.h` (≈340 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## Purpose

Public prototypes for nodeAgg.c PLUS the **shared layout structs** that
execExpr.c references when compiling agg-transition expressions
(`ExecBuildAggTrans`). That cross-dependency is why these structs live in
the header.

## Key structs

- `AggStatePerTransData` — per state value. Shared across multiple Aggrefs
  if they share transfn + arguments + inputCollation. Records:
  transfn/serialfn/deserialfn FmgrInfos and pre-init `FunctionCallInfo`s,
  tuplesort state for DISTINCT/ORDER BY, equality FmgrInfo + ExprState for
  DISTINCT comparison, initValue, type info, slots.
- `AggStatePerAggData` — per finalfn. Multiple identical Aggrefs share one.
  Holds finalfn FmgrInfo, direct args, result type info, `shareable` flag
  (false if finalfn is read-write — like `array_agg_finalfn` that takes
  ownership of state).
- `AggStatePerGroupData` — per-group working state. `transValue`,
  `transValueIsNull`, `noTransValue`. Tiny because in HASHED mode there's
  one per group per agg, embedded in the hashtable's `additionalsize`.
  Has explicit `FIELDNO_*` macros for JIT to reference offsets safely.
- `AggStatePerPhaseData` — for grouping sets, one per phase (a phase is one
  pass over sorted/partitioned input).
- `AggStatePerHashData` — for HASHED phase, one per grouping set.

## Public functions

`ExecInitAgg / ExecEndAgg / ExecReScanAgg`,
`hash_agg_entry_size`, `hash_agg_set_limits` (HashAgg memory budgeting
called by planner for cost estimates and by executor for spill thresholds),
`ExecAggEstimate/InitializeDSM/InitializeWorker/RetrieveInstrumentation`
for parallel.

## Tags

- [verified-by-code] struct field list + FIELDNO_* macros for JIT.
- [from-comment] AggStatePerGroupData's `noTransValue` vs `transValueIsNull`
  distinction (header comment is the only place this is spelled out).

## Synthesized by
<!-- backlinks:auto -->
- [idioms/aggregate-grouping-sets.md](../../../../idioms/aggregate-grouping-sets.md)
- [idioms/aggregate-hash-vs-sort.md](../../../../idioms/aggregate-hash-vs-sort.md)
