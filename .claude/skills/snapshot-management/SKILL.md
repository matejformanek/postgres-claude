---
name: snapshot-management
description: PostgreSQL's MVCC snapshot infrastructure — `src/backend/utils/time/snapmgr.c` — `GetTransactionSnapshot` / `GetLatestSnapshot` / `PushActiveSnapshot` / `RegisterSnapshot` and the tuple-visibility machinery in `heapam_visibility.c`. Covers the ActiveSnapshot stack, RegisteredSnapshots heap, snapshot export for parallel workers, historic snapshots for logical decoding, and the interaction with xmin horizon. Loads when the user asks about `Snapshot` semantics, MVCC visibility (`HeapTupleSatisfiesMVCC`), catalog snapshots vs transaction snapshots, isolation levels, exported snapshots for pg_dump, or `SET LOCAL transaction_isolation`. Skip when the ask is about xact.c commit/abort mechanics or about xid horizons for freezing (see `vacuum-autovacuum`).
when_to_load: Debug snapshot leaks; understand isolation-level snapshot behavior; touch snapshot registration/export for parallel workers or logical decoding; investigate "why is this row visible/invisible" bugs.
companion_skills:
  - vacuum-autovacuum
  - locking
  - resource-owners
---

# snapshot-management — MVCC snapshots + tuple visibility

Every SQL statement running under MVCC needs a snapshot: a fixed view of what transactions have committed (visible) and what's still in-flight or aborted (invisible). Snapshots are cheap to acquire but must be kept alive precisely as long as they're needed — else the xmin horizon advances, dead tuples get vacuumed, and a still-alive snapshot may crash trying to read them.

## The file map

| File | KB | Role |
|---|---:|---|
| `utils/time/snapmgr.c` | 60 | The manager. GetSnapshot family, ActiveSnapshot stack, RegisteredSnapshots heap, exported snapshots, historic snapshots. |
| `utils/time/combocid.c` | 10 | Combo CommandId support — when a tuple is both inserted and deleted by different subtransactions of the same top transaction, you need a combo cid. |
| `access/heap/heapam_visibility.c` | ~ | The `HeapTupleSatisfies*` family — visibility check given tuple + snapshot. |
| `include/access/xact.h` | — | XID / CommandId types + globals like `TransactionXmin`. |
| `include/utils/snapshot.h` | — | The `SnapshotData` struct. |

## The Snapshot struct (fields that matter)

```c
typedef struct SnapshotData {
    SnapshotType snapshot_type;   /* MVCC, HISTORIC, DIRTY, ANY, NONSTALE, ... */

    TransactionId xmin;           /* xids >= this MIGHT be in-flight */
    TransactionId xmax;           /* xids >= this are definitely not visible */
    TransactionId *xip;           /* array of in-flight XIDs */
    uint32 xcnt;                  /* length of xip[] */

    TransactionId *subxip;        /* in-flight subxids */
    int32 subxcnt;

    bool suboverflowed;           /* subxact array overflowed */
    bool takenDuringRecovery;     /* on a standby */

    CommandId curcid;             /* current command within this txn */
    uint32 speculativeToken;      /* speculative INSERT machinery */

    ResourceOwner regd_count;     /* refcount if registered */
    uint32 active_count;          /* refcount from active stack */
    ...
} SnapshotData;
```

`xmin` + `xmax` + `xip[]` define the visibility rule:
- xid < xmin → committed AND visible.
- xid >= xmax → not visible (later than snapshot).
- xmin ≤ xid < xmax → visible iff NOT in xip[] (in-flight at snapshot time).

## The Snapshot lifecycle

Snapshots are managed via THREE stacks/heaps:

1. **ActiveSnapshot stack** — the "current" snapshot for statement execution. `PushActiveSnapshot` at statement start, `PopActiveSnapshot` at end. Refcount here.
2. **RegisteredSnapshots heap** — for snapshots needed longer than a single statement (cursors, exported snapshots, portal snapshots). `RegisterSnapshot` / `UnregisterSnapshot` for refcounting.
3. **Historic snapshots** — for logical decoding replay. Built by `snapbuild.c` state machine (see `logical-replication` skill).

## Isolation levels — what snapshot?

| Isolation | Snapshot policy |
|---|---|
| `READ UNCOMMITTED` | Same as READ COMMITTED (PG treats these equivalently). |
| `READ COMMITTED` (default) | New snapshot at start of EACH statement. |
| `REPEATABLE READ` | Single snapshot at first statement, held for the whole transaction. |
| `SERIALIZABLE` | Same as REPEATABLE READ + SSI predicate-lock tracking (`predicate-locks` idiom). |

The `SET transaction_isolation` command determines the acquisition pattern.

## Snapshot export

For pg_dump's `--snapshot` flag and other multi-connection consistency needs:

- `pg_export_snapshot()` returns a text handle.
- Another connection can `SET TRANSACTION SNAPSHOT '<handle>'` to see the same snapshot.
- The exporting transaction must remain alive until all importers finish.

## Historic snapshots (logical decoding)

Logical decoding needs to see the catalog as of a specific LSN, not the current time. `snapbuild.c` builds a snapshot with `snapshot_type = SNAPSHOT_HISTORIC_MVCC` — its xmin/xmax reflect the past, filtered through pg_class snapshots that were live at decoding time.

