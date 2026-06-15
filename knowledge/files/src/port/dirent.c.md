---
path: src/port/dirent.c
anchor_sha: e18b0cb7344
loc: 137
depth: read
---

# src/port/dirent.c

## Purpose

Win32/MSVC implementation of POSIX `opendir`/`readdir`/`closedir`. The CRT
doesn't ship a `dirent` family, so PG provides one wrapping `FindFirstFile`/
`FindNextFile`. Also synthesizes a `d_type` field (DT_LNK / DT_DIR / DT_REG)
by inspecting Win32 file attributes — including treating
`IO_REPARSE_TAG_MOUNT_POINT` junctions as `DT_LNK` so recursive directory
walks see them as symlinks, matching PG's `pgsymlink` convention. Whole
file is implicitly Windows-only (only included in Win32 builds; no `#ifdef
WIN32` because the standalone dirent.h declaration covers it).
`[verified-by-code]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `DIR *opendir(const char *dirname)` | `dirent.c:33` | Opens a directory iterator; NULL on failure |
| `struct dirent *readdir(DIR *d)` | `:78` | Returns pointer to internal `d_name` buffer (not malloc'd); NULL at end |
| `int closedir(DIR *d)` | `:127` | Closes the handle; returns 0 on success |

(`struct DIR` defined here at `:25`.)

## Internal landmarks

- `opendir` (`:33`) — `GetFileAttributes` preflight to reject non-existent
  paths (ENOENT) and non-directories (ENOTDIR), then `malloc` a `DIR` and a
  pattern string of the form `"dirname\\*"` (appending `\` if not already
  trailing). The actual FindFirstFile call is deferred to the first
  `readdir`. `[verified-by-code]`
- `readdir` (`:78`) — first call invokes `FindFirstFile(d->dirname, &fd)`,
  subsequent calls do `FindNextFile(d->handle, &fd)`. End-of-stream sets
  `errno = 0` (matching mingw's behavior) and returns NULL. Other errors
  go through `_dosmaperr`.
- `d_type` synthesis (`:111-121`) — three-way cascade:
  - reparse point with tag MOUNT_POINT → DT_LNK (junction-emulated symlink)
  - directory attribute → DT_DIR
  - else → DT_REG
  The reparse check is **first** because junctions also have the directory
  attribute set, and the caller cares more about "is this a link" than
  "is this a dir". `[verified-by-code]` `[from-comment]`
- `closedir` (`:127`) — `FindClose` on the handle (if valid), free both
  the dirname string and the DIR struct. The handle may be invalid if no
  readdir was ever called.

## Invariants & gotchas

- **`d_ino = 0` always** (`:70`). Win32 doesn't expose inode numbers via
  `WIN32_FIND_DATA`. Code that hashes/sorts by inode will silently misbehave
  on Windows — but PG doesn't do that anywhere.
- **`d_reclen = 0` always** (`:71`). Field exists for binary compat with
  Linux's dirent; not meaningful on Win32. `[verified-by-code]`
- **The returned `struct dirent *` aliases internal storage.** Subsequent
  `readdir` calls overwrite `d->ret.d_name`. Callers must `strdup` if they
  want to retain the name beyond the next call. (This matches POSIX, but
  it's worth remembering — porting from a system with a thread-safe
  `readdir_r` can hide bugs.)
- **Reparse-point detection requires `dwReserved0 == IO_REPARSE_TAG_MOUNT_POINT`.**
  Other reparse tags (e.g. true NTFS symbolic links with
  `IO_REPARSE_TAG_SYMLINK`) fall through to `DT_DIR` or `DT_REG`. PG only
  creates MOUNT_POINT junctions via `pgsymlink`, so this matches our own
  output; foreign-created reparse points might be misclassified.
- `MAX_PATH` is the implicit bound on `d_name` length (commented at `:107`).
  Long-path support (`\\?\` prefix) isn't handled here.

## Cross-refs

- `knowledge/files/src/port/dirmod.c.md` — `pgsymlink`/`pgreadlink`
  produce and consume the reparse points this file detects.
- `source/src/backend/storage/file/fd.c` — primary caller (directory
  scans in tablespace handling, WAL archive sweeping).
- `source/src/include/port/win32_port.h` — `DIR` and `struct dirent`
  type declarations.
