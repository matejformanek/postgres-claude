---
path: src/backend/port/win32_shmem.c
anchor_sha: e18b0cb7344
loc: 651
depth: read
---

# src/backend/port/win32_shmem.c

## Purpose

Provides PG's main shared-memory segment on Windows using
**`CreateFileMapping` against the system page file** (i.e. an anonymous file
mapping) — the Win32 analog to anonymous mmap on Unix. Selected
automatically when building for Windows; there is no SysV-style
on-Windows fallback because Windows has no SysV IPC. The file additionally
handles Windows-specific complications around handle inheritance, address-
space reservation in child processes, and protective regions to dodge
default-thread-pool stack-allocation collisions. `[verified-by-code]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `PGShmemHeader *PGSharedMemoryCreate(Size size, PGShmemHeader **shim)` | `win32_shmem.c:207` | Postmaster startup; allocates and maps the segment |
| `bool PGSharedMemoryIsInUse(unsigned long id1, unsigned long id2)` | `:113` | OpenFileMapping probe |
| `void PGSharedMemoryReAttach(void)` | `:424` | EXEC_BACKEND-style child re-attaches via inherited HANDLE |
| `void PGSharedMemoryNoReAttach(void)` | `:472` | Child opts out; must still close inherited handle |
| `void PGSharedMemoryDetach(void)` | `:505` | UnmapViewOfFile + CloseHandle |
| `int pgwin32_ReserveSharedMemoryRegion(HANDLE hChild)` | `:573` | Postmaster reserves child's address space pre-CreateProcess |
| `void GetHugePageSize(Size *, int *)` | `:630` | Stub — returns 0 |
| `bool check_huge_page_size(int *, void **, GucSource)` | `:642` | GUC check hook (rejects nonzero) |
| `HANDLE UsedShmemSegID`, `void *UsedShmemSegAddr`, `void *ShmemProtectiveRegion` | `:42-45` | Externs |

## Internal landmarks

- **`GetSharedMemName`** (`:65`) — builds a name like
  `Global\PostgreSQL:<expanded-DataDir-with-/-not-\>`. Then comment at
  `:87-92` notes that the `Global\` part is overwritten by the path
  expansion, leaving it in the session namespace because the global
  namespace caused permission errors. So in practice the name lives in
  the local session namespace. `[from-comment]`
- **`ShmemProtectiveRegion`** (`:23-41`) — a 10× thread-stack-size
  `MEM_RESERVE`/`PAGE_NOACCESS` region allocated immediately before the
  real shmem reservation. Workaround for a Windows Server 2016 bug
  where the default thread pool would asynchronously allocate a stack at
  the just-freed UsedShmemSegAddr between
  `PGSharedMemoryReAttach`'s `VirtualFree` and `MapViewOfFileEx`,
  causing the re-mapping to fail. Theory: if the allocator is consistent
  about preferring region A before region B, give it a region A to grab
  so region B (ours) stays free. `[from-comment at :23-40]`
- **`PGSharedMemoryCreate` retry loop** (`:278-331`) — `CreateFileMapping`
  can return a handle to an existing segment with
  `ERROR_ALREADY_EXISTS`. Sleeps 1s and retries up to 10×. If still
  taken at the end → FATAL "pre-existing shared memory block is still in
  use" (`:337-340`).
- **`DuplicateHandle` for inheritability** (`:347`) — `CreateFileMapping`
  returns a non-inheritable handle. To allow child backends to inherit
  it across `CreateProcess`, the handle is duplicated with
  `bInheritHandle = TRUE` and the original closed. `[verified-by-code]`
- **`pgwin32_ReserveSharedMemoryRegion`** (`:573`) — called by the
  postmaster *before* `CreateProcess` on a child, using `VirtualAllocEx`
  to pre-reserve both the protective region and the shmem address range
  in the child's not-yet-started address space. The child must later
  `VirtualFree` these in `PGSharedMemoryReAttach` (`:436-441`) and then
  immediately `MapViewOfFileEx` at the same address. Without this dance,
  DLL load order / thread-pool init could grab the address we need.
  Uses `LOG` not `FATAL` (`:587`) because it runs in the postmaster.
- **Large pages** (`:236-262`) — gated on `huge_pages` GUC and
  `SeLockMemoryPrivilege` (acquired via `EnableLockPagesPrivilege` at
  `:137`). Uses `SEC_LARGE_PAGES` + `SEC_COMMIT` mapping flags and
  `FILE_MAP_LARGE_PAGES` access. Falls back to non-huge on
  `ERROR_NO_SYSTEM_RESOURCES` with `huge_pages=try` (`:295-310`).

## Invariants & gotchas

- **Name collision = data-dir collision.** Two postmasters with the same
  data directory will see the same `Global\PostgreSQL:...` name and the
  second will fail the 10-retry loop. This is how Windows enforces
  one-postmaster-per-DataDir without a SysV-style key search.
- **No EXEC_BACKEND-vs-fork distinction.** Windows always uses
  `CreateProcess`-style child spawn (semantically `fork+exec`). The
  `PGSharedMemoryReAttach` codepath is therefore the *only* path on
  Windows. `[verified-by-code]`
- **Address-space reservation is bidirectional.** Postmaster reserves
  in child (`pgwin32_ReserveSharedMemoryRegion`, `:573`), child releases
  the reservation just before mapping (`:436-441`). The protective
  region exists to defend the window between those two events.
- **`CloseHandle` of `UsedShmemSegID` is mandatory in NoReAttach.**
  Comment at `:484-487`: if the child opts out of shmem but doesn't
  close the inherited handle, Windows considers the process a referent
  and will never release the underlying mapping. So
  `PGSharedMemoryNoReAttach` explicitly calls `PGSharedMemoryDetach`
  (`:489`).
- **`huge_page_size` GUC is forced 0 on Windows.** `check_huge_page_size`
  rejects any nonzero value (`:642-650`); Windows queries the actual
  size via `GetLargePageMinimum` (`:239`) and there's no way to override.
- **Handle leak on crash is harmless.** Unlike SysV semaphores/shmem on
  Unix, Win32 anonymous file mappings are reaped by the kernel when the
  last handle closes. A `kill -9 postgres` releases all handles → mapping
  gone → no `ipcs`-style cleanup needed.
- **`UsedShmemSegSize` is private to this file** (`:46`) — only used by
  `pgwin32_ReserveSharedMemoryRegion`. Postmaster passes the size to
  children implicitly via reserving the exact address range in each
  child before launch.

## Cross-refs

- `knowledge/subsystems/storage-ipc.md` — overall IPC layer.
- `knowledge/files/src/include/storage/pg_shmem.h.md` — abstract
  interface and `PGShmemHeader`.
- `knowledge/files/src/backend/port/sysv_shmem.c.md` — Unix analog.
- `knowledge/files/src/backend/port/win32/signal.c.md` — companion
  Win32-only signal-emulation infrastructure.
- `knowledge/files/src/backend/postmaster/postmaster.c.md` —
  `pgwin32_ReserveSharedMemoryRegion` caller, runs around
  `CreateProcess`.
