---
source_url: https://www.postgresql.org/docs/current/index-locking.html
fetched_at: 2026-06-12T20:47:00Z
anchor_sha: e18b0cb
chapter: "63.4 Index Locking Considerations"
---

# Index Locking Considerations (docs §63.4)

Distilled from the PG docs chapter on what an index access method must do about
concurrency. This is the rulebook behind `amgettuple` / `ambulkdelete` pin
discipline. `[from-docs]` unless a `source/` cite is given.

## Non-obvious claims

- **The core system's table-level index locks deliberately don't conflict.**
  Index scans take `AccessShareLock`; index updates (including plain `VACUUM`)
  take `RowExclusiveLock`; only CREATE/DROP/REINDEX take `ACCESS EXCLUSIVE`
  (`SHARE UPDATE EXCLUSIVE` under `CONCURRENTLY`). Because scan-locks and
  update-locks don't conflict, **fine-grained intra-index locking is entirely
  the AM's responsibility** — the heavyweight lock manager won't serialize a
  scan against a concurrent insert. `[from-docs]`
- **Three ordering rules keep heap and index mutually consistent:** (1) a new
  heap entry is made *before* its index entries — so concurrent scans may miss
  not-yet-committed rows (fine for uncommitted data, but drives the uniqueness
  protocol in §63.5); (2) `VACUUM` must remove *all* index entries before the
  heap entry they point at is deleted; (3) an index scan must **hold a pin on
  the index page containing the item last returned by `amgettuple`**, and
  `ambulkdelete` must not delete entries from pages currently pinned by another
  backend. `[from-docs]`
- **The pin is a "reader in flight" proxy against TID recycling.** Without it:
  reader sees index entry → `VACUUM` deletes the heap tuple → another backend
  reuses that item-pointer slot → reader fetches a wholly unrelated row that may
  spuriously match the scan keys. The pin makes `ambulkdelete` block until the
  reader moves on, so the heap TID can't be recycled mid-flight. Cost is paid
  only in the rare actual-conflict case. `[from-docs]`
- **The TID-recycle hazard only bites non-MVCC snapshots** (e.g. `SnapshotAny`,
  `SnapshotDirty`). MVCC snapshots are immune because a recycled-into row has a
  different xmin and won't be judged visible. This is *why* the rules below hinge
  on snapshot type. `[from-docs]`
- **Synchronous vs. asynchronous scan is a snapshot-driven choice.** A
  non-MVCC snapshot forces *synchronous* scanning — fetch each heap tuple
  immediately after reading its index entry, while the pin is held (expensive,
  high lock traffic). MVCC snapshots permit *asynchronous* scanning — collect
  many TIDs, visit the heap later — for far less index-lock overhead and better
  heap access locality. `[from-docs]`
- **`amgetbitmap` keeps no per-tuple index pin at all**, so bitmap index scans
  are *only* safe with MVCC-compliant snapshots. (Contrast `amgettuple`, which
  carries the pin.) `[from-docs]`
- **Predicate (SSI) locking granularity is the `ampredlocks` flag.** If unset,
  any scan in a serializable txn takes a nonblocking predicate lock on the
  *whole index*, generating rw-conflicts against every concurrent serializable
  insert into that index — coarse, more false cancellations. If set, the AM does
  finer-grained predicate locking (btree does page/tuple-level) to cut
  serialization-failure frequency. `[from-docs]`
- The chapter explicitly points at `src/backend/access/nbtree/README` and
  `src/backend/access/hash/README` for the worked design rationale. `[from-docs]`

## Links into corpus

- [[knowledge/subsystems/access-nbtree.md]] — btree is the reference
  implementation of all three rules; its README is the cited design doc.
- [[knowledge/subsystems/access-heap.md]] — the heap side of "heap entry before
  index entry" and the TID-recycle hazard.
- [[knowledge/subsystems/storage-lmgr.md]] — the table-level lock modes
  (AccessShare / RowExclusive / AccessExclusive) referenced here.
- [[knowledge/idioms/locking-overview.md]] — pin vs. content-lock vs. predicate
  lock taxonomy.
- [[knowledge/files/src/backend/access/index/genam.c.md]],
  [[knowledge/files/src/backend/access/index/indexam.c.md]] — `amgettuple` /
  `amgetbitmap` / `ambulkdelete` dispatch wrappers.
- Skill: `access-method-apis` (IndexAmRoutine callback contracts),
  `locking` (predicate locks, pin/content-lock rules).

## Citations

- All claims `[from-docs]` per source_url above. Design rationale lives in
  `source/src/backend/access/nbtree/README` and
  `source/src/backend/access/hash/README` (referenced by the chapter; verify at
  anchor e18b0cb before quoting line numbers).
