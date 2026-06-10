---
path: src/include/executor/nodeIncrementalSort.h
anchor_sha: 4b0bf0788b0
loc: 28
depth: read
---

# nodeIncrementalSort.h

- **Source path:** `source/src/include/executor/nodeIncrementalSort.h`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 28

## Purpose

Prototype header for the `IncrementalSort` executor node
(`nodeIncrementalSort.c`). When input is already sorted by a prefix of the
required sort keys, it sorts only within each prefix group (a "sort
group"), cutting memory and enabling early output. Carries the
shared-instrumentation surface so parallel-worker sort stats reach EXPLAIN
ANALYZE. [verified-by-code]

## Public symbols

| Symbol | Kind | Notes |
|---|---|---|
| `ExecInitIncrementalSort(IncrementalSort *, EState *, int eflags)` | init | returns `IncrementalSortState *` |
| `ExecEndIncrementalSort` / `ExecReScanIncrementalSort` | teardown / rescan | |
| `ExecIncrementalSortEstimate / InitializeDSM / InitializeWorker` | instrumentation | shared-sort DSM for worker stats |
| `ExecIncrementalSortRetrieveInstrumentation` | instrumentation | pull worker sort counters |

## Invariants & gotchas

- **No mark/restore** (unlike plain [[nodeSort.h]]): incremental sort is
  not offered as a mergejoin inner. [verified-by-code, absence of MarkPos]
- The Estimate/InitializeDSM/InitializeWorker quartet here is *only* for
  instrumentation aggregation — the node is not parallel-aware in the
  scan-partitioning sense. [inferred]

## Cross-refs

- [[nodeSort.h]] — the full-sort sibling (mark/restore-capable).

## Tags

- [verified-by-code] prototype surface; [inferred] instrumentation-only role.
