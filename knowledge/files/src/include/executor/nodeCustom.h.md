---
path: src/include/executor/nodeCustom.h
anchor_sha: 4b0bf0788b0
loc: 42
depth: read
---

# nodeCustom.h

- **Source path:** `source/src/include/executor/nodeCustom.h`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 42

## Purpose

Prototype header for the `CustomScan` executor node (`nodeCustom.c`) — the
extension hook that lets a loadable module inject its own scan/join
execution provider via `CustomScanMethods` + `CustomExecMethods`. The
generic shell here dispatches into the extension's callbacks. One of the
two public extensibility seams (the other is the FDW [[nodeForeignscan.h]]).
[verified-by-code]

## Public symbols

| Symbol | Kind | Notes |
|---|---|---|
| `ExecInitCustomScan(CustomScan *, EState *, int eflags)` | init | returns `CustomScanState *` |
| `ExecEndCustomScan` / `ExecReScanCustomScan` | teardown / rescan | |
| `ExecCustomMarkPos` / `ExecCustomRestrPos` | mark/restore | only if the provider sets the capability flag |
| `ExecCustomScanEstimate / InitializeDSM / ReInitializeDSM / InitializeWorker` | parallel-aware | provider-driven parallel state |
| `ExecShutdownCustomScan(CustomScanState *)` | shutdown | early release hook |

## Invariants & gotchas

- This header is **part of the extension ABI** — a CustomScan provider in
  a third-party `.so` calls and is called through these signatures. Changes
  here are extension-breaking. See the `extension-development` skill.
  [inferred]
- Mark/restore is only valid when the provider advertises
  `CUSTOMPATH_SUPPORT_MARK_RESTORE`; otherwise the planner won't place it
  under a mergejoin. [from-comment]

## Cross-refs

- [[nodeForeignscan.h]] — the FDW extensibility seam.

## Tags

- [verified-by-code] prototype surface; [inferred] ABI-stability note.
