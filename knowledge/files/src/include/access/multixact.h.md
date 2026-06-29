# multixact.h

- **Source path:** `source/src/include/access/multixact.h`
- **Lines:** 159
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `multixact.c`, `heapam.c` (heavy user).

## Purpose

Public interface to pg_multixact. Defines `MultiXactId` / `MaxMultiXactId`,
the `MultiXactStatus` enum (lock modes), the `MultiXactMember` pair,
the WAL record types, and the function prototypes for create/expand/
read/freeze/truncate. [from-comment] `multixact.h:3-4`.

## Top-of-file comment (verbatim)

```
multixact.h

PostgreSQL multi-transaction-log manager
```
[verified-by-code] `multixact.h:1-4`.

## Key types / constants

- `InvalidMultiXactId = 0`, `FirstMultiXactId = 1`,
  `MaxMultiXactId = 0xFFFFFFFF`. [verified-by-code] `multixact.h:25-27`.
- `MultiXactStatus` (`multixact.h:36-46`) [verified-by-code]:
  - `ForKeyShare = 0x00`
  - `ForShare = 0x01`
  - `ForNoKeyUpdate = 0x02`
  - `ForUpdate = 0x03`
  - `NoKeyUpdate = 0x04` (update not touching key cols)
  - `Update = 0x05` (other updates + delete)
- `MaxMultiXactStatus = MultiXactStatusUpdate`. [verified-by-code]
- `ISUPDATE_from_mxstatus(status) = (status > ForUpdate)`.
  [verified-by-code] `multixact.h:51-52`.
- `MultiXactMember { TransactionId xid; MultiXactStatus status; }`.
  [verified-by-code] `multixact.h:55-59`.

## WAL opcodes

- `XLOG_MULTIXACT_ZERO_OFF_PAGE = 0x00`
- `XLOG_MULTIXACT_ZERO_MEM_PAGE = 0x10`
- `XLOG_MULTIXACT_CREATE_ID = 0x20`
- `XLOG_MULTIXACT_TRUNCATE_ID = 0x30`

[verified-by-code] `multixact.h:67-70`.

### `xl_multixact_create` (`multixact.h:72-78`) [verified-by-code]

`{ MultiXactId mid; MultiXactOffset moff; int32 nmembers;
MultiXactMember members[]; }`. `SizeOfMultiXactCreate =
offsetof(members)`.

### `xl_multixact_truncate` (`multixact.h:82-91`) [verified-by-code]

`{ Oid oldestMultiDB; MultiXactId oldestMulti; MultiXactOffset
oldestOffset; }`.

## Public surface

- Creation: `MultiXactIdCreate`, `MultiXactIdExpand`,
  `MultiXactIdCreateFromMembers` — `multixact.h:96-102`
  [verified-by-code]
- Read / scan: `ReadNextMultiXactId`, `ReadMultiXactIdRange`,
  `MultiXactIdIsRunning`, `MultiXactIdSetOldestMember`,
  `GetMultiXactIdMembers`, `GetMultiXactInfo` —
  `multixact.h:104-112` [verified-by-code]
- Comparison: `MultiXactIdPrecedes`,
  `MultiXactIdPrecedesOrEquals` — `multixact.h:113-115`
  [verified-by-code]
- Sync: `multixactoffsetssyncfiletag`,
  `multixactmemberssyncfiletag` — `multixact.h:117-118`
  [verified-by-code]
- xact hooks: `AtEOXact_MultiXact`, `AtPrepare_MultiXact`,
  `PostPrepare_MultiXact` — `multixact.h:120-122` [verified-by-code]
- Lifecycle: `BootStrapMultiXact`, `StartupMultiXact`,
  `TrimMultiXact`, `SetMultiXactIdLimit`, `MultiXactGetCheckptMulti`,
  `CheckPointMultiXact`, `GetOldestMultiXactId`, `TruncateMultiXact`,
  `MultiXactSetNextMXact`, `MultiXactAdvanceNextMXact`,
  `MultiXactAdvanceOldest`, `MultiXactMemberFreezeThreshold` —
  `multixact.h:124-143` [verified-by-code]
- 2PC: `multixact_twophase_recover/postcommit/postabort` —
  `multixact.h:145-150` [verified-by-code]
- WAL rmgr: `multixact_redo`, `multixact_desc`, `multixact_identify`
  — `multixact.h:152-154` [verified-by-code]
- Debug stringification: `mxid_to_string`, `mxstatus_to_string` —
  `multixact.h:155-157` [verified-by-code]

## Key invariants

1. **First two MXID values are reserved** for truncation Xid + epoch
   of first segment. [from-comment] `multixact.h:21-23`.

2. **Update statuses are exactly the two highest values.**
   `ISUPDATE_from_mxstatus` test exploits this. [verified-by-code]
   `multixact.h:51-52`.

## Cross-references

- `multixact.c` implements all prototypes.
- `heapam.c` consumes `MultiXactStatus` for `xmax` lock-mode encoding.
- `twophase_rmgr.c` plumbs the 2PC callbacks.

## Confidence tag tally

- `[verified-by-code]`: 26
- `[from-comment]`: 2

## Synthesized by
<!-- backlinks:auto -->
- [data-structures/multixactid.md](../../../../data-structures/multixactid.md)
- [idioms/multixact-slru.md](../../../../idioms/multixact-slru.md)
