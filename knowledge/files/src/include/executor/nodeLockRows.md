# `executor/nodeLockRows.h` — SELECT FOR UPDATE/SHARE declarations

**Verified against source pin `4b0bf0788b0`** (path: `source/src/include/executor/nodeLockRows.h`)

## Role
Declares entry points for `LockRows` — the executor node that implements `SELECT … FOR {UPDATE | NO KEY UPDATE | SHARE | KEY SHARE}`. Per row from its child plan, takes the requested row-level lock (calling `heap_lock_tuple` and following any updated-version chain), and either returns the (re-fetched) row or skips it under `SKIP LOCKED` / errors out under `NOWAIT`.

## Public API
- `ExecInitLockRows(LockRows *, EState *, int eflags)` — nodeLockRows.h:19
- `ExecEndLockRows(LockRowsState *)` — nodeLockRows.h:20
- `ExecReScanLockRows(LockRowsState *)` — nodeLockRows.h:21

## Phase D
Logical replication / catalog-xmin interaction (A8 echo). `SELECT FOR KEY SHARE` on catalog rows holds tuple-level locks that interact with `catalog_xmin` horizon advancement. A long-running `FOR UPDATE` session can pin xmin and stall logical-decoding slot advancement, indirectly back-pressuring publishers.

## Cross-refs
- Plan node: `LockRows` in `nodes/plannodes.h`
- State node: `LockRowsState` in `nodes/execnodes.h`
- Row-lock impl: `access/heapam.h` (`heap_lock_tuple`), `access/tableam.h` (`tuple_lock`)
- `.c` impl: `source/src/backend/executor/nodeLockRows.c`
- Wait policy: `nodes/lockoptions.h` (LockClauseStrength, LockWaitPolicy)

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/executor.md](../../../../subsystems/executor.md)
