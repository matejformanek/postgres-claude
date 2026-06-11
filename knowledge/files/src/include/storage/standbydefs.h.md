# `src/include/storage/standbydefs.h`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~75
- **Source:** `source/src/include/storage/standbydefs.h`

Frontend-exposed definitions for the **Standby Rmgr** (`RM_STANDBY_ID`)
WAL record layouts and resource-manager descriptor callbacks. Split
from the broader `standby.h` so that `pg_waldump` and other frontend
tools can decode standby-related WAL without pulling in the backend's
full `standby.h`. [from-comment]

## API / declarations

### Rmgr descriptor callbacks
- `standby_redo(XLogReaderState *record)` — redo dispatch for
  RM_STANDBY records (lock acquisition, running-xacts snapshots,
  invalidations) on a standby. [verified-by-code]
- `standby_desc(StringInfo buf, XLogReaderState *record)` —
  human-readable description (used by `pg_waldump`). [verified-by-code]
- `standby_identify(uint8 info)` — name the record type for
  introspection. [verified-by-code]
- `standby_desc_invalidations(StringInfo buf, int nmsgs,
  SharedInvalidationMessage *msgs, Oid dbId, Oid tsId, bool
  relcacheInitFileInval)` — separately-callable invalidations
  formatter (also used by the COMMIT rmgr's descriptor since commits
  carry inval messages too). [verified-by-code] [inferred]

### WAL message-type tags (info-byte high nibble)
- `XLOG_STANDBY_LOCK   = 0x00` — AccessExclusiveLock taken by
  primary that the standby must replay against its lock manager.
- `XLOG_RUNNING_XACTS  = 0x10` — periodic snapshot of currently-
  running xids so a standby can build a Hot-Standby visibility
  snapshot.
- `XLOG_INVALIDATIONS  = 0x20` — invalidation messages from XID-less
  commits (subxact-only or VACUUM). [verified-by-code]

### Record payloads
- `xl_standby_locks { int nlocks; xl_standby_lock locks[FAM]; }` —
  array of `xl_standby_lock` (defined in `standby.h`; carries db oid +
  relid + xid). [verified-by-code]
- `xl_running_xacts { int xcnt; int subxcnt; bool subxid_overflow;
  TransactionId nextXid; TransactionId oldestRunningXid; TransactionId
  latestCompletedXid; TransactionId xids[FAM]; }` — snapshot record.
  `subxid_overflow == true` means the standby must conservatively
  treat all subxids as in-flight. [verified-by-code] [from-comment]
- `xl_invalidations { Oid dbId; Oid tsId; bool relcacheInitFileInval;
  int nmsgs; SharedInvalidationMessage msgs[FAM]; }` — used when
  a transaction without an assigned xid (e.g. VACUUM, catalog-only
  cache flush) commits. [verified-by-code] [from-comment]
- `MinSizeOfInvalidations = offsetof(xl_invalidations, msgs)` —
  used to bounds-check WAL reads before indexing `msgs[]`. [verified-by-code]

## Notable invariants / details

- Three records, three info-byte tags — kept terse so the dispatcher
  in `standby_redo` is a single switch. New record types would force
  a backwards-compat decision (the upper info nibble is the only
  discriminator for RM_STANDBY). [inferred]
- `oldestRunningXid` is **not** `oldestXmin` (comment line 53). It's
  the smallest xid still in progress, not the snapshot horizon — a
  trap for anyone scanning this header looking for snapshot
  thresholds. [from-comment]
  [ISSUE-undocumented-invariant: `oldestRunningXid` vs `oldestXmin`
  distinction is in a one-line inline comment only; consumers reading
  the struct in isolation could conflate them (nit)]
- `subxid_overflow` boolean shrinks a potentially unbounded subxid
  list down to a one-bit "we're at the cap" flag. Standby visibility
  then conservatively treats any unknown xid as potentially in
  progress. [from-comment]
- The frontend split (this file vs `standby.h`) is the standard PG
  pattern for "let pg_waldump decode this without dragging in the
  backend's lock manager". [inferred]

## Potential issues

- Line 41. `xl_standby_lock` is forward-referenced; its actual layout
  lives in `standby.h`. A frontend tool including only `standbydefs.h`
  would still need to chase through. [verified-by-code]
  [ISSUE-doc-drift: `standbydefs.h` claims frontend exposure but
  depends on `xl_standby_lock` declared in the backend's `standby.h`
  (maybe)]
- Lines 38-70. All three payload structs use `FLEXIBLE_ARRAY_MEMBER`
  but only `xl_invalidations` exposes its `offsetof`-based
  `MinSizeOfInvalidations`. Decoders of `xl_standby_locks` and
  `xl_running_xacts` must compute the equivalent themselves. [verified-by-code]
  [ISSUE-api-shape: only `xl_invalidations` exposes a `MinSizeOf*`
  helper; `xl_standby_locks` and `xl_running_xacts` should likely
  follow suit (nit)]
- Lines 60-70. `xl_invalidations` carries `tsId` (tablespace OID)
  alongside `dbId`. The original Hot-Standby invalidation design
  used both for filtering, but in current code only `dbId` is
  consulted by `standby_redo`. Worth confirming whether `tsId` is
  still load-bearing. [unverified]
  [ISSUE-question: is `xl_invalidations.tsId` still consumed during
  redo, or is it vestigial? (nit)]
