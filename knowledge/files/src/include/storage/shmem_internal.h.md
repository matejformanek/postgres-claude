# `src/include/storage/shmem_internal.h`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~54
- **Source:** `source/src/include/storage/shmem_internal.h`

Internal half of the shared-memory request/init API. Public callers
use `shmem.h` (which advertises `RegisterShmemCallbacks`,
`ShmemRequestStruct/Hash`, `ShmemInitStruct`, etc.); this header is
for code inside `src/backend/storage/ipc/` and `storage/lmgr/` that
needs the **allocator-internal** entry points and the shmem-area
**kind** enum. PG18-era addition (alongside the `ShmemCallbacks`
machinery and `subsystemlist.h` reorg). [verified-by-code] [inferred]

## API / declarations

- `enum ShmemRequestKind` — the three kinds of shmem areas:
  - `SHMEM_KIND_STRUCT = 0` — plain contiguous bytes.
  - `SHMEM_KIND_HASH` — hash table backed by contiguous shmem.
  - `SHMEM_KIND_SLRU` — SLRU buffers + control. [verified-by-code]
- Forward decl `typedef struct PGShmemHeader PGShmemHeader` (avoids
  pulling in `storage/pg_shmem.h`). [from-comment]
- `ShmemCallRequestCallbacks(void)` — invoked at postmaster startup to
  fire every registered `request_fn` so subsystems can reserve their
  needs before allocation. [inferred]
- `InitShmemAllocator(PGShmemHeader *seghdr)` — set up the allocator
  on top of the just-mapped segment. [inferred]
- `AttachShmemAllocator(PGShmemHeader *seghdr)` — EXEC_BACKEND only;
  reattach in a freshly-forked backend. [verified-by-code]
- `ResetShmemAllocator(void)` — used in single-user / re-init paths. [inferred]
- `ShmemRequestInternal(ShmemStructOpts *options, ShmemRequestKind kind)`
  — the actual workhorse behind `ShmemRequestStruct` /
  `ShmemRequestHash`; reserves space and (for hashes) routes through
  `shmem_hash_*`. [verified-by-code]
- `ShmemGetRequestedSize(void)` / `ShmemInitRequested(void)` /
  `ShmemAttachRequested(void)` (EXEC_BACKEND) — three-phase
  allocate/init/attach used by `CreateSharedMemoryAndSemaphores`. [verified-by-code]
- `pg_get_shmem_pagesize(void)` — page-size used for shmem mappings
  (huge-pages-aware on Linux). Exported `PGDLLIMPORT`. [verified-by-code]
- `shmem_hash_create / shmem_hash_init / shmem_hash_attach` — shmem-
  hash-specific lifecycle in `shmem_hash.c`. [verified-by-code]

## Notable invariants / details

- The header is `#include`d only by `shmem.c`, `shmem_hash.c`,
  `ipci.c`, and a handful of EXEC_BACKEND glue files. Not a
  user-facing API; extensions should use `shmem.h`. [inferred]
- The forward-decl trick for `PGShmemHeader` (line 28-29) keeps this
  header light enough to be pulled into other low-level allocator
  code without dragging in OS-specific `pg_shmem.h`. [from-comment]
- The `ShmemRequestKind` enum (line 20-25) is exported here because
  both the request and the hash-table-creation paths share the same
  area accounting; without the enum, the allocator can't distinguish
  hash and SLRU areas at request time. [verified-by-code]
- All three of `ShmemInitRequested` and friends and `Attach*` are
  `#ifdef EXEC_BACKEND` guarded only on the *attach* side — the
  initial allocate/init paths are unconditional. EXEC_BACKEND only
  exists on Windows now (and a few rare debugging configurations);
  this header still exposes both. [verified-by-code]

## Potential issues

- Line 45. `pg_get_shmem_pagesize` is `PGDLLIMPORT`-exposed, which
  makes it part of the extension ABI even though the rest of this
  file is "internal". Extension authors that need huge-page-aware
  sizing have a legitimate use; nothing else here is similarly
  marked. [verified-by-code]
  [ISSUE-api-shape: `pg_get_shmem_pagesize` is PGDLLIMPORT-exported from
  an "internal" header; either it should move to `shmem.h` or the file
  comment should explain the carve-out (nit)]
- Lines 32-43. EXEC_BACKEND code paths (`AttachShmemAllocator`,
  `ShmemAttachRequested`) are compile-time guarded but referenced from
  the comment in `shmem.c` as Windows-only. With EXEC_BACKEND
  effectively a Windows-only mode, the `#ifdef` ladder is correct but
  invisible to most non-Windows reviewers. [verified-by-code]
  [ISSUE-doc-drift: `#ifdef EXEC_BACKEND` lines lack a comment that
  this is the Windows fork-emulation path (nit)]
