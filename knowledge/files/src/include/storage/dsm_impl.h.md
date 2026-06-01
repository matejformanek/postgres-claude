# `storage/dsm_impl.h`

- **Source:** `source/src/include/storage/dsm_impl.h` (79 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** full-read

Low-level DSM impl primitives. See `dsm_impl.c.md` for per-backend
notes.

## Impl IDs

```
DSM_IMPL_POSIX    = 1   /* shm_open + mmap (Linux default) */
DSM_IMPL_SYSV     = 2   /* shmget */
DSM_IMPL_WINDOWS  = 3
DSM_IMPL_MMAP     = 4   /* file-backed mmap in pg_dynshmem/ */
```

`USE_DSM_*` macros gate which impls are compiled in. Default selection
in the header (`:26-39`): POSIX if `HAVE_SHM_OPEN`, else SYSV; Windows
on Windows. `USE_DSM_MMAP` is always defined on non-Windows.

## Operations

`dsm_op` enum: `DSM_OP_CREATE`, `_ATTACH`, `_DETACH`, `_DESTROY`.

`dsm_impl_op` is the single dispatch function; the upper layer
(`dsm.c`) calls it through this façade.

## `dsm_handle`

A bare `uint32`. `DSM_HANDLE_INVALID = 0`. `dsm.c` enforces "even
numbers only" for OS-backed segments; odd-numbered handles are
reserved for main-region DSMs (carved out of preallocated main shmem).

## `min_dynamic_shared_memory` GUC

Reserves a chunk of the *main* shmem segment (sized by this GUC) for
DSM use. `dsm.c::dsm_main_space_*` carves these out with a freepage
allocator. Used by short-lived parallel-query segments to avoid
`shm_open` syscalls.

## Directory layout

- `pg_dynshmem/` — used by mmap impl for actual files, and by other
  impls for crash-recovery state (a small file with the previous
  control-segment handle).
- `pg_dynshmem/mmap.<handle>` — files for the mmap impl.
