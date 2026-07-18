---
path: src/port/win32stat.c
anchor_sha: e18b0cb7344
loc: 302
depth: read
---

# src/port/win32stat.c

## Purpose

Windows replacements for `lstat(2)`, `stat(2)`, and `fstat(2)` —
`_pglstat64`, `_pgstat64`, `_pgfstat64`. Built primarily on
`GetFileInformationByHandle`, plus `readlink()` for junction-point
(symlink) handling. Provides 64-bit file sizes via the `_64` suffix in
the function names. `[verified-by-code]`

Why this is non-trivial:

- Windows' native `_stat64` family is buggy with junction points: it
  follows them silently and returns the target's info, with no way to
  ask for the link itself. This file uses `pgwin32_open_handle` to get
  a HANDLE without following, then disambiguates junctions via
  `readlink`.
- Windows file types must be translated to POSIX `S_IFREG`/`S_IFDIR`
  /`S_IFCHR`/`S_IFIFO`/`S_IFLNK` modes manually.
- FILETIME (100-ns ticks since 1601) must be converted to `time_t`
  (seconds since 1970).

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `int _pglstat64(const char *name, struct stat *buf)` | `win32stat.c:113` | Does not follow symlinks/junctions |
| `int _pgstat64(const char *name, struct stat *buf)` | `win32stat.c:198` | Follows junction points up to depth 8 |
| `int _pgfstat64(int fileno, struct stat *buf)` | `win32stat.c:255` | Dispatches by file type (disk/pipe/char) |

Internally also: `filetime_to_time` (`win32stat.c:24`), `fileattr_to_unixmode`
(`:47`), `fileinfo_to_stat` (`:67`).

## Internal landmarks

- **`filetime_to_time`** (`:24-40`) — same constant `116444736000000000`
  as `win32gettimeofday.c` for the 1601→1970 epoch shift. Returns -1
  for filetimes pre-1970 (`:33-34`); otherwise integer-divides by
  10 million.
- **`fileattr_to_unixmode`** (`:47-62`) — maps Win32 file attributes
  to a POSIX `mode_t`:
  - `FILE_ATTRIBUTE_DIRECTORY` → `_S_IFDIR`, else `_S_IFREG`.
  - `FILE_ATTRIBUTE_READONLY` → `_S_IREAD` only; else `_S_IREAD |
    _S_IWRITE`.
  - Always sets `_S_IEXEC` (`:59`) — "no need to simulate using CMD's
    PATHEXT extensions" (the comment notes the simplification).
- **`fileinfo_to_stat`** (`:67-107`) — fills a `struct stat` from
  `BY_HANDLE_FILE_INFORMATION`:
  - mtime always set, atime/ctime fall back to mtime if zero
    (`:83-98`).
  - mode via `fileattr_to_unixmode`.
  - `st_nlink = nNumberOfLinks`; `st_size` from
    `nFileSizeHigh:nFileSizeLow` packed into 64 bits (`:101-104`).
- **`_pglstat64`** (`:113-192`) — non-following stat:
  1. `pgwin32_open_handle(name, O_RDONLY, true)` — open with
     `FILE_FLAG_BACKUP_SEMANTICS` (so directories open too) and
     **without** `FILE_FLAG_OPEN_REPARSE_POINT`.
  2. If open returns ENOENT for what *might* be a junction-to-nowhere,
     proceed with a zeroed buf and let the junction-detect logic below
     decide (`:127-138`).
  3. Otherwise fill via `fileinfo_to_stat`.
  4. **Junction detection** (`:148-187`): if buf says directory, or
     handle was invalid, try `readlink(name, next, sizeof(next))`:
     - If readlink succeeds, it's a junction — replace `S_IFDIR` with
       `S_IFLNK`, set `st_size` to link-target length (POSIX
       requirement).
     - If `EACCES + STATUS_DELETE_PENDING` → translate to ENOENT
       (file was unlinked underneath us).
     - `EINVAL` from readlink → not a junction, leave as directory.
- **`_pgstat64`** (`:198-249`) — following stat: calls `_pglstat64`,
  then **loop**: while result is symlink, `readlink` to get target,
  call `_pglstat64` on target. Bail with `ELOOP` after 8 iterations
  (`:214-218`).
- **`_pgfstat64`** (`:255-302`) — fstat dispatch by
  `pgwin32_get_file_type`:
  - `FILE_TYPE_DISK` → `fileinfo_to_stat`.
  - `FILE_TYPE_PIPE` → synthesize `S_IFIFO`.
  - `FILE_TYPE_CHAR` → synthesize `S_IFCHR`.
  - `REMOTE`/`UNKNOWN` → `EINVAL`.
  Pipe/char buffers are zero-filled with just `st_mode`, `st_dev =
  st_rdev = fileno`, `st_nlink = 1`.

## Invariants & gotchas

- **Junctions are reported as symlinks (`S_IFLNK`)** — PG treats
  Windows directory junctions and Unix symlinks uniformly. This is
  load-bearing for tablespace handling, where each tablespace dir is
  a symlink/junction.
- **Loop limit 8 for symlink chains** (`_pgstat64`, `:214`) — same as
  the typical Linux `MAXSYMLINKS` value. Cycles report `ELOOP`.
- **`pgwin32_open_handle` private-handle path** (`:118-119`): uses a
  HANDLE-based open that doesn't consume a CRT fd slot — avoids
  running out of fds on heavy stat traffic.
- **`STATUS_DELETE_PENDING` translation** (`:162-164`, `:229-232`):
  files in the "marked for deletion but still open" state appear as
  EACCES from Windows but should be reported as ENOENT (they're
  effectively gone). The check uses `pg_RtlGetLastNtStatus` from
  `win32ntdll.c`.
- **`readlink` is called twice on `_pgstat64`** in the symlink path
  (`:220-225`) — once by `_pglstat64` for `st_size`, once by
  `_pgstat64` for the actual chase. The comment notes this could be
  optimized but stat-on-symlinks is rare enough not to bother.
- **`memset(buf, 0, ...)` happens at the top of `fileinfo_to_stat`**
  (`:72`) so partial fills don't leak stack garbage. `_pgfstat64`
  re-zeros for pipe/char branches (`:296`).
- `st_atime` falls back to `st_mtime`, not 0 (`:91-92`) — Windows
  filesystems often have `LastAccessTime` disabled (NTFS opt-out via
  registry), so the fallback avoids 1970-epoch atimes in PG logs.
- `_S_IEXEC` is always set (`:59`) — every file *appears* executable.
  Code that gates on executable bit (e.g. command lookup) will
  silently succeed on Windows where it would fail on Unix.

## Cross-refs

- `knowledge/files/src/port/win32ntdll.c.md` — provides
  `pg_RtlGetLastNtStatus` for STATUS_DELETE_PENDING discrimination.
- `knowledge/files/src/port/win32common.c.md` — `pgwin32_get_file_type`
  is the fstat dispatcher.
- `source/src/port/win32opendir.c`, `source/src/port/dirmod.c` —
  sibling Windows file-system shims (open, readlink, symlink).
- `source/src/include/port/win32_port.h` — macro routing `stat`,
  `lstat`, `fstat` → `_pg*64` variants on Windows.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/port.md](../../../subsystems/port.md)
