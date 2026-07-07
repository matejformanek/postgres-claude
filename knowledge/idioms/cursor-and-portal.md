# Cursors and Portals — the PortalData lifecycle

A **Portal** in PG is the in-memory representation of an
executing query — the bridge between parsed SQL and ongoing
execution that pulls results lazily. SQL `DECLARE CURSOR`
creates one; client protocol's "extended query" also uses
them (named or unnamed). The PortalData struct + the 4-phase
lifecycle (CreatePortal → PortalStart → PortalRun →
PortalDrop) are the executor's primary interface for
user-driven query execution.

Anchors:
- `source/src/include/utils/portal.h:107-113, 115` —
  states + struct [verified-by-code]
- `source/src/backend/utils/mmgr/portalmem.c` —
  implementation
- `knowledge/subsystems/tcop.md` — surrounding system
- `knowledge/data-structures/tupletableslot.md` — slots
  carry results

## The 5 portal states

[verified-by-code `portal.h:107-108`]

```c
typedef enum
{
    PORTAL_NEW,       /* freshly created */
    PORTAL_DEFINED,   /* parse / plan complete */
    PORTAL_READY,     /* PortalStart complete, can run */
    PORTAL_ACTIVE,    /* portal is running */
    PORTAL_DONE,      /* exhausted */
    PORTAL_FAILED,    /* error during run */
} PortalStatus;
```

The state machine:

```
NEW → DEFINED → READY → ACTIVE → DONE
                          ↓
                       FAILED (on error)
```

## CreatePortal — the new-empty state

```c
extern Portal CreatePortal(const char *name, bool allowDup,
                           bool dupSilent);
```

[verified-by-code `portal.h:229`]

- **`name`** — portal identifier. Empty string `""` means
  "unnamed" (default).
- **`allowDup`** — replace any existing portal with this
  name?
- **`dupSilent`** — silently replace (no NOTICE)?

The portal is allocated in `PortalMemory` — a long-lived
context that survives backend operations.

## PortalDefineQuery + PortalStart

The portal's plan and state get populated:

```c
PortalDefineQuery(portal, prepStmtName, sourceText,
                  commandTag, plansource, plan);
PortalStart(portal, params, eflags, snapshot);
```

After PortalStart, the portal is READY: the executor is
initialized but no tuples have been pulled.

## PortalRun — pulling results

```c
bool PortalRun(Portal portal, long count, bool isTopLevel,
               DestReceiver *dest, ...);
```

Pulls `count` rows (or remaining; 0 = all) into the
`DestReceiver`. The portal transitions ACTIVE → DONE on
exhaustion, ACTIVE → READY if more rows remain.

Cursors use small counts to fetch row-by-row:

```sql
DECLARE c CURSOR FOR SELECT ...;
FETCH 100 FROM c;   -- PortalRun with count=100
FETCH 100 FROM c;   -- another PortalRun
```

## PortalDrop — explicit cleanup

```c
extern void PortalDrop(Portal portal, bool isTopCommit);
```

[verified-by-code `portal.h:236`]

Closes the portal: releases the executor state, drops
buffer pins, drops snapshot if held, removes from the
portal registry.

Implicit drops happen:
- At end of transaction for non-WITH-HOLD cursors.
- At backend exit.
- On error (failed portals get dropped).

## WITH HOLD — portals across transactions

Normally, a portal exists only within its declaring
transaction. `DECLARE c CURSOR WITH HOLD FOR ...` creates a
**holdable** portal:

1. Define + start as usual.
2. At commit, **materialize the entire result** into a
   tuplestore.
3. The portal stays open; subsequent FETCHes pull from the
   tuplestore.
4. The underlying executor state is freed.

Holdable cursors trade memory (the materialized
tuplestore) for cross-transaction persistence.

## Named vs unnamed portals

Each connection has:
- The **unnamed portal** (`""`) — used by `psql`'s
  simple queries and the extended protocol's default.
