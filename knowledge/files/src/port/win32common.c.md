---
path: src/port/win32common.c
anchor_sha: e18b0cb7344
loc: 64
depth: read
---

# src/port/win32common.c

## Purpose

Tiny helper file holding routines shared between the various
`win32*.c` ports — currently just `pgwin32_get_file_type`, a wrapper
around `GetFileType()` that disambiguates the genuinely-unknown
"`FILE_TYPE_UNKNOWN`" success from the error case (they share the same
return value, requiring `GetLastError()` to tell apart). `[from-comment]`
`[verified-by-code]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `DWORD pgwin32_get_file_type(HANDLE hFile)` | `win32common.c:31` | Returns the Win32 file-type code (`FILE_TYPE_DISK`/`PIPE`/`CHAR`/`REMOTE`/`UNKNOWN`); sets `errno` on failure |

## Internal landmarks

- `errno = 0` reset at entry (`win32common.c:36`) — caller checks `errno
  != 0` to detect error, because the success return is also a `DWORD`.
- **Special handle values** (`win32common.c:43-47`): `INVALID_HANDLE_VALUE`
  and `(HANDLE) -2` are both rejected up-front. `-2` is the
  Microsoft-CRT sentinel for "stdin/stdout/stderr not associated with a
  stream" — `_get_osfhandle()` returns it for redirected/closed
  standard streams.
- **The double-check** (`win32common.c:49-61`): call `GetFileType`, then
  immediately call `GetLastError`. If type came back `UNKNOWN` *and*
  last error is not `NO_ERROR`, it's a real error; map it via
  `_dosmaperr`. Otherwise `UNKNOWN` is a legitimate success indicating
  an exotic device type.

## Invariants & gotchas

- **Caller error convention**: check `errno != 0` after calling, not
  the return value (since `FILE_TYPE_UNKNOWN` is sometimes valid).
  Callers like `win32fseek.c:36-38` and `win32stat.c:267-269` follow
  this pattern.
- The `(HANDLE) -2` check is a CRT-specific footgun — without it,
  `pgwin32_get_file_type(_get_osfhandle(fileno(closed_stream)))` would
  pass an invalid pseudo-handle to `GetFileType` and get
  unpredictable results.

## Cross-refs

- `knowledge/files/src/port/win32fseek.c.md` — uses this to refuse
  `fseek` on non-disk handles.
- `knowledge/files/src/port/win32stat.c.md` — uses this in
  `_pgfstat64` to dispatch on file type.
