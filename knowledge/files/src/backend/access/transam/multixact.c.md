# multixact.c

- **Source path:** `source/src/backend/access/transam/multixact.c`
- **Lines:** 3014
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `source/src/include/access/multixact.h`,
  `source/src/include/access/multixact_internal.h`,
  `slru.c` (storage layer), `heapam.c` (consumer for row-locking).

## Purpose

The pg_multixact SLRU manager. Stores, for each `MultiXactId`, a
variable-length array of `MultiXactMember` (`TransactionId` + flag bits)
used to express that multiple transactions hold locks (or lock-and-update)
on the same heap tuple. Two SLRUs are used: OFFSETs (fixed-size, indexed
by MXID) and MEMBERs (variable-length, indexed by offset). [from-comment]
`multixact.c:3-25`.

## Top-of-file comment (verbatim)

```
multixact.c
    PostgreSQL multi-transaction-log manager

The pg_multixact manager is a pg_xact-like manager that stores an array of
MultiXactMember for each MultiXactId.  It is a fundamental part of the
shared-row-lock implementation.  Each MultiXactMember is comprised of a
TransactionId and a set of flag bits.  ...

We use two SLRU areas, one for storing the offsets at which the data
starts for each MultiXactId in the other one.  This trick allows us to
store variable length arrays of TransactionIds.

XLOG interactions: this module generates a record whenever a new OFFSETs or
MEMBERs page is initialized to zeroes, as well as an
XLOG_MULTIXACT_CREATE_ID record whenever a new MultiXactId is defined.
This module ignores the WAL rule "write xlog before data," because it
suffices that actions recording a MultiXactId in a heap xmax do follow that
rule.  ...

Like clog.c, and unlike subtrans.c, we have to preserve state across
crashes and ensure that MXID and offset numbering increases monotonically
across a crash.
```
[from-comment] `multixact.c:3-49`.

## Public surface

- `MultiXactIdCreate(xid1, status1, xid2, status2)` — `multixact.c:358`
  [verified-by-code]
- `MultiXactIdExpand(multi, xid, status)` — `multixact.c:411`
  [verified-by-code]
- `MultiXactIdIsRunning(multi, isLockOnly)` — `multixact.c:522`
  [verified-by-code]
- `MultiXactIdSetOldestMember()` — `multixact.c:596` [verified-by-code]
- `MultiXactIdSetOldestVisible()` — `multixact.c:646` [verified-by-code]
- `ReadNextMultiXactId()` — `multixact.c:679` [verified-by-code]
- `ReadMultiXactIdRange(*oldest, *next)` — `multixact.c:696` [verified-by-code]
- `MultiXactIdCreateFromMembers(nmembers, members)` — `multixact.c:715`
  [verified-by-code]
- `GetMultiXactIdMembers(multi, **members, allow_old, isLockOnly)` —
  `multixact.c:1172` [verified-by-code]
- Two-phase commit hooks: `AtPrepare_MultiXact`, `PostPrepare_MultiXact`,
  `multixact_twophase_recover`, `multixact_twophase_postcommit`,
  `multixact_twophase_postabort` — `multixact.c:1656-1764`
  [verified-by-code]
- Shmem + startup: `MultiXactShmemRequest`, `MultiXactShmemInit`,
  `BootStrapMultiXact`, `StartupMultiXact`, `TrimMultiXact`,
  `CheckPointMultiXact` — `multixact.c:1766-2063` [verified-by-code]
- `MultiXactSetNextMXact(next, nextOffset)` — `multixact.c:2063`
  [verified-by-code]
- `SetMultiXactIdLimit(oldest_datminmxid, oldest_datoid)` — `multixact.c:2085`
  [verified-by-code]
- `MultiXactAdvanceNextMXact` / `MultiXactAdvanceOldest` —
  `multixact.c:2239, 2266` [verified-by-code]
- `ExtendMultiXactOffset` / `ExtendMultiXactMember` —
  `multixact.c:2283, 2317` [verified-by-code]
- `GetOldestMultiXactId` — `multixact.c:2378` [verified-by-code]
- `MultiXactMemberFreezeThreshold` — `multixact.c:2590` [verified-by-code]
- `multixact_redo` — (later in file; not located here) [unverified]

## Key types / constants

- `MULTIXACT_MEMBER_LOW_THRESHOLD = 2 000 000 000`,
  `_HIGH_THRESHOLD = 4 000 000 000` — disk-usage knobs for vacuum
  aggressiveness. [verified-by-code] `multixact.c:99-100`.
- `MultiXactMember` — `{ TransactionId xid; MultiXactStatus status; }`,
  defined in `multixact.h`.
- `MultiXactStatus` — enum of lock modes (FOR_KEY_SHARE, FOR_SHARE,
  FOR_NOKEY_UPDATE, FOR_UPDATE, NO_KEY_UPDATE, UPDATE) per
  `multixact.h`.
- Per-backend caches: `OldestMemberMXactId[]`, `OldestVisibleMXactId[]`,
  per-PGPROC slots. Used by `MultiXactIdSetOldestMember/Visible`.
  [verified-by-code] `multixact.c:240-280`.

## Key invariants and locking

