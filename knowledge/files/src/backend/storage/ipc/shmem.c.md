# `storage/ipc/shmem.c`

- **Source:** `source/src/backend/storage/ipc/shmem.c` (1298 lines)
- **Header:** `source/src/include/storage/shmem.h`, `storage/shmem_internal.h`
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** deep-read

## Purpose

The shared-memory allocator + named-area registry. Every fixed-size
shmem region in PG (lock tables, ProcArray, buffer pool descriptors,
sinval buffer, …) is carved here.

Two coexisting interfaces:
1. **`ShmemRequestStruct` / `RegisterShmemCallbacks`** — modern,
   declarative. Used by all builtin subsystems via
   `subsystemlist.h`. `[verified-by-code]`.
2. **`ShmemInitStruct` / `RequestAddinShmemSpace`** — legacy. Still
   present mainly for extensions. New code should not use it.
   `[from-comment]` `shmem.c:105-119`.

## Layout

The first thing in the segment (at `PGShmemHeader->content_offset`) is
`ShmemAllocatorData` `:224-234`:

```c
struct ShmemAllocatorData {
    Size     free_offset;   /* bump-pointer; first free byte */
    slock_t  shmem_lock;    /* spinlock protecting free_offset */
    HASHHDR *index;         /* points to ShmemIndex (a HASHHDR) */
    size_t   index_size;
    LWLock   index_lock;    /* ShmemIndexLock */
};
```

After that sits `ShmemIndex` — a HASH table of `ShmemIndexEnt`
(key = 48-byte string name, value = `{void *location; Size size,
allocated_size}`). `:255-272`. Every named area is registered here,
which is what `pg_shmem_allocations` reads.

`ShmemAlloc` is a **bump allocator** — `free_offset` only grows; you
cannot free anything. `[from-comment] :43-46`. The bump uses a
spinlock, all allocations are aligned to at least `PG_CACHE_LINE_SIZE`
(currently 128 B on most platforms). `:804-816`.

## Lifecycle state machine (per-process)

`enum shmem_request_state` `:184-213`:

```
Postmaster:  INITIAL → REQUESTING → INITIALIZING → DONE
EXEC_BACKEND child:  INITIAL → REQUESTING → ATTACHING → DONE
Late request:  DONE → REQUESTING → AFTER_STARTUP_ATTACH_OR_INIT → DONE
```

The state is checked on every entry, so requesting shmem at the
wrong moment is a hard error.

## The pipeline

1. `RegisterBuiltinShmemCallbacks()` in `ipci.c` walks
   `subsystemlist.h`, appending each `ShmemCallbacks` to
   `registered_shmem_callbacks` (a `List` in `TopMemoryContext`).
   Also done for extensions via `RegisterShmemCallbacks`. `:872-892`.
2. `ShmemCallRequestCallbacks()` (called from postmaster startup) sets
   state to `REQUESTING` and runs every `request_fn`. Each callback
   issues `ShmemRequestStruct(.name=..., .size=..., .ptr=&MyShmem)`
   calls, appending `ShmemRequest` entries to `pending_shmem_requests`.
   `:977-992`.
3. `ShmemGetRequestedSize()` sums all sizes (with cache-line padding)
   plus the ShmemIndex hash space. `:390-414`.
4. After `PGSharedMemoryCreate`, `InitShmemAllocator(seghdr)` builds
   the allocator + ShmemIndex inside the new segment, and registers
   ShmemIndex *into itself* under name "ShmemIndex". `:636-736`.
5. `ShmemInitRequested()` walks `pending_shmem_requests`,
   `InitShmemIndexEntry` for each — inserts the hash entry,
   calls `ShmemAllocRaw` for the area, sets `*(request->options->ptr)`
   to the new location, then for `SHMEM_KIND_HASH` / `SHMEM_KIND_SLRU`
   calls `shmem_hash_init` / `shmem_slru_init`. `:423-454`.
6. Then runs every `init_fn` callback in registration order. State
   becomes `DONE`. `:447-453`.

In EXEC_BACKEND mode, each child re-runs `request_fn` (to populate
`pending_shmem_requests`), then `ShmemAttachRequested` looks up each
name in `ShmemIndex` and sets the local pointer variable, then calls
`attach_fn` if any. `:462-498`.

## After-startup requests

If `SHMEM_CALLBACKS_ALLOW_AFTER_STARTUP` is set in
`ShmemCallbacks.flags`, an extension loaded into a *backend* (not via
`shared_preload_libraries`) can still call `RegisterShmemCallbacks`.
The system then immediately runs `CallShmemCallbacksAfterStartup`
under `ShmemIndexLock` EXCLUSIVE: looks up whether the area already
exists; if all areas are new, calls `init_fn`; if all already exist,
calls `attach_fn`; mixed → `elog(ERROR, "found some but not all")`.
`:894-972`. **No builtin subsystem uses this; only extensions.**
`[from-comment] :164-166`.

## Locking

- `ShmemAllocator->shmem_lock` (spinlock) — protects `free_offset`.
  Held only for the duration of a single bump. `:820-834`.
- `ShmemIndexLock` (LWLock embedded in `ShmemAllocator->index_lock`) —
  protects ShmemIndex hash. SHARED for lookups (e.g. attach),
  EXCLUSIVE for `ShmemInitStruct` / `InitShmemIndexEntry`. `:236, 1024, 1037`.

## `ShmemInitStruct` (legacy)

Re-implemented as a thin wrapper over `AttachShmemIndexEntry` (with
`missing_ok=true`) and `InitShmemIndexEntry`. Returns the pointer and
sets `*foundPtr` so the caller can decide whether to initialize.
`:1009-1041`. **Note:** it still requires the size to match an
already-initialized entry; mismatch → `ERROR`.

## SQL-visible functions

- `pg_get_shmem_allocations()` SRF — walks `ShmemIndex` under shared
  `ShmemIndexLock`, reports `(name, offset, size, allocated_size)` for
  every named entry, plus an "<anonymous>" row for the unnamed
  allocations between named entries and a "<free>" row for the rest of
  the bump-pointer's slack. `:1044-1100`.
- `pg_get_shmem_allocations_numa()` — NUMA breakdown (touches each page
  once to materialize the mapping). `:1101+`.

## Cross-references

- `shmem_hash.c` — `shmem_hash_init/_attach/_create` for the
  `SHMEM_KIND_HASH` requests.
- `slru.c` — `shmem_slru_init/_attach` for `SHMEM_KIND_SLRU`.
- `ipci.c::CreateSharedMemoryAndSemaphores` is the only caller of
  `InitShmemAllocator` and `ShmemInitRequested`.
- `pg_shmem.c` — `PGSharedMemoryCreate` (the actual OS syscalls).

## Open questions

- Is there a way for an extension to *grow* its requested size after
  startup if it discovers it underestimated? Reading the code, **no**:
  `ShmemAllocator->free_offset` is a one-way bump pointer, and
  `SHMEM_INDEX_ADDITIONAL_SIZE=128` slots is the only reserve.
  `[verified-by-code] :255-262`. Late callers can only use the slack
  baked into `CalculateShmemSize()` (the literal `100000` plus rounding
  to 8 KiB).
- What happens if two extensions name their shmem areas identically?
  At `ShmemRequestInternal:368-374` the dedup is within a single
  process's `pending_shmem_requests`. At `InitShmemIndexEntry:522-523`,
  a duplicate in the index ERROR's out. So the collision *is* caught,
  but only when the second registrant tries to `ShmemInitRequested`,
  which is late in startup.
