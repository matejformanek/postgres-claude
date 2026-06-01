# `src/include/storage/fd.h`

- **Last verified commit:** `ef6a95c7c64`

## Purpose

Public interface to fd.c: the VFD API plus the AllocateFile-family
wrappers plus the file-sync utility functions (fsync_fname,
durable_rename, etc.).

## Surface (high level)

GUCs / globals:
- `max_files_per_process`, `max_safe_fds`, `data_sync_retry`,
  `recovery_init_sync_method`, `io_direct_flags`, `file_extend_method`.

VFD core:
- `File` opaque integer handle; `PathNameOpenFile`,
  `OpenTemporaryFile`, `FileClose`, `FileReadV`, `FileWriteV`,
  `FileStartReadV` (AIO), `FileSync`, `FileZero`, `FileFallocate`,
  `FileSize`, `FileTruncate`, `FileWriteback`, `FilePrefetch`,
  `FilePathName`, `FileGetRawDesc`, `FileGetRawFlags`,
  `FileGetRawMode`.

PathName-temp:
- `PathNameCreateTemporaryFile`, `PathNameOpenTemporaryFile`,
  `PathNameDeleteTemporaryFile`, `PathNameCreateTemporaryDir`,
  `PathNameDeleteTemporaryDir`.

stdio-style wrappers (subtxn-cleaned):
- `AllocateFile`, `AllocateDir`, `OpenPipeStream`, `OpenTransientFile`
  + `FreeFile`/`FreeDir`/`ClosePipeStream`/`CloseTransientFile`.

Bare-open + external accounting:
- `BasicOpenFile`, `BasicOpenFilePerm`, `AcquireExternalFD`,
  `ReserveExternalFD`, `ReleaseExternalFD`, `set_max_safe_fds`.

fsync utilities:
- `pg_fsync`, `pg_fsync_no_writethrough`, `pg_fsync_writethrough`,
  `pg_fdatasync`, `pg_flush_data`, `pg_truncate`, `fsync_fname`,
  `durable_rename`, `durable_unlink`, `SyncDataDirectory`,
  `MakePGDirectory`.

## Tag tally

`[verified-by-code]` 1.
