# xloginsert.c

- **Source path:** `source/src/backend/access/transam/xloginsert.c`
- **Lines:** 1441
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `source/src/include/access/{xloginsert.h,xlogrecord.h}`,
  `xlog.c` (`XLogInsertRecord`), `xlogreader.c` (decoding the format
  produced here), README §"Constructing a WAL record".

## Purpose

Producer-side WAL: collect registered buffers and data via the
`XLogBeginInsert → XLogRegister* → XLogInsert` API, decide which buffers
need full-page images, assemble the final `XLogRecData` chain, and hand
off to `xlog.c:XLogInsertRecord`. [from-comment] `xloginsert.c:3-13`.

## Top-of-file comment (verbatim)

```
xloginsert.c
    Functions for constructing WAL records

Constructing a WAL record begins with a call to XLogBeginInsert,
followed by a number of XLogRegister* calls. The registered data is
collected in private working memory, and finally assembled into a chain
of XLogRecData structs by a call to XLogRecordAssemble(). See
access/transam/README for details.
```
[from-comment] `xloginsert.c:3-9`.

## Public surface

- `XLogBeginInsert(void)` — `xloginsert.c:153` [verified-by-code]
- `XLogEnsureRecordSpace(int max_block_id, int ndatas)` — `xloginsert.c:179`
  [verified-by-code]
- `XLogResetInsertion(void)` — `xloginsert.c:226` [verified-by-code]
- `XLogRegisterBuffer(uint8, Buffer, uint8 flags)` — `xloginsert.c:246`
  [verified-by-code]
- `XLogRegisterBlock(uint8, RelFileLocator *, ForkNumber, BlockNumber, …)` —
  `xloginsert.c:317` [verified-by-code]
- `XLogRegisterData(const void *, uint32)` — `xloginsert.c:372` [verified-by-code]
- `XLogRegisterBufData(uint8, const void *, uint32)` — `xloginsert.c:413`
  [verified-by-code]
- `XLogSetRecordFlags(uint8 flags)` — `xloginsert.c:464` [verified-by-code]
- `XLogInsert(RmgrId, uint8 info)` — `xloginsert.c:482` [verified-by-code]
- `XLogSimpleInsertInt64` — `xloginsert.c:547` [verified-by-code]
- `XLogGetFakeLSN(Relation)` — `xloginsert.c:562` [verified-by-code]
- `XLogRecordAssemble(...)` — `xloginsert.c:621` [verified-by-code]
- `XLogCheckBufferNeedsBackup(Buffer)` — `xloginsert.c:1104`
  [verified-by-code]
- `XLogSaveBufferForHint(Buffer, bool buffer_std)` — `xloginsert.c:1134`
  [verified-by-code]
- `log_newpage` / `log_newpages` / `log_newpage_buffer` /
  `log_newpage_range` — `xloginsert.c:1191-1395` [verified-by-code]
- `InitXLogInsert(void)` — `xloginsert.c:1397` [verified-by-code]

## Key types / structs

- `registered_buffer[]` and `registered_data[]` — backend-local
  scratch areas built up by the `XLogRegister*` calls. (Static module
  state; not exposed.) Defaults: up to 5 block refs, 20 data chunks;
  raisable via `XLogEnsureRecordSpace`. [from-README] (README:546-553).
- `XLogRecData` — the chain produced by `XLogRecordAssemble` and
  consumed by `XLogInsertRecord`. Defined in `xlogrecord.h`.

## Key invariants and locking

1. **`XLogBeginInsert` is mandatory; `XLogInsert` errors if it wasn't
   called.** [verified-by-code] `xloginsert.c:486-488`.

2. **Info-mask rule.** Caller may set `XLR_RMGR_INFO_MASK`,
   `XLR_SPECIAL_REL_UPDATE`, `XLR_CHECK_CONSISTENCY`; other bits
   PANIC. [verified-by-code] `xloginsert.c:491-497`.

3. **FPI decision is racy without an insertion lock.** `XLogInsert`
   reads `GetFullPageWriteInfo` *before* taking the WAL insertion lock,
   then `XLogInsertRecord` rechecks; if the world changed
   (`runningBackups > 0`, `fullPageWrites` toggled, or a checkpoint
   advanced `RedoRecPtr`), it returns `InvalidXLogRecPtr` and the loop
   re-assembles. [from-comment] [verified-by-code] `xloginsert.c:522-535`.

