# Snapshots — export, historic, and parallel-worker transport

There are three ways a snapshot can leave the backend that
took it:

1. **Exported** — `pg_export_snapshot()` writes a text file in
   `pg_snapshots/`; another backend imports it with
   `SET TRANSACTION SNAPSHOT '...'`.  pg_dump uses this.
2. **Historic** — `SetupHistoricSnapshot` swaps a special
   "time-travel" snapshot into place during logical
   decoding, so catalog reads see the catalog state at
   replay time.
3. **Parallel-worker** — `SerializeSnapshot` / `RestoreSnapshot`
   marshal the snapshot through a DSM segment so parallel
   workers see exactly what the leader sees.

This doc covers each.  The static slots and per-query
acquisition are [[snapshot-static-and-current]]; the refcounted
stack/heap is [[snapshot-active-stack-and-registered]].

**Anchors** (all cites against `source/` at commit `e18b0cb7344`):
- `source/src/backend/utils/time/snapmgr.c:1108-1900` — Export/Import/Serialize/Restore + Historic
- `source/src/backend/replication/logical/snapbuild.c` — builds historic snapshots from WAL
- `source/src/backend/access/transam/parallel.c` — caller of `SerializeSnapshot` for workers

## Exported snapshots — the on-disk format

### `ExportSnapshot`

`snapmgr.c:1114-1285` [verified-by-code].  The function does
**three things**:

1. Sanity checks (not in subtransaction, get topXid for
   inclusion).
2. Copy the snapshot to `TopTransactionContext`, add it to
   `exportedSnapshots`, and **manually pseudo-register** it so
   its xmin is honored for the rest of the transaction.
3. Write a text-format file under `pg_snapshots/`.

The pseudo-registration at `snapmgr.c:1188-1189`
[verified-by-code]:

```c
snapshot->regd_count++;
pairingheap_add(&RegisteredSnapshots, &snapshot->ph_node);
```

— same trick `GetNonHistoricCatalogSnapshot` uses (see
[[snapshot-static-and-current]]).  Manual add to the
RegisteredSnapshots heap without going through
`RegisterSnapshot`, because there's no `ResourceOwner` to bind
the lifetime to — the snapshot lives until xact end.

### The file format

`snapmgr.c:1198-1242` [verified-by-code].  Each line is
`fieldname:value`:

```
vxid:<procNumber>/<lxid>
pid:<MyProcPid>
dbid:<MyDatabaseId>
iso:<XactIsoLevel>
ro:<XactReadOnly>
xmin:<snapshot->xmin>
xmax:<snapshot->xmax>
xcnt:<snapshot->xcnt + addTopXid>
xip:<xid>      (xcnt lines)
xip:<topXid>   (if addTopXid)
sof:<0 or 1>   (suboverflowed flag)
sxcnt:<N>      (only if !suboverflowed)
sxp:<subxid>   (sxcnt lines)
rec:<takenDuringRecovery>
```

Three quirks worth understanding:

#### 1. Our own topXid is added to xip if it fits

Lines 1207-1224 [from-comment]:

> We must include our own top transaction ID in the top-xid
> data, since by definition we will still be running when the
> importing transaction adopts the snapshot, but
> GetSnapshotData never includes our own XID in the snapshot.
>
> However, it could be that our topXid is after the xmax, in
> which case we shouldn't include it because xip[] members are
> expected to be before xmax.

So if `xmin <= topXid < xmax`, append our XID to `xip` so the
importer sees us as in-progress.  If `topXid >= xmax`, omit it
because no rows tagged with our XID can possibly be in the
visible range.

#### 2. Committed subxact children are added to subxip

Line 1163 [verified-by-code]:

```c
nchildren = xactGetCommittedChildren(&children);
```

Comment at lines 1158-1161 [from-comment]:

> We do however allow previous committed subtransactions to
> exist.  Importers of the snapshot must see them as still
> running, so get their XIDs to add them to the snapshot.

Subxacts that committed earlier in *our* transaction are
treated as "in-progress" by the importer — they won't actually
be in-progress at the importer's `xmin` < their xid time, but
we add them as overflow.  This preserves the "we're still
running" property.

#### 3. The `.tmp` rename pattern

