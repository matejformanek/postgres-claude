---
path: src/include/executor/nodeLockRows.h
anchor_sha: 4b0bf0788b0
loc: 23
depth: read
---

# nodeLockRows.h

- **Source path:** `source/src/include/executor/nodeLockRows.h`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 23

## Purpose

Prototype header for the `LockRows` executor node (`nodeLockRows.c`), which
implements row-level locking for `SELECT ... FOR UPDATE / FOR SHARE / FOR
NO KEY UPDATE / FOR KEY SHARE`. For each row from its child it takes the
requested tuple lock, follows update chains, and runs EvalPlanQual on
concurrent updates. [verified-by-code]

## Public symbols

| Symbol | Kind | Notes |
|---|---|---|
| `ExecInitLockRows(LockRows *, EState *, int eflags)` | init | returns `LockRowsState *` |
| `ExecEndLockRows(LockRowsState *)` | teardown | |
| `ExecReScanLockRows(LockRowsState *)` | rescan | |

## Invariants & gotchas

- This is where **EvalPlanQual** (EPQ) re-checking lives for locking
  SELECTs: on a concurrent update the node re-evaluates the plan against
  the updated tuple to decide whether it still qualifies. See the executor
  README §EvalPlanQual. [from-README]
- Lock strength comes from the `rowMarks` list; different result relations
  in one query can take different lock modes. [inferred]

## Cross-refs

- [[nodeModifyTable.h]] — the write-side row locking / EPQ counterpart.

## Tags

- [verified-by-code] prototype surface; [from-README] EPQ role.
