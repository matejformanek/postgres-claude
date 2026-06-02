# xlogdefs.h

- **Source path:** `source/src/include/access/xlogdefs.h`
- **Lines:** 86
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `xlog.h`, `xlogrecord.h`, `xlogreader.h`,
  `transam.h`.

## Purpose

The smallest, most-includable WAL types: `XLogRecPtr` (uint64 LSN),
`XLogSegNo` (segment number), `TimeLineID` (uint32), `ReplOriginId`
(uint16), plus the default-sync-method selection macros.
[from-comment] `xlogdefs.h:3-5`.

## Top-of-file comment (verbatim)

```
xlogdefs.h

Postgres write-ahead log manager record pointer and
timeline number definitions
```
[verified-by-code] `xlogdefs.h:1-5`.

## Key types

- `XLogRecPtr = uint64` — pointer into the WAL byte stream.
  [verified-by-code] `xlogdefs.h:21`.
- `XLogSegNo = uint64` — segment-file sequence number.
  [verified-by-code] `xlogdefs.h:52`.
- `TimeLineID = uint32`. [verified-by-code] `xlogdefs.h:63`.
- `ReplOriginId = uint16` — declared here to avoid pulling in
  `origin.h` everywhere. [from-comment] [verified-by-code]
  `xlogdefs.h:65-69`.

## Constants / macros

- `InvalidXLogRecPtr = 0`. [verified-by-code] `xlogdefs.h:28`.
- `XLogRecPtrIsValid(r) = ((r) != 0)`,
  `XLogRecPtrIsInvalid(r) = ((r) == 0)`. [verified-by-code]
  `xlogdefs.h:29-30`.
- `FirstNormalUnloggedLSN = 1000` — first LSN handed out by
  `XLogGetFakeLSN` for unlogged relations; values below are
  reserved for AM-private uses. [from-comment] [verified-by-code]
  `xlogdefs.h:32-37`.
- `LSN_FORMAT_ARGS(lsn) = (uint32)(lsn >> 32), (uint32)(lsn)` —
  printf helper for `%X/%08X` output. [verified-by-code]
  `xlogdefs.h:47`.

## Sync-method default

```
#if defined(PLATFORM_DEFAULT_WAL_SYNC_METHOD)
  DEFAULT_WAL_SYNC_METHOD = PLATFORM_DEFAULT_WAL_SYNC_METHOD
#elif defined(O_DSYNC) && (!defined(O_SYNC) || O_DSYNC != O_SYNC)
  DEFAULT_WAL_SYNC_METHOD = WAL_SYNC_METHOD_OPEN_DSYNC
#else
  DEFAULT_WAL_SYNC_METHOD = WAL_SYNC_METHOD_FDATASYNC
#endif
```
[verified-by-code] `xlogdefs.h:78-84`.

## Key invariants

1. **`InvalidXLogRecPtr = 0` is safe** because bootstrap skips the
   first WAL segment, so no record starts at byte 0. [from-comment]
   `xlogdefs.h:23-26`.

2. **TLI changes only across PITR / promotion.** Not changed by
   crash recovery. [from-comment] `xlogdefs.h:55-61`.

## Cross-references

- `xlog.h` includes this for `XLogRecPtr` everywhere.
- `transam.h`, `xlogrecord.h`, `xlogreader.h` all depend on this.
- `replication/origin.h` uses `ReplOriginId`.

## Confidence tag tally

- `[verified-by-code]`: 12
- `[from-comment]`: 5

## Synthesized by
<!-- backlinks:auto -->
- [architecture/wal.md](../../../../architecture/wal.md)