# `src/backend/commands/sequence_xlog.c`

- **Last verified commit:** `c776550e4662` (re-pinned 2026-07-02; was `e18b0cb7344`. LOC ~80→81; 8e684ce11dda added one `XLogFlushBufferForRedoIfInit` call in `seq_redo`.)
- **Lines:** ~81
- **Source:** `source/src/backend/commands/sequence_xlog.c`

PG18+ split out of `sequence.c`: the RMGR redo and mask routines for
sequences. Tiny. The file's identification banner still reads
`sequence.c` (stale, since the split). [verified-by-code]

## API / entry points

- `seq_redo(record)` — RMGR redo callback for `RM_SEQ_ID`. Only
  knows one info opcode (`XLOG_SEQ_LOG`); anything else PANICs.
  Reinits the page each time. After the `memcpy` + `MarkBufferDirty`
  it calls `XLogFlushBufferForRedoIfInit(record, 0, buffer)`
  (`sequence_xlog.c:65`, new in 8e684ce11dda) — a no-op unless the
  sequence lives in an unlogged relation's init fork, in which case it
  flushes the buffer to disk so the reinit isn't lost when the init
  fork is copied to the main fork at end of recovery / on standby
  promotion. [verified-by-code]
- `seq_mask(page, blkno)` — RMGR mask callback used by
  `wal_consistency_checking` to zero out fields not bit-exactly
  reproducible (LSN, checksum, unused space). [verified-by-code]

## Notable invariants / details

- The "build in local workspace, then memcpy in" pattern (lines
  41-65) is mandatory: hot-standby readers may concurrently inspect
  the buffer, so we must not transiently trash it. PG's standard
  sequence-redo idiom. [from-comment]
- Local page is `palloc`'d to inherit `MAXALIGN`. Freed with `pfree`
  at the end. [from-comment]
- Page format: standard page + `sequence_magic` special area + a
  single item at `FirstOffsetNumber`. The XLOG payload is
  `xl_seq_rec` header followed by the item bytes. [verified-by-code]
- `seq_mask` masks LSN/checksum and unused space via the standard
  `bufmask.h` helpers; the item itself is bit-exact across
  primary/standby so no per-item masking needed.

## Potential issues

- Lines 50, 68. `palloc`/`pfree` of the local page on every redo —
  modest overhead for high-velocity sequence WAL traffic. A static
  buffer in `seq_redo` would suffice since startup-process redo is
  single-threaded. Probably never a real bottleneck. [ISSUE-style:
  palloc churn per redo (nit)]
- File comment header still says `sequence.c` (line 3). Cosmetic,
  but a `hf(docs)` candidate. [unverified]

## Synthesized by
<!-- backlinks:auto -->

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `commands`](../../../../issues/commands.md)
<!-- issues:auto:end -->
