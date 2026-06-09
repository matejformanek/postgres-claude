# `src/include/port/win32ntdll.h`

## Role

Dynamically-loaded Windows NT-internal function pointers. Three
function-pointer typedefs and PGDLLIMPORT globals
`[verified-by-code]` `source/src/include/port/win32ntdll.h:24-32`:

- `pg_RtlGetLastNtStatus` — read the last NT status from a syscall
  (when win32 error mapping loses information).
- `pg_RtlNtStatusToDosError` — translate NTSTATUS to Win32 errno.
- `pg_NtFlushBuffersFileEx` — the proper "durable fsync" on Windows:
  takes a flush flag (`FLUSH_FLAGS_FILE_DATA_SYNC_ONLY`) that maps
  to fdatasync-equivalent semantics, unlike `_commit` (which is
  weaker) or `FlushFileBuffers` (which flushes the drive cache).

`extern int initialize_ntdll(void)` populates the pointers via
`LoadLibrary("ntdll.dll") + GetProcAddress` at startup.

## Public API

- `pg_RtlGetLastNtStatus`, `pg_RtlNtStatusToDosError`,
  `pg_NtFlushBuffersFileEx` — function pointers.
- `int initialize_ntdll(void)` — call once at backend startup.
- `FLUSH_FLAGS_FILE_DATA_SYNC_ONLY 0x4` — provided if not in the SDK
  `[verified-by-code]` `source/src/include/port/win32ntdll.h:20-22`.

## Invariants

1. **Pointers are NULL until `initialize_ntdll` succeeds.** Any
   caller before init crashes `[inferred]`.
2. **NTDLL is undocumented Microsoft territory.** These APIs are
   "stable" only in practice; Microsoft reserves the right to break
   them. PG accepts the risk for the fsync semantics gain.
3. **Header is Windows-only**; never included on other platforms
   (no platform-gate visible in this header itself; expected to be
   compiled only under WIN32 builds via Makefile/meson rules)
   `[inferred]`.

## Trust-boundary / Phase D surface

- **`pg_NtFlushBuffersFileEx` is the only path to a proper
  WAL-fdatasync equivalent on Windows.** Without it, PG falls back
  to `_commit`, which is `FlushFileBuffers` underneath and flushes
  the entire drive cache — both too strong (slow) and arguably not
  even durable on some drives that lie about cache flush.
  Pinning durability on an undocumented NT API is a known
  trade-off. **Phase-D-doc-cluster:** durability semantics on
  Windows hinge on this header + win32_port.h's `_commit`.
- **Loading ntdll.dll** — `LoadLibrary("ntdll.dll")` returns the
  handle to a DLL that's always already loaded in any Windows
  process. No DLL-injection risk from this path.
- **Function-pointer null check** required before each call (or
  rely on `initialize_ntdll` having succeeded). A missing-symbol
  case (Windows version without `NtFlushBuffersFileEx` — added in
  Windows 8.1) must fall back to `FlushFileBuffers`. PG handles
  this with NULL-pointer check at call sites
  `[inferred from header shape; verify in fd.c]`.

## Cross-refs

- `source/src/port/win32ntdll.c` — the LoadLibrary + GetProcAddress
  implementation `[unverified path]`.
- `source/src/backend/storage/file/fd.c` — `pg_fsync` /
  `pg_flush_data` call site.
- `source/src/include/port/win32_port.h` — provides the weaker
  `_commit` fallback.

## Issues / unresolved

- **ISSUE-trust**: relying on undocumented `ntdll.dll` exports is a
  known forward-compat risk; documented at the call sites but not
  here. (severity: low, narrative)
- **ISSUE-portability**: `FLUSH_FLAGS_FILE_DATA_SYNC_ONLY 0x4` is
  hardcoded; if Microsoft changes the flag value, silent breakage.
  Practical risk is zero (NT internals are very stable in practice).
  (severity: trivial)
