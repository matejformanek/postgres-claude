# xlogreader.c

- **Source path:** `source/src/backend/access/transam/xlogreader.c`
- **Lines:** 2218
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `source/src/include/access/xlogreader.h`,
  `xlogrecord.h`, `xloginsert.c` (producer of the format), front-end
  tools (`pg_waldump`, `pg_rewind`, `pg_basebackup`).

## Purpose

The portable WAL-record decoder. Front-end-and-backend dual-build (no
`ereport`, no server statics). Validates record headers, reassembles
cross-page continuation records, optionally decompresses block images,
and exposes the decoded form via accessors like `XLogRecGetBlockTag`,
`XLogRecGetBlockData`, `RestoreBlockImage`. [from-comment]
`xlogreader.c:3-15`.

## Top-of-file comment (verbatim)

```
xlogreader.c
    Generic XLog reading facility
...
NOTES
    See xlogreader.h for more notes on this facility.

    This file is compiled as both front-end and backend code, so it
    may not use ereport, server-defined static variables, etc.
```
[verified-by-code] `xlogreader.c:3-15`.

## Public surface

Allocation + setup:

- `XLogReaderAllocate(wal_segment_size, waldir, ...)` —
  `xlogreader.c:108` [verified-by-code]
- `XLogReaderFree(state)` — `xlogreader.c:163` [verified-by-code]
- `XLogReaderSetDecodeBuffer` — `xlogreader.c:92` [verified-by-code]
- `WALOpenSegmentInit` — `xlogreader.c:209` [verified-by-code]
- `XLogBeginRead(state, RecPtr)` — `xlogreader.c:233` [verified-by-code]

Reading:

- `XLogReadRecord(state, **errormsg)` — `xlogreader.c:391`
  [verified-by-code]
- `XLogNextRecord(state, **errormsg)` — `xlogreader.c:327`
  [verified-by-code]
- `XLogReleasePreviousRecord(state)` — `xlogreader.c:251`
  [verified-by-code]
- `XLogReadAhead(state, nonblocking)` — `xlogreader.c:978`
  [verified-by-code]
- `XLogFindNextRecord` — `xlogreader.c:1401` [verified-by-code]
- `WALRead(state, ...)` — `xlogreader.c:1533` [verified-by-code]
- `ReadPageInternal` — `xlogreader.c:1012` [verified-by-code]

Decoding helpers (front-end safe):

- `XLogReadRecordAlloc`, `XLogDecodeNextRecord`, `DecodeXLogRecord`,
  `DecodeXLogRecordRequiredSpace`, `ResetDecoder` —
  `xlogreader.c:440-1701` [verified-by-code]

Validation:

- `ValidXLogRecordHeader` — `xlogreader.c:1139` [verified-by-code]
- `ValidXLogRecord` — `xlogreader.c:1205` [verified-by-code]
- `XLogReaderValidatePageHeader` — `xlogreader.c:1236`
  [verified-by-code]

Accessors over decoded record:

- `XLogRecGetBlockTag` / `…BlockTagExtended` / `XLogRecGetBlockData`
  — `xlogreader.c:2010, 2036, 2064` [verified-by-code]
- `RestoreBlockImage(record, block_id, page)` — `xlogreader.c:2095`
  [verified-by-code]
- `XLogRecGetFullXid(record)` — `xlogreader.c:2206` [verified-by-code]

Error reporting:

- `report_invalid_record` — `xlogreader.c:73` [verified-by-code]
- `XLogReaderInvalReadState` / `XLogReaderResetError` —
  `xlogreader.c:1125, 1377` [verified-by-code]

## Key types

- `XLogReaderState` — declared in `xlogreader.h`. Contains
  `DecodedXLogRecord` queue, current `ReadRecPtr`/`EndRecPtr`,
  read callback (`XLogReaderRoutine.page_read`), error-state buffer,
  decode-buffer pointer.
