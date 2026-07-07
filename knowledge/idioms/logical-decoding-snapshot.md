# Logical-decoding snapshot — historic-snapshot construction

Logical decoding reads WAL and produces a **stream of logical
changes** (INSERT / UPDATE / DELETE / COMMIT events) to be
consumed by an output plugin. To do so faithfully, it
reconstructs the **historic snapshot** — a snapshot AS IT
WOULD HAVE BEEN at each commit's moment — so the decoder can
resolve catalog OIDs to names, look up types, and properly
deform tuples. The `SnapBuild` machinery in
`replication/logical/snapbuild.c` is the state machine that
builds this snapshot from cold-start to fully-consistent.

Anchors:
- `source/src/backend/replication/logical/snapbuild.c:364` —
  SnapBuildBuildSnapshot [verified-by-code]
- `source/src/backend/replication/logical/snapbuild.c:444` —
  SnapBuildInitialSnapshot [verified-by-code]
- `source/src/backend/replication/logical/snapbuild.c:542` —
  SnapBuildExportSnapshot [verified-by-code]
- `knowledge/idioms/snapshot-acquisition.md` — companion
  (regular snapshot machinery)
- `knowledge/idioms/output-plugin-callbacks.md` — companion
  (consumes decoded changes)
- `knowledge/idioms/replication-slot-advance.md` — companion
  (slot's catalog_xmin protects this)
- `.claude/skills/replication-overview/SKILL.md` — companion

## The problem

A logical decoder must answer: "what does this WAL record
mean, as a SQL-level change?". To do that, it needs to look up
the catalog (pg_class, pg_attribute, pg_type, ...) as those
catalogs LOOKED at the time the WAL record was written.

A current snapshot wouldn't work: a column might have been
dropped or renamed since. Logical decoding needs the **historic
state** — which catalog tuples were visible at each point in
WAL.

The trick: use the same MVCC machinery the executor uses, but
build the snapshot from WAL records of past transactions, NOT
from currently-running ones.

## The SnapBuild state machine

[from-comment `snapbuild.c`]

Logical decoding starts a "snapshot building" state machine
that goes through 4 phases:

| State | Meaning |
|---|---|
| `SNAPBUILD_START` | Nothing seen yet; can't decode catalog. |
| `SNAPBUILD_BUILDING_SNAPSHOT` | Saw a running-xacts WAL record; gathering xids. |
| `SNAPBUILD_FULL_SNAPSHOT` | All running xids finished; can decode catalogs in this xact. |
| `SNAPBUILD_CONSISTENT` | Old running xids all finished; can decode arbitrary historic xacts. |

Transitions:
- START → BUILDING: see XLOG_RUNNING_XACTS.
- BUILDING → FULL: all xids from that record finished.
- FULL → CONSISTENT: all xids that were running at decoding
  start have finished.

Once CONSISTENT, decoded changes can be emitted.

## SnapBuildBuildSnapshot — assembling a historic snapshot

[verified-by-code `snapbuild.c:364`]

```c
static Snapshot SnapBuildBuildSnapshot(SnapBuild *builder);
```

Constructs a Snapshot struct that reflects the catalog state
as of `builder->xmin`:
- `xmin`, `xmax` — the historic snapshot's bounds.
- `xip` array — xids that were in-progress (and thus invisible).
- `subxip` — subtransactions.
- `snapshot_type = SNAPSHOT_HISTORIC_MVCC` — the executor's
  visibility tests will use historic rules.

The historic snapshot is then pushed onto the snapshot stack
via `PushActiveSnapshot`; subsequent catalog accesses
(`SearchSysCache*` etc.) consult it.

## SnapBuildInitialSnapshot — for the slot's initial export

[verified-by-code `snapbuild.c:444`]

```c
Snapshot SnapBuildInitialSnapshot(SnapBuild *builder);
```

When a CREATE_REPLICATION_SLOT command issues `CREATE
PUBLICATION ... WITH (SNAPSHOT='use')`, the client gets back a
snapshot ID that the next backend session can `SET TRANSACTION
SNAPSHOT` to.

`SnapBuildInitialSnapshot` constructs the snapshot AT the slot
creation point. The client uses it to initial-sync the
replica's data exactly matching the WAL stream that the
publisher will deliver.

## SnapBuildExportSnapshot — exposing it to other sessions

[verified-by-code `snapbuild.c:542`]

```c
const char *SnapBuildExportSnapshot(SnapBuild *builder);
```

Returns a snapshot ID string that other backends can use via
`SET TRANSACTION SNAPSHOT 'id'`. The snapshot is held by the
publishing backend for the duration; the subscriber must
acquire and use it before the publisher releases.

This is the snapshot-export-import pattern adapted for logical
replication: the subscriber's COPY can see exactly the data the
publisher saw at the slot creation point.

## The catalog_xmin guard

[per `replication-slot-advance` companion]

The slot's `catalog_xmin` is the **oldest xid whose catalog
modifications the decoder still needs**. While the slot is
active, no autovacuum can clean up older catalog tuples — the
decoder might still need them to reconstruct historic state.

This is why a slow / abandoned slot can block xid wraparound
prevention: `catalog_xmin` is pinned, vacuum can't advance.

## How decoded changes use the snapshot

[from `decode.c` flow]

1. WAL reader pulls a record.
2. SnapBuild updates state (xact begin / commit / etc.).
3. For an INSERT/UPDATE/DELETE record at commit time:
   - Push the historic snapshot.
   - For each tuple in the change:
     - Decode tuple data using current catalog state (which
       respects the historic snapshot).
     - Call the output plugin's `change_cb`.
   - Pop the snapshot.

The catalog access during decode is read-only via SysCache.
Modifications are forbidden during decoding (would break the
ordering invariant).

## On-disk persistence

The SnapBuild state can be **persisted to disk** between
walsender restarts via the `pg_logical/snapshots/` directory.
This lets a slot resume decoding without re-traversing all of
WAL.

Format: serialized SnapBuild struct + the xid arrays;
re-loaded on walsender startup.

## Common review-time concerns

- **catalog_xmin pin** — blocks vacuum on slow slots.
- **Historic snapshot stack** — must push/pop symmetrically.
- **Catalog reads only** during decode; writes forbidden.
- **State machine sequence** — START → BUILDING → FULL →
  CONSISTENT; can't skip.
- **Persisted state** — restart-resumable; obsolete state
  files cleaned by `pg_logical/snapshots/` mgmt.
- **Slot-creation snapshot** for initial sync — narrow window
  between publisher's CREATE_REPLICATION_SLOT and
  subscriber's COPY.

## Invariants

- **[INV-1]** Snapshot reflects catalog state at the WAL
  record's commit time.
- **[INV-2]** State transitions: START → BUILDING → FULL →
  CONSISTENT.
- **[INV-3]** catalog_xmin pinned on slot; protects historic
  catalog tuples.
- **[INV-4]** Output plugin sees changes ONLY in CONSISTENT
  state.
- **[INV-5]** Historic snapshot is SNAPSHOT_HISTORIC_MVCC
  type.

## Useful greps

- The state machine:
  `grep -n 'SnapBuildCurrentState\|SNAPBUILD_' source/src/backend/replication/logical/snapbuild.c | head -10`
- Build + export:
  `grep -n 'SnapBuildBuildSnapshot\|SnapBuildExportSnapshot\|SnapBuildInitialSnapshot' source/src/backend/replication/logical/snapbuild.c | head -5`
- Historic visibility:
  `grep -RIn 'SNAPSHOT_HISTORIC_MVCC\|HistoricMVCC' source/src/backend | head -10`

## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/replication/logical/snapbuild.c`](../files/src/backend/replication/logical/snapbuild.c.md) | 364 | SnapBuildBuildSnapshot |
| [`src/backend/replication/logical/snapbuild.c`](../files/src/backend/replication/logical/snapbuild.c.md) | 444 | SnapBuildInitialSnapshot |
| [`src/backend/replication/logical/snapbuild.c`](../files/src/backend/replication/logical/snapbuild.c.md) | 542 | SnapBuildExportSnapshot |
| [`src/backend/replication/logical/snapbuild.c`](../files/src/backend/replication/logical/snapbuild.c.md) | — | full module |

<!-- /callsites:auto -->

## Scenarios that use me
<!-- scenarios:auto -->

*Auto-derived from direct references + transitive file-overlap.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

- [`add-new-replication-message`](../scenarios/add-new-replication-message.md)

<!-- /scenarios:auto -->
## Cross-references

- `knowledge/idioms/snapshot-acquisition.md` — regular
  snapshot machinery this builds on top of.
- `knowledge/idioms/output-plugin-callbacks.md` — consumer
  of decoded changes.
- `knowledge/idioms/replication-slot-advance.md` —
  catalog_xmin pinning.
- `knowledge/idioms/walsender-state-machine.md` — walsender
  that runs the decoder.
- `knowledge/idioms/xmin-horizon-management.md` —
  catalog_xmin participates in horizon calculations.
- `knowledge/data-structures/snapshot-lifecycle.md` —
  Snapshot struct.
- `knowledge/subsystems/replication.md` — replication
  subsystem.
- `.claude/skills/replication-overview/SKILL.md` —
  companion.
- `source/src/backend/replication/logical/snapbuild.c` —
  full module.
