---
path: src/port/open.c
anchor_sha: e18b0cb7344
loc: 232
depth: read
---

# src/port/open.c

## Purpose

Windows replacement for POSIX `open()` and `fopen()`. Windows' default file
sharing semantics differ sharply from POSIX: by default a Windows file is
exclusively locked against rename/unlink while open. PG relies heavily on
the POSIX behavior — open a file, rename it, keep using the old fd. This
file's `pgwin32_open` recreates that by passing
`FILE_SHARE_READ|FILE_SHARE_WRITE|FILE_SHARE_DELETE` to `CreateFile`, plus
a retry loop for antivirus/backup software's sharing-violation transient
errors. Whole file is gated by `#ifdef WIN32`. `[verified-by-code]`
`[from-comment]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `HANDLE pgwin32_open_handle(const char *fileName, int fileFlags, bool backup_semantics)` | `open.c:65` | Internal — returns raw Win32 HANDLE for use by `pgwin32_open` and `_pgstat64` |
| `int pgwin32_open(const char *fileName, int fileFlags, ...)` | `:168` | POSIX-style `open()` replacement returning an fd |
| `FILE *pgwin32_fopen(const char *fileName, const char *mode)` | `:205` | POSIX-style `fopen()` replacement |

## Internal landmarks

- `openFlagsToCreateFileFlags` (`:29`) — switch over `(O_CREAT | O_TRUNC |
  O_EXCL)` mapping to Win32 `OPEN_EXISTING` / `OPEN_ALWAYS` /
  `TRUNCATE_EXISTING` / `CREATE_ALWAYS` / `CREATE_NEW`. Handles `O_EXCL`
  without `O_CREAT` as if `O_EXCL` weren't set (POSIX-undefined behavior).
- Flag assertion (`:75-78`) — asserts that fileFlags only contains
  recognized bits; an unknown bit would silently break the translation.
- `SECURITY_ATTRIBUTES` setup (`:80-92`) — sets `bInheritHandle =
  !(fileFlags & O_CLOEXEC)`. The comment notes this is preferred over
  `SetHandleInformation` after-the-fact because there's a race window
  between `CreateFile` and the clear-inheritance call where a child
  process could be `fork`'d (via `CreateProcess` from another thread).
  `[from-comment]`
- Retry loop (`:94-162`) — on `ERROR_SHARING_VIOLATION` /
  `ERROR_LOCK_VIOLATION` (antivirus, backup software), sleeps 100ms and
  retries up to 300 times = 30s total, with an `ereport(LOG)` at loop=50
  warning the operator about possible AV interference. After 30s,
  surrenders.
- `STATUS_DELETE_PENDING` translation (`:139-158`) — Windows returns
  `ERROR_ACCESS_DENIED` for a file that's been deleted but still has open
  handles. The NT-level status code is `STATUS_DELETE_PENDING`; we probe
  for it via `pg_RtlGetLastNtStatus()` and translate to either
  `ERROR_FILE_NOT_FOUND` (no `O_CREAT`, file is "gone") or
  `ERROR_FILE_EXISTS` (with `O_CREAT`, we can't create over the corpse).
  `[from-comment]`
- `pgwin32_open` (`:168`) — calls `pgwin32_open_handle`, then
  `_open_osfhandle` to get a CRT fd. In FRONTEND builds the default is
  text mode (`O_TEXT`) to match pre-PG12 behavior; explicit `O_BINARY` /
  `O_TEXT` overrides via `_setmode`. `[from-comment]`
- `pgwin32_fopen` (`:205`) — translates the C `mode` string ("r", "w",
  "a", "+", "b", "t") to POSIX `open()` flags, calls `pgwin32_open`, then
  `_fdopen` to wrap.

## Invariants & gotchas

- **Concurrent rename/unlink is the whole point.** Without
  `FILE_SHARE_DELETE` here, PG's pattern of "open data file, rename file
  to back it up, keep writing" would deadlock on Windows. `[from-comment]`
- **30s antivirus tolerance is a hard cap.** If AV/backup software holds
  a file lock for >30s the open fails; the operator gets a LOG line at
  5s. Real production: stop running AV on `$PGDATA`. `[from-comment]`
- The `_OPEN_OSFHANDLE` call (`:192`) — on its failure path we CloseHandle
  but per the inline comment, that won't clobber errno. The errno set by
  `_open_osfhandle` is what propagates.
- `pgwin32_open_handle`'s `backup_semantics` parameter (`:65`) — when true,
  adds `FILE_FLAG_BACKUP_SEMANTICS` to allow opening directories (which
  Win32 `CreateFile` normally refuses). `_pgstat64` is the only known caller
  passing true.

## Cross-refs

- `source/src/backend/storage/file/fd.c` — primary caller (`OpenTransientFile`,
  `BasicOpenFile` etc. eventually land here on Windows).
- `source/src/port/win32stat.c` — `_pgstat64` uses `pgwin32_open_handle` with
  `backup_semantics=true`.
- `knowledge/files/src/port/dirmod.c.md` — sibling Windows shim file.
- `source/src/include/port/win32ntdll.h` — `pg_RtlGetLastNtStatus`,
  `initialize_ntdll`.
