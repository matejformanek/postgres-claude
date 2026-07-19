# commit_ts.h

- **Source path:** `source/src/include/access/commit_ts.h`
- **Lines:** 60
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `commit_ts.c`.

## Purpose

Public interface for the commit-timestamp SLRU.

## Top-of-file comment (verbatim)

```
commit_ts.h

PostgreSQL commit timestamp manager
```
[verified-by-code] `commit_ts.h:1-4`.

## Public surface

- GUC extern `track_commit_timestamp`. [verified-by-code] `commit_ts.h:20`.
- `TransactionTreeSetCommitTsData(xid, nsubxids, subxids, ts, nodeid)`
  — `commit_ts.h:22` [verified-by-code]
- `TransactionIdGetCommitTsData(xid, *ts, *nodeid)` — `commit_ts.h:25`
  [verified-by-code]
- `GetLatestCommitTsData(*ts, *nodeid)` — `commit_ts.h:27`
  [verified-by-code]
- Lifecycle: `BootStrapCommitTs`, `StartupCommitTs`,
  `CommitTsParameterChange`, `CompleteCommitTsInitialization`,
  `CheckPointCommitTs`, `ExtendCommitTs`, `TruncateCommitTs`,
  `SetCommitTsLimit`, `AdvanceOldestCommitTsXid` —
  `commit_ts.h:30-39` [verified-by-code]
- `committssyncfiletag` — `commit_ts.h:41` [verified-by-code]
- WAL: `commit_ts_redo`, `commit_ts_desc`, `commit_ts_identify` —
  `commit_ts.h:56-58` [verified-by-code]

## WAL opcodes

- `COMMIT_TS_ZEROPAGE = 0x00`, `COMMIT_TS_TRUNCATE = 0x10` —
  `commit_ts.h:44-45` [verified-by-code]

## Key types

- `xl_commit_ts_truncate { int64 pageno; TransactionId oldestXid; }`,
  `SizeOfCommitTsTruncate = offsetof(oldestXid) + sizeof(TransactionId)`.
  [verified-by-code] `commit_ts.h:47-54`.

## Cross-references

- `commit_ts.c` is the implementation.
- `xact.c:RecordTransactionCommit` calls
  `TransactionTreeSetCommitTsData`.
- `replication/origin.h` provides `ReplOriginId`.

## Confidence tag tally

- `[verified-by-code]`: 14

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/access-transam.md](../../../../subsystems/access-transam.md)