- Many **named portals** — created by `DECLARE CURSOR`,
  prepared statements, etc.

The unnamed portal is auto-replaced on each new query.
Named portals must be explicitly dropped.

## The extended protocol's portal usage

[from `tcop.md`]

The frontend/backend protocol's extended-query path:

1. **Parse** — produce a prepared statement.
2. **Bind** — bind a portal to the statement + parameters.
3. **Execute** — pull rows from the portal.
4. **Close** — drop the portal.

So named portals are how protocol-level query state is
managed.

## Snapshot semantics

Portals can carry their own snapshot (passed to
PortalStart). This is how `DECLARE ... CURSOR WITHOUT HOLD`
gives consistent results across multiple FETCHes — the
snapshot pins the visibility horizon.

For WITH HOLD, the snapshot is released at commit; the
materialized tuplestore preserves the data.

## ResourceOwner integration

Each portal owns a ResourceOwner that tracks buffers,
snapshots, and other resources acquired during execution.
PortalDrop releases the ResourceOwner, freeing everything.

This is how portals are leak-safe: errors during query
execution trigger the longjmp, the longjmp's cleanup
includes the portal's ResourceOwner, which releases all
held resources.

## Common review-time concerns

- **Don't reuse a portal name** without explicit drop +
  recreate; use `allowDup = true` if needed.
- **WITH HOLD memory** — materialization can OOM on
  large result sets. Set `cursor_tuple_fraction` to hint.
- **Cross-transaction cursor access** requires WITH HOLD;
  ordinary cursors are torn down at commit.
- **Snapshot in held cursors** is released at commit; the
  data is what's frozen.
- **PortalDrop is reentrant-safe** — fine to call on an
  already-failed portal.

## Invariants

- **[INV-1]** Portal state machine: NEW → DEFINED → READY
  → ACTIVE → DONE / FAILED.
- **[INV-2]** WITH HOLD materializes at commit; ordinary
  cursors don't.
- **[INV-3]** Unnamed portal auto-replaced on each new
  query.
- **[INV-4]** Per-portal ResourceOwner is leak-safety.
- **[INV-5]** PortalDrop is the explicit cleanup
  endpoint; idempotent.

## Useful greps

- The lifecycle functions:
  `grep -n 'CreatePortal\|PortalDefineQuery\|PortalStart\|PortalRun\|PortalDrop' source/src/backend/utils/mmgr/portalmem.c | head -10`
- State transitions:
  `grep -n 'PortalStatus\|PORTAL_READY\|PORTAL_ACTIVE\|PORTAL_DONE' source/src/include/utils/portal.h`
- WITH HOLD materialization:
  `grep -RIn 'HoldablePortal\|PersistHoldablePortal' source/src/backend | head -5`



## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/utils/mmgr/portalmem.c`](../files/src/backend/utils/mmgr/portalmem.c.md) | — | implementation |
| [`src/include/utils/portal.h`](../files/src/include/utils/portal.md) | 107 | 115 — states + struct |
| [`src/include/utils/portal.h`](../files/src/include/utils/portal.md) | — | public API |

<!-- /callsites:auto -->



## Scenarios that use me
<!-- scenarios:auto -->

*Auto-derived from direct references + transitive file-overlap.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

_(none detected — this idiom is either cross-cutting infrastructure or an internal helper pattern)_

<!-- /scenarios:auto -->

## Cross-references

- `knowledge/subsystems/tcop.md` — the surrounding
  traffic-cop layer.
- `knowledge/data-structures/tupletableslot.md` — slots
  carry portal-produced rows.
- `knowledge/data-structures/resourceowner.md` — per-portal
  ResourceOwner tracks resources.
- `knowledge/idioms/snapshot-acquisition.md` — portal
  snapshots register against ResourceOwner.
- `.claude/skills/executor-and-planner/SKILL.md` —
  the executor PortalRun drives.
- `source/src/include/utils/portal.h` — public API.
- `source/src/backend/utils/mmgr/portalmem.c` —
  implementation.
