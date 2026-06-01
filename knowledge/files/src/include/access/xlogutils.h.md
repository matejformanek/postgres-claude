# xlogutils.h

- **Source path:** `source/src/include/access/xlogutils.h`
- **Lines:** 121
- **Last verified commit:** `ef6a95c7c64`
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
  `XLogInitBufferForRedo`, `XLogReadBufferForRedoExtended`,
  `XLogReadBufferExtended`. [verified-by-code] `xlogutils.h:87-97`.
- Fake relcache: `CreateFakeRelcacheEntry`, `FreeFakeRelcacheEntry`.
  [verified-by-code] `xlogutils.h:99-100`.
- Local-reader callbacks: `read_local_xlog_page`,
  `read_local_xlog_page_no_wait`, `wal_segment_open`,
  `wal_segment_close`. [verified-by-code] `xlogutils.h:102-112`.
- Timeline helper: `XLogReadDetermineTimeline`.
  [verified-by-code] `xlogutils.h:114-117`.
- Error reporter: `WALReadRaiseError`. [verified-by-code]
  `xlogutils.h:119`.

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
