# nodeIndexscan.h

- **Source:** `source/src/include/executor/nodeIndexscan.h` (~55 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## Node API

`ExecInitIndexScan`, `ExecEndIndexScan`, `ExecIndexMarkPos`,
`ExecIndexRestrPos`, `ExecReScanIndexScan`, parallel DSM hooks,
parallel instrumentation hooks.

## Shared helpers (also used by nodeIndexonlyscan.c and nodeBitmapIndexscan.c)

- `ExecIndexBuildScanKeys(planstate, index, quals, isorderby, &scanKeys,
  &numScanKeys, &runtimeKeys, &numRuntimeKeys, &arrayKeys, &numArrayKeys)`
  — translate qual list into ScanKey arrays. **The `isorderby` flag** flips
  the semantics: order-by keys go to the AM's separate orderby ScanKey
  array used by kNN-style indexes.
- `ExecIndexEvalRuntimeKeys(econtext, runtimeKeys, n)` — re-evaluate Param-
  dependent scan keys at each scan start.
- `ExecIndexEvalArrayKeys / ExecIndexAdvanceArrayKeys` — for
  `col = ANY(ARRAY[$1, $2, $3])` style: drive a per-array-element iteration
  inside one IndexScan call.

## Tags

- [verified-by-code] all prototypes.
