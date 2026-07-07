# Snapshot acquisition — the GetSnapshot family

Snapshots define MVCC visibility — "which tuples can this
transaction see?" The snapshot-manager API offers half a dozen
"get a snapshot" entry points, each with a different lifetime
and isolation semantics. Picking the wrong one produces subtle
visibility bugs that pass dev tests and fail in production
under concurrency. This doc enumerates the entry points and
the rules for which to pick.

Anchors:
- `source/src/include/utils/snapmgr.h:77-97` — public API
  [verified-by-code]
- `source/src/backend/utils/time/snapmgr.c` — implementation
- `knowledge/data-structures/snapshot-lifecycle.md` —
  companion: the Snapshot struct itself

## The five entry points

```c
extern Snapshot GetTransactionSnapshot(void);
extern Snapshot GetLatestSnapshot(void);

extern void     PushActiveSnapshot(Snapshot snapshot);
extern void     PushActiveSnapshotWithLevel(Snapshot snapshot, int);
extern void     PopActiveSnapshot(void);
extern Snapshot GetActiveSnapshot(void);

extern Snapshot RegisterSnapshot(Snapshot snapshot);
extern void     UnregisterSnapshot(Snapshot snapshot);
extern Snapshot RegisterSnapshotOnOwner(Snapshot snapshot, ResourceOwner);
extern void     UnregisterSnapshotFromOwner(Snapshot snapshot, ResourceOwner);
```

[verified-by-code `snapmgr.h:77-97`]

Three orthogonal axes:

| Axis | Choice |
|---|---|
| **What snapshot** | `GetTransactionSnapshot` (xact-fixed) vs `GetLatestSnapshot` (statement-fresh) |
| **Visibility scope** | Push/Pop on the active-snapshot stack OR Register against a ResourceOwner |
| **Owner** | `CurrentResourceOwner` (default) OR explicit `ResourceOwnerXxx` |

## GetTransactionSnapshot vs GetLatestSnapshot

- **`GetTransactionSnapshot()`** — returns the snapshot for
  the current transaction. Under `READ COMMITTED`, this is the
  current statement's snapshot. Under `REPEATABLE READ` /
  `SERIALIZABLE`, this is the same snapshot for the whole
  transaction.
- **`GetLatestSnapshot()`** — returns a fresh snapshot of the
  current global state, regardless of isolation level. Used
  when a code path MUST see the latest committed state (e.g.
  a foreign-key trigger checking referential integrity).

The distinction matters at higher isolation levels: at
`REPEATABLE READ`, `GetTransactionSnapshot` returns the
xact-start snapshot, hiding committed changes. A code path
needing to see those changes must use `GetLatestSnapshot`.

## Active snapshot stack

`PushActiveSnapshot(snap)` / `PopActiveSnapshot()` manage a
stack of snapshots "currently in use by a code path." The top
of the stack is what `GetActiveSnapshot()` returns; this is
the snapshot used by most MVCC visibility checks during query
execution.

The pattern:

```c
Snapshot snap = GetTransactionSnapshot();
PushActiveSnapshot(snap);
PG_TRY();
{
    /* execute work using the pushed snapshot */
}
PG_FINALLY();
{
    PopActiveSnapshot();
}
PG_END_TRY();
```

The Push/Pop pairs MUST be balanced. An unbalanced pop is
detected at transaction commit.

`PushActiveSnapshotWithLevel(snap, level)` is for nested
PL/pgSQL contexts that want to track the procedural depth
explicitly; rare outside PL.

## Registered snapshots — the ResourceOwner pattern

```c
Snapshot snap = RegisterSnapshot(GetLatestSnapshot());
/* ... use the snapshot, even across transaction boundaries ... */
UnregisterSnapshot(snap);
```

Registered snapshots live until UnregisterSnapshot (or until
their ResourceOwner is released, whichever first). Used when
the snapshot must survive across a Push/Pop boundary —
typically for cursors that hold a snapshot across the cursor
lifetime even though the executor is invoked many times.

`RegisterSnapshotOnOwner(snap, owner)` lets the caller
specify a non-default ResourceOwner. Use when the snapshot
should outlive the current ResourceOwner (e.g. cursor that
lives until commit, but execution is per-statement).

## The "which entry point?" decision tree

1. **Need a snapshot for this statement's MVCC visibility?**
   → `GetTransactionSnapshot()` + `PushActiveSnapshot`.
