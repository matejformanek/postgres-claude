# `src/include/executor/execAsync.h`

**Pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`

## Role

Async-execution dispatch — used by `Append` to overlap subplan
fetches when the subplan is an async-capable foreign scan
(`postgres_fdw`).

## Public API

[verified-by-code: lines 18-23]

```c
void ExecAsyncRequest(AsyncRequest *areq);
void ExecAsyncConfigureWait(AsyncRequest *areq);
void ExecAsyncNotify(AsyncRequest *areq);
void ExecAsyncResponse(AsyncRequest *areq);
void ExecAsyncRequestDone(AsyncRequest *areq, TupleTableSlot *result);
void ExecAsyncRequestPending(AsyncRequest *areq);
```

`AsyncRequest` is defined in `nodes/execnodes.h` — carries
`requestor` (the Append parent), `requestee` (the async child),
`callback_pending`, `request_index`, `result`.

The protocol [from `execAsync.c`, sketched here]:
1. Append calls `ExecAsyncRequest(areq)` → child either returns
   immediately via `ExecAsyncRequestDone` (synchronous-ish) or
   marks pending via `ExecAsyncRequestPending`.
2. Append polls FDs via `ExecAsyncConfigureWait` → kernel.
3. On readiness, executor calls `ExecAsyncNotify(areq)` → child
   reads from its socket and eventually invokes
   `ExecAsyncResponse(areq)` or `ExecAsyncRequestDone`.

## Invariants

- **INV-CHILD-CAPABILITY** [inferred] Only ForeignScan + CustomScan
  nodes implementing the async hooks may be a `requestee`. The
  Append planner checks `pathlist` for async-capable paths.
- **INV-PAIRED-CALLBACK** [inferred] After `ExecAsyncRequestPending`
  the child *must* eventually call exactly one of
  `ExecAsyncRequestDone` or another `ExecAsyncRequestPending`.

## Trust boundary (Phase D — A11 cross-link)

- **FDW connection rebind**: with `postgres_fdw`, async execution
  multiplexes multiple foreign-server connections from a single
  backend. A connection cached against one user mapping could in
  principle be reused for another query if connection-cache
  invalidation is missed — A11 finding (`postgres_fdw connection
  cache mishandling` cluster).
- **Wait-event leak**: `ExecAsyncConfigureWait` registers FDs in
  the backend's `WaitEventSet`, visible in
  `pg_stat_activity.wait_event_type=Client`. Cross-role observers
  can see when an FDW backend is waiting on a remote.

## Cross-refs

- `nodes/execnodes.h` — `AsyncRequest`.
- `executor/nodeAppend.h` — the async-Append node.
- `executor/nodeForeignscan.h` + `foreign/fdwapi.h` — FDW async
  hooks (`ForeignAsyncRequest`, `ForeignAsyncConfigureWait`,
  `ForeignAsyncNotify`).
- A11 postgres_fdw connection cache cluster.

## Issues

- [ISSUE-PHASE-D-A11: async execution is the FDW path most prone to
  connection-cache reuse mishaps under role/UM changes; not
  documented at header (medium, A11 cluster echo)] — entire file.
