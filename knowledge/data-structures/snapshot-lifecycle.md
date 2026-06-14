# Snapshot — lifecycle and visibility semantics

- **Source path:** `source/src/backend/utils/time/snapmgr.c`, `combocid.c`
- **Header:** `source/src/include/utils/snapmgr.h`, `snapshot.h`
- **Last verified commit:** `e18b0cb7344`
- **Companion docs:** `knowledge/files/src/backend/utils/time/snapmgr.c.md`,
  `knowledge/idioms/error-handling.md` (snapshot ↔ ERROR cleanup),
  `knowledge/architecture/mvcc.md`

## 1. What a Snapshot is

A `SnapshotData` is the read-side view of which transactions are committed
at the moment the snapshot is taken. It does NOT contain the rows that are
visible — it contains the *predicate* for deciding visibility one row at a
time when those rows are read.

```c
typedef struct SnapshotData {
    SnapshotType snapshot_type;     // MVCC, SELF, ANY, TOAST, DIRTY, HISTORIC_MVCC, NONITEMPOTENT
    TransactionId xmin;             // earliest xid still potentially in progress
    TransactionId xmax;             // first xid NOT yet seen — all >= xmax are "future"
    TransactionId *xip;             // in-progress xids in [xmin, xmax)
    uint32 xcnt;                    // length of xip
    TransactionId *subxip;          // sub-transaction xids (for committed subxacts)
    int32 subxcnt;
    bool suboverflowed;             // procarray overflowed; treat all subxacts as in-progress
    bool takenDuringRecovery;       // built from xl_running_xacts during recovery
    bool copied;
    CommandId curcid;               // for SELF, the command id boundary
    uint32 speculativeToken;
    XLogRecPtr lsn;                 // for historic MVCC (logical decoding)
    TimestampTz whenTaken;
    ...
} SnapshotData;
```

[verified-by-code source/src/include/utils/snapshot.h]

## 2. The visibility test in two lines

For an MVCC snapshot, a tuple is visible if:

```
xmin committed  AND  (xmax is invalid OR xmax not-yet-committed-from-this-snapshot's-pov)
```

The "from this snapshot's POV" reduces to `XidInMVCCSnapshot`, which checks:
- `xid < snap->xmin` → committed before us, definitely visible (or invisible
  if xmax)
- `xid >= snap->xmax` → started after us, definitely not visible
- `xip` array lookup → in-progress at the moment we took the snapshot
- subxip array — for committed sub-xacts of a still-running parent

The function deliberately never reports the caller's own xid as in-progress
(`snapmgr.c:1862-1867`). Callers must check `TransactionIdIsCurrentTransactionId`
first. [verified-by-code `snapmgr.c:1868`]

## 3. The MVCC ordering rule

When checking a remote xid's commit state, the only safe ordering is:

```
1. TransactionIdIsCurrentTransactionId(xid)   // is it me?
2. XidInMVCCSnapshot(xid, snap)                // was it in progress when I took my snap?
3. TransactionIdIsInProgress(xid)              // is it still in progress NOW?
4. TransactionIdDidCommit(xid)                 // did it commit (per pg_xact)?
```

The pairing of steps 3 + 4 — `IsInProgress` BEFORE `DidCommit` — is critical:
`xact.c` records the pg_xact commit before clearing `MyProc->xid`. The
reverse order can read pg_xact-committed but still-in-procarray, and
decide "crashed". This is the rule documented at
`heapam_visibility.c:13-35`. [verified-by-code]

## 4. Two registries, both ref-counted

A snapshot's lifetime is governed by TWO independent ref counts; the
snapshot is only freed when both reach zero:

- **Active stack** (`ActiveSnapshot`): a stack tracking pushes / pops via
  `PushActiveSnapshot` / `PopActiveSnapshot`. Mirrors C call structure.
- **RegisteredSnapshots pairing-heap** (keyed on xmin): owned by
  ResourceOwners or, for a few internal "pseudo-registered" cases
  (FirstXactSnapshot, CatalogSnapshot, exported snapshots), by snapmgr.c
  itself.

`MyProc->xmin` (which the procarray broadcasts as the global xmin floor) is
recomputed only when the active stack is empty (`SnapshotResetXmin`
early-returns if `ActiveSnapshot != NULL`). [verified-by-code
`snapmgr.c:785-787, 898-902, 937-955`]

