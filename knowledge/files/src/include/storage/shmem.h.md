# `storage/shmem.h`

- **Source:** `source/src/include/storage/shmem.h` (197 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** full-read

Public API for the shared-memory allocator. See `shmem.c.md` for the
implementation.

## Historical note (from the header comment)

> "A long time ago, Postgres' shared memory region was allowed to be
> mapped at a different address in each process, and shared memory
> 'pointers' were passed around as offsets relative to the start of
> the shared memory region. That is no longer the case." `:11-17`.

**Every process maps shmem at the same address**, so shared-memory
pointers can be passed around directly. (Contrast with DSM, where you
still need offsets or `dsa_pointer`.)

## Key types

- **`ShmemStructOpts`** — `{name, size, alignment, **ptr}`. Used with
  the macro `ShmemRequestStruct(.name = ..., .size = ..., .ptr = &...)`.
  Designated initializers required for sane usage.
- **`ShmemHashOpts`** — embeds `ShmemStructOpts` + `nelems` + a
  `HASHCTL` + flags. The hash table backing is contiguous.
- **`ShmemCallbacks`** — `{flags, request_fn, init_fn, attach_fn,
  opaque_arg}`. Subsystems register one of these via
  `RegisterShmemCallbacks` (builtins via `subsystemlist.h`; extensions
  via `_PG_init`).

## Allowed-after-startup flag

`SHMEM_CALLBACKS_ALLOW_AFTER_STARTUP` allows extensions loaded into a
backend (not via `shared_preload_libraries`) to register late. **No
builtin subsystem uses this**; only extensions. `:159-167`.

## Legacy functions

`ShmemInitStruct`, `ShmemInitHash`, `ShmemAlloc`, `ShmemAllocNoError`,
`RequestAddinShmemSpace`. Kept for backwards compat with extensions
predating the callback system. New extension code should use
`ShmemRequestStruct` + `RegisterShmemCallbacks`. `[from-comment]
shmem.c:105-119`.

## `pg_get_shmem_pagesize`

Exposed via `PGDLLIMPORT` for extensions; not directly defined here.
Used for huge-page alignment.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/storage-ipc.md](../../../../subsystems/storage-ipc.md)
