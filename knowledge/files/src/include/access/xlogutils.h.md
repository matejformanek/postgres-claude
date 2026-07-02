# xlogutils.h

- **Source path:** `source/src/include/access/xlogutils.h`
- **Lines:** 123
- **Last verified commit:** `c776550e4662` (re-pinned 2026-07-02; was `ef6a95c7c64`). 8e684ce11dda ("Fix unlogged sequence corruption after standby promotion") added the `XLogFlushBufferForRedoIfInit` prototype at `:90-91`, shifting all cites below it +2.
- **Companion files:** `xlogutils.c`, `xlogreader.h`.

## Purpose

Public surface of `xlogutils.c`: the `HotStandbyState` enum,
`InRecovery` / `standbyState` externs, the `XLogRedoAction` enum
(return codes for `XLogReadBufferForRedo[Extended]`), and all the
helper prototypes for redo handlers and local WAL readers.
[from-comment] `xlogutils.h:1-9`.

## Top-of-file comment (verbatim)

```
xlogutils.h

Utilities for replaying WAL records.
```
[verified-by-code] `xlogutils.h:1-4`.

## Key types

### `HotStandbyState` (`xlogutils.h:50-56`) [verified-by-code]

- `STANDBY_DISABLED` — crash recovery or HS turned off.
- `STANDBY_INITIALIZED` — `InitRecoveryTransactionEnvironment` done,
  but tracking not yet initialized from RUNNING_XACTS / shutdown-CKPT.
- `STANDBY_SNAPSHOT_PENDING` — tracking initialized but incomplete.
- `STANDBY_SNAPSHOT_READY` — connections OK; snapshots can be taken.

Macro `InHotStandby = (standbyState >= STANDBY_SNAPSHOT_PENDING)`.
[verified-by-code] `xlogutils.h:60`.

### `XLogRedoAction` (`xlogutils.h:72-79`) [verified-by-code]

`BLK_NEEDS_REDO`, `BLK_DONE`, `BLK_RESTORED`, `BLK_NOTFOUND`.

### `ReadLocalXLogPageNoWaitPrivate` (`xlogutils.h:82-85`)
[verified-by-code]

`{ bool end_of_wal; }`.

## Public surface

- GUC extern `ignore_invalid_pages`. [verified-by-code]
  `xlogutils.h:18`.
- Globals: `InRecovery` (startup-process-only), `standbyState`
  (startup-process-only — `STANDBY_DISABLED` everywhere else).
  [from-comment] [verified-by-code] `xlogutils.h:21-58`.
- Invalid-pages: `XLogHaveInvalidPages`, `XLogCheckInvalidPages`.
  [verified-by-code] `xlogutils.h:63-64`.
- Drop forwarding: `XLogDropRelation`, `XLogDropDatabase`,
  `XLogTruncateRelation`. [verified-by-code] `xlogutils.h:66-69`.
- Redo buffer helpers: `XLogReadBufferForRedo`,
  `XLogInitBufferForRedo`, `XLogFlushBufferForRedoIfInit` (**new** in
  8e684ce11dda — if `block_id`'s fork is `INIT_FORKNUM`, immediately
  `FlushOneBuffer(buffer)`. At end of crash recovery the init forks of
  unlogged relations are copied to the main fork *directly from disk*,
  bypassing shared buffers; so a redo routine that updates an init fork
  without a full-page image must flush after `PageSetLSN` +
  `MarkBufferDirty`, else the change is lost. This is the unlogged
  sequence-corruption fix; `seq_redo` and the hash-index redo handlers
  now call it), `XLogReadBufferForRedoExtended`,
  `XLogReadBufferExtended`. [verified-by-code] `xlogutils.h:87-99`.
- Fake relcache: `CreateFakeRelcacheEntry`, `FreeFakeRelcacheEntry`.
  [verified-by-code] `xlogutils.h:101-102`.
- Local-reader callbacks: `read_local_xlog_page`,
  `read_local_xlog_page_no_wait`, `wal_segment_open`,
  `wal_segment_close`. [verified-by-code] `xlogutils.h:104-114`.
- Timeline helper: `XLogReadDetermineTimeline`.
  [verified-by-code] `xlogutils.h:116-119`.
- Error reporter: `WALReadRaiseError`. [verified-by-code]
  `xlogutils.h:121`.

## Key invariants

1. **`InRecovery` and `standbyState` are only valid in the startup
   process.** Other backends see `STANDBY_DISABLED` and should test
   `RecoveryInProgress()` instead. [from-comment] `xlogutils.h:21-58`.

## Cross-references

- `xlogutils.c` implements all prototypes.
- Every redo handler in the source tree includes this header.

## Confidence tag tally

- `[verified-by-code]`: 16
- `[from-comment]`: 2

## Synthesized by
<!-- backlinks:auto -->
- [idioms/xlog-region-replay.md](../../../../idioms/xlog-region-replay.md)
