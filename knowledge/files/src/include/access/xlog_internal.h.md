# xlog_internal.h

- **Source path:** `source/src/include/access/xlog_internal.h`
- **Lines:** 407
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `xlog.c`, `xlogreader.c`, `xlogdefs.h`,
  `xlogrecord.h`. Front-end safe.

## Purpose

WAL-file-level internals: page headers, segment math, filename
encoding, the `RmgrData` struct (rmgr callback table entry), and
checkpoint record layout. Includable from front-end tools like
`pg_receivewal` and `pg_waldump`. [from-comment] `xlog_internal.h:5-12`.

## Top-of-file comment (verbatim)

```
xlog_internal.h

PostgreSQL write-ahead log internal declarations

NOTE: this file is intended to contain declarations useful for
manipulating the XLOG files directly, but it is not supposed to be
needed by rmgr routines ...

Note: This file must be includable in both frontend and backend contexts,
to allow stand-alone tools like pg_receivewal to deal with WAL files.
```
[verified-by-code] `xlog_internal.h:1-12`.

## Key types / constants

### `XLogPageHeaderData` (`xlog_internal.h:37-51`) [verified-by-code]

```
uint16     xlp_magic     XLOG_PAGE_MAGIC = 0xD120
uint16     xlp_info      flag bits
TimeLineID xlp_tli       TLI of first record on page
XLogRecPtr xlp_pageaddr  XLOG address of this page
uint32     xlp_rem_len   continuation: bytes remaining from prev page
```

### `XLogLongPageHeaderData` (`xlog_internal.h:62-68`)
[verified-by-code]

`{ XLogPageHeaderData std; uint64 xlp_sysid; uint32 xlp_seg_size;
uint32 xlp_xlog_blcksz; }`. First page of every segment has this.

`SizeOfXLogShortPHD` and `SizeOfXLogLongPHD` are MAXALIGN'd.

### `xlp_info` flags (`xlog_internal.h:75-81`) [verified-by-code]

`XLP_FIRST_IS_CONTRECORD = 0x0001`, `XLP_LONG_HEADER = 0x0002`,
`XLP_FIRST_IS_OVERWRITE_CONTRECORD = 0x0004`, `XLP_ALL_FLAGS = 0x0007`.

### Segment math constants

- `WalSegMinSize = 1 MB`, `WalSegMaxSize = 1 GB`.
  [verified-by-code] `xlog_internal.h:87-88`.
- `DEFAULT_MIN_WAL_SEGS = 5`, `DEFAULT_MAX_WAL_SEGS = 64`.
  [verified-by-code] `xlog_internal.h:90-91`.
- `IsValidWalSegSize(size)` = power of 2 and in
  [`WalSegMinSize`, `WalSegMaxSize`]. [verified-by-code]
  `xlog_internal.h:94-97`.
- `XLogSegmentsPerXLogId(s) = 2^32 / s`. [verified-by-code]
  `xlog_internal.h:99-100`.
- `XLByteToSeg` / `XLByteToPrevSeg` macros. [verified-by-code]
  `xlog_internal.h:116-120`.

### Other structures (below shown lines, present in file)

- `RmgrData` — the rmgr-table-entry struct with name, redo, desc,
  identify, startup, cleanup, mask, decode callbacks. [unverified]
- `CheckPoint`, `xl_end_of_recovery`, `xl_parameter_change`,
  `xl_overwrite_contrecord` — checkpoint and miscellaneous record
  payloads. [unverified] — not deep-read here.
- Filename macros (`XLogFileName`, `XLogFromFileName`, `TLHistoryFileName`,
  `IsTLHistoryFileName`, etc.). [unverified]

## Key invariants

1. **`XLOG_PAGE_MAGIC` is a WAL version indicator.** Change with any
   record-format change. [from-comment] `xlog_internal.h:35`.

2. **Continuation records.** When a record spans pages, the next
   page sets `XLP_FIRST_IS_CONTRECORD` and `xlp_rem_len` carries the
   remaining bytes. Continuation data is unaligned.
   [from-comment] `xlog_internal.h:44-50`.

3. **Front-end safety.** No backend-only includes here.
   [from-comment] `xlog_internal.h:11-12`.

## Cross-references

- `xlog.c` and `xlogreader.c` consume the page headers.
- `pg_waldump`, `pg_receivewal` link against this header.
- `rmgr.c` populates the `RmgrTable[]` of `RmgrData`.

## Open questions

- The full enumeration of `XLOG_*` opcodes, `CheckPoint` layout,
  and filename macros not done here. [unverified]

## Confidence tag tally

- `[verified-by-code]`: 16
- `[from-comment]`: 3
- `[unverified]`: 4
