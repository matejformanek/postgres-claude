# xlogarchive.c

- **Source path:** `source/src/backend/access/transam/xlogarchive.c`
- **Lines:** 726
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `source/src/include/access/xlogarchive.h`,
  `postmaster/pgarch.c` (archiver process), `xlog.c`,
  `xlogrecovery.c`, `common/archive.c`.

## Purpose

Backend-side helpers for the WAL archive. Two directions:

- Recovery: shell out to `restore_command` to fetch a WAL segment
  from the archive (`RestoreArchivedFile`).
- Live system: create `.ready` / `.done` markers in `archive_status/`
  for the archiver to act on (`XLogArchiveNotify*`,
  `XLogArchiveCheckDone`, etc.).

[from-comment] `xlogarchive.c:3-5`.

## Top-of-file comment (verbatim)

```
xlogarchive.c
   Functions for archiving WAL files and restoring from the archive.
```
[verified-by-code] `xlogarchive.c:3-4`.

## Public surface

- `RestoreArchivedFile(path, xlogfname, …)` — `xlogarchive.c:55`
  [verified-by-code]
- `ExecuteRecoveryCommand(command, commandName, …)` — `xlogarchive.c:296`
  [verified-by-code]
- `KeepFileRestoredFromArchive(path, xlogfname)` — `xlogarchive.c:359`
  [verified-by-code]
- `XLogArchiveNotify(xlog)` — `xlogarchive.c:445` [verified-by-code]
- `XLogArchiveNotifySeg(segno, tli)` — `xlogarchive.c:493`
  [verified-by-code]
- `XLogArchiveForceDone(xlog)` — `xlogarchive.c:511` [verified-by-code]
- `XLogArchiveCheckDone(xlog)` — `xlogarchive.c:566` [verified-by-code]
- `XLogArchiveIsBusy(xlog)` / `IsReadyOrDone(xlog)` / `IsReady(xlog)` —
  `xlogarchive.c:620, 665, 695` [verified-by-code]
- `XLogArchiveCleanup(xlog)` — `xlogarchive.c:713` [verified-by-code]

## Key invariants and locking

1. **`.ready` → archiver picks up → `.done`.** `XLogArchiveNotify`
   creates `<xlog>.ready`. The archiver renames to `.done` on
   success. [from-comment] `xlogarchive.c:445-…`.

2. **Recycling waits for archive completion.** `xlog.c:RemoveXlogFile`
   consults `XLogArchiveCheckDone` to know whether a segment may
   be recycled.

3. **`restore_command` is a shell command.** Substitutes
   `%f` / `%p` / `%r` via `common/percentrepl.c`; runs under
   `system()` with sigchld restored. [verified-by-code]
   `xlogarchive.c:55-295`.

4. **`KeepFileRestoredFromArchive`** is the rename of a restored
   segment into pg_wal; it also creates a `.done` marker so the file
   is not re-archived if it was originally produced here.

## Functions of note

### `RestoreArchivedFile` — `xlogarchive.c:55` [verified-by-code]

The recovery-time fetch. Builds command via
`BuildRestoreCommand`, runs it with `system()`, validates that the
file exists and is the right size before returning. PANIC on
SIGTERM/SIGQUIT from the child to avoid silent data corruption.

### `XLogArchiveCheckDone` — `xlogarchive.c:566` [verified-by-code]

Helper for `RemoveXlogFile`: returns true if segment has a `.done`
marker, segment is older than required, or archiving is disabled.

## Cross-references

- `postmaster/pgarch.c` is the consumer of `.ready` files.
- `xlog.c:RemoveOldXlogFiles` / `RemoveXlogFile` use the check
  functions.
- `xlogrecovery.c:WaitForWALToBecomeAvailable` uses
  `RestoreArchivedFile` to fetch missing segments.
- `walreceiver.c` does not go through here for streaming WAL.

## Open questions

- The signal-handling semantics around `system()` (SIGINT propagation,
  SIGCHLD restoration) not deep-read. [unverified]

## Confidence tag tally

- `[verified-by-code]`: 14
- `[from-comment]`: 2
- `[unverified]`: 1

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
