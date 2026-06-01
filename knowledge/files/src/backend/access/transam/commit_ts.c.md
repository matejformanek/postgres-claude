# commit_ts.c

- **Source path:** `source/src/backend/access/transam/commit_ts.c`
- **Lines:** 1035
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `source/src/include/access/commit_ts.h`, `slru.c`,
  `xact.c` (calls `TransactionTreeSetCommitTsData`), `replication/origin.c`.

## Purpose

SLRU storing `(commit timestamp, ReplOriginId)` per committed transaction.
Active only when `track_commit_timestamp = on`. Used by logical
replication conflict resolution and by `pg_xact_commit_timestamp` SQL
function. [from-comment] `commit_ts.c:3-13`.

## Top-of-file comment (verbatim)

```
commit_ts.c
    PostgreSQL commit timestamp manager

This module is a pg_xact-like system that stores the commit timestamp
for each transaction.

XLOG interactions: this module generates an XLOG record whenever a new
CommitTs page is initialized to zeroes.  Other writes of CommitTS come
from recording of transaction commit in xact.c, which generates its own
XLOG records for these events and will re-perform the status update on
redo; so we need make no additional XLOG entry here.
```
[from-comment] `commit_ts.c:3-13`.

## Public surface

- `TransactionTreeSetCommitTsData(xid, nsubxids, subxids, ts, nodeid)` —
  `commit_ts.c:150` [verified-by-code]
- `TransactionIdSetCommitTs(xid, ts, nodeid, slotno)` — `commit_ts.c:258`
  [verified-by-code]
- `TransactionIdGetCommitTsData(xid, *ts, *nodeid)` — `commit_ts.c:283`
  [verified-by-code]
- `GetLatestCommitTsData(*ts, *nodeid)` — `commit_ts.c:369` [verified-by-code]
- SQL accessors: `pg_xact_commit_timestamp`, `pg_last_committed_xact`,
  `pg_xact_commit_timestamp_origin` — `commit_ts.c:406, 429, 473`
  [verified-by-code]
- Shmem + lifecycle: `CommitTsShmemRequest`, `CommitTsShmemInit`,
  `BootStrapCommitTs`, `StartupCommitTs`, `CompleteCommitTsInitialization`,
  `CommitTsParameterChange`, `ActivateCommitTs`, `DeactivateCommitTs`,
  `CheckPointCommitTs`, `ExtendCommitTs`, `TruncateCommitTs`,
  `SetCommitTsLimit`, `AdvanceOldestCommitTsXid` — `commit_ts.c:515-952`
  [verified-by-code]
- `commit_ts_redo` — `commit_ts.c:995` [verified-by-code]

## Key types

- `CommitTimestampEntry { TimestampTz time; ReplOriginId nodeid; }`
  — 8 + 2 = 10 bytes per xact. [verified-by-code] `commit_ts.c:55-59`.

## Key invariants and locking

1. **WAL-free in steady state.** Only new-page zeroing emits a WAL
   record. `xact.c`'s commit record carries the timestamp; redo
   re-applies. [from-comment] `commit_ts.c:9-13`.

2. **Activation can happen at runtime** (`ActivateCommitTs`),
   parameter change handled by `CommitTsParameterChange`. The
   `commit_ts.c:645` body decides whether to enable/disable the
   feature. [verified-by-code]

3. **`TransactionTreeSetCommitTsData` chunks by SLRU page**,
   delegating to `SetXidCommitTsInPage` (`commit_ts.c:231`).

## Functions of note

### `TransactionTreeSetCommitTsData` — `commit_ts.c:150-…` [verified-by-code]

Called from `xact.c:RecordTransactionCommit` for every committing top
transaction tree (parent + subxacts).

### `TransactionIdGetCommitTsData` — `commit_ts.c:283-…` [verified-by-code]

Reads the SLRU page; raises an error if commit_ts is disabled
(`error_commit_ts_disabled` `commit_ts.c:390`).

### `ExtendCommitTs` — `commit_ts.c:821` [verified-by-code]

Called from `varsup.c:GetNewTransactionId` while holding `XidGenLock`,
parallel to `ExtendCLOG` / `ExtendSUBTRANS`.

### `commit_ts_redo` — `commit_ts.c:995` [verified-by-code]

Redo handler for `RM_COMMIT_TS_ID`: zero-page and truncate records.

## Cross-references

- `xact.c:RecordTransactionCommit` (`xact.c:1510`) calls
  `TransactionTreeSetCommitTsData`.
- `varsup.c:GetNewTransactionId` calls `ExtendCommitTs`.
- `replication/logical/origin.c` provides `ReplOriginId`.
- `slru.c` is the storage layer.

## Open questions

- The exact moment `track_commit_timestamp = off → on` becomes safe to
  query (the initialization handshake in
  `CompleteCommitTsInitialization`) not deep-read. [unverified]

## Confidence tag tally

- `[verified-by-code]`: 20
- `[from-comment]`: 3
- `[unverified]`: 1
