# xact.h

- **Source path:** `source/src/include/access/xact.h`
- **Lines:** 538
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `xact.c` (implementation),
  `source/src/backend/access/rmgrdesc/xactdesc.c` (parse helpers shared
  front/back).

## Purpose

Public interface for `xact.c`: isolation/read-only/deferrable GUCs,
`synchronous_commit` enum, `XactEvent`/`SubXactEvent` callback types,
`MyXactFlags` bits, the full WAL record layout for `XLOG_XACT_*`
records, and all extern prototypes. [from-comment] `xact.h:3-12`.

## Top-of-file comment (verbatim)

```
xact.h
   postgres transaction system definitions
```
[verified-by-code] `xact.h:3-4`.

## Public surface (selection)

GUC variables: `DefaultXactIsoLevel`, `XactIsoLevel`,
`DefaultXactReadOnly`, `XactReadOnly`, `DefaultXactDeferrable`,
`XactDeferrable`, `synchronous_commit`, `xact_is_sampled`,
`CheckXidAlive`, `bsysscan`, `MyXactFlags`. [verified-by-code]
`xact.h:41-97`.

State/entry functions (all `extern`): `IsTransactionState`,
`IsAbortedTransactionBlockState`, `GetTop*TransactionId*`,
`GetCurrent*TransactionId*`, `CommandCounterIncrement`,
`ForceSyncCommit`, `StartTransactionCommand`,
`CommitTransactionCommand`, `AbortCurrentTransaction`,
`BeginTransactionBlock`, `EndTransactionBlock`,
`PrepareTransactionBlock`, `UserAbortTransactionBlock`,
`BeginImplicitTransactionBlock`/`End`, savepoint family,
`BeginInternalSubTransaction`, `ReleaseCurrentSubTransaction`,
`RollbackAndReleaseCurrentSubTransaction`, parallel-bridge
`EnterParallelMode`/`ExitParallelMode`/`IsInParallelMode`,
serialization helpers, callback registrar, `XactLogCommitRecord`,
`XactLogAbortRecord`, `xact_redo`, parse helpers.
[verified-by-code] `xact.h:440-537`.

## Key types / structs

### Enums

- `SyncCommitLevel` — `SYNCHRONOUS_COMMIT_OFF`, `_LOCAL_FLUSH`,
  `_REMOTE_WRITE`, `_REMOTE_FLUSH` (default `ON`), `_REMOTE_APPLY`.
  [verified-by-code] `xact.h:69-78`.
- `XactEvent` — `COMMIT`, `PARALLEL_COMMIT`, `ABORT`,
  `PARALLEL_ABORT`, `PREPARE`, `PRE_COMMIT`, `PARALLEL_PRE_COMMIT`,
  `PRE_PREPARE`. [verified-by-code] `xact.h:127-137`.
- `SubXactEvent` — `START_SUB`, `COMMIT_SUB`, `ABORT_SUB`,
  `PRE_COMMIT_SUB`. [verified-by-code] `xact.h:141-147`.

### Flag bits

- Isolation: `XACT_READ_UNCOMMITTED..XACT_SERIALIZABLE`.
  [verified-by-code] `xact.h:36-39`.
- `MyXactFlags`: `XACT_FLAGS_ACCESSEDTEMPNAMESPACE` (no PREPARE),
  `_ACQUIREDACCESSEXCLUSIVELOCK`, `_NEEDIMMEDIATECOMMIT`,
  `_PIPELINING`. [verified-by-code] `xact.h:103-122`.

### XLOG opcodes (in `xl_info`)

`XLOG_XACT_COMMIT = 0x00`, `_PREPARE = 0x10`, `_ABORT = 0x20`,
`_COMMIT_PREPARED = 0x30`, `_ABORT_PREPARED = 0x40`,
`_ASSIGNMENT = 0x50`, `_INVALIDATIONS = 0x60`. `XLOG_XACT_OPMASK =
0x70`; `XLOG_XACT_HAS_INFO = 0x80` indicates a following `xinfo`
field. [verified-by-code] `xact.h:170-183`.

### xinfo bits (`xl_xact_xinfo.xinfo`)

`XACT_XINFO_HAS_{DBINFO, SUBXACTS, RELFILELOCATORS, INVALS,
TWOPHASE, ORIGIN, AE_LOCKS, GID, DROPPED_STATS}` and the high-bit
`XACT_COMPLETION_*` triplet (`APPLY_FEEDBACK`,
`UPDATE_RELCACHE_FILE`, `FORCE_SYNC_COMMIT`). [verified-by-code]
`xact.h:189-217`.

### WAL record structs

- `xl_xact_assignment` (top + sub xids) — `xact.h:219-226`.
- `xl_xact_xinfo` (uint32 padded for alignment) —
  `xact.h:245-254`.
- `xl_xact_dbinfo` (`{dbId, tsId}`) — `xact.h:256-260`.
- `xl_xact_subxacts`, `xl_xact_relfilelocators`,
  `xl_xact_stats_item(s)`, `xl_xact_invals`, `xl_xact_twophase`,
  `xl_xact_origin` — `xact.h:262-319`.
- `xl_xact_commit { TimestampTz xact_time; }` followed by optional
  records as documented in the comment block. [from-comment]
  `xact.h:321-335`.
- `xl_xact_abort` — same pattern, no invals. `xact.h:337-351`.
- `xl_xact_prepare` (`magic`, `total_len`, `xid`, `database`,
  `prepared_at`, `owner`, `nsubxacts`, `ncommitrels`, `nabortrels`,
  `ncommitstats`, `nabortstats`, `ninvalmsgs`, `initfileinval`,
  `gidlen`, `origin_lsn`, `origin_timestamp`). [verified-by-code]
  `xact.h:353-371`.
- `xl_xact_parsed_commit` / `_abort` / `_prepare` — deconstructed
  views built by the parse helpers. [verified-by-code]
  `xact.h:378-433`.

### Other

- `SavedTransactionCharacteristics` — `{ save_XactIsoLevel,
  save_XactReadOnly, save_XactDeferrable }`. [verified-by-code]
  `xact.h:153-158`.
- `GIDSIZE = 200` — max GID length including NUL.
  [verified-by-code] `xact.h:31`.

## Key invariants and locking

1. **Alignment.** "All the individual data chunks should be sized to
   multiples of sizeof(int) and only require int32 alignment."
   [from-comment] `xact.h:238-240`.

2. **`xl_xact_origin` stored unaligned.** Documented in the
   `xl_xact_commit` "follows if" comment. [from-comment]
   `xact.h:333`.

3. **Isolation macros.** `IsolationUsesXactSnapshot() = (XactIsoLevel
   >= XACT_REPEATABLE_READ)`; `IsolationIsSerializable() =
   (XactIsoLevel == XACT_SERIALIZABLE)`. [verified-by-code]
   `xact.h:52-53`.

## Cross-references

- `xact.c` implements all the extern prototypes.
- `rmgrdesc/xactdesc.c` implements `xact_desc`, `xact_identify`,
  and the three `Parse*Record` helpers (front-end-safe).
- `twophase.c` uses `xl_xact_prepare` / commit/abort with
  `twophase_xid`.

## Open questions

None significant.

## Confidence tag tally

- `[verified-by-code]`: 22
- `[from-comment]`: 3

## Synthesized by
<!-- backlinks:auto -->
- [idioms/subtransaction-stack.md](../../../../idioms/subtransaction-stack.md)

- [subsystems/access-transam.md](../../../../subsystems/access-transam.md)