- `DecodedXLogRecord` — parsed record, with `XLogRecordBlockHeader[]`
  per-block info and pointers into a contiguous decode buffer.
- `XLogReaderRoutine` — function-pointer table:
  `page_read`, `segment_open`, `segment_close`.

## Key invariants and locking

1. **No `ereport`, no global statics.** This file is built into
   both backend and the frontend `libpgcommon`/`libpq` clients;
   error reporting uses `state->errormsg_buf`. [from-comment]
   `xlogreader.c:11-15`.

2. **`XLogReaderState` is single-threaded.** The reader is owned by
   the caller (startup process, walreceiver, pg_waldump);
   no internal locking.

3. **CRC validation.** `ValidXLogRecord` checks
   `pg_crc32c` over the record body including the header but
   excluding `xl_crc` itself. [verified-by-code] `xlogreader.c:1205-…`.

4. **Cross-page continuation records.** `XLogDecodeNextRecord`
   reassembles records that straddle WAL pages, validating the page
   header (`XLP_FIRST_IS_CONTRECORD`) at each step.

5. **`DecodeXLogRecordRequiredSpace`** lets the caller size the
   decode buffer up front; oversized records bypass the static
   buffer via `XLogReadRecordAlloc(allow_oversized=true)`.
   [verified-by-code] `xlogreader.c:1668, 440-…`.

6. **`RestoreBlockImage`** is the canonical FPI extractor: handles
   pglz/lz4/zstd decompression and the standard-page "hole"
   restoration. [verified-by-code] `xlogreader.c:2095-…`.

## Functions of note

### `XLogReadRecord` — `xlogreader.c:391-…` [verified-by-code]

Synchronous fetch-next. Calls `XLogDecodeNextRecord`; if more bytes
needed, calls `state->routine.page_read` (set by caller —
`XLogPageRead` in backend, file-fetch in front-end). Returns
`XLogRecord *` or NULL with `*errormsg` set.

### `DecodeXLogRecord` — `xlogreader.c:1701-…` [verified-by-code]

The big one: walks `XLogRecord` header → `XLogRecordBlockHeader`s →
`XLogRecordDataHeader{Short,Long}` → block images (with optional
compression flags). Fills a `DecodedXLogRecord` slot. Validates
buffer-image flags (`BKPBLOCK_HAS_IMAGE`, `BKPIMAGE_IS_COMPRESSED`,
`BKPIMAGE_APPLY`, etc.).

### `XLogFindNextRecord` — `xlogreader.c:1401-…` [verified-by-code]

Used at startup to seek the first valid record at-or-after a given
LSN, by scanning page headers for `XLP_LONG_HEADER` / valid
record-length fields. Used by `pg_rewind` and recovery initialization.

### `WALRead` — `xlogreader.c:1533-…` [verified-by-code]

Low-level read into the reader's segment file via the
`page_read`/`segment_open` callbacks; emits structured errors via
`WALReadError`.

## Cross-references

- `xlogrecovery.c:XLogPageRead` is the backend `page_read` callback.
- `xlogutils.c:wal_segment_open`/`_close`,
  `read_local_xlog_page*` are the helper callbacks.
- `xlogprefetcher.c` wraps the reader to issue async block fetches.
- `pg_waldump`, `pg_rewind`, `pg_basebackup` link the same .c file
  with their own callbacks.
- `xlogrecord.h` defines the wire format this file decodes.

## Open questions

- Compression dispatch in `RestoreBlockImage` covers pglz, lz4, zstd;
  exact decompression error handling not deep-read. [unverified]
- Buffer-image flag interactions (`BKPIMAGE_HAS_HOLE`,
  `BKPIMAGE_APPLY`, `BKPIMAGE_IS_COMPRESSED`) not enumerated here.
  [unverified]

## Confidence tag tally

- `[verified-by-code]`: 33
- `[from-comment]`: 2
- `[unverified]`: 2