1. **Two SLRUs (OFFSETs, MEMBERs) — wraparound-protected.** Counter
   advancement must stay outside the wraparound horizon computed from
   the global oldest MXID stored in pg_control + shared mem.
   [from-comment] `multixact.c:43-60`.

2. **MXID assignment respects WAL-before-data through the heap.**
   This module *ignores* the WAL-before-data rule itself because the
   heap update that places the MXID in `xmax` already follows it.
   [from-comment] `multixact.c:27-37`.

3. **Crash safety via redo replay rebuilding pages.** "XLOG records
   completely rebuild the data entered since the last checkpoint."
   `CheckPointMultiXact` flushes/syncs all dirty OFFSETs/MEMBERs
   before considering the checkpoint complete. [from-comment]
   `multixact.c:38-41`.

4. **OldestMember / OldestVisible interlock.** Backends register the
   oldest MXID they could need to look at (`SetOldestMember`) before
   creating or examining; vacuum uses the minimum to know what can be
   removed. [from-comment] [verified-by-code] `multixact.c:596-678`.

5. **Wraparound defenses at allocation.** Like XID, MXID allocation
   trips autovacuum / warn / stop levels via `SetMultiXactIdLimit`
   and `GetNewMultiXactId`. [verified-by-code]
   `multixact.c:979-…` (GetNewMultiXactId).

6. **MultiXactGenLock + MultiXactOffsetSLRULock / MembersSLRULock**
   ordering: `MultiXactGenLock` is taken to advance counters; SLRU
   bank locks come from slru.c. [unverified] — exact ordering not
   re-derived from a single comment.

## Functions of note

### `MultiXactIdCreate` — `multixact.c:358-410` [verified-by-code]

Creates a new MXID with two members (`xid1`, `xid2`). Wraps
`MultiXactIdCreateFromMembers(2, …)`.

### `MultiXactIdExpand` — `multixact.c:411-…` [verified-by-code]

Given an existing MXID and a new member, returns either the same MXID
(if the member is already present), or a freshly-allocated MXID with
the expanded set. The dedup + create logic is the hot path for
shared-row-locking concurrency.

### `MultiXactIdCreateFromMembers` — `multixact.c:715-815` [verified-by-code]

Cache-first lookup (`mXactCacheGetBySet`), then `GetNewMultiXactId` +
`RecordNewMultiXact` + WAL log (`XLOG_MULTIXACT_CREATE_ID`).

### `GetNewMultiXactId` — `multixact.c:979-…` [verified-by-code]

Mirror of `varsup.c:GetNewTransactionId` but for MXID. Holds
`MultiXactGenLock` exclusive; extends both SLRUs (`ExtendMultiXactOffset`,
`ExtendMultiXactMember`); enforces wraparound limits; advances
counters.

### `GetMultiXactIdMembers` — `multixact.c:1172-…` [verified-by-code]

The decode side: given an MXID, returns its member array. Reads the
OFFSETs page to find the offset and the next-MXID's offset (member
count = difference), then reads MEMBERs pages.

### `MultiXactIdIsRunning` — `multixact.c:522` [verified-by-code]

Used by tuple-visibility code. Walks the MXID's members and asks
`TransactionIdIsInProgress` for each non-aborted xid.

### `CheckPointMultiXact` — `multixact.c:2039` [verified-by-code]

Flushes dirty pages for both SLRUs. Required before the checkpoint
record is written (see invariant 3).

### `multixact_twophase_*` (recover/postcommit/postabort) —
`multixact.c:1719-1764` [verified-by-code]

Twophase-rmgr callbacks. On `PREPARE`, this records the prepared
xact's oldest-needed MXID via 2PC's per-rmgr state file; on recovery
it re-registers; on commit/abort it cleans up.

## Cross-references

- `heapam.c` is the primary consumer (`heap_lock_tuple`,
  `heap_update`, freeze code).
- `vacuumlazy.c` / `vacuum.c` truncate via `SetMultiXactIdLimit`.
- `procarray.c:GetOldestMultiXactId` is called by autovacuum / vacuum.
- `slru.c` provides shared buffer + LWLock infrastructure for both
  SLRUs.
- `twophase.c` calls into `*_twophase_*` callbacks.
- WAL: `RM_MULTIXACT_ID` rmgr entry (in `rmgrlist.h`); records:
  `XLOG_MULTIXACT_ZERO_OFF_PAGE`, `XLOG_MULTIXACT_ZERO_MEM_PAGE`,
  `XLOG_MULTIXACT_CREATE_ID`, `XLOG_MULTIXACT_TRUNCATE_ID`.
  [unverified] — exact names not re-located here.

## Open questions

- Locking ordering between `MultiXactGenLock`, `MultiXactOffsetSLRULock`,
  `MultiXactMemberSLRULock`, and the cache pin locks not re-derived.
  [unverified]
- The `mXactCache*` LRU is per-backend; eviction policy not analyzed.
  [unverified]
- Vacuum's interaction with `MULTIXACT_MEMBER_*_THRESHOLD` (which
  vacuum step inspects member usage) not located here. [unverified]

## Confidence tag tally

- `[verified-by-code]`: 32
- `[from-comment]`: 8
- `[unverified]`: 4