Lines 1250-1276 [verified-by-code]:

```c
snprintf(pathtmp, sizeof(pathtmp), "%s.tmp", path);
if (!(f = AllocateFile(pathtmp, PG_BINARY_W)))
    ereport(ERROR, ... "could not create file");
if (fwrite(buf.data, buf.len, 1, f) != 1)
    ereport(ERROR, ...);
if (FreeFile(f))
    ereport(ERROR, ...);
if (rename(pathtmp, path) < 0)
    ereport(ERROR, ...);
```

Write to `.tmp` then `rename` — atomic from the importer's
perspective.  ImportSnapshot's character-validation check on
the filename means it won't even try to read a `.tmp` file.

The comment at line 1261 [from-comment]:

> no fsync() since file need not survive a system crash

Exported snapshots are scoped to a running cluster; if the
publisher crashes, the snapshot is useless anyway.

### Cleanup

The `exportedSnapshots` list is drained at `AtEOXact_Snapshot`
(see `snapmgr.c:1038-1066` covered in
[[snapshot-active-stack-and-registered]]) — each file is
`unlink()`ed and the pseudo-registration removed from the
heap.  A `WARNING` is emitted if `unlink` fails; the commit
proceeds anyway since rolling back a successful commit isn't
an option.

## ImportSnapshot — `SET TRANSACTION SNAPSHOT`

`snapmgr.c:1380+` (declaration at line 1386).  Implementation
walks the file with `parseIntFromText` / `parseXidFromText` /
`parseVxidFromText` parsers (lines 1306-1378
[verified-by-code]), reconstructs a `SnapshotData`, and calls
`SetTransactionSnapshot`.

Validation enforced by the parsers:

- Filename must contain only `[0-9A-Fa-f-]` (rejects `.tmp`).
- File must be readable (rejects exporter-crashed cases).
- All fields must parse cleanly; missing or malformed lines
  → ERROR.
- Source backend must still be alive (`vxid` check via
  `BackendIdGetProc`).
- Importer must be in a transaction that hasn't taken a
  snapshot yet.

The session-level rule: you can only `SET TRANSACTION
SNAPSHOT` once per transaction, and only as the very first
statement after `BEGIN`.  `FirstSnapshotSet` enforces this.

## Historic snapshots — the logical-decoding catalog view

### Why "historic"?

Logical decoding replays changes from WAL.  Each replayed
INSERT/UPDATE/DELETE was committed at some `XLogRecPtr` in the
past, and the catalog state at that LSN may differ from the
current catalog state — schemas could have been altered,
columns added, types changed.

So the catalog scans done by the decoding output plugin need
to see **the catalog as it was at the change-replay LSN**, not
the catalog as it is now.  That's what historic snapshots do.

### `SetupHistoricSnapshot`

`snapmgr.c:1668-1678` [verified-by-code]:

```c
void
SetupHistoricSnapshot(Snapshot historic_snapshot, HTAB *tuplecids)
{
    Assert(historic_snapshot != NULL);

    HistoricSnapshot = historic_snapshot;
    tuplecid_data = tuplecids;
}
```

Two pointers set:

- **`HistoricSnapshot`** — the snapshot itself.  Built by
  `snapbuild.c` by replaying WAL and tracking commits / aborts
  to derive an MVCC snapshot at a specific LSN.
- **`tuplecid_data`** — a hash table mapping `(table, ctid) →
  (cmin, cmax)` for tuples written by transactions that are
  in-progress at the historic LSN.  Needed because in-progress
  transactions don't have a committed `cmin`/`cmax`, so
  visibility within the same transaction has to consult this
  side-table.

### How historic shadows normal snapshot fetches

In [[snapshot-static-and-current]] we saw the two top-of-
function checks:

```c
/* GetTransactionSnapshot */
if (HistoricSnapshotActive())
{
    Assert(!FirstSnapshotSet);
    return HistoricSnapshot;
}

/* GetCatalogSnapshot */
if (HistoricSnapshotActive())
    return HistoricSnapshot;
```

So whenever the decoder calls any catalog-scanning
infrastructure, the snapshot returned is the historic one.
The output plugin doesn't have to know — it just calls
`SearchSysCache*` as usual.

### Teardown

