# `src/include/storage/smgr.h`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** 144

## Purpose

Public interface to the storage-manager switch. Defines
`SMgrRelationData`/`SMgrRelation` (the cached-file-handle struct) and
declares every `smgr*` function implemented in smgr.c.

## Types

- `SMgrRelationData` (lines 35–70): rlocator (hashtable key), cached
  fork sizes (`smgr_cached_nblocks[]`, only reliable in recovery),
  target-block hint (`smgr_targblock`), the `smgr_which` index into
  `smgrsw[]`, md-private fields (`md_num_open_segs[]`,
  `md_seg_fds[]`), pin count, and dlist node for the unpinned list.
- `SmgrIsTemp(smgr)` macro (line 74): true if `smgr_rlocator.backend
  != INVALID_PROC_NUMBER`.

## Inline helpers

- `smgrread(reln, fork, blkno, buffer)` — wraps `smgrreadv` with
  nblocks=1.
- `smgrwrite(reln, fork, blkno, buffer, skipFsync)` — likewise.

## Cross-refs

- Defines surface used by `bufmgr.c`, `relcache.c`, every AM's
  recovery hook (`smgrcreate`, `smgrtruncate`).

## Tag tally

`[verified-by-code]` 3.
