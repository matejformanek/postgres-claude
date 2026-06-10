---
path: src/include/executor/nodeFunctionscan.h
anchor_sha: 4b0bf0788b0
loc: 23
depth: read
---

# nodeFunctionscan.h

- **Source path:** `source/src/include/executor/nodeFunctionscan.h`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 23

## Purpose

Prototype header for the `FunctionScan` executor node
(`nodeFunctionscan.c`) — executes a set-returning function in `FROM`
(`SELECT * FROM generate_series(...)`, `ROWS FROM (f(), g())`). It
materialises each function's output into a tuplestore. [verified-by-code]

## Public symbols

| Symbol | Kind | Notes |
|---|---|---|
| `ExecInitFunctionScan(FunctionScan *, EState *, int eflags)` | init | returns `FunctionScanState *` |
| `ExecEndFunctionScan(FunctionScanState *)` | teardown | frees the per-function tuplestores |
| `ExecReScanFunctionScan(FunctionScanState *)` | rescan | re-runs the function on parameter change |

## Invariants & gotchas

- Has an explicit `ExecEnd` (unlike Values/Worktable/NamedTuplestore)
  because it owns tuplestore(s) and function call state to release.
  [verified-by-code, execProcnode.c]

## Cross-refs

- [[nodeTableFuncscan.h]] — `XMLTABLE`/`JSON_TABLE` sibling.
- [[nodeValuesscan.h]] — the constant-rows sibling (no ExecEnd).

## Tags

- [verified-by-code] prototype surface.