This is why long-held active snapshots block `pg_xact` truncation and bloat
catalog tables.

## 5. The CatalogSnapshot trick

Catalog reads use a separate snapshot (`CatalogSnapshot`) that's refreshed
on every command boundary, not held across the whole xact. This lets a
running statement see catalog changes from sibling xacts that committed
after the statement started — without it, you couldn't ALTER TABLE in one
session and have a freshly-started statement in another session see the new
columns.

The CatalogSnapshot is excluded from `SnapshotSetCommandId` so it doesn't
participate in cmin/cmax visibility within the current command. Open
question: are any consumers relying on this exclusion? Flagged in
`snapmgr.c:499` as a candidate for behavioral verification.

## 6. SetTransactionSnapshot and import/export

`SET TRANSACTION SNAPSHOT` re-uses a snapshot taken by another transaction.
The implementation calls `ProcArrayInstallRestoredXmin` or
`ProcArrayInstallImportedXmin` atomically — these are the load-bearing
safety operations that prevent the global xmin from going backward. If
either fails (e.g. the originator's xid is no longer running), the import
errors out. [verified-by-code `snapmgr.c:554-577`]

Same primitive backs parallel-worker snapshot restoration: leader exports
the snapshot, workers import it, and the global xmin is held by the
leader's PGPROC throughout.

## 7. Historic snapshot (logical decoding)

`HistoricMVCCSnapshot` (snapshot_type = `SNAPSHOT_HISTORIC_MVCC`) is used by
logical decoding to read catalog rows AS-OF the LSN where a logical xact's
changes were emitted. The `lsn` field of `SnapshotData` carries the as-of
point; the `subxip` array carries the committed subxacts of the *target*
xact (the one being decoded). The historic snapshot is built by `snapbuild.c`
from `xl_running_xacts` records during decoding — see
`knowledge/files/src/backend/replication/logical/snapbuild.c.md`.

## 8. The lifecycle in pictures

```
[user statement begins]
    -> GetTransactionSnapshot()
       -> if FirstXactSnapshot is set, return it
       -> else call GetSnapshotData(); register as FirstXactSnapshot
          if isolation=REPEATABLE READ or higher
    -> PushActiveSnapshot
    -> RegisterSnapshot(snap, resowner)
[executor runs, calls HeapTupleSatisfiesMVCC over and over]
    -> XidInMVCCSnapshot
    -> TransactionIdIsInProgress
    -> TransactionIdDidCommit
[user statement ends]
    -> PopActiveSnapshot
    -> UnregisterSnapshot when resowner releases it
    -> if both refs go to zero, SnapshotResetXmin recomputes MyProc->xmin
[next statement begins — at READ COMMITTED, builds a fresh snapshot;
 at REPEATABLE READ, reuses FirstXactSnapshot]
```

## 9. Common bugs

- **Storing a snapshot pointer beyond the active stack scope** —
  RegisteredSnapshot it (with a ResourceOwner), or copy it
  (`CopySnapshot`), or you'll read freed memory after the resowner
  releases.
- **Computing visibility without checking the current xact first** —
  `TransactionIdIsCurrentTransactionId` must precede `XidInMVCCSnapshot`,
  otherwise self-modifications can look "in progress" to the running xact.
- **Trusting `XidInMVCCSnapshot` alone for committed-yet-invisible** —
  it tells you the xid was in progress at snapshot time; you still need
  `TransactionIdDidCommit` to distinguish committed (invisible) from
  aborted (invisible for different reason).
- **Catalog-snapshot leak** — calling code that fetches `CatalogSnapshot`
  and then doesn't refresh it across DDL boundaries. The DDL committed
  but you're still looking at the pre-DDL catalog rows.

## 10. Glossary

- **xmin / xmax / xip**: the boundary xids of the snapshot. The xid arrays
  hold "in progress at the moment the snapshot was taken".
- **Active snapshot**: a snapshot on the C-call stack via
  `PushActiveSnapshot`.
- **Registered snapshot**: a snapshot in the pairing heap, ref-counted by
  ResourceOwners or by snapmgr itself.
- **CatalogSnapshot**: per-command-refreshed snapshot for catalog reads.
- **HistoricMVCCSnapshot**: as-of snapshot for logical decoding to read
  catalogs at a past LSN.
- **MyProc->xmin**: the floor below which `pg_xact` can be truncated and
  dead tuples can be reclaimed. Held back by registered snapshots and
  the active stack.
