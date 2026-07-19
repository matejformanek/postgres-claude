---
path: src/port/win32fdatasync.c
anchor_sha: e18b0cb7344
loc: 51
depth: read
---

# src/port/win32fdatasync.c

## Purpose

Windows implementation of POSIX `fdatasync(int fd)` — flushes file
*data* (not metadata) to stable storage. Built on top of the undocumented
NT-internal `NtFlushBuffersFileEx` with the `FLUSH_FLAGS_FILE_DATA_SYNC_ONLY`
flag, which is the only known way to get true `fdatasync`-semantics on
Windows. `FlushFileBuffers` (the documented Win32 call) is more like
`fsync` — it forces a full metadata flush too, which is slower.
`[verified-by-code]`

This matters for WAL: `wal_sync_method=fdatasync` (the default on Linux)
maps via this wrapper to `NtFlushBuffersFileEx` on Windows, giving the
backend the data-only durability guarantee it expects.

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `int fdatasync(int fd)` | `win32fdatasync.c:23` | Returns 0 on success, -1 with `errno` on failure |

## Internal landmarks

- `_get_osfhandle(fd)` (`win32fdatasync.c:29`) converts the CRT fd to
  a Win32 `HANDLE`; INVALID_HANDLE_VALUE → `errno=EBADF`.
- `initialize_ntdll()` (`:36`) lazily loads `ntdll.dll` and resolves
  `NtFlushBuffersFileEx` (along with other undocumented helpers). See
  `knowledge/files/src/port/win32ntdll.c.md` for the resolver.
- `pg_NtFlushBuffersFileEx` is called with
  `FLUSH_FLAGS_FILE_DATA_SYNC_ONLY` (`:41`) — the magic flag that
  makes this `fdatasync`-flavored, not `fsync`-flavored.
- Failure path uses `pg_RtlNtStatusToDosError(status)` (`:49`) to
  translate the NTSTATUS into a Win32 error code, then feeds that to
  `_dosmaperr` to set `errno`. Two-step translation because NTSTATUS
  values don't directly map to errno.

## Invariants & gotchas

- **Undocumented API dependency.** `NtFlushBuffersFileEx` and the
  `FLUSH_FLAGS_FILE_DATA_SYNC_ONLY` flag are in the NT kernel's
  internal interface — Microsoft can in principle change them, though
  they've been stable for many Windows versions.
- `initialize_ntdll()` is idempotent (per `win32ntdll.c`), so repeated
  `fdatasync` calls don't re-load the DLL.
- If `ntdll.dll` resolution fails (`initialize_ntdll() < 0`),
  `fdatasync` returns -1 with `errno` already set by the resolver. The
  caller can't easily tell apart "ntdll missing" from "actual flush
  failed".
- The `IO_STATUS_BLOCK iosb` (`:25, :39`) is zero-initialized and
  passed to receive the operation result; we don't actually inspect it
  beyond `NT_SUCCESS(status)`.

## Cross-refs

- `knowledge/files/src/port/win32ntdll.c.md` — the lazy resolver this
  file depends on.
- `knowledge/subsystems/` — WAL `wal_sync_method` selection routes
  here for `fdatasync` and `fdatasync_writethrough` on Windows.
- `source/src/backend/storage/file/fd.c` — `pg_fdatasync` caller.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/port.md](../../../subsystems/port.md)
