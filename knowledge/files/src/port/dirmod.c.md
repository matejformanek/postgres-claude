---
path: src/port/dirmod.c
anchor_sha: e18b0cb7344
loc: 422
depth: read
---

# src/port/dirmod.c

## Purpose

Windows/Cygwin replacements for POSIX directory-manipulation functions:
`rename(2)`, `unlink(2)`, `symlink(2)`, `readlink(2)`. Symlinks on Windows
are emulated via NTFS **junction points** (reparse points of type
`IO_REPARSE_TAG_MOUNT_POINT`), which is the only mechanism that doesn't
require admin privileges. The whole file is gated by Windows-or-Cygwin
ifdefs; on real Unix it compiles to nothing. `[verified-by-code]`
`[from-comment]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `int pgrename(const char *from, const char *to)` | `dirmod.c:52` | Atomic rename with retry on sharing violations |
| `int pgunlink(const char *path)` | `:119` | Unlink with retry; handles junction-point case via `rmdir` |
| `int pgsymlink(const char *oldpath, const char *newpath)` (Win32 only) | `:219` | Creates an NTFS junction point |
| `int pgreadlink(const char *path, char *buf, size_t size)` (Win32 only) | `:309` | Reads junction-point target |

## Internal landmarks

- `pgrename` retry loop (`:64-94`) — `MoveFileEx(MOVEFILE_REPLACE_EXISTING)`
  with 100ms sleeps; caps at 100 loops = 10s. Retries only on
  `ERROR_ACCESS_DENIED`, `ERROR_SHARING_VIOLATION`, `ERROR_LOCK_VIOLATION`
  (antivirus / backup software). Comment notes "We don't expect real
  permission errors where we currently use rename()". `[from-comment]`
- `lstat_error_was_status_delete_pending` (`:104`) — detects the NT-level
  STATUS_DELETE_PENDING via `pg_RtlGetLastNtStatus()`, used to wait out
  files that are unlinked-but-still-open during recursive directory removal.
  `[from-comment]`
- `pgunlink` (`:119`) — fast path: try plain `unlink`. On EACCES, lstat to
  see if it's a junction (`S_ISLNK`); if so retry via `rmdir(path)`, else
  retry with `unlink`. 10s timeout on retry loop.
- `pgsymlink` (`:219`) — the heavy lifting:
  - `CreateDirectory` (the junction point must be a directory).
  - Open with `FILE_FLAG_OPEN_REPARSE_POINT | FILE_FLAG_BACKUP_SEMANTICS`.
  - Prepend `\??\` to oldpath to make it an "unparsed native win32 path"
    (`:240-243`).
  - Convert `/` to `\` (`:245-246`).
  - Build `REPARSE_JUNCTION_DATA_BUFFER` (`:197-207`) — local replacement
    for VC6's REPARSE_DATA_BUFFER, only the SymbolicLinkReparseBuffer union
    member. Convert path to wide chars.
  - `DeviceIoControl(FSCTL_SET_REPARSE_POINT)` (`:263-267`) — coded
    manually as `CTL_CODE(FILE_DEVICE_FILE_SYSTEM, 41, METHOD_BUFFERED,
    FILE_ANY_ACCESS)` because the SDK macro varies by version.
    `[from-comment]`
  - On failure, clean up `CreateDirectory` via `RemoveDirectory` and
    emit ereport(ERROR) or fprintf depending on FRONTEND.
- `pgreadlink` (`:309`) — analogous but reads the reparse point. On
  success, strips a leading `\??\X:\` (RtlPathTypeDriveAbsolute) prefix to
  return a user-friendly path. `[from-comment]`

## Invariants & gotchas

- **Junctions ≠ symlinks.** Junctions only work for directories (not
  files) and only within a single volume. PG only uses them to emulate
  tablespace symlinks in PGDATA, which fits both constraints. Future code
  that wanted file-level symlinks on Windows would need a different mechanism
  (true symbolic links require `SeCreateSymbolicLinkPrivilege` which
  unprivileged services don't have).
- **`\??\` prefix is mandatory.** NT-native paths use `\??\` for the
  "DosDevices" namespace; without it the junction would point to an
  invalid target. The `memcmp("\\??\\", oldpath, 4)` check at `:240`
  avoids double-prepending.
- **10s retry budget** on rename/unlink is a hard cap. AV scanners holding
  files for longer cause user-visible failures.
- **`pgrename` and `pgunlink` are #defined as `rename` / `unlink` at the
  bottom of the file** (`:182-183`) so the rest of the codebase can use
  the POSIX names but get our shim on Windows. The `#undef` at `:26-27`
  prevents recursion when redefining.
- The reparse-point control code `41` (FSCTL function code for
  SET_REPARSE_POINT) is hardcoded because the SDK macro
  `FSCTL_SET_REPARSE_POINT` has differed between versions. `[from-comment]`

## Cross-refs

- `source/src/backend/storage/file/fd.c` — primary consumer of `pgrename`
  / `pgunlink` (transparently via `#define rename pgrename`).
- `source/src/backend/commands/tablespace.c` — `pgsymlink` consumer for
  tablespace links.
- `knowledge/files/src/port/open.c.md` — sibling Windows shim.
- `knowledge/files/src/port/dirent.c.md` — sibling opendir/readdir shim.
