# xlogarchive.h

- **Source path:** `source/src/include/access/xlogarchive.h`
- **Lines:** 35
- **Last verified commit:** `ef6a95c7c64`
- **Companion files:** `xlogarchive.c`.

## Purpose

Prototype-only header for the backend's WAL archive helpers.
[from-comment] `xlogarchive.h:3-4`.

## Top-of-file comment (verbatim)

```
xlogarchive.h
   Prototypes for WAL archives in the backend
```
[verified-by-code] `xlogarchive.h:3-4`.

## Public surface

- `RestoreArchivedFile(path, xlogfname, recovername, expectedSize, cleanupEnabled)` —
  `xlogarchive.h:20` [verified-by-code]
- `ExecuteRecoveryCommand(command, name, failOnSignal, wait_event_info)` —
  `xlogarchive.h:23` [verified-by-code]
- `KeepFileRestoredFromArchive(path, xlogfname)` — `xlogarchive.h:25`
  [verified-by-code]
- `XLogArchiveNotify(xlog)` / `XLogArchiveNotifySeg(segno, tli)` —
  `xlogarchive.h:26-27` [verified-by-code]
- `XLogArchiveForceDone(xlog)` — `xlogarchive.h:28` [verified-by-code]
- `XLogArchiveCheckDone(xlog)` — `xlogarchive.h:29` [verified-by-code]
- `XLogArchiveIsBusy(xlog)` / `_IsReady(xlog)` / `_IsReadyOrDone(xlog)` —
  `xlogarchive.h:30-32` [verified-by-code]
- `XLogArchiveCleanup(xlog)` — `xlogarchive.h:33` [verified-by-code]

## Cross-references

- `xlogarchive.c` is the implementation.

## Confidence tag tally

- `[verified-by-code]`: 10
- `[from-comment]`: 1

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/access-transam.md](../../../../subsystems/access-transam.md)
