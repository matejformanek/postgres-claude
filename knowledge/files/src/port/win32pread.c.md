---
path: src/port/win32pread.c
anchor_sha: e18b0cb7344
loc: 50
depth: read
---

# src/port/win32pread.c

## Purpose

Windows implementation of POSIX `pread(2)`: read at an explicit file
offset without using or updating the file's current position. Maps
to Win32 `ReadFile` with an `OVERLAPPED` struct carrying the offset.
`[verified-by-code]`

PG relies on `pg_pread` for any "read at offset X" call — buffer
manager reads of relation pages, WAL recovery, etc. The wrapper hides
the OVERLAPPED-vs-pread API mismatch.

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `ssize_t pg_pread(int fd, void *buf, size_t size, pgoff_t offset)` | `win32pread.c:19` | EOF returns 0; error returns -1 with `errno` |

## Internal landmarks

- `_get_osfhandle(fd)` (`win32pread.c:26`) — CRT fd → Win32 HANDLE.
  INVALID_HANDLE_VALUE → `EBADF`.
- **Size clamp** (`win32pread.c:34`): `size = Min(size, 1024 * 1024 *
  1024)` — Win32 `ReadFile`'s `nNumberOfBytesToRead` is a `DWORD`
  (32-bit). Capping to 1 GB avoids overflow when callers ask for huge
  reads; the caller's loop must accept short reads anyway.
- **OVERLAPPED offset packing** (`win32pread.c:37-38`): low 32 bits to
  `Offset`, high 32 bits to `OffsetHigh`. The struct is zero-init at
  `:22` (`OVERLAPPED overlapped = {0}`), so `hEvent` and other fields
  start clean.
- **EOF detection** (`win32pread.c:42-43`): when `ReadFile` returns
  FALSE with `GetLastError() == ERROR_HANDLE_EOF`, that's not an
  error — return 0 to signal EOF, mirroring POSIX `pread`.
- Other errors → `_dosmaperr(GetLastError())` and return -1.

## Invariants & gotchas

- **The OVERLAPPED struct still changes the file position despite not
  using it** (`win32pread.c:36`): documented Win32 quirk. POSIX
  `pread` is contractually atomic and **does not update offset** — on
  Windows we cannot honor that. If a caller mixes `pg_pread` with
  positional reads via `read()` (which uses the file position), the
  position state will be unpredictable. PG callers don't do this in
  practice — but it's a real corner. `[from-comment]`
- The 1 GB clamp means callers may see fewer bytes returned than
  requested even when no EOF or error — they must loop.
- This file is the counterpart to `win32pwrite.c`; they share the
  same OVERLAPPED-offset and size-clamp patterns.

## Cross-refs

- `knowledge/files/src/port/win32pwrite.c.md` — sibling.
- `source/src/include/port.h` — declares `pg_pread` prototype and
  routes calls.
- `source/src/backend/storage/file/fd.c` — primary backend consumer.
