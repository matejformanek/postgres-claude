# pquery.c

- **Source:** `source/src/backend/tcop/pquery.c` (1788 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read (top comment + PortalStart/PortalRun structure)

## Purpose

The **portal runner**. A `Portal` is the runtime-visible container around
one or more `PlannedStmt`s plus a `QueryDesc`, an `ActiveSnapshot`, a
`ResourceOwner`, and its own memory context (`portalContext`). pquery.c
implements `PortalStart`, `PortalRun`, `PortalRunFetch`, `PortalRunUtility`,
`PortalRunMulti` — i.e. everything you do to a portal between definition
and drop.

## Global

`ActivePortal` (`:36`) — current innermost executing portal. Saved/restored
around each `PortalStart`/`PortalRun` via `PG_TRY` so nesting works.

## Key entry points

| Line | Symbol | Role |
|---|---|---|
| 68 | `CreateQueryDesc` | wrap a `PlannedStmt` for the executor |
| 107 | `FreeQueryDesc` | free same |
| 138 | `ProcessQuery` | one-shot: ExecutorStart → ExecutorRun → ExecutorFinish → ExecutorEnd (used internally by RunUtility for utility-with-tuples) |
| 206 | `ChoosePortalStrategy` | decide PORTAL_ONE_SELECT / PORTAL_ONE_RETURNING / PORTAL_ONE_MOD_WITH / PORTAL_UTIL_SELECT / PORTAL_MULTI_QUERY |
| 430 | `PortalStart` | initialize executor state, acquire snapshot, set tupDesc, set status to `PORTAL_READY` |
| 620 | `PortalSetResultFormat` | apply per-column format codes (text/binary) |
| 681 | `PortalRun` | the dispatcher — switches on `portal->strategy` |
| 860 | `PortalRunSelect` | the SELECT path: ExecutorRun forward or backward into a DestReceiver |
| 991 | `FillPortalStore` | for non-trivial strategies, drain into a `Tuplestorestate` so later FETCHes / rewinds work |
| 1118 | `PortalRunUtility` | wrap a utility statement |
| 1182 | `PortalRunMulti` | execute a list of stmts as a portal step |
| 1374 | `PortalRunFetch` | cursor `FETCH` direction/count |
| 1666 | `DoPortalRewind` | rewind cursor |
| 1712 | `PlannedStmtRequiresSnapshot` | decide if a stmt needs a snapshot |
| 1761 | `EnsurePortalSnapshotExists` | lazily attach `ActiveSnapshot` to a portal |

## Control-flow sketch

`PortalDefineQuery` (in `utils/mmgr/portalmem.c`) creates the portal.
Then:

```
PortalStart(portal, params, eflags, snapshot)   // sets status=READY
[ PortalSetResultFormat(...) ]                  // optional
PortalRun(portal, count, isTopLevel, run_once, dest, altdest, qc)
…
PortalDrop(portal, false)                       // utils/mmgr/portalmem.c
```

Inside `PortalRun`:

- Save/restore `ActivePortal`, `CurrentResourceOwner`, `PortalContext`. `:430-460+`
- Push `PortalContext` as current memory context.
- Dispatch on `portal->strategy`.
- On error: status → `PORTAL_FAILED`; cleanup in `PortalErrorCleanup`
  (called from PostgresMain's sigsetjmp).

## Snapshots

- `PORTAL_ONE_SELECT` carries an `ActiveSnapshot`; cursors that need to
  outlive their statement push a `HoldStandbySnapshot`. See
  `EnsurePortalSnapshotExists` and the `setHoldSnapshot` flag threading.

## Interactions

- Executor: `executor/execMain.c` (ExecutorStart/Run/Finish/End).
- Utility: `tcop/utility.c::ProcessUtility`.
- Portal storage: `utils/mmgr/portalmem.c` (PortalCreate, PortalDefineQuery,
  PortalDrop).
- Snapshots: `utils/time/snapmgr.c`.
- Header: `tcop/pquery.h`.