2. **Need to see absolute latest committed state, regardless
   of isolation level?**
   → `GetLatestSnapshot()` + Push/Pop (or Register if
   long-lived).
3. **Need the snapshot to outlive the current Push/Pop
   region?**
   → `RegisterSnapshot()` to extend lifetime.
4. **Just need to inspect what's currently active?**
   → `GetActiveSnapshot()` (read-only).

## Snapshot xmin contribution

Every active or registered snapshot contributes its `xmin` to
the global `RecentXmin` horizon, which controls VACUUM. A
long-held registered snapshot is the canonical cause of
"VACUUM can't clean dead tuples" complaints.

The Unregister step releases the xmin contribution; cursors
held idle for hours produce stale-horizon bloat.

## Common review-time concerns

- **Long-held registered snapshots = VACUUM bloat.**
  Anything held past a single statement is a hazard. Cursors
  should `RegisterSnapshot` only if they actually need
  cursor-stability semantics.
- **Push without Pop = assertion at commit.** PG_FINALLY or
  PG_TRY+catch ensures Pop on error.
- **`GetLatestSnapshot` inside a serializable transaction**
  breaks serializability (you see committed state the
  isolation level says shouldn't be visible). Almost always
  wrong inside user-facing query execution.
- **Inside parallel workers**, snapshot is inherited from the
  leader. Workers must not acquire their own — that creates
  visibility divergence.
- **Snapshot manipulation inside an SRF state machine** —
  remember that SRFs run across multiple ExecProcNode calls;
  Push at the first call, Pop at terminator.

## Snapshot vs catalog snapshot

`GetCatalogSnapshot()` is a separate mechanism for system-
catalog reads. It uses a more aggressive freshness policy —
DDL must always see the latest catalog state. User SQL uses
the MVCC snapshot family above; catalog code paths use
`GetCatalogSnapshot`. Don't conflate.

## Invariants

- **[INV-1]** Push/Pop pairs MUST balance; unbalance is
  detected at xact commit.
- **[INV-2]** Registered snapshots contribute to global xmin;
  long lifetime delays VACUUM cleanup.
- **[INV-3]** `GetTransactionSnapshot` semantics differ by
  isolation level; `GetLatestSnapshot` doesn't.
- **[INV-4]** Parallel workers inherit the leader's snapshot;
  no per-worker acquisition.
- **[INV-5]** Catalog snapshots are separate; use
  `GetCatalogSnapshot` for catalog reads.

## Useful greps

- All snapshot acquisition sites:
  `grep -RIn 'GetTransactionSnapshot\|GetLatestSnapshot' source/src/backend | wc -l`
- Push/Pop usage:
  `grep -RIn 'PushActiveSnapshot\|PopActiveSnapshot' source/src/backend | head -20`
- Register/Unregister patterns:
  `grep -RIn 'RegisterSnapshot' source/src/backend | head -20`

## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/utils/time/snapmgr.c`](../files/src/backend/utils/time/snapmgr.c.md) | — | implementation |
| [`src/include/utils/snapmgr.h`](../files/src/include/utils/snapmgr.h.md) | 77 | public API |
| [`src/include/utils/snapmgr.h`](../files/src/include/utils/snapmgr.h.md) | — | public API |

<!-- /callsites:auto -->

## Scenarios that use me
<!-- scenarios:auto -->

*Auto-derived from direct references + transitive file-overlap.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

_(none detected — this idiom is either cross-cutting infrastructure or an internal helper pattern)_

<!-- /scenarios:auto -->
## Cross-references

- `knowledge/data-structures/snapshot-lifecycle.md` — the
  Snapshot struct's xmin/xmax/xip[] internals.
- `knowledge/data-structures/resourceowner.md` — Register*
  attaches to a ResourceOwner.
- `.claude/skills/catalog-conventions/SKILL.md` —
  `GetCatalogSnapshot` for catalog reads.
- `.claude/skills/locking/SKILL.md` — snapshot acquisition
  takes `ProcArrayLock`-share; one of the most contended
  LWLocks.
- `knowledge/idioms/lwlock-rank-discipline.md` —
  `ProcArrayLock` rank.
- `knowledge/idioms/predicate-locks.md` — SSI snapshot
  semantics layered on top of MVCC.
- `source/src/include/utils/snapmgr.h` — public API.
- `source/src/backend/utils/time/snapmgr.c` —
  implementation.
