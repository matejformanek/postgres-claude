# MVCC — architectural overview

Scope: conceptual reference for PostgreSQL's multi-version concurrency
control. Companion: `wal.md`. File-level docs for `access/heap`,
`access/transam`, and `storage/ipc/procarray.c` belong in
`knowledge/subsystems/` once those subsystems are documented.

Source anchors:
- `source/src/backend/access/transam/README` (especially "Interlocking
  Transaction Begin, Transaction End, and Snapshots", "pg_xact and
  pg_subtrans", "Transaction Emulation during Recovery")
- `source/src/backend/access/heap/heapam_visibility.c` (top comment)
- `source/src/backend/utils/time/snapmgr.c` (top comment)
- `source/src/include/access/htup_details.h` (tuple header)
- `source/src/backend/storage/ipc/procarray.c` (top comment)
- `source/doc/src/sgml/mvcc.sgml` (the chapter the docs site builds from)

## 1. The MVCC model in one paragraph

A write produces a *new* tuple version, not an in-place overwrite. Each tuple
carries `xmin` (inserting xact) and `xmax` (deleting/locking xact). Each
read uses a *snapshot* — a set of xact IDs visible to the reader — and
decides per-tuple whether to see it. Readers don't block writers, writers
don't block readers; conflict resolution happens at write time via row locks
and (for serializable) predicate locks. Dead tuple versions are reclaimed by
VACUUM. [from-comment `heapam_visibility.c:38-57`; from-doc
`mvcc.sgml:32-46`]

## 2. The tuple header

`HeapTupleHeaderData`: 23 bytes fixed + nulls bitmap + alignment.
[verified-by-code `source/src/include/access/htup_details.h:153-185`]

Visibility-related fields: [verified-by-code `htup_details.h:122-181`]

| field | meaning |
|---|---|
| `t_xmin` | inserting xact ID |
| `t_xmax` | deleting or locking xact ID (0 if none) |
| `t_cid` | inserting OR deleting **command id** within the inserter/deleter (shares space with `t_xvac`; if both cmin and cmax matter, becomes a "combo CID" — see `combocid.c`) |
| `t_ctid` | TID of *this* tuple, or of its replacement; chain links to newer versions |
| `t_infomask` | flag bits (see below) |
| `t_infomask2` | attribute count + more flags |

Key `t_infomask` bits: [verified-by-code `htup_details.h:188-219`]

| bit | meaning |
|---|---|
| `HEAP_XMIN_COMMITTED` | hint: xmin committed |
| `HEAP_XMIN_INVALID` | hint: xmin aborted (or never assigned) |
| `HEAP_XMIN_FROZEN` | = `COMMITTED | INVALID` together: xmin is *frozen* |
| `HEAP_XMAX_COMMITTED` | hint: xmax committed |
| `HEAP_XMAX_INVALID` | hint: xmax aborted/missing |
| `HEAP_XMAX_IS_MULTI` | xmax is a MultiXactId (multiple lockers) |
| `HEAP_XMAX_LOCK_ONLY` | xmax is only a lock, not a delete |
| `HEAP_COMBOCID` | t_cid encodes both cmin & cmax via combo table |
| `HEAP_UPDATED` | this row is an UPDATE successor of another |

### `t_ctid` semantics

[from-comment `htup_details.h:86-112`]

- On insert, `t_ctid` is set to the tuple's own TID.
- On update, the old version's `t_ctid` points at the new version.
- On partition-key UPDATE that moves the row, `t_ctid` gets a sentinel
  (`ItemPointerSetMovedPartitions`).
- A tuple is the *latest* version iff `t_xmax` is invalid OR
  `t_ctid` points to itself.
- Beware: VACUUM may have erased the successor before the predecessor; when
  chasing `t_ctid`, verify the target's `xmin` equals the source's `xmax`.

### Combo CID

Cmin and cmax share a single 4-byte slot (`t_cid`). If a tuple is both
inserted and deleted in the same transaction, a "combo CID" is allocated in
backend-local memory that maps to the real (cmin, cmax) pair; the
`HEAP_COMBOCID` infomask bit flags this. The combo table is local to the
inserting/deleting backend — other backends never need cmin/cmax for that
xact anyway. [from-comment `htup_details.h:73-84`]

## 3. Transaction IDs (XID), VXID, SubTransactionId

[from-README `source/src/backend/access/transam/README:190-221`]

- **XID**: 32-bit, assigned **lazily** — only when a transaction first writes
  (insert/update/delete or a few other cases). Read-only xacts get no XID.
- A subtransaction that needs an XID first forces its parent to acquire one,
  so child XID > parent XID — an invariant relied on widely.
- **VXID** (`procNumber, backend-local-counter`) — every top-level xact has
  one; assigned at start without shared-memory contention. Used for holding
  locks before an XID is assigned. Never appears on disk.
- **SubTransactionId** — backend-local counter; top-level xact is 1,
  subxacts are 2+. Resets each top transaction. Subxacts share the parent's
  VXID.

## 4. pg_xact and pg_subtrans

[from-README `transam/README:342-396`]

- **pg_xact** (CLOG): 2-bit status per XID — *in progress*, *committed*,
  *aborted*, *sub-committed*.
- The "sub-committed" state exists only briefly during commit when the
  transaction's CLOG entries span more than one page — a two-phase update
  ensures atomicity from any reader's perspective.
- **pg_subtrans**: parent XID per XID. Used to walk up the subxact tree
  during visibility checks when the in-PGPROC subxid cache has overflowed.
- Both backed by SLRU (`slru.c`); a small number of pages in shared memory,
  spill to disk on demand.

## 5. The ProcArray and snapshots

`ProcArray` (`source/src/backend/storage/ipc/procarray.c`) holds a PGPROC
slot per active backend; the key shared arrays are `ProcGlobal->xids[]`
(top-level XID) and the per-PGPROC subxid cache. Prepared 2PC transactions
also occupy slots, distinguished by `pid == 0`. [verified-by-code
`procarray.c:7-20`]

### Snapshot construction

A `Snapshot` is, conceptually: [from-README `transam/README:224-329`]

| field | meaning |
|---|---|
| `xmin` | smallest XID still considered in-progress |
| `xmax` | one past the largest XID that could be in our snapshot (`latestCompletedXid + 1`) |
| `xip[]` | XIDs of in-progress xacts in `[xmin, xmax)` |
| `subxip[]` | known subxact XIDs (when caches haven't overflowed) |

Decision rule for whether an XID is *visible* (committed before the snapshot):
- XID < xmin → committed and visible (or aborted; pg_xact decides).
- XID ≥ xmax → not visible (future).
- xmin ≤ XID < xmax and XID ∈ xip[] → in-progress, not visible.
- xmin ≤ XID < xmax and XID ∉ xip[] → completed; consult pg_xact for
  commit/abort. [inferred from heapam_visibility.c logic + README]

### The snapshot/commit interlock

The correctness invariant: *if my snapshot considers X committed and any
snapshot of X considered Y committed, my snapshot must also consider Y
committed.* [from-README `transam/README:241-244`]

Enforcement: `GetSnapshotData` takes `ProcArrayLock` in **shared** mode;
`ProcArrayEndTransaction` takes it in **exclusive** mode while clearing the
ending xact's XID and advancing `latestCompletedXid`. This serializes "exit
the running set" against "build a snapshot", which is stronger than strictly
necessary but simple. [from-README `transam/README:246-263`]

Read-only xacts (no XID) can end without `ProcArrayLock` because they don't
affect anyone else's snapshot. [from-README `transam/README:264-270`]

Performance note: since v14 `GetSnapshotData` no longer computes an accurate
oldest-xmin globally; it maintains approximate horizons (`GlobalVisTest*`)
and only falls back to `ComputeXidHorizons` when needed. [from-README
`transam/README:320-329`]

## 6. The visibility functions

[from-comment `heapam_visibility.c:38-57`]

| function | use case |
|---|---|
| `HeapTupleSatisfiesMVCC(tup, snap)` | normal queries (excludes current command) |
| `HeapTupleSatisfiesUpdate` | UPDATE/DELETE path; richer return values |
| `HeapTupleSatisfiesSelf` | sees own xact, all commands |
| `HeapTupleSatisfiesDirty` | sees open xacts too (FK checks, predicate locks) |
| `HeapTupleSatisfiesVacuum` | VACUUM: is this dead to everyone? |
| `HeapTupleSatisfiesToast` | TOAST chunks (skipped during aborted VACUUM) |
| `HeapTupleSatisfiesAny` | always true (debugging / dump) |

### The race that drives the rule "check `TransactionIdIsInProgress` before `TransactionIdDidCommit`"

`xact.c` records commit/abort in pg_xact *before* clearing
`MyProc->xid`. So there is a window where both
`TransactionIdIsInProgress` and `TransactionIdDidCommit` return true. If a
visibility check only asked DidCommit, it could mark a tuple committed —
but a concurrent `GetSnapshotData` (still seeing the xact in ProcArray)
would consider it in-progress, leading to inconsistent visibility decisions
across backends. So all visibility paths check IsInProgress first.
[from-comment `heapam_visibility.c:13-27`]

For MVCC snapshots specifically, the analogue is `XidInMVCCSnapshot`
against the snapshot's xip[]; same ordering rule. [from-comment
`heapam_visibility.c:33-36`]

## 7. Hint bits

A hint bit is a cached visibility answer written into the tuple's infomask
on first inspection. It is *not authoritative* — pg_xact is. It can be
re-derived at any time. [wiki: <https://wiki.postgresql.org/wiki/Hint_Bits>;
from-comment `heapam_visibility.c:5-12`]

Setting rules: [from-comment `heapam_visibility.c:101-125`]

- The setter must hold the buffer's content lock (at least share).
- Setting `XMIN_COMMITTED` / `XMAX_COMMITTED` is only safe if the commit
  record is **guaranteed flushed before the page**. If not, we defer until
  WAL has flushed past the commit's LSN (see `transam/README:822-841` for
  the clog-page LSN trick).
