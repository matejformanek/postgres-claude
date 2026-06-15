---
path: src/port/win32pwrite.c
anchor_sha: e18b0cb7344
loc: 47
depth: read
---

# src/port/win32pwrite.c

## Purpose

Windows implementation of POSIX `pwrite(2)`: write at an explicit file
offset without using or updating the file's current position. Maps to
Win32 `WriteFile` with an `OVERLAPPED` struct carrying the offset.
`[verified-by-code]`

Counterpart to `win32pread.c`; same pattern. PG calls `pg_pwrite`
wherever it writes at a specific offset — buffer-manager flush, WAL
write, temp-file output, etc.

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `ssize_t pg_pwrite(int fd, const void *buf, size_t size, pgoff_t offset)` | `win32pwrite.c:19` | Returns bytes written; -1 with `errno` on error |

## Internal landmarks

- `_get_osfhandle(fd)` (`win32pwrite.c:26`) — fd → HANDLE.
  INVALID_HANDLE_VALUE → `EBADF`.
- Size clamp to 1 GB (`win32pwrite.c:34`) — `WriteFile`'s
  `nNumberOfBytesToWrite` is `DWORD`. Callers must accept short
  writes.
- OVERLAPPED offset packing (`win32pwrite.c:37-38`) — low/high split,
  same as `win32pread.c`.
- Failure path: `_dosmaperr(GetLastError())`, return -1.
- Success: return `result`, the byte count `WriteFile` reported via
  the OVERLAPPED output.

## Invariants & gotchas

- **The OVERLAPPED struct still changes the file position despite not
  using it** (`win32pwrite.c:36`) — same caveat as `pg_pread`.
- **No short-write retry inside the wrapper.** If `WriteFile` reports
  fewer bytes than requested, that's what `pg_pwrite` returns — the
  caller must loop. This matches POSIX `pwrite` semantics on signal
  interruption etc.
- Even though `pg_pwrite` succeeded, durability is not guaranteed
  until `fdatasync`/`fsync` runs against the same fd; PG uses the
  separate `pg_fdatasync` (`win32fdatasync.c`) for that.

## Cross-refs

- `knowledge/files/src/port/win32pread.c.md` — sibling.
- `knowledge/files/src/port/win32fdatasync.c.md` — durability call.
- `source/src/backend/storage/file/fd.c` — primary backend consumer.
