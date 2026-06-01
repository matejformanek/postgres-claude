# `src/backend/storage/smgr/bulk_write.c`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** 351
- **Source:** `source/src/backend/storage/smgr/bulk_write.c`

## Purpose

A bypass of the buffer manager for populating a *new* relation in bulk
(CREATE INDEX, REINDEX, CLUSTER, etc.). Bypassing bufmgr avoids buffer
lock and partition-lock overhead; the cost is that the new pages will
need a re-read once the build commits. Also responsible for WAL-logging
the new pages in batches and dealing with the
checkpoint-arrived-during-bulk-write race. [from-comment]
(`bulk_write.c:1-26`)

## Top of file

Caller assumes nobody else is writing the fork concurrently. Mixing
`smgr_bulk_*` with normal bufmgr access to the same relation/fork is
*undefined* behavior (`bulk_write.c:6-10`).

## Public surface (bulk_write.h)

- `smgr_bulk_start_rel(Relation, ForkNumber) → BulkWriteState *`
- `smgr_bulk_start_smgr(SMgrRelation, ForkNumber, bool use_wal)`
- `smgr_bulk_get_buf(BulkWriteState *) → BulkWriteBuffer` —
  IO-aligned, BLCKSZ-sized buffer.
- `smgr_bulk_write(BulkWriteState *, BlockNumber, BulkWriteBuffer,
  bool page_std)` — queues the page; takes ownership of the buffer.
- `smgr_bulk_finish(BulkWriteState *)` — flush + fsync/registersync.

## Types

- `BulkWriteState` (lines 61–79): SMgrRelation + fork + use_wal flag +
  pending-write queue (up to `XLR_MAX_BLOCK_ID` entries) + the
  `relsize` snapshot + `start_RedoRecPtr` taken at start.
- `PendingWrite` (lines 51–56): BulkWriteBuffer + blkno + page_std.

## Functions of note

**`smgr_bulk_flush` (lines 242–312)** — sorts the queue by blkno,
batches all pending pages into a single `log_newpages` WAL record (when
`use_wal`), then walks the queue in block order calling either
`smgrextend` or `smgrwrite`. If the block is past the current
`relsize`, fills the gap with all-zero `smgrextend` calls. All writes
pass `skipFsync=true` to avoid hammering the sync queue.
[verified-by-code]

**`smgr_bulk_finish` (lines 130–222)** — the tricky bit. Three branches:
1. Temp relation: do nothing (never fsync temp).
2. `!use_wal` (unlogged rel, or wal_level=minimal): conservatively
   `smgrregistersync` — checkpointer will sync at next/shutdown
   checkpoint. The wal_level=minimal case would technically need
   nothing here because `smgrDoPendingSyncs` handles it at commit, but
   we can't tell the two cases apart so we register sync regardless.
   [from-comment] (`bulk_write.c:145-180`)
3. `use_wal` (normal permanent rel): the checkpoint-race path. We set
   `MyProc->delayChkptFlags |= DELAY_CHKPT_START`, *then* compare
   `start_RedoRecPtr` against current `GetRedoRecPtr()`. If they
   differ, a checkpoint ran during our write — that checkpoint missed
   fsyncing our pages, so we fall back to `smgrimmedsync` and emit a
   DEBUG1. Otherwise, `smgrregistersync`. Clear the flag in either
   branch. [verified-by-code] (`bulk_write.c:198-220`)

## Invariants

- A given block must be written at most once per bulk-write session
  (queue dedup is asserted in `buffer_cmp`, `bulk_write.c:230-231`).
- `MAX_PENDING_WRITES = XLR_MAX_BLOCK_ID` so the batched WAL record
  fits.
- Checksum is set on each page in `smgr_bulk_flush` (line 282) right
  before the write.
- Buffers must be IO-aligned (palloc'd via `MemoryContextAllocAligned`
  with `PG_IO_ALIGN_SIZE`).

## Cross-refs

- Outbound: `smgrextend`, `smgrwrite`, `smgrnblocks`, `smgrregistersync`,
  `smgrimmedsync`, `log_newpages`, `GetRedoRecPtr`,
  `PageSetChecksum`.
- Used by: `nbtsort.c`, `gistbuild.c`, `_h_indexbuild` (hash),
  `spginsert`, `brinbuild`, etc. (Not verified file-by-file.)
  `[unverified]`

## Open questions

- The DELAY_CHKPT_START flag is read by xlog.c during checkpoint
  start; verifying the ordering against `GetRedoRecPtr()` would
  require reading `CheckpointerMain`. `[unverified]`

## Tag tally

`[verified-by-code]` 4 / `[from-comment]` 2 / `[unverified]` 2.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