4. **`XLogEnsureRecordSpace` must run before `XLogBeginInsert` and
   outside a critical section.** [from-README] (README:550-553).
   [unverified] — exact assertion not located here.

5. **Bootstrap mode short-circuits.** Non-`RM_XLOG_ID` records do
   nothing; returns the fixed `SizeOfXLogLongPHD` LSN. [verified-by-code]
   `xloginsert.c:505-510`.

## Functions of note

### `XLogInsert` — `xloginsert.c:482-540` [verified-by-code]

The user-facing assembly + insert. Sanity-checks info bits, then loops:
`GetFullPageWriteInfo` → `XLogRecordAssemble` → `XLogInsertRecord`; if
the latter returns `Invalid` (FPI race), re-loop. Calls
`XLogResetInsertion` on success.

### `XLogRecordAssemble` — `xloginsert.c:621-…` [verified-by-code]

Walks `registered_buffer[0..max_registered_block_id]` and decides for
each:

- If the buffer is dirty since RedoRecPtr (i.e. needs FPI),
  attach `BkpBlock` header + compressed/uncompressed page image.
- Compression dispatch on `wal_compression`: `PGLZ`, `LZ4`, `ZSTD`
  (built-in conditional on `USE_LZ4` / always `zstd`; see includes at
  `xloginsert.c:886-890`).
- Build the chained `XLogRecData` (`xl_rmid`, `xl_info`, `xl_tot_len`,
  `xl_xid`, body, then per-buffer `XLogRecordBlockHeader` + optional
  `BkpImage` + per-buffer data).
- Compute CRC over all chunks except `xl_crc`. [unverified] — full
  walk-through not done; this function is ~400 lines.

### `XLogRegisterBuffer` — `xloginsert.c:246-315` [verified-by-code]

Records a `Buffer` reference with flags from
`REGBUF_{FORCE_IMAGE,NO_IMAGE,WILL_INIT,STANDARD,KEEP_DATA}`. The
README's "Constructing a WAL record" section is the authoritative
spec; see `README:555-588`.

### `XLogSaveBufferForHint` — `xloginsert.c:1134-…` [verified-by-code]

Implements the `XLOG_FPI_FOR_HINT` path from README §"Writing Hints":
when a hint bit is being set on a buffer that has not yet been
modified since the last checkpoint and checksums are on, this emits a
full-page image so torn-page hazards are mitigated. The redo handler
just restores the page.

### `log_newpage*` family — `xloginsert.c:1191-1395` [verified-by-code]

The "page was completely rewritten" shortcut. `log_newpage` logs one
page; `log_newpages` logs a vector; `log_newpage_range` logs a range
of newly-extended pages. They emit `XLOG_FPI` records consumed by the
`xlog_redo` handler in `xlog.c` (the rmgr `RM_XLOG_ID`).

### `XLogGetFakeLSN(Relation)` — `xloginsert.c:562` [verified-by-code]

Returns a synthetic LSN for index AMs that need ordering markers on
unlogged or temp pages (no torn-page protection needed because data
doesn't survive crash anyway).

## Cross-references

- `xlog.c:XLogInsertRecord` is the consumer.
- `xlog.c:GetFullPageWriteInfo` provides the FPI inputs.
- `xlogreader.c` parses the format this file emits (see
  `XLogRecordBlockHeader`, `BkpImage` in `xlogrecord.h`).
- `rmgrlist.h` defines `RmgrId` values; `RM_XLOG_ID` handles the FPI
  and hint records produced here.
- Heap AM, btree, etc. are the heavy callers via
  `XLogRegister{Buffer,Data,BufData}`.

## Open questions

- Detailed FPI compression dispatch (`pglz_compress`, `LZ4_compress*`,
  `ZSTD_compress*`) not re-derived. [unverified]
- Exact assertions enforcing "XLogEnsureRecordSpace outside critical
  section" not located. [unverified]
- The `BkpImage` "hole" optimization for `REGBUF_STANDARD` (skipping
  `pd_lower..pd_upper`) implementation not deep-read. [unverified]

## Confidence tag tally

- `[verified-by-code]`: 18
- `[from-comment]`: 2
- `[from-README]`: 2
- `[unverified]`: 4

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
- [idioms/hint-bits-setbufferdirty.md](../../../../../idioms/hint-bits-setbufferdirty.md)
- [idioms/wal-record-construction.md](../../../../../idioms/wal-record-construction.md)

