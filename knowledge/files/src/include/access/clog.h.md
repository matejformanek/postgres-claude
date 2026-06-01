# clog.h

- **Source path:** `source/src/include/access/clog.h`
- **Lines:** 60
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `clog.c`.

## Purpose

Public interface to pg_xact. Exports the `XidStatus` codes, the
`xl_clog_truncate` WAL payload, and the function prototypes used by
`xact.c` / `transam.c` / `varsup.c`. [from-comment] `clog.h:3-4`.

## Top-of-file comment (verbatim)

```
clog.h

PostgreSQL transaction-commit-log manager
```
[verified-by-code] `clog.h:1-4`.

## Key types / constants

- `XidStatus = int`; `TRANSACTION_STATUS_IN_PROGRESS = 0x00`,
  `_COMMITTED = 0x01`, `_ABORTED = 0x02`, `_SUB_COMMITTED = 0x03`.
  [verified-by-code] `clog.h:25-30`.
- `xl_clog_truncate { int64 pageno; TransactionId oldestXact; Oid
  oldestXactDb; }`. [verified-by-code] `clog.h:32-37`.

## WAL opcodes (`xl_info`)

- `CLOG_ZEROPAGE = 0x00`. [verified-by-code] `clog.h:53`.
- `CLOG_TRUNCATE = 0x10`. [verified-by-code] `clog.h:54`.

## Public surface

- `TransactionIdSetTreeStatus(xid, nsubxids, subxids, status, lsn)` —
  `clog.h:39` [verified-by-code]
- `TransactionIdGetStatus(xid, *lsn)` — `clog.h:41` [verified-by-code]
- `BootStrapCLOG`, `StartupCLOG`, `TrimCLOG`, `CheckPointCLOG`,
  `ExtendCLOG`, `TruncateCLOG` — `clog.h:43-48` [verified-by-code]
- `clogsyncfiletag`, `clog_redo`, `clog_desc`, `clog_identify` —
  `clog.h:50, 56-58` [verified-by-code]

## Key invariants

1. **All-zeroes is "in progress".** Initial-state semantics matches
   page-zeroing. [from-comment] `clog.h:19-20`.

2. **SUB_COMMITTED is transient.** "A subcommitted transaction is a
   committed subtransaction whose parent hasn't committed or aborted
   yet." Marked subcommitted only briefly during multi-page commit
   (see README §pg_xact). [from-comment] `clog.h:22-23`.

## Cross-references

- `clog.c` is the implementation.
- `transam.c:TransactionIdDidCommit` consumes
  `TransactionIdGetStatus`.
- `xact.c:RecordTransactionCommit` writes via
  `TransactionIdCommitTree` (in `transam.c`) which calls
  `TransactionIdSetTreeStatus`.

## Confidence tag tally

- `[verified-by-code]`: 8
- `[from-comment]`: 2
