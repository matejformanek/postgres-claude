# xloginsert.h

- **Source path:** `source/src/include/access/xloginsert.h`
- **Lines:** 71
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `xloginsert.c`, `xlogrecord.h`, `xlog.h`,
  `README` (constructing-a-WAL-record narrative).

## Purpose

Tiny public header for the WAL-record construction API. Exposes
`REGBUF_*` flag bits, default working-buffer limits, and the seven
prototypes of `xloginsert.c`. [from-comment] `xloginsert.h:3-4`.

## Top-of-file comment (verbatim)

```
xloginsert.h

Functions for generating WAL records
```
[verified-by-code] `xloginsert.h:1-4`.

## Public surface

- `XLogBeginInsert`, `XLogSetRecordFlags`, `XLogInsert`,
  `XLogSimpleInsertInt64`, `XLogEnsureRecordSpace`, `XLogRegisterData`,
  `XLogRegisterBuffer`, `XLogRegisterBlock`, `XLogRegisterBufData`,
  `XLogResetInsertion`, `XLogCheckBufferNeedsBackup` — `xloginsert.h:44-56`
  [verified-by-code]
- `log_newpage`, `log_newpages`, `log_newpage_buffer`,
  `log_newpage_range` — `xloginsert.h:58-64` [verified-by-code]
- `XLogSaveBufferForHint`, `XLogGetFakeLSN`, `InitXLogInsert` —
  `xloginsert.h:65-69` [verified-by-code]

## Key constants

- `XLR_NORMAL_MAX_BLOCK_ID = 4`, `XLR_NORMAL_RDATAS = 20` — default
  scratch limits; `XLogEnsureRecordSpace` raises them.
  [verified-by-code] `xloginsert.h:28-29`.

## REGBUF flags (`xloginsert.h:31-41`) [verified-by-code]

```
REGBUF_FORCE_IMAGE  0x01    force FPI
REGBUF_NO_IMAGE     0x02    suppress FPI
REGBUF_WILL_INIT    0x06    (= FORCE | NO_IMAGE) page re-init at replay,
                            implies NO_IMAGE
REGBUF_STANDARD     0x08    standard page layout — skip the pd_lower..pd_upper
                            hole
REGBUF_KEEP_DATA    0x10    include rmgr data even with FPI
REGBUF_NO_CHANGE    0x20    intentional clean-buffer registration
```

## Cross-references

- `xloginsert.c` is the implementation.
- `xlogrecord.h` defines the actual on-wire structures (the
  `BKPBLOCK_*` / `BKPIMAGE_*` flag bits map roughly to these
  `REGBUF_*`).

## Open questions

None.

## Confidence tag tally

- `[verified-by-code]`: 7
- `[from-comment]`: 1

## Synthesized by
<!-- backlinks:auto -->
- [architecture/wal.md](../../../../architecture/wal.md)