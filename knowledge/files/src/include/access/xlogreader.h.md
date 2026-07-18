# xlogreader.h

- **Source path:** `source/src/include/access/xlogreader.h`
- **Lines:** 444
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `xlogreader.c`, `xlogrecord.h`.

## Purpose

Public interface to the generic WAL reading facility. Front-end-and-
backend dual-build. Defines `XLogReaderState` (the reader handle),
`XLogReaderRoutine` (callback table), `DecodedXLogRecord`, and the
prototypes of all reader functions. [from-comment] `xlogreader.h:3-32`.

## Top-of-file comment (verbatim)

```
xlogreader.h
   Definitions for the generic XLog reading facility

NOTES
   See the definition of the XLogReaderState struct for instructions on
   how to use the XLogReader infrastructure.

   The basic idea is to allocate an XLogReaderState via
   XLogReaderAllocate(), position the reader to the first record with
   XLogBeginRead() or XLogFindNextRecord(), and call XLogReadRecord()
   until it returns NULL.

   Callers supply a page_read callback if they want to call
   XLogReadRecord or XLogFindNextRecord; ...

   After reading a record with XLogReadRecord(), it's decomposed into
   the per-block and main data parts, and the parts can be accessed
   with the XLogRec* macros and functions.
```
[verified-by-code] `xlogreader.h:1-32`.

## Public surface (types)

- `WALOpenSegment { int ws_file; XLogSegNo ws_segno; TimeLineID ws_tli; }`
  — `xlogreader.h:45-50` [verified-by-code]
- `WALSegmentContext { char ws_dir[MAXPGPATH]; int ws_segsize; }` —
  `xlogreader.h:53-57` [verified-by-code]
- `XLogPageReadCB`, `WALSegmentOpenCB`, `WALSegmentCloseCB` —
  callback types. [verified-by-code] `xlogreader.h:62-70`.
- `XLogReaderRoutine` — `{ page_read, segment_open, segment_close }`.
  [verified-by-code] `xlogreader.h:72-115`.
- `XL_ROUTINE(...)` — compound-literal helper macro for routine
  initialization. [verified-by-code] `xlogreader.h:117`.
- `XLogReaderState` (forward `xlogreader.h:59`, full def later in
  this header) — the reader handle.
- `DecodedXLogRecord` — the parsed record format with
  block-references array. (Not shown in the read snippet.)
- `WALReadError` — error info for `WALRead`. (Not shown.)

## Public surface (prototypes)

The deep `xlogreader.c` doc enumerates these — `XLogReaderAllocate`,
`XLogReaderFree`, `XLogBeginRead`, `XLogFindNextRecord`,
`XLogReadRecord`, `XLogNextRecord`, `XLogReleasePreviousRecord`,
`XLogReadAhead`, `WALRead`, `DecodeXLogRecord`, plus the
`XLogRecGet*` accessors. [verified-by-code] (full enumeration is
later in the file).

## Key invariants and locking

1. **Callback contract for `page_read`.** Must read at least
   `reqLen` bytes starting at `targetPagePtr`, return the actual
   byte count (≤ `XLOG_BLCKSZ`) or `-1`; may sleep waiting for
   bytes. [from-comment] `xlogreader.h:73-93`.

2. **`page_read` sets `state->seg.ws_tli`.** Required so the reader
   knows which TLI the page came from. [from-comment]
   `xlogreader.h:90-92`.

3. **`segment_open`'s `tli_p` is in/out.** Caller proposes a TLI;
   callback may return the actual TLI opened. [from-comment]
   `xlogreader.h:103-106`.

4. **`segment_close` sets `ws_file = -1`.** Documented contract.
   [from-comment] `xlogreader.h:110-113`.

5. **No `ereport`, no globals.** Implied by dual-build constraint
   (see xlogreader.c).

## Cross-references

- `xlogreader.c` — implementation.
- `xlogrecord.h` — wire format the reader decodes.
- `xlogrecovery.c:XLogPageRead` and `xlogutils.c:read_local_xlog_page`
  are the two backend `page_read` callbacks.
- `pg_waldump`, `pg_rewind`, `pg_basebackup`, `pg_walinspect`
  consume this header from front-end builds.

## Open questions

- The `XLogReaderState` struct definition and `DecodedXLogRecord`
  field layout not enumerated here (deeper in the file).
  [unverified]

## Confidence tag tally

- `[verified-by-code]`: 9
- `[from-comment]`: 5
- `[unverified]`: 1

## Synthesized by
<!-- backlinks:auto -->
- [data-structures/xlogreaderstate.md](../../../../data-structures/xlogreaderstate.md)

- [subsystems/access-transam.md](../../../../subsystems/access-transam.md)