```c
/* snapmgr.c:1685-1689 */
void
TeardownHistoricSnapshot(bool is_error)
{
    HistoricSnapshot = NULL;
    tuplecid_data = NULL;
}
```

Just nulls the pointers.  The snapshot itself is owned by
`snapbuild.c` and freed by its own cleanup path.  The `is_error`
parameter exists for future use but is currently ignored.

### `HistoricSnapshotGetTupleCids`

`snapmgr.c:1697-1702` [verified-by-code].  The (cmin, cmax)
hash table is queried by `HeapTupleSatisfiesHistoricMVCC` (in
`heapam_visibility.c`) when checking whether a tuple
within an in-progress catalog-modifying transaction is visible
at the historic-snapshot's `curcid`.

This is what makes "decode a SCHEMA-modifying transaction's
own rows that came after its DDL" work — without it, the
decoded output for `INSERT after ALTER TABLE` would see the
post-ALTER schema but try to apply pre-ALTER tuple format.

## Parallel-worker snapshot transport

When a parallel-aware plan spawns workers, every worker needs
to see the same snapshot as the leader.  The transport is via
the parallel-query DSM segment using a fixed-size header plus
variable-size XID arrays.

### `SerializedSnapshotData` — the wire format

`snapmgr.c:251-260` [verified-by-code]:

```c
typedef struct SerializedSnapshotData
{
    TransactionId xmin;
    TransactionId xmax;
    uint32        xcnt;
    int32         subxcnt;
    bool          suboverflowed;
    bool          takenDuringRecovery;
    CommandId     curcid;
} SerializedSnapshotData;
```

Seven scalar fields followed by `xcnt + subxcnt` `TransactionId`
values inline.  The comment at lines 246-250 [from-comment]:

> Only these fields need to be sent to the cooperating
> backend; the remaining ones can (and must) be set by the
> receiver upon restore.

So things like `regd_count`, `active_count`, `copied`,
`ph_node`, `snapXactCompletionCount` are left for the
receiver to initialize properly.

### `EstimateSnapshotSpace` — DSM allocation budget

`snapmgr.c:1711-1728` [verified-by-code]:

```c
Size
EstimateSnapshotSpace(Snapshot snapshot)
{
    Size size;

    Assert(snapshot->snapshot_type == SNAPSHOT_MVCC);

    size = add_size(sizeof(SerializedSnapshotData),
                    mul_size(snapshot->xcnt, sizeof(TransactionId)));
    if (snapshot->subxcnt > 0 &&
        (!snapshot->suboverflowed || snapshot->takenDuringRecovery))
        size = add_size(size,
                        mul_size(snapshot->subxcnt, sizeof(TransactionId)));

    return size;
}
```

The serialize-time decision: if `suboverflowed && !takenDuringRecovery`,
the subxid array is dropped (the receiver will fall back to
clog probes).  But on a standby snapshot, **the subxip array
holds top-level XIDs too**, so we mustn't drop it.

The parallel-context shared-state initialization (in
`parallel.c`) calls `EstimateSnapshotSpace` for both the
transaction snapshot and the active snapshot, plus other
shared state, and allocates one DSM segment to fit everything.

### `SerializeSnapshot` — write to the DSM

`snapmgr.c:1736-1783` [verified-by-code].  Three blocks of memcpy:

```c
/* Header */
memcpy(start_address, &serialized_snapshot, sizeof(SerializedSnapshotData));

/* XID array */
if (snapshot->xcnt > 0)
    memcpy((TransactionId *) (start_address + sizeof(SerializedSnapshotData)),
           snapshot->xip, snapshot->xcnt * sizeof(TransactionId));

/* SubXID array */
if (serialized_snapshot.subxcnt > 0)
{
    Size subxipoff = sizeof(SerializedSnapshotData) +
                     snapshot->xcnt * sizeof(TransactionId);
    memcpy((TransactionId *) (start_address + subxipoff),
           snapshot->subxip, snapshot->subxcnt * sizeof(TransactionId));
}
```

The "drop suboverflowed array unless takenDuringRecovery"
filter at line 1756-1757 [verified-by-code]:

```c
if (serialized_snapshot.suboverflowed && !snapshot->takenDuringRecovery)
    serialized_snapshot.subxcnt = 0;
```

