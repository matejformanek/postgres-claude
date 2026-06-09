# `src/include/storage/pg_shmem.h`

- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
- **Lines:** 94

## Role

**Shared-memory bootstrap header** — the platform abstraction
above SysV / mmap / Windows shmem. Defines the
`PGShmemHeader` magic-cookie prefix that lets a postmaster
detect & clean up stranded segments from a prior crashed
postmaster.

## Public API

- `PGShmemHeader { magic=679834894, creatorPID, totalsize,
  content_offset, dsm_control, device, inode }` (lines 29-42)
  — first 28-44 bytes of every Postgres shmem segment
- GUCs:
  - `shared_memory_type` (`SHMEM_TYPE_WINDOWS/SYSV/MMAP`)
    — default is `MMAP` on non-Windows non-EXEC_BACKEND
  - `huge_pages` (`OFF/ON/TRY`), `huge_pages_status`,
    `huge_page_size`
- `UsedShmemSegID`, `UsedShmemSegAddr` (line 73) — globals
  set by the active SHMEM impl
- `PGSharedMemoryCreate`, `PGSharedMemoryIsInUse`,
  `PGSharedMemoryDetach`
- EXEC_BACKEND: `PGSharedMemoryReAttach`,
  `PGSharedMemoryNoReAttach` (Windows / launched workers
  re-attach paths)
- `GetHugePageSize` — populates `hugepagesize` + `mmap_flags`

## Invariants

- INV-1: `PGShmemMagic = 679834894` — collision-resistant 32-bit
  magic to distinguish PG segments from other apps' shmem.
- INV-2: `device`/`inode` of `$PGDATA` (line 38-40) included so
  that two postmaster instances on different data dirs don't
  collide on segment ID. Windows skips (no useful inode).
- INV-3: `dsm_control` (line 37) — points the dynamic-shmem
  area for cooperative cleanup across the postmaster crash
  boundary.

## Trust boundary (Phase D)

- **Segment-ID collision** (`PGSharedMemoryIsInUse`) is the
  perimeter — a malicious local process could spam SysV IDs
  with the PG magic to convince a new postmaster the segment
  is in use and refuse startup. Already documented as a known
  local-DoS surface; mitigated on modern Linux by namespaces.
- `huge_pages = on` + insufficient huge-page reserve halts
  startup → DoS by sysadmin misconfiguration, not user.
- `PGSharedMemoryCreate` chooses 0600 perms; world access
  would be a serious data leak. (Already correct.)

## Cross-refs

- `knowledge/files/src/backend/port/sysv_shmem.c.md` (if exists)
- `knowledge/files/src/backend/port/sysv_sema.c.md` (if exists)
- `knowledge/files/src/include/storage/pg_sema.h.md`
- `knowledge/files/src/include/storage/shmem.h.md` (existing) —
  the dynahash + Shmem indexed allocators on top

## Issues

None at header level.
