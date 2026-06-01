# `src/backend/utils/mmgr/portalmem.c`

- **File:** `source/src/backend/utils/mmgr/portalmem.c` (1295 lines)
- **Last verified commit:** `ef6a95c7c64de07dff4dd1f1da88ffae7b086ef3` (2026-06-01)

## Purpose

Backend-local portal lifecycle + per-portal memory contexts. A
**portal** is the execution-state object behind every cursor, every
extended-protocol named statement, and every implicit container for an
in-progress simple query. This file owns the portal-name hash table,
the `TopPortalContext` AllocSet (parent of every portal's private
context), the `PORTAL_NEW → DEFINED → READY → ACTIVE → DONE|FAILED`
state machine, and the at-(sub)commit / at-(sub)abort / at-cleanup
hooks the transaction machinery calls during commit/rollback. It does
**not** run the executor; that's `pquery.c` / `portalcmds.c`.

## Top-of-file comment (verbatim)

```
Portals are objects representing the execution state of a query.
This module provides memory management services for portals, but it
doesn't actually run the executor for them.
```
(`portalmem.c:5-8` [from-comment])

## Public surface

Creation / lookup:
- `EnablePortalManager()` (`:106`) — backend startup; creates
  `TopPortalContext` as a child of `TopMemoryContext` with
  `ALLOCSET_DEFAULT_SIZES` and the portal-name `HTAB`.
- `GetPortalByName(name)` (`:132`).
- `CreatePortal(name, allowDup, dupSilent)` (`:177`).
- `CreateNewPortal()` (`:237`) — synthesizes `<unnamed portal N>`.
- `PortalDefineQuery(...)` (`:284`).
- `PortalCreateHoldStore(portal)` (`:332`) — creates `holdContext`
  (a *sibling* of the portal context, child of `TopPortalContext`,
  so a cursor's tuplestore can outlive the portal's main context
  during HOLD).

Pinning / state:
- `PinPortal` / `UnpinPortal` (`:372, 381`).
- `MarkPortalActive` / `MarkPortalDone` / `MarkPortalFailed`
  (`:396, 415, 443`).

Teardown:
- `PortalDrop(portal, isTopCommit)` (`:469`).
- `PortalHashTableDeleteAll()` (`:608`).

Transaction hooks (called from `xact.c`):
- `PreCommit_Portals(isPrepare)` (`:678`) — handles holdable cursors,
  refuses to commit if there's a non-pinned non-holdable open portal,
  etc.
- `AtAbort_Portals()` (`:782`).
- `AtCleanup_Portals()` (`:860`).
- `PortalErrorCleanup()` (`:919`).
- `AtSubCommit_Portals(mySubid, parentSubid, parentXactOwner, ...)`
  (`:945`).
- `AtSubAbort_Portals(mySubid, ...)` (`:981`).
- `AtSubCleanup_Portals(mySubid)` (`:1094`).
- `ThereAreNoReadyPortals()` (`:1173`).
- `HoldPinnedPortals()` (`:1209`).
- `ForgetPortalSnapshots()` (`:1258`).

System view:
- `pg_cursor(PG_FUNCTION_ARGS)` (`:1133`) — the SRF that backs
  `pg_catalog.pg_cursors`.

## Key data structures

- `Portal` (defined in `utils/portal.h`) — large struct with `name`,
  `prepStmtName`, `sourceText`, `commandTag`, `stmts`, `cplan`
  (cached plan refcount, released in `PortalReleaseCachedPlan`),
  `portalContext` (an AllocSet child of `TopPortalContext`),
  `holdContext`, `holdStore`, `holdSnapshot`, `portalSnapshot`,
  `resowner`, `cleanup` hook, `status`, `portalPinned`, `activeSubid`,
  etc. [from-comment, declared in header].
- `PortalHashEnt` (`:50-54`) — hash entry: 64-char portal name +
  `Portal` pointer. Hash table is `PortalHashTable` (`:56`).
- `TopPortalContext` static (`:93`) — single backend-wide AllocSet
  parent of every portal's `portalContext` *and* every `holdContext`.

## Key invariants

- **Status transitions go through the marker functions, never direct
  assignment.** Each function comment says so explicitly
  (`:393, 412, 440` [from-comment]). `MarkPortalActive` records the
  current subtransaction in `activeSubid`, which is what
  `AtSubAbort_Portals` uses to decide which portals to kill.
- **A holdable cursor's `holdContext` is NOT a child of the portal's
  `portalContext`** — it's a sibling under `TopPortalContext`
  (`:340-347` [from-comment]). This is intentional: on PortalDrop the
  portal context goes away but the holdContext (containing the
  materialized tuplestore) lives on until the cursor is closed.
- **`PortalDrop` is single-pass and idempotent under abort retry.**
  The hash-table delete happens early (`:516`) so a failed cleanup
  step won't put the dropper into an infinite retry loop —
  "Better to leak a little memory than to get into an infinite
  error-recovery loop" (`:511-515` [from-comment]).