— sets `subxcnt = 0` in the on-wire copy so the receiver
won't try to read absent data.

### `RestoreSnapshot` — read from the DSM

`snapmgr.c:1793-1847` [verified-by-code]:

```c
Snapshot
RestoreSnapshot(char *start_address)
{
    SerializedSnapshotData serialized_snapshot;
    Size size;
    Snapshot snapshot;
    TransactionId *serialized_xids;

    memcpy(&serialized_snapshot, start_address, sizeof(SerializedSnapshotData));
    serialized_xids = (TransactionId *)
                      (start_address + sizeof(SerializedSnapshotData));

    /* We allocate any XID arrays needed in the same palloc block. */
    size = sizeof(SnapshotData)
         + serialized_snapshot.xcnt * sizeof(TransactionId)
         + serialized_snapshot.subxcnt * sizeof(TransactionId);

    snapshot = (Snapshot) MemoryContextAlloc(TopTransactionContext, size);
    snapshot->snapshot_type = SNAPSHOT_MVCC;
    snapshot->xmin = serialized_snapshot.xmin;
    snapshot->xmax = serialized_snapshot.xmax;
    /* ... copy fields ... */
    snapshot->snapXactCompletionCount = 0;

    if (serialized_snapshot.xcnt > 0)
    {
        snapshot->xip = (TransactionId *) (snapshot + 1);
        memcpy(snapshot->xip, serialized_xids,
               serialized_snapshot.xcnt * sizeof(TransactionId));
    }

    if (serialized_snapshot.subxcnt > 0)
    {
        snapshot->subxip = ((TransactionId *) (snapshot + 1)) +
                           serialized_snapshot.xcnt;
        memcpy(snapshot->subxip, serialized_xids + serialized_snapshot.xcnt,
               serialized_snapshot.subxcnt * sizeof(TransactionId));
    }

    snapshot->regd_count = 0;
    snapshot->active_count = 0;
    snapshot->copied = true;

    return snapshot;
}
```

Three things to notice:

#### Single-allocation layout

`sizeof(SnapshotData) + xcnt*sizeof(XID) + subxcnt*sizeof(XID)`
is one palloc.  `snapshot->xip` points into the trailing
bytes; `snapshot->subxip` points further in.  This is the same
pattern `CopySnapshot` uses.

#### `snapXactCompletionCount = 0`

`snapXactCompletionCount` is a cache invalidation hint used by
the procarray's snapshot-recompute fast path.  In the
restored copy, the cache hint is reset — workers can't reuse
the leader's cache state.

#### `copied = true` + zero refcounts

The worker is given a stable heap copy with both refcounts at
zero.  The receiver then `PushActiveSnapshot`s or
`RegisterSnapshot`s it as appropriate; both operations bump
the refcounts.

### `RestoreTransactionSnapshot` — install as the worker's snapshot

`snapmgr.c:1853-1856` [verified-by-code]:

```c
void
RestoreTransactionSnapshot(Snapshot snapshot, PGPROC *source_pgproc)
{
    SetTransactionSnapshot(snapshot, NULL, InvalidPid, source_pgproc);
}
```

Wraps the same `SetTransactionSnapshot` used by
`SET TRANSACTION SNAPSHOT`.  The `source_pgproc` parameter is
the leader's PGPROC — this lets the worker's
`SetTransactionSnapshot` register itself in the
procarray-snapshot machinery as "I depend on the leader" so
parallel xmin advance honors both processes correctly.

## The three transport mechanisms compared

| Mechanism | Encoding | Lifetime | Visible to |
|---|---|---|---|
| Export | text file in pg_snapshots/ | from export until xact end | any other backend with `SET TRANSACTION SNAPSHOT` |
| Historic | in-memory SnapshotData | from `SetupHistoricSnapshot` until `Teardown` | only the calling backend |
| Parallel | DSM byte sequence | for the parallel context's life | only the parallel workers attached to this leader |

| Use case | Why this mechanism |
|---|---|
| pg_dump on a hot snapshot | Export — coordinator dumps schema then workers dump data on same snapshot |
| Logical replication output plugin | Historic — catalog must look like it did at change-time |
| `Parallel Seq Scan` | Parallel — workers must see same in-progress xacts as leader |

