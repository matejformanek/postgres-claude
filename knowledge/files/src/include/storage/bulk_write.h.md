# `src/include/storage/bulk_write.h`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** 41

## Purpose

Public interface to bulk_write.c. Declares the opaque
`BulkWriteState` and the `BulkWriteBuffer` alias for
`PGIOAlignedBlock *` (separate typedef so callers can't accidentally
mix it with other block buffers).

## Surface

- `smgr_bulk_start_rel(Relation, ForkNumber)`
- `smgr_bulk_start_smgr(SMgrRelation, ForkNumber, bool use_wal)`
- `smgr_bulk_get_buf(BulkWriteState *)`
- `smgr_bulk_write(BulkWriteState *, BlockNumber, BulkWriteBuffer,
  bool page_std)`
- `smgr_bulk_finish(BulkWriteState *)`

## Tag tally

`[verified-by-code]` 1.
