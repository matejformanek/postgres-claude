---
path: src/port/win32error.c
anchor_sha: e18b0cb7344
loc: 214
depth: read
---

# src/port/win32error.c

## Purpose

Translates Win32 `GetLastError()` codes (DWORD `ERROR_*` constants)
into POSIX-flavored `errno` values via `_dosmaperr()`. Every other
`win32*.c` file in this directory calls `_dosmaperr(GetLastError())` on
failure of a Win32 API — this is the central lookup table.
`[verified-by-code]`

The naming (`_dosmaperr` with leading underscore) mirrors the Microsoft
CRT's internal helper of the same name. PG provides its own version
because the MSVC one isn't always reachable, and because PG's table
includes mappings (notably `ERROR_DELETE_PENDING`) that MS doesn't.

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `void _dosmaperr(unsigned long e)` | `win32error.c:177` | Sets global `errno`; `e == 0` clears `errno` to 0 |

## Internal landmarks

- **Static mapping table** (`win32error.c:20-174`) — array of `{DWORD
  winerr; int doserr;}` pairs. ~50 entries covering the common
  file/path/permission/quota/network errors.
- **Note `ERROR_INVALID_HANDLE` appears twice** (`:42-44` → `EBADF`,
  `:120-122` → `EINVAL`). The linear scan returns the first match, so
  `EBADF` wins. The second entry is dead code — likely a historical
  bug that lookups never hit, but never cleaned up. `[inferred]`
- **`ERROR_DELETE_PENDING → ENOENT`** (`:165-167`) — a Windows-specific
  fingerprint. When a file is marked for deletion but still open
  elsewhere, Win32 returns this code; PG treats it as "file doesn't
  exist" so retry loops in `unlink`/`open` behave sensibly. This is
  load-bearing for the backend file-access layer.
- **Logging on mapped hits and misses** (`win32error.c:193-211`):
  - Backend (`!FRONTEND`): mapped hits go to `DEBUG5`, unmapped codes
    go to `LOG`.
  - Frontend (`FRONTEND`): mapped hits are silent unless
    `FRONTEND_DEBUG` is set; unmapped codes always print to stderr.
- **Unknown code → `EINVAL`** (`win32error.c:213`) — sentinel for
  "we've never seen this Win32 error", with a LOG/stderr trace to alert
  developers.

## Invariants & gotchas

- `_dosmaperr(0)` is **always called as success** (`:181-185`) — it
  clears `errno` rather than mapping to anything. Callers that
  unconditionally call `_dosmaperr(GetLastError())` after a Win32 call
  may get `errno=0` if `GetLastError` happens to be 0 (which can occur
  on Win32 calls that don't update it). Defensive callers check the
  Win32 return value separately.
- The linear scan is O(n) in table size. Called per Win32 error, which
  is rare; not a hotpath concern.
- **No mapping for `ERROR_OPERATION_ABORTED`** (associated with
  `CancelIoEx`) or other newer codes — extend the table when new Win32
  surface gets used.
- The table is intentionally **incomplete**: codes that PG never
  expects to see (printer errors, DDE errors, GUI errors) are
  omitted. Hitting one of those falls through to the `LOG`/stderr
  unknown-code path.
- `errno` is set unconditionally — callers must save `errno` before
  calling if they want to preserve a prior value.

## Cross-refs

- `knowledge/files/src/port/strerror.c.md` — the next step:
  formatting the resulting `errno` into a human string.
- Every `win32*.c` file in `src/port/` — each one calls
  `_dosmaperr(GetLastError())` after a Win32 API failure.
- `knowledge/files/src/port/win32ntdll.c.md` — `pg_RtlNtStatusToDosError`
  is the NT-status counterpart, feeding the same `_dosmaperr` table
  via the DOS-error code it returns.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/port.md](../../../subsystems/port.md)
