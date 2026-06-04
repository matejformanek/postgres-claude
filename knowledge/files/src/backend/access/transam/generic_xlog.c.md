# generic_xlog.c

- **Source path:** `source/src/backend/access/transam/generic_xlog.c`
- **Lines:** 544
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `source/src/include/access/generic_xlog.h`,
  `xloginsert.c` (called by `GenericXLogFinish`).

## Purpose

Generic WAL: lets extensions (and core) record arbitrary page changes
without writing a custom rmgr. The producer registers buffers, edits
their image, and `GenericXLogFinish` computes a fragment-based delta
between the original and the edited page; redo simply applies the
delta. [from-comment] `generic_xlog.c:3-4`, `generic_xlog.c:22-43`.

## Top-of-file comment (verbatim)

```
generic_xlog.c
 Implementation of generic xlog records.
```
[verified-by-code] `generic_xlog.c:3-4`. Followed by an inline narrative
on the delta format (`generic_xlog.c:22-43`).

## Public surface

- `GenericXLogStart(Relation)` — `generic_xlog.c:269` [verified-by-code]
- `GenericXLogRegisterBuffer(state, buffer, flags)` — `generic_xlog.c:299`
  [verified-by-code]
- `GenericXLogFinish(state)` — `generic_xlog.c:337` [verified-by-code]
- `GenericXLogAbort(state)` — `generic_xlog.c:444` [verified-by-code]
- `generic_redo(XLogReaderState *)` — `generic_xlog.c:478` [verified-by-code]
- `generic_mask(page, blkno)` — `generic_xlog.c:539` [verified-by-code]

## Key types / constants

- `FRAGMENT_HEADER_SIZE = 2 * sizeof(OffsetNumber) = 4` bytes.
  [verified-by-code] `generic_xlog.c:45`.
- `MATCH_THRESHOLD = FRAGMENT_HEADER_SIZE` — fragments with smaller
  gaps are merged. [from-comment] [verified-by-code] `generic_xlog.c:34-46`.
- `MAX_DELTA_SIZE = BLCKSZ + 2 * FRAGMENT_HEADER_SIZE` — worst case
  per page. [verified-by-code] `generic_xlog.c:47`.
- `GenericXLogPageData` — `{ Buffer buffer; int flags; int deltaLen;
  char *image; char delta[MAX_DELTA_SIZE]; }`. [verified-by-code]
  `generic_xlog.c:50-58`.
- `GenericXLogState` — array of up to `MAX_GENERIC_XLOG_PAGES` page
  entries. Defined in this file. [verified-by-code] `generic_xlog.c:127-…`.

## Key invariants and locking

1. **Buffer must already be exclusive-locked.** Caller's responsibility;
   matches the README's "Step 1" of the WAL recipe.
   [from-README] (README:439-441).

2. **Critical section straddles delta-finish.** `GenericXLogFinish`
   enters `START_CRIT_SECTION`, `MarkBufferDirty`, `XLogInsert`,
   `PageSetLSN`, then `END_CRIT_SECTION`. [verified-by-code]
   `generic_xlog.c:337-…`.

3. **Fragments cannot span the page hole.** "We do not bother to merge
   fragments across the 'lower' and 'upper' parts of a page."
   [from-comment] `generic_xlog.c:37-43`.

4. **Worst-case delta is bigger than the page itself.** Same comment:
   "the worst-case delta size includes two fragment headers plus a full
   page's worth of data."

## Functions of note

### `GenericXLogStart` / `GenericXLogRegisterBuffer` —
`generic_xlog.c:269, 299` [verified-by-code]

Producer API. `Start` allocates a state object. `RegisterBuffer`
makes an aligned working copy of the original page that the caller
will mutate; the buffer reference is kept for `Finish`.

### `GenericXLogFinish` — `generic_xlog.c:337` [verified-by-code]

Computes the delta between the working image and the original
buffer page (`computeDelta` `generic_xlog.c:228`); under
`START_CRIT_SECTION`, copies the working image back into the buffer,
marks dirty, calls `XLogBeginInsert` + `XLogRegisterBuffer(…,
REGBUF_FORCE_IMAGE)` for any FPI-required pages or
`XLogRegisterBufData(delta)` for delta pages, then `XLogInsert`.
Updates page LSN.

### `generic_redo` — `generic_xlog.c:478-538` [verified-by-code]

Recovery handler for `RM_GENERIC_ID`. For each block, reads the page
via `XLogReadBufferForRedoExtended`; if FPI, the page is already
restored; otherwise `applyPageRedo(page, delta, len)` walks the
fragments and writes each into the page. PageSetLSN, MarkBufferDirty.

### `generic_mask` — `generic_xlog.c:539` [verified-by-code]

For `wal_consistency_checking`: masks volatile parts of the page
(LSN, etc.) so the original and replayed copies can be byte-compared.

## Cross-references

- `xloginsert.c`: `XLogBeginInsert` / `XLogRegisterBuffer` /
  `XLogRegisterBufData` / `XLogInsert`.
- `access/bufmask.h`: page masking helpers used by `generic_mask`.
- `RmgrTable[RM_GENERIC_ID]` in `rmgrlist.h` points
  `rm_redo = generic_redo`, `rm_mask = generic_mask`.
- `contrib/bloom` is the canonical core user of generic xlog.

## Open questions

- `MAX_GENERIC_XLOG_PAGES` value not located here; declared in
  `generic_xlog.h`. [unverified]
- Fragment-merging algorithm in `computeRegionDelta`/`computeDelta`
  not deep-read. [unverified]

## Confidence tag tally

- `[verified-by-code]`: 14
- `[from-comment]`: 3
- `[from-README]`: 1
- `[unverified]`: 2

## Synthesized by
<!-- backlinks:auto -->
- [architecture/wal.md](../../../../../architecture/wal.md)
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
