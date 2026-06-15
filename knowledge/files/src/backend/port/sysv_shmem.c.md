---
path: src/backend/port/sysv_shmem.c
anchor_sha: e18b0cb7344
loc: 994
depth: read
---

# src/backend/port/sysv_shmem.c

## Purpose

Provides PG's main shared-memory segment (the one that holds shared buffers,
ProcArray, lock manager tables, etc.) on Unix. Despite the filename, it is
NOT pure SysV: since PG 9.3, the implementation defaults to
**anonymous-mmap-with-SysV-shim** (`sysv_shmem.c:44-67`) — a large
`MAP_SHARED | MAP_ANONYMOUS` mmap'd region backs the actual shared memory,
while a tiny SysV shmem block (just `sizeof(PGShmemHeader)`) is kept solely
as an interlock so we can detect via `shm_nattch` whether any child
backends are still attached. As of PG 12, full SysV mode is still selectable
via `shared_memory_type = sysv`. `[from-comment]`

This file is the Unix backing for `PGSharedMemoryCreate`, which is the
allocator the postmaster invokes during `PostgresMain` startup to carve out
the entire shared-memory area. Everything in `storage/buffer/`,
`storage/lmgr/`, `storage/ipc/shmem.c` ultimately lives inside the segment
this file mapped. `[verified-by-code]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `PGShmemHeader *PGSharedMemoryCreate(Size size, PGShmemHeader **shim)` | `sysv_shmem.c:702` | Postmaster startup; returns address of main shmem block |
| `bool PGSharedMemoryIsInUse(unsigned long id1, unsigned long id2)` | `sysv_shmem.c:318` | "Is the previous postmaster's segment still active?" |
| `void PGSharedMemoryDetach(void)` | `sysv_shmem.c:972` | Detach from main + anonymous segments (for inherited subprocs) |
| `void PGSharedMemoryReAttach(void)` | `sysv_shmem.c:892` | EXEC_BACKEND only — re-attach SysV segment in child |
| `void PGSharedMemoryNoReAttach(void)` | `sysv_shmem.c:941` | EXEC_BACKEND only — child opts out of shmem |
| `void GetHugePageSize(Size *, int *)` | `sysv_shmem.c:480` | Reads `/proc/meminfo` Hugepagesize line |
| `bool check_huge_page_size(int *, void **, GucSource)` | `sysv_shmem.c:579` | GUC check hook |
| `unsigned long UsedShmemSegID` / `void *UsedShmemSegAddr` | `:95-96` | Externs — recorded for ReAttach / pid lockfile |

## Internal landmarks

- **`IpcMemoryState` enum** (`sysv_shmem.c:85-92`) — five-way classification
  of any shmem ID we encounter:
  `ANALYSIS_FAILURE` / `ATTACHED` / `ENOENT` / `FOREIGN` / `UNATTACHED`.
  Drives the recycling logic in `PGSharedMemoryCreate` (`:767-842`).
- **`InternalIpcMemoryCreate`** (`:122`) — wraps `shmget(IPC_CREAT|IPC_EXCL)`
  with verbose errno taxonomy (`EINVAL` retry trick at `:185-212`,
  `SHMMAX`/`SHMALL`/`SHMMNI` errhints at `:229-249`). Registers
  `IpcMemoryDetach` and `IpcMemoryDelete` as `on_shmem_exit` callbacks.
- **`PGSharedMemoryAttach`** (`:348`) — the validator. Attempts `shmctl
  IPC_STAT`, then `shmat`. Confirms the header magic + `device` + `inode`
  match this DataDir (`:438-446`). Detects abandoned PG segments via
  `shm_nattch == 0` (`:454`).
- **`PGSharedMemoryCreate` recycling loop** (`:767-842`) — for each
  candidate key:
  - `SHMSTATE_FOREIGN` → bump key, retry.
  - `SHMSTATE_ATTACHED` → FATAL "still in use".
  - `SHMSTATE_UNATTACHED` → it's our crashed predecessor; zap it (incl.
    DSM control via `dsm_cleanup_using_control_segment` at `:834`) and
    retry the SAME key. **Note: this is where DSM cleanup is wired
    into shmem startup.**
- **`CreateAnonymousSegment`** (`:600`) — issues the big mmap. Tries
  `MAP_HUGETLB` first if `huge_pages=on/try` (`:611-630`), falls back to
  plain anonymous mmap on failure. Rounds size up to a multiple of the
  huge page size to dodge a Linux mmap/munmap mismatch bug
  (`[from-comment at :459-466]`).
- **DataDir inode = key seed.** Same trick as `sysv_sema.c`. `:715-720`,
  `:765`. Makes the search deterministic per DataDir, maximizing the
  chance of finding our own dead postmaster's segment first.
- **PID lockfile entry** (`:270-276`) — writes `<key> <id>` to
  `LOCK_FILE_LINE_SHMEM_KEY` in `postmaster.pid`. That's what
  `pg_ctl status` and `PGSharedMemoryIsInUse` from a *new* postmaster
  consult to decide whether the old one is still around.

## Invariants & gotchas

- **Anonymous mmap is the default; SysV is a shim.** `shared_memory_type =
  mmap` (default) → `sysvsize = sizeof(PGShmemHeader)` (`:748`). The big
  segment is anon-mmap, the SysV block is essentially a 24-byte beacon.
  `[verified-by-code at :739-757]`
- **EXEC_BACKEND forces full SysV.** Anonymous mmap regions are NOT
  inherited across `exec()`. So on Windows-style EXEC_BACKEND builds, the
  entire segment uses SysV (`:58-63`, `[from-comment]`). Practical
  consequence: EXEC_BACKEND builds need much higher `SHMMAX`.
- **Huge pages are mmap-only.** `:730-734` rejects `huge_pages=on` when
  `shared_memory_type != mmap`. No huge-page support in the SysV path.
- **PG_SHMEM_ADDR env var** (`:140-153`) — debugging escape hatch for
  EXEC_BACKEND on macOS, where ASLR can place the postmaster's chosen
  shmat address somewhere the child can't reproduce. Default for macOS
  64-bit is `0x80000000000` (`:151`).
- **`SHMSTATE_UNATTACHED` zaps DSM too** (`:833-834`) — if the crashed
  postmaster had a DSM control segment, this is the place that cleans up
  the associated dynamic-shmem area. Without it, DSM segments from
  crashed postmasters would leak in `/dev/shm/` (Linux POSIX-shm DSM) or
  in SysV (sysv-shm DSM) until next reboot.
- **`HAVE_LINUX_EIDRM_BUG`** (`:386-389`, `:429-432`) — old Linux kernels
  returned `EIDRM` where the spec says `EINVAL`. Configure probes for
  this and the code branches accordingly.
- **`UsedShmemSegAddr` and `AnonymousShmem` are postmaster-global,
  inherited.** They get fork-inherited; children rely on the same address
  being valid in their own address space (which is automatic with
  non-EXEC_BACKEND fork, and reconstructed by `PGSharedMemoryReAttach` in
  EXEC_BACKEND).
- **`IpcMemoryDelete` is `on_shmem_exit`-registered AT CREATE TIME**
  (`:253`). Crash before that line → kernel SysV segment leak. The
  recycling-on-startup logic exists precisely to recover from that.
- **DataDir collision is the unrecoverable case.** If
  `PGSharedMemoryAttach` reports `ATTACHED` (live `shm_nattch > 0` with a
  matching DataDir header), the new postmaster aborts with
  `ERRCODE_LOCK_FILE_EXISTS` and the "Terminate any old server processes"
  hint (`:799-804`). Not a recycling case — there's a live process in
  there.

## Cross-refs

- `knowledge/subsystems/storage-ipc.md` — overall IPC layer.
- `knowledge/files/src/include/storage/pg_shmem.h.md` — `PGShmemHeader`
  layout and the abstract interface.
- `knowledge/files/src/backend/storage/ipc/dsm.c.md` —
  `dsm_cleanup_using_control_segment` consumer.
- `knowledge/files/src/backend/port/win32_shmem.c.md` — Windows analog
  (uses `CreateFileMapping` instead of `shmget`/`mmap`).
- `knowledge/files/src/backend/port/sysv_sema.c.md` — sister file that
  uses the same DataDir-inode key-seeding and dead-postmaster recycling
  patterns.
