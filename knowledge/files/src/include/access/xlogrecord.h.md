# xlogrecord.h

- **Source path:** `source/src/include/access/xlogrecord.h`
- **Lines:** 248
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `xloginsert.c` (writer), `xlogreader.c` (reader),
  `xlog.c`.

## Purpose

The on-disk WAL record format definitions. Front-end + backend
includable. Defines `XLogRecord` (the fixed 24-byte header),
the chain of `XLogRecordBlockHeader` + optional `XLogRecordBlockImageHeader`
+ optional `XLogRecordBlockCompressHeader` + per-block data + main data,
and the assorted flag bits. [from-comment] `xlogrecord.h:3-4`, `21-40`.

## Top-of-file comment (verbatim)

```
xlogrecord.h

Definitions for the WAL record format.
```
[verified-by-code] `xlogrecord.h:1-4`.

## Public surface (structs)

### `XLogRecord` (`xlogrecord.h:41-53`) [verified-by-code]

```
uint32        xl_tot_len   total len of entire record
TransactionId xl_xid       xact id
XLogRecPtr    xl_prev      ptr to previous record
uint8         xl_info      flag bits (high 4 = rmgr, low 4 = system)
RmgrId        xl_rmid      resource manager
(2 bytes pad)
pg_crc32c     xl_crc       CRC for this record
```

`SizeOfXLogRecord = offsetof(xl_crc) + sizeof(pg_crc32c)`.
[verified-by-code] `xlogrecord.h:55`.

### `XLogRecordBlockHeader` (`xlogrecord.h:103-113`) [verified-by-code]

`{ uint8 id; uint8 fork_flags; uint16 data_length; }`. Followed
optionally by `XLogRecordBlockImageHeader`, `RelFileLocator` (unless
`BKPBLOCK_SAME_REL`), and the `BlockNumber`. Not aligned: must be
copied to aligned storage before use. [from-comment] `xlogrecord.h:100-101`.

### `XLogRecordBlockImageHeader` (`xlogrecord.h:141-151`)
[verified-by-code]

`{ uint16 length; uint16 hole_offset; uint8 bimg_info; }`.

### `XLogRecordBlockCompressHeader` (`xlogrecord.h:173-176`)
[verified-by-code]

`{ uint16 hole_length; }` — only present when both `BKPIMAGE_HAS_HOLE`
and `BKPIMAGE_COMPRESSED()`.

### Main-data headers (`xlogrecord.h:213-225`) [verified-by-code]

`XLogRecordDataHeaderShort { uint8 id; uint8 data_length; }`.
`XLogRecordDataHeaderLong { uint8 id; uint32 data_length; }`
(unaligned). The structs are documentation-only — see comment.

## Key flag bits

### `xl_info` (`xlogrecord.h:62-91`) [verified-by-code]

- `XLR_INFO_MASK = 0x0F` (system bits).
- `XLR_RMGR_INFO_MASK = 0xF0` (rmgr opcode bits).
- `XLR_SPECIAL_REL_UPDATE = 0x01` — relation-files touched outside
  block refs (informational for external WAL readers).
- `XLR_CHECK_CONSISTENCY = 0x02` — force per-block FPI for
  consistency-check replay.

### `bimg_info` (`xlogrecord.h:157-167`) [verified-by-code]

- `BKPIMAGE_HAS_HOLE = 0x01` — standard-page hole removed.
- `BKPIMAGE_APPLY = 0x02` — page image should be restored during
  replay (vs. used only for consistency check).
- `BKPIMAGE_COMPRESS_PGLZ/LZ4/ZSTD = 0x04/0x08/0x10`.
- Macro `BKPIMAGE_COMPRESSED(info)` tests any of the three.

### `fork_flags` (`xlogrecord.h:196-202`) [verified-by-code]

- `BKPBLOCK_FORK_MASK = 0x0F` — fork number.
- `BKPBLOCK_FLAG_MASK = 0xF0`.
- `BKPBLOCK_HAS_IMAGE = 0x10`.
- `BKPBLOCK_HAS_DATA = 0x20`.
- `BKPBLOCK_WILL_INIT = 0x40` — redo re-inits.
- `BKPBLOCK_SAME_REL = 0x80` — `RelFileLocator` omitted (inherit
  from previous block).

### Reserved IDs (`xlogrecord.h:241-246`) [verified-by-code]

- `XLR_MAX_BLOCK_ID = 32` (in practice; rmgr-chosen up to this).
- `XLR_BLOCK_ID_DATA_SHORT = 255`.
- `XLR_BLOCK_ID_DATA_LONG = 254`.
- `XLR_BLOCK_ID_ORIGIN = 253`.
- `XLR_BLOCK_ID_TOPLEVEL_XID = 252`.

### Size limit

`XLogRecordMaxSize = 1020 * 1024 * 1024` (≈ MaxAllocSize - 4 MiB
overhead, to fit one decoded record in a `palloc`).
[from-comment] [verified-by-code] `xlogrecord.h:66-74`.

## Cross-references

- `xloginsert.c:XLogRecordAssemble` is the canonical writer.
- `xlogreader.c:DecodeXLogRecord` is the canonical reader.
- `xlog.c:CopyXLogRecordToWAL` copies the assembled record into the
  WAL buffers.
- `pg_waldump` / `pg_walinspect` use the headers for human-readable
  output.

## Open questions

None.

## Confidence tag tally

- `[verified-by-code]`: 13
- `[from-comment]`: 3

## Synthesized by
<!-- backlinks:auto -->
- [architecture/wal.md](../../../../architecture/wal.md)
- [subsystems/access-transam.md](../../../../subsystems/access-transam.md)