Historic snapshots are ONLY valid for catalog access; user table access under a historic snapshot is a coding error.

## The visibility gauntlet

`HeapTupleSatisfiesMVCC(tup, snapshot)` runs:

1. Check `HEAP_XMIN_INVALID` hint — early no.
2. If `HEAP_XMIN_COMMITTED`: check `xmin < snapshot->xmin` for fast-yes; else check `TransactionIdIsCurrentTransactionId(xmin)` for own-txn visibility; else check against `xip[]`.
3. If not marked: consult CLOG (via `TransactionIdDidCommit` etc.) + potentially set hint bit.
4. Then similar dance for `xmax` — is the tuple deleted?
5. Consider inserting subtransaction (`combocid` complications).

The gauntlet is called from every heap scan, every index-fetch, every visibility-map decision. Its performance depends critically on hint bits (see `hint-bits-setbufferdirty` idiom).

## Common patch shapes

### Register a snapshot for a long-lived caller

- `RegisterSnapshot(snap)` — bumps refcount, ties to CurrentResourceOwner.
- Use snapshot for whatever purpose.
- `UnregisterSnapshot(snap)` at end.
- If you exit via ereport(ERROR), the ResourceOwner cleanup handles it.

### Add a new snapshot type

Very rare — `SnapshotType` enum has: MVCC / HISTORIC / DIRTY / NONVACUUMABLE / ANY / TOAST / SELF / NONMVCC. Adding one requires:
- Enum extension.
- New `HeapTupleSatisfies*` function.
- Wire into `HeapTupleSatisfies` dispatch.
- Rare — most needs are covered by existing types.

### Debug "row visibility surprises"

- `HeapTupleSatisfiesMVCC` decision path — set breakpoint.
- Check for combocid: was the tuple modified by a subtxn that later rolled back?
- Check snapshot xmin/xmax/xip against tuple xmin/xmax.
- Under READ COMMITTED, each SELECT gets a fresh snapshot — check timing.

### Export a snapshot to a parallel worker

- `pg_export_snapshot` on leader.
- Workers use `SetTransactionSnapshot` to import.
- Workers inherit the same view of the world.
- The Parallel Query machinery does this automatically for you — usually.

## Pitfalls

- **Snapshot leaks are silent** — a Register without Unregister is not warned. The snapshot stays alive, its xmin holds catalog_xmin, vacuum doesn't clean up.
- **Historic snapshots aren't user-table safe** — using one on a user table is undefined behavior. Only catalog access is validated.
- **`RegisterSnapshot(GetTransactionSnapshot())` vs pushed** — pushing and registering are different mechanisms; the API distinguishes but callers sometimes muddle.
- **`suboverflowed` snapshots are slower** — the subxact array has a fixed size (`PGPROC_MAX_CACHED_SUBXIDS = 64`). Above that, snapshots consult pg_subtrans SLRU per lookup.
- **`TransactionXmin` (global) vs snapshot->xmin** — global is the OLDEST live xmin cluster-wide; a local snapshot's xmin is per-that-snapshot. Don't confuse.
- **Hint bits are perf-critical** — a table where hint bits keep getting cleared (frequent CLOG-hit-on-miss) causes visibility to be much slower.
- **Catalog snapshots vs transaction snapshots** — some code paths use `GetCatalogSnapshot()` — a special always-fresh snapshot for catalog access. Don't confuse with your transaction snapshot.
- **Speculative insert token** — `INSERT ... ON CONFLICT DO NOTHING` uses `SpeculativeInsertion` to reserve a xid before determining commit/abort. Interacts with visibility in subtle ways.
- **`SnapshotAny` sees EVERYTHING including in-flight** — used by system tools like `pg_visibility`. Not for user queries.
- **Combocid on a Subtxn rollback** — a tuple inserted in subtxn A, deleted in subtxn B, where A rolls back after B commits → weird combocid state.

## Related corpus

- **Idioms** (many hits): `snapshot-acquisition`, `snapshot-active-stack-and-registered`, `snapshot-export-historic-parallel`, `snapshot-static-and-current`, `heap-tuple-visibility-mvcc`, `combocid-handling`, `logical-decoding-snapshot`, `predicate-locks`, `xmin-horizon-management`.
- **Subsystems**: `access-heap` (visibility check callers), `access-transam` (xid/subxid machinery).
- **Data structures**: `snapshot-lifecycle` (the SnapshotData struct + refcounting rules).

## Corpus-chain shortcut

```
python3 scripts/corpus-chain.py --file src/backend/utils/time/snapmgr.c
python3 scripts/corpus-chain.py --idiom snapshot-active-stack-and-registered
```

## Boundary

**Use this skill** for snapshot management + visibility + isolation-level snapshot policy.

**Don't use** for:
- **xact.c commit/abort** — different concern; see `access-transam` subsystem.
- **Locks** — different from visibility. See `locking`.
- **VACUUM's use of GlobalVisState** — related but consumer-side; see `vacuum-autovacuum`.
- **Predicate locks for SSI** — sibling concern; see `predicate-locks` idiom.
- **Logical decoding snapbuild** — historic-snapshot builder; see `logical-decoding-snapshot` idiom.
