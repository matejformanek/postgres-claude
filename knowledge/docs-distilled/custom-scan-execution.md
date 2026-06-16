---
source_url: https://www.postgresql.org/docs/current/custom-scan-execution.html
chapter: "60.3 Executing Custom Scans"
fetched_at: 2026-06-15
anchor_sha: b78cd2bda5b1a306e2877059011933de1d0fb735
---

# Custom scan execution (`CustomScanState`) — §60.3

Distilled from §60.3. Execution-side companion to
[[knowledge/docs-distilled/custom-scan-plan.md]]; parent
[[knowledge/docs-distilled/custom-scan.md]]. The `CustomExecMethods`
table here is the executor analogue of the FDW exec callbacks.

## Non-obvious claims

- `CustomScanState` = `ScanState ss` + `uint32 flags` + `methods`
  pointer. Unlike `CustomScan`, it **need not be `copyObject`-able**, so
  providers normally embed it as the first member of a larger private
  struct. [from-docs §60.3]
- **For a join-replacement scan, `ss.ss_currentRelation` is left NULL**
  (there is no single base relation), mirroring the `scanrelid=0` rule on
  the plan node. [from-docs §60.3]
- Four required callbacks: `BeginCustomScan` (finish init of private
  fields; standard fields already set by `ExecInitCustomScan`),
  `ExecCustomScan` (fill `ps_ResultTupleSlot` with the next tuple in the
  current scan direction, or return NULL/empty slot), `EndCustomScan`
  (cleanup — required even if it does nothing), `ReScanCustomScan`
  (rewind). [from-docs §60.3]
- `MarkPosCustomScan` / `RestrPosCustomScan` are only needed if the
  provider set the `CUSTOMPATH_SUPPORT_MARK_RESTORE` flag (path → plan →
  state). Omit them otherwise. [from-docs §60.3]
- **Parallel support is a grouped opt-in** mirroring FDW/parallel-node
  conventions: `EstimateDSMCustomScan` (bytes; may overestimate, must not
  underestimate), `InitializeDSMCustomScan` (leader sets up shared
  state), `InitializeWorkerCustomScan` (worker derives local state),
  `ReInitializeDSMCustomScan` (reset shared state before a rescan). All
  optional; supply the whole set or none. [from-docs §60.3]
- **Split-of-responsibility contract:** `ReInitializeDSMCustomScan`
  should reset *only shared* state; `ReScanCustomScan` should reset *only
  local* state. The docs note the DSM-reinit currently runs before the
  rescan callback but explicitly warn **not to rely on that ordering**.
  [from-docs §60.3]
- `ShutdownCustomScan` is the "node won't run to completion" hook: it
  fires *before the DSM segment is destroyed*, so it is where a provider
  drains shared results — but it is **not always called**; `EndCustomScan`
  can be reached without it. So end-of-node cleanup must be idempotent
  across the two. [from-docs §60.3]
- `ExplainCustomScan(node, ancestors, es)` is optional; the common
  `ScanState` data (target list, scan relation) prints without it — it
  only adds *private* detail. [from-docs §60.3]

## Links into corpus

- Plan-side companion (this run): [[knowledge/docs-distilled/custom-scan-plan.md]].
- Parent chapter: [[knowledge/docs-distilled/custom-scan.md]].
- Source structs: [[knowledge/files/src/include/nodes/extensible.h.md]]
  (`CustomScanState`, `CustomExecMethods`).
- FDW parallel/async exec analogue: [[knowledge/docs-distilled/fdw-callbacks.md]]
  (§58.2.10 parallel callbacks — same Estimate/Initialize DSM idiom).
- Executor node lifecycle: [[knowledge/subsystems/optimizer.md]]
  (and the executor file docs for `ExecInitNode`/`ExecProcNode`).

## Caveats / verification

- `[from-docs §60.3]`. Callback signatures cross-checked against the
  §60.3 prose; re-verify against
  `source/src/include/nodes/extensible.h` at anchor
  `b78cd2bda5b1a306e2877059011933de1d0fb735` for exact field order and
  the `CUSTOMPATH_*` flag bit values.