- **Pinned portals are protected from drop** but *not* from
  transaction-abort cleanup — `AtAbort_Portals` will unpin and kill
  them (`:368-370` [from-comment]).
- **`PortalDefineQuery` must not ereport.** If it failed before
  storing `cplan`, the plancache refcount the caller incremented
  would leak (`:278-282` [from-comment]).
- **Cached-plan refcount handoff** is the most subtle ownership
  contract: caller did `GetCachedPlan` (incrementing the refcount),
  passes the resulting `CachedPlan*` to `PortalDefineQuery`,
  ownership transfers to portal, refcount released by
  `PortalReleaseCachedPlan` inside `PortalDrop` (`:265-269, 307-325`).

## Functions of note

1. **`EnablePortalManager` (`:106-128`)** — wires the parent context
   and the hash table at backend start. `PORTALS_PER_USER = 16` sized
   initial capacity (the hash can grow); kept small intentionally so
   `hash_seq_search` calls during transaction end stay cheap
   (`:34-39` [from-comment]).

2. **`PortalCreateHoldStore` (`:332-362`)** — creates the holdable-
   cursor materialization context. `tuplestore_begin_heap` is called
   with `interXact=true` so files survive transaction end.

3. **`PortalDrop` (`:469+`)** — full teardown: refuses if pinned or
   ACTIVE, runs the cleanup hook (executor shutdown if still
   active), deletes from hash, releases cached plan, unregisters
   `holdSnapshot` from the portal's resowner, then deletes
   `portalContext` (via `MemoryContextDelete` — recursive over any
   child contexts the portal accumulated). `holdContext` is
   independently deleted only when the cursor is closed / the
   transaction holding it commits.

4. **`PreCommit_Portals` (`:678+`)** — walks all portals: holdable
   cursors are persisted (their state moved to inter-xact-safe
   storage), non-holdable open portals at COMMIT time are dropped;
   `PrepareTransaction` flow refuses to commit if any portal exists
   that can't be persisted. This is the path that converts an open
   `DECLARE CURSOR ... WITH HOLD` into a holdStore-backed dataset
   that survives the transaction.

5. **`AtAbort_Portals` (`:782+`) / `AtCleanup_Portals` (`:860+`)** —
   the two-phase abort. `AtAbort_Portals` marks all portals failed,
   runs their cleanup hooks (which talk to the executor — these can
   ereport). `AtCleanup_Portals` runs after the resource owner is
   torn down and actually drops the portals (which can no longer
   ereport because contexts are deleted in known-safe order).

6. **`AtSubAbort_Portals` (`:981+`)** — portals created in (or that
   became ACTIVE in) the aborted subtransaction get killed/unpinned;
   their `activeSubid` and `createSubid` decide what to do. Portals
   that *executed* in the aborted subxact have their state forced
   to FAILED so they can't be re-run.

7. **`pg_cursor` (`:1133+`)** — SRF returning all portals for the
   `pg_cursors` view: name, statement, is_holdable, is_binary,
   is_scrollable, creation_time.

## Cross-references

- `source/src/include/utils/portal.h` — `Portal` struct definition.
- `source/src/backend/tcop/pquery.c` — runs portals.
- `source/src/backend/commands/portalcmds.c` — `DECLARE CURSOR`,
  `FETCH`, `CLOSE`; portal cleanup hook implementation.
- `source/src/backend/access/transam/xact.c` — calls
  `PreCommit_Portals` / `AtAbort_Portals` / `AtCleanup_Portals` /
  `AtSubCommit_Portals` / `AtSubAbort_Portals` / `AtSubCleanup_Portals`.
- `source/src/backend/utils/cache/plancache.c` — cached-plan ref
  counting that portals participate in.
- `mcxt.c` — `TopPortalContext` is a normal AllocSet child of
  `TopMemoryContext`. `PortalContext` (in `memutils.h`/`mcxt.c`) is
  a *global pointer to the currently-active portal's* portalContext;
  not the same as `TopPortalContext`.

## Open questions

- The exact sequencing of `PortalCleanup` ↔ `PortalDrop` when a
  cursor's executor errors out mid-fetch is non-trivial; the comment
  on `PortalDrop` (`:498-505`) hints that `cleanup` may have already
  run via `MarkPortalFailed` and needs to be a one-shot. I haven't
  traced every code path in `portalcmds.c` here [unverified].
- `holdSnapshot` registration/unregistration is delicate w.r.t.
  failed transactions — the abort path may already have torn down
  the resowner and released the snapshot (`:522-533` [from-comment]).
  Worth a careful read if you're touching snapshot lifetime.

## Confidence tag tally

- `[verified-by-code]` × ~10
- `[from-comment]` × ~8
- `[unverified]` × 2

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/utils-mmgr.md](../../../../../subsystems/utils-mmgr.md)
