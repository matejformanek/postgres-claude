# `src/include/storage/sync.h`

- **Last verified commit:** `ef6a95c7c64`
- **Lines:** 67

## Purpose

Public interface of the fsync-request subsystem (sync.c) and the
shared `FileTag` type used by both the queue and the per-handler
callbacks.

## Types

- `SyncRequestType` enum: `SYNC_REQUEST`, `SYNC_UNLINK_REQUEST`,
  `SYNC_FORGET_REQUEST`, `SYNC_FILTER_REQUEST`.
- `SyncRequestHandler` enum: `SYNC_HANDLER_MD`, `…_CLOG`,
  `…_COMMIT_TS`, `…_MULTIXACT_OFFSET`, `…_MULTIXACT_MEMBER`,
  `SYNC_HANDLER_NONE`.
- `FileTag` struct (lines 50–56): `int16 handler` + `int16 forknum`
  + `RelFileLocator rlocator` + `uint64 segno`. Comment notes that
  sync.c has no knowledge of internal structure — fields are
  whatever md.c (the primary user) needs.

## Surface

- `InitSync`, `SyncPreCheckpoint`, `SyncPostCheckpoint`,
  `ProcessSyncRequests`, `RememberSyncRequest`,
  `RegisterSyncRequest`.

## Tag tally

`[verified-by-code]` 2.
