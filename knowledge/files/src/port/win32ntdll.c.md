---
path: src/port/win32ntdll.c
anchor_sha: e18b0cb7344
loc: 71
depth: read
---

# src/port/win32ntdll.c

## Purpose

Lazy loader for undocumented (but widely available) NT-kernel
functions in `ntdll.dll`. PG depends on three of them:

- `RtlGetLastNtStatus` — fetches the most recent NTSTATUS from the
  current thread (used to distinguish `STATUS_DELETE_PENDING` from
  other access-denied errors in `win32stat.c`).
- `RtlNtStatusToDosError` — translates NTSTATUS → Win32 DOS error code,
  enabling `_dosmaperr` to then translate to errno.
- `NtFlushBuffersFileEx` — the `fdatasync`-flavored flush primitive
  used by `win32fdatasync.c`.

These aren't exported in the platform headers, so the file uses
`LoadLibraryEx` + `GetProcAddress` to resolve them at runtime, exposing
them through `pg_*` global function pointers. `[verified-by-code]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `RtlGetLastNtStatus_t pg_RtlGetLastNtStatus` | `win32ntdll.c:20` | Function-pointer global |
| `RtlNtStatusToDosError_t pg_RtlNtStatusToDosError` | `win32ntdll.c:21` | Function-pointer global |
| `NtFlushBuffersFileEx_t pg_NtFlushBuffersFileEx` | `win32ntdll.c:22` | Function-pointer global |
| `int initialize_ntdll(void)` | `win32ntdll.c:39` | Idempotent; 0 on success, -1 with `errno` on failure |

## Internal landmarks

- `routines[]` table (`win32ntdll.c:30-34`) — `{name, address}` pairs
  driving the resolver loop.
- `static bool initialized` (`:36`) — first-call guard; subsequent
  calls return immediately (`:43-44`). Note this is **not**
  thread-safe; the assumption is that the first caller is the
  postmaster's main thread before any worker is forked.
- `LoadLibraryEx("ntdll.dll", NULL, 0)` (`:46`) — full search path,
  no special flags. `ntdll.dll` is always loaded in every Windows
  process, so `LoadLibraryEx` is effectively a refcount bump.
- Loop at `:52-66`: `GetProcAddress` for each symbol; failure
  releases `ntdll.dll` via `FreeLibrary` and returns -1 with `errno`
  set by `_dosmaperr`.

## Invariants & gotchas

- **Idempotent but not thread-safe** (`:43-44`). The `initialized`
  flag is a plain `bool`, no synchronization. PG's per-connection
  fork model means each backend will initialize independently on
  first use — fine. A multithreaded frontend could race.
- **`FreeLibrary` is called only on the error path** (`:60`). The
  happy path leaks the handle for process lifetime, which is
  intentional — `ntdll.dll` is loaded in every Windows process
  anyway, and we want the resolved function pointers to remain
  valid.
- If `ntdll.dll` somehow lacks one of the three required symbols,
  the entire `initialize_ntdll` fails — even if only one symbol is
  needed by the immediate caller. The cost of probing all three is
  the worst-case latency of three `GetProcAddress` calls; acceptable
  for a one-shot init.
- **No explicit `pg_NtFlushBuffersFileEx == NULL` check elsewhere**:
  callers (`win32fdatasync.c`) call `initialize_ntdll` first and
  bail on its return — they don't separately null-check the
  function pointer.

## Cross-refs

- `source/src/include/port/win32ntdll.h` — the `_t` typedefs and
  declarations of the `pg_*` globals.
- `knowledge/files/src/port/win32fdatasync.c.md` — consumer of
  `pg_NtFlushBuffersFileEx`.
- `knowledge/files/src/port/win32stat.c.md` — consumer of
  `pg_RtlGetLastNtStatus` for `STATUS_DELETE_PENDING` discrimination.