The export format is **stable across PG versions** for major-
version compatibility (pg_upgrade can dump from old, import
into new with the same exported snapshot).  Historic and
parallel are **in-process** so version stability doesn't
matter.

## Invariants worth remembering

1. **`pg_export_snapshot` can only run at top-level**
   (not in a subtransaction).  We can't guarantee the same
   subxact will still be alive at import time.
2. **The exporter's own topXid goes in xip** only when
   `xmin <= topXid < xmax`.
3. **Committed subxact children of the exporter get added to
   subxip** so importers treat them as in-progress.
4. **Export uses `.tmp` then rename** for atomicity.  No
   fsync because crashes invalidate the file anyway.
5. **`HistoricSnapshot` shadows both `GetTransactionSnapshot`
   and `GetCatalogSnapshot`** when set.
6. **`HistoricSnapshotActive()` is the gate for all
   historic-aware code paths.**
7. **`tuplecid_data` is the `(table, ctid) → (cmin, cmax)`
   side table** for visibility inside catalog-modifying
   in-progress xacts.
8. **`SerializedSnapshotData` is fixed-size header + variable
   xip/subxip arrays.**  `EstimateSnapshotSpace` knows the
   total.
9. **`suboverflowed && !takenDuringRecovery` ⇒ drop subxip
   array.**  Standby snapshots are exceptional because subxip
   carries top XIDs.
10. **`RestoreSnapshot` returns a `copied = true` snapshot
    with refcounts zero.**  Caller must `Push` or
    `Register` to take ownership.

## Useful greps

```bash
# Export/import entry points
grep -n "ExportSnapshot\|ImportSnapshot\|SetTransactionSnapshot\|RestoreTransactionSnapshot" \
    source/src/backend/utils/time/snapmgr.c

# Historic API
grep -rn "SetupHistoricSnapshot\|TeardownHistoricSnapshot\|HistoricSnapshotActive\|HistoricSnapshotGetTupleCids" \
    source/src/backend/

# Parallel-worker serialization
grep -n "SerializeSnapshot\|RestoreSnapshot\|EstimateSnapshotSpace" \
    source/src/backend/

# pg_snapshots dir convention
grep -rn "SNAPSHOT_EXPORT_DIR\|pg_snapshots" source/src/

# The text format fields
grep -n "appendStringInfo.*\"vxid\\|\"xmin\\|\"xmax\\|\"xcnt\\|\"sof\\|\"sxcnt\\|\"sxp\\|\"rec\"" \
    source/src/backend/utils/time/snapmgr.c
```



## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/access/transam/parallel.c`](../files/src/backend/access/transam/parallel.c.md) | — | caller of SerializeSnapshot for workers |
| [`src/backend/replication/logical/snapbuild.c`](../files/src/backend/replication/logical/snapbuild.c.md) | — | builds historic snapshots from WAL |
| [`src/backend/utils/time/snapmgr.c`](../files/src/backend/utils/time/snapmgr.c.md) | 1108 | Export/Import/Serialize/Restore + Historic |

<!-- /callsites:auto -->

## Cross-references

- [[snapshot-static-and-current]] — the static slots that
  `HistoricSnapshot` shadows; `CurrentSnapshotData` is what
  `ExportSnapshot` typically copies from.
- [[snapshot-active-stack-and-registered]] — the pairing-heap
  registration that exports manually replicate; restored
  parallel snapshots are pushed onto the active stack.
- [[logical-decoding-snapshot]] — the WAL-replay side that
  builds `HistoricSnapshot` in the first place.
- [[parallel-worker-coordination]] — the DSM machinery that
  carries serialized snapshots to workers.
- [[xmin-horizon-management]] — exported snapshots pin xmin
  until xact end.
- [[catalog-conventions]] — historic catalog visibility
  honors `xmin <= xact_id < xmax` exactly as MVCC.
- [[buffer-manager]] — `AllocateFile`/`FreeFile` are used by
  the export path; they manage the per-process file-descriptor
  pool.
- [[heap-tuple-visibility-mvcc]] — `HeapTupleSatisfiesHistoricMVCC`
  is the consumer of the (cmin, cmax) tuplecid hash.
