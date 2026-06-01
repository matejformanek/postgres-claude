# `src/backend/storage/smgr/README`

- **Last verified commit:** `ef6a95c7c64`
- **Source:** `source/src/backend/storage/smgr/README`

## Purpose

Top-of-tree README for the smgr (storage manager) subsystem — the layer
between higher-level relation access and the kernel filesystem.

## Key claims (all `[from-README]`)

- Berkeley-era PG had multiple smgr implementations (WORM, persistent memory);
  only the "magnetic disk" smgr remains, but the dispatch switch (`smgrsw`)
  is kept in place against the future possibility (lines 8–17).
- The switch layer's overhead is negligible compared to storage I/O, so
  collapsing it would save nothing meaningful (line 14–17).
- The two files: `smgr.c` is the dispatch + SMgrRelation hashtable;
  `md.c` is the only implementation, wrapping kernel FS ops (lines 26–34).
- `md.c` relies on `src/backend/storage/file/fd.c` for VFD management
  (line 34) — i.e., the smgr does not call `open(2)` directly.

## Relation Forks (lines 37–52, all `[from-README]`)

- Since 8.4 a single smgr relation is multiple physical files ("forks").
- `MAIN_FORKNUM` (fork 0) is the heap; FSM, VM, init forks live alongside.
- Main fork is always assumed to exist.
- Fork numbers are assigned in `src/include/common/relpath.h`.
- All smgr/md functions take a `ForkNumber` arg in addition to
  rel-locator + block number.
- The buffer manager provides a `ReadBuffer` shortcut that defaults to
  `MAIN_FORKNUM` for convenience.

## Cross-refs

- See `knowledge/files/src/backend/storage/smgr/smgr.c.md` for the dispatch.
- See `knowledge/files/src/backend/storage/smgr/md.c.md` for the segment +
  fsync-request implementation.

## Tag tally

`[from-README]` 9 / `[unverified]` 0.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
