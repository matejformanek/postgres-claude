# `src/include/utils/portal.h`

**Pin:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`

## Role

Defines the *Portal* — the execution-state frame for a running or
runnable query [from-comment: lines 7-9]. Backs both SQL `CURSOR`s
and the wire-protocol Bind/Execute portals.

## Public API

### Strategies [verified-by-code: lines 89-96]

`PortalStrategy`:
- `PORTAL_ONE_SELECT` — incremental, scrollable, holdable.
- `PORTAL_ONE_RETURNING` — INSERT/UPDATE/DELETE/MERGE with
  RETURNING; runs to completion on first execute, results in
  tuplestore.
- `PORTAL_ONE_MOD_WITH` — single SELECT with data-modifying CTE;
  same behavior as RETURNING.
- `PORTAL_UTIL_SELECT` — utility statement with SELECT-like result
  (EXPLAIN, SHOW); buffers results.
- `PORTAL_MULTI_QUERY` — everything else; no partial execution.

### Status [verified-by-code: lines 103-111]

`PortalStatus`: NEW → DEFINED → READY ↔ ACTIVE → DONE / FAILED.
ACTIVE can transition back to READY if the query is not run to
completion [from-comment: lines 99-101].

### `PortalData` struct [verified-by-code: lines 115-205]

Key fields:
- Identity: `name`, `prepStmtName`, `sourceText`, `commandTag`.
- Memory: `portalContext`, `resowner` (resource owner), `cleanup`
  callback.
- Subxact bookkeeping: `createSubid`, `activeSubid`, `createLevel`.
- Plan: `stmts` (list of `PlannedStmt`), `cplan` (CachedPlan),
  `portalParams`, `queryEnv`.
- Strategy + cursor options.
- `portalPinned` (cannot be dropped), `autoHeld` (auto-converted
  pinned→held).
- `queryDesc` (live executor state) — call `ExecutorEnd` if non-NULL.
- `tupDesc` + `formats[]` for results.
- `portalSnapshot` — outermost ActiveSnapshot needed to detoast
  results and bound exposed xmin [lines 162-168].
- `holdStore`, `holdContext`, `holdSnapshot` — tuplestore for
  cross-transaction holdable cursors.
- Cursor position: `atStart`, `atEnd`, `portalPos`.
- `creation_time`, `visible` (pg_cursors).

### Functions [lines 215-249]

Lifecycle: `EnablePortalManager`, `CreatePortal`, `CreateNewPortal`,
`PortalDefineQuery`, `PortalDrop`, `PortalHashTableDeleteAll`,
`GetPortalByName`.

Pin: `PinPortal` / `UnpinPortal` — pinned portals survive transaction
end via `HoldPinnedPortals`.

Lifecycle hooks per subxact: `AtSubCommit_Portals`,
`AtSubAbort_Portals`, `AtSubCleanup_Portals`; per top xact:
`PreCommit_Portals`, `AtAbort_Portals`, `AtCleanup_Portals`,
`PortalErrorCleanup`.

State markers: `MarkPortalActive`, `MarkPortalDone`,
`MarkPortalFailed`.

Holdable: `PortalCreateHoldStore`, `ThereAreNoReadyPortals`,
`ForgetPortalSnapshots`.

## Invariants

- **INV-SCROLL** [from-comment: lines 11-15] Scrolling and partial
  fetch only on single-SELECT portals — never on update-type queries
  (rewrites cannot reorder side effects).
- **INV-SNAPSHOT** [from-comment: lines 162-168] An active snapshot
  is held for "all but a few utility commands" to keep TOAST
  references in results detoastable.
- **INV-PINNED-DROP** [from-comment: line 151] A pinned portal
  cannot be dropped.
- **INV-HOLDSTORE-SNAPSHOT** [from-comment: lines 178-185] If
  `holdStore` may contain TOAST references, `holdSnapshot` must be
  registered to prevent vacuum from removing referenced toast data
  — *or* tuples must be force-detoasted (held-cursor path).
- **INV-RESOWNER** [verified-by-code: line 121] Each portal owns a
  `ResourceOwner` distinct from its caller's, so a portal's
  buffer/cache refs are released independently.

## Trust boundary (Phase D)

- `sourceText` is the **raw user-submitted SQL text** [line 136];
  surfaced in `pg_cursors`, `pg_stat_activity` (via copy to
  `st_activity_raw`), and error CONTEXT. Same password-in-query
  leak surface as `backend_status.h`.
- `portalParams` carries bound parameter Datums — these flow through
  to the SPI layer / plancache without serialization unless parallel
  workers are spawned (then `tqueue.h` serialization kicks in).
- Cross-role visibility: cursors are session-local — no cross-role
  leak surface here.

## Cross-refs

- `utils/plancache.h` — `CachedPlan` lifecycle.
- `executor/execdesc.h` — `QueryDesc`.
- `executor/spi.h` — SPI cursors call `SPI_cursor_open` which
  returns a Portal.
- `utils/resowner.h` — portal owns one.

## Issues

- [ISSUE-DOC: relationship between PortalSnapshot, holdSnapshot, and
  Active Snapshot Stack is documented across multiple comments;
  contributors regularly get this wrong (medium)] — lines 162-186.
- [ISSUE-API: no header-visible constant for the cursor option
  bitmask (`CURSOR_OPT_*`) — they live in `parsenodes.h` (low)] —
  line 147.
