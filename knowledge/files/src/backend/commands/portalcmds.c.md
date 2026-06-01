# portalcmds.c

- **Source path:** `source/src/backend/commands/portalcmds.c`
- **Lines:** 507
- **Last verified commit:** `ef6a95c7c64`

## Purpose

"Utility commands affecting portals (that is, SQL cursor commands). Note: see also tcop/pquery.c, which implements portal operations for the FE/BE protocol. This module uses pquery.c for some operations. And both modules depend on utils/mmgr/portalmem.c, which controls storage management for portals (but doesn't run any queries in them)." [from-comment, portalcmds.c:3-9]

## Public surface

- `PerformCursorOpen` — DECLARE CURSOR. Creates a portal, planned the query with cursor-friendly options (no parallel, hold-on-rewind, etc.), stores the plan in the portal.
- `PerformPortalFetch` — FETCH / MOVE; calls `PortalRunFetch` in pquery.c.
- `PerformPortalClose` — CLOSE.
- `PortalCleanup` — registered as the portal's cleanup callback; ends the executor, closes the snapshot, frees memory.
- `PersistHoldablePortal` — for WITH HOLD cursors: at commit time, materialise the entire remaining result into a tuplestore so the cursor survives the transaction boundary.

## Holdable cursors

A `DECLARE … CURSOR WITH HOLD` portal must outlive the declaring transaction. At commit, `PersistHoldablePortal` drains the executor into a tuplestore and detaches the portal from the snapshot. Subsequent FETCHes read from the tuplestore. This is the only PostgreSQL feature where executor state crosses a transaction boundary.

## Confidence tag tally

`[verified-by-code]=3 [from-comment]=2`