- Setting `XMIN_INVALID` / `XMAX_INVALID` (abort) is always safe.
- Hint-only writes use `MarkBufferDirtyHint()`, which emits
  `XLOG_FPI_FOR_HINT` if checksums or `wal_log_hints` are on (otherwise a
  torn page could corrupt user data on the page).

## 8. Isolation levels in PostgreSQL

PostgreSQL accepts all four SQL-standard isolation levels but implements
**three** distinct levels internally — Read Uncommitted is mapped to Read
Committed. [verified-by-code in docs:
`source/doc/src/sgml/mvcc.sgml:270-276`]

| SQL level | PG behaviour | implementation |
|---|---|---|
| Read Uncommitted | = Read Committed | (no separate code path) |
| Read Committed (default) | new snapshot per statement | snapshot at each command start |
| Repeatable Read | = **Snapshot Isolation** (SI) | one snapshot for the whole xact |
| Serializable | **Serializable Snapshot Isolation** (SSI) | SI + predicate locks + cycle detection |

[from-doc `mvcc.sgml:588-599` — "The Repeatable Read isolation level is
implemented using a technique known in academic database literature and in
some other database products as Snapshot Isolation."]

[from-doc `mvcc.sgml:853-854` — "in academic database literature as
Serializable Snapshot Isolation, which builds on Snapshot Isolation by
adding checks for serialization anomalies"]

PG's RR is *stronger* than the SQL standard requires — phantom reads are
prevented, which is allowed because the standard specifies what
anomalies must **not** occur, not what must occur. [from-doc
`mvcc.sgml:278-283`]

Pre-9.1, "SERIALIZABLE" gave what is now Repeatable Read (pure SI). True
SSI shipped in 9.1. [from-doc `mvcc.sgml:602-609`]

### Common misconception

> "Repeatable Read in PostgreSQL is the same as the SQL standard Repeatable
> Read, with phantom reads possible."

False. PG's RR uses Snapshot Isolation, which prevents phantoms (because
the entire xact reads from one snapshot). PG's RR is closer to the
standard's Serializable than to the standard's Repeatable Read — except
for SI's classic write-skew anomaly, which only Serializable (SSI)
prevents. [from-doc `mvcc.sgml:278-283`, `mvcc.sgml:588-599`]

### Common misconception (#2, related)

> "Serializable in PG is two-phase locking."

False. It's SSI — optimistic, snapshot-based, with predicate locks tracking
read dependencies and aborting transactions that would otherwise form a
dangerous read/write cycle. [from-doc `mvcc.sgml:850-855`]

## 9. VACUUM and dead tuples

A tuple version is *dead* when no current or future snapshot can see it. The
threshold is the cluster-wide oldest xmin (`ComputeXidHorizons`) — a tuple
deleted by a transaction whose XID is below that horizon is removable.
[from-README `transam/README:296-318`]

VACUUM responsibilities:
- Remove dead tuple versions (and their index entries).
- Defragment pages.
- Update the **visibility map** (pages with only all-visible tuples can be
  skipped by index-only scans).
- **Freeze** old tuples to prevent XID wraparound (next section).
- Update `pg_class.relfrozenxid` and `pg_database.datfrozenxid`.

A long-running transaction holds the horizon back system-wide, blocking
cleanup of dead rows even in unrelated tables. This is the "idle in
transaction" / "long open snapshot" hazard.

### HOT updates

A **Heap-Only Tuple** update is an UPDATE that:
- changes no indexed column, AND
- finds room for the new version on the same page as the old.

The new version is *not* indexed; index entries continue to point at the
chain root, and `t_ctid` chains lead to the latest version. This avoids
index bloat and lets *single-page* pruning reclaim space without a
table-wide VACUUM. [from-README `source/src/backend/access/heap/README.HOT`]

Pruning happens opportunistically (on access, when a page is full enough to
justify it); it collapses HOT chains, leaving "redirect" line pointers so
that index entries still resolve.

## 10. Freezing and XID wraparound

XIDs are 32-bit, so the "space" of XIDs is a circular range of 2^32. The
visibility logic uses modulo-2^31 comparisons (`TransactionIdPrecedes`),
which means an XID "in the past" stays in the past for only ~2 billion
XIDs of forward progress.

**Freezing** rewrites an old tuple's `xmin` (and possibly `xmax`) marker
state so the tuple is unconditionally visible, regardless of any future
wraparound:

- The current mechanism sets both `HEAP_XMIN_COMMITTED` *and*
  `HEAP_XMIN_INVALID` simultaneously (`HEAP_XMIN_FROZEN`), a sentinel
  meaning "frozen". [verified-by-code `htup_details.h:204-206`]
- Older PG versions overwrote the XID with `FrozenTransactionId`; the
  combined-bits form preserves the original XID for forensics.

Triggers: autovacuum runs an anti-wraparound vacuum when
`pg_class.relfrozenxid` falls behind by `vacuum_freeze_table_age` /
`autovacuum_freeze_max_age`. If wraparound is genuinely imminent, the
cluster shuts down to single-user mode and refuses new XIDs. [unverified
exact GUC/threshold values — verify against `vacuum.sgml`]

## 11. Visibility map and PD_ALL_VISIBLE

Each heap page has an `PD_ALL_VISIBLE` page-header flag. Each relation has a
fork-based **visibility map** (one bit per heap page) summarizing the same.
Invariant: VM bit set ⇒ heap page has `PD_ALL_VISIBLE`. [from-README
`transam/README:648-665`]

Used by index-only scans (skip the heap fetch if VM says the page is
all-visible) and by VACUUM (skip all-visible pages in non-aggressive mode).

Clearing PD_ALL_VISIBLE is treated as a *durable* change so the invariant
holds across crashes; setting it is also durable when checksums or
`wal_log_hints` are on. Otherwise setting is a pure hint. [from-README
`transam/README:648-665`]

## 12. MVCC during recovery / on standbys

Hot standby allows read-only queries while WAL is being replayed. To make
MVCC consistent, the standby must know which XIDs are in flight on the
primary. The primary periodically emits a `RUNNING_XACTS` snapshot record;
between such records, the standby tracks XIDs it has seen in WAL via
**KnownAssignedXids** (in `procarray.c`). Standby `GetSnapshotData` uses
this array as if it were ProcArray xids. [verified-by-code
`procarray.c:22-36`; from-README `transam/README:887-913`]

Recovery conflicts arise when replay needs to remove a tuple still visible
to a standby snapshot: the standby either delays replay
(`max_standby_*_delay`) or cancels the offending query. [inferred from
hot-standby docs]

## 13. Open questions and unverifieds

- `[unverified]` Exact list of phantom-vs-write-skew anomalies: PG's RR
  prevents phantoms but not write skew; PG's S prevents both. Worth a
  worked example using `pg_regress` or isolation tests.
- `[unverified]` `vacuum_freeze_min_age`, `vacuum_freeze_table_age`,
  `autovacuum_freeze_max_age` exact defaults and interaction — needs a
  read of `vacuum.c` and `config.sgml`.
- `[unverified]` Whether `HeapTupleSatisfiesVacuum` returns
  `HEAPTUPLE_RECENTLY_DEAD` vs `HEAPTUPLE_DEAD` based purely on
  OldestXmin, or also on per-tuple checks (`MultiXactId` etc.).
- `[inferred]` Snapshot field semantics in §5 are paraphrased from the
  README; the actual `SnapshotData` struct in `snapshot.h` was not opened
  in this pass.
