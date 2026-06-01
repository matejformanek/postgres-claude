# `storage/ipc/dsm_impl.c`

- **Source:** `source/src/backend/storage/ipc/dsm_impl.c` (1054 lines)
- **Header:** `source/src/include/storage/dsm_impl.h`
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## Purpose

**OS-level backend implementations of dynamic shared memory.** This is
the layer below `dsm.c`. `dsm.c` calls `dsm_impl_op(op, handle, …)`
and this file dispatches to one of:

- `dsm_impl_posix` — `shm_open(2)` + `mmap(2)` (default on most Unix).
  Identifiers live in a system-wide namespace under `/dev/shm` (Linux).
- `dsm_impl_sysv` — `shmget(2)` + `shmat(2)`. Older SysV API, often
  small default limits (`SHMMAX`/`SHMALL`); rarely chosen.
- `dsm_impl_windows` — `CreateFileMapping` + `MapViewOfFileEx`.
- `dsm_impl_mmap` — file-backed `mmap` in `pg_dynshmem/`. Used as a
  fallback or for ports where anonymous shared memory is unavailable;
  slower because dirty pages incur writeback.

> "As ever, Windows requires its own implementation." [from-comment]
> `:37`.

## Operations (`dsm_op`)

- `DSM_OP_CREATE` — create+attach a new segment of `request_size`.
- `DSM_OP_ATTACH` — map an existing segment.
- `DSM_OP_DETACH` — unmap.
- `DSM_OP_DESTROY` — unmap + remove from OS namespace.

## Per-impl notes

### POSIX (`shm_open` + `mmap`)

- Name format: `/PostgreSQL.<handle>` (slash + uppercase prefix).
- Uses `dsm_impl_posix_resize(fd, size)` to grow files (combining
  `posix_fallocate` and `ftruncate`).
- Cleanup on `DSM_OP_DESTROY`: `shm_unlink` removes the name; existing
  attaches survive until last unmap.

### SysV (`shmget`)

- Handle is mapped to a key via `IPCProtection`-derived computation
  (since SysV uses 32-bit `key_t`).
- Smaller default `SHMMAX` (often 32 MiB) makes large segments
  unreliable on many systems.

### Windows

- Names go in `Global\\PostgreSQL.<handle>`. Permissions inherited from
  postmaster.
- Handle inheritance is *explicit*; in EXEC_BACKEND mode the parent
  duplicates handles.

### MMAP

- Files in `pg_dynshmem/<handle>`. Cleaned up by
  `dsm_cleanup_for_mmap` in `dsm.c` at postmaster startup.

## GUC: `dynamic_shared_memory_type`

Sets `dynamic_shared_memory_type` (POSIX / SYSV / WINDOWS / MMAP).
`USE_DSM_*` macros at compile time gate which impls are present.

## Cross-references

- `dsm.c` — sole caller of `dsm_impl_op`.
- `port/pg_shmem.c` — main-shmem-region creation (independent OS path).
- `utils/misc/guc_tables.c` — `dynamic_shared_memory_type` GUC.

## Open questions

1. **Linux's `/dev/shm` filesystem size** caps POSIX DSM at usually
   half of RAM; on small VMs this can become a problem for parallel
   query. Not enforced by this file; surfaces as runtime errors
   from `shm_open` returning `ENOSPC`. `[unverified]`.
2. **Anti-reattach protection on POSIX after a crash**: the file
   relies on `dsm.c::dsm_cleanup_using_control_segment` to find and
   destroy leftovers. If postmaster crashes between creating a
   segment and writing the new control-segment handle to
   `postmaster.pid`, the segment leaks. `[inferred]`.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/storage-ipc.md](../../../../../subsystems/storage-ipc.md)
