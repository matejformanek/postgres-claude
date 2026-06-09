# `executor/nodeMemoize.h` — Memoize result-cache declarations

**Verified against source pin `4b0bf0788b0`** (path: `source/src/include/executor/nodeMemoize.h`)

## Role
Declares entry points for `Memoize` — the LRU result-cache plan node introduced in PG 14. Sits between an inner plan (typically a parameterized index path) and an outer driver (typically a Nested Loop); caches by parameter-key, evicts via LRU. Parallel-aware for instrumentation.

## Public API
- `ExecInitMemoize` / `ExecEndMemoize` / `ExecReScanMemoize` — nodeMemoize.h:20-22
- `ExecEstimateCacheEntryOverheadBytes(double ntuples)` — nodeMemoize.h:23 (planner-side cost-model helper)
- Parallel instrumentation: `ExecMemoizeEstimate` / `…InitializeDSM` / `…InitializeWorker` / `…RetrieveInstrumentation` — nodeMemoize.h:24-30 (no per-worker DSM state — workers maintain private caches; only stats merge)

## Phase D
Hash-flood DoS (A11 echo). The cache is a `simplehash`-style table keyed by parameter values; adversarial parameter values with crafted hash collisions can degrade lookup to O(n) and inflate cache memory. Eviction respects `work_mem` so the worst case is wall-time degradation rather than OOM, but planner cost-model assumes well-distributed keys.

## Cross-refs
- Plan node: `Memoize` in `nodes/plannodes.h`
- State node: `MemoizeState` in `nodes/execnodes.h`
- `.c` impl: `source/src/backend/executor/nodeMemoize.c`
- Planner cost: `optimizer/path/costsize.c` (`cost_memoize_rescan`)
- Hash impl: `lib/simplehash.h`
