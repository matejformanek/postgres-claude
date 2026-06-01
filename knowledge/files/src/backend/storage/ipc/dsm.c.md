# `storage/ipc/dsm.c`

- **Source:** `source/src/backend/storage/ipc/dsm.c` (1311 lines)
- **Header:** `source/src/include/storage/dsm.h`
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** deep-read (spine + lifecycle)

## Purpose

**Dynamic Shared Memory (DSM)** — segments that can be created and
destroyed during server runtime, unlike the main shared-memory region
(`shmem.c`) which is sized once at postmaster startup. Primary user:
**parallel query** (each parallel group allocates a DSM segment to
ferry tuples + plan state to workers).

This file is the **convenience layer**: lifetime management, resource
owner integration, refcount control-segment bookkeeping. The
OS-level creation/destruction lives in `dsm_impl.c`.

> "Unlike the low-level facilities provided by dsm_impl.h and
> dsm_impl.c, mappings and segments created using this module will be
> cleaned up automatically." `[from-comment] dsm.c:6-16`.

## The control segment

A *separate* DSM segment, created at postmaster startup
(`dsm_postmaster_startup`), holds the `dsm_control_header` — refcount
table for all live segments. Format:

```c
struct dsm_control_header {
    uint32 magic;       /* PG_DYNSHMEM_CONTROL_MAGIC = 0x9a503d32 */
    uint32 nitems;
    uint32 maxitems;
    dsm_control_item item[FLEXIBLE_ARRAY_MEMBER];
};
struct dsm_control_item {
    dsm_handle handle;
    uint32     refcnt;   /* 2+ active, 1 moribund, 0 gone */
    size_t     first_page, npages;
    void      *impl_private_pm_handle;  /* Windows only */
    bool       pinned;
};
```

Sizing: `maxitems = 64 + 5 * MaxBackends`. `:204-206`.

The control segment handle itself is stored in `PGShmemHeader->dsm_control`,
so a crash-recovery postmaster restart can find leftover DSM segments
via `dsm_cleanup_using_control_segment` and destroy them.

**Crash safety**: at every fresh postmaster startup, the previous
control handle (if any) is read from `postmaster.pid`-ish state and
each non-zero-refcount segment is destroyed via the `dsm_impl_op`
backend. `:247-317`. The control segment is then created with a new
random handle (`pg_prng_uint32 << 1`, even numbers only; odd-numbered
handles are reserved for "main region" DSMs). `:216-228`.

## Main-region DSM (`dsm_main_space`)

To avoid the overhead of `shm_open` for small segments, DSM
preallocates a slab inside the main shared memory at postmaster
startup (registered as a normal shmem area via `dsm_shmem_callbacks`).
Small segments are carved out of this slab using a `freepage` allocator.
Handles with the **low bit set** are main-region slot numbers, not
real OS shm handles. `:1270-1294`.

## Per-backend state

`dsm_segment` is a backend-private descriptor:

```c
struct dsm_segment {
    dlist_node    node;            /* in dsm_segment_list */
    ResourceOwner resowner;
    dsm_handle    handle;
    uint32        control_slot;
    void         *impl_private;    /* OS-specific */
    void         *mapped_address;
    Size          mapped_size;
    slist_head    on_detach;       /* callbacks */
};
```

The `ResourceOwner` integration means that when a transaction aborts
or `CurrentResourceOwner` is released, any DSM mappings it created
are auto-detached. `dsm_pin_mapping(seg)` moves the segment to
`TopTransactionResourceOwner` so it survives subtransaction cleanup;
`dsm_pin_segment(seg)` bumps refcount to keep it alive even after
*every* backend has detached (used for shmem-resident DSMs that
postmaster manages).

## Lifecycle

### `dsm_create(size, flags)` (`:524`)

1. Allocate from main region if possible; else create new OS segment
   via `dsm_impl_op(DSM_OP_CREATE, …)` with a random handle.
2. Insert refcount=2 entry into control segment (one for the creator,
   one is the "exists" mark — refcount drops to 1 when there are no
   active mappings; the actual destroy happens at refcount 0).
3. Register `dsm_resource` for `CurrentResourceOwner`.

### `dsm_attach(handle)` (`:673`)

Other backend joins: find the control slot by handle, bump refcount,
`dsm_impl_op(DSM_OP_ATTACH, …)` to map the OS segment.

### `dsm_detach(seg)` (`:811`)

Walks `on_detach` callbacks (in reverse order — slist push order),
unmaps, decrements refcount. If we were the last user and the
segment was not `pinned`, calls `DSM_OP_DESTROY`.

### `dsm_postmaster_shutdown` (`:368`)

Registered as `on_shmem_exit`. Walks the control segment and destroys
every segment with non-zero refcount (so a clean shutdown doesn't
leak OS resources).

## on_dsm_detach callbacks

`on_dsm_detach(seg, fn, arg)` — register a callback to run when this
backend detaches (`slist_push_head`). `cancel_on_dsm_detach` looks up
and removes. Used by `shm_mq` (sender/receiver detach), parallel
query (DSA detach), tuplestore-on-DSM cleanup, etc.

Like the `on_shmem_exit` callbacks in `ipc.c`, each callback is removed
from the list *before* being invoked — re-entry via ereport doesn't
re-run completed ones. `:1140-1180`.

## `dsm_backend_shutdown` (`:765`)

Called from `shmem_exit` in `ipc.c`. Walks all current mappings and
calls `dsm_detach`. **This is hand-called** from `shmem_exit` rather
than registered as an `on_shmem_exit` callback, because it has its own
internal "progressive removal" loop that survives partial errors.
`[from-comment]` `ipc.c:260-269`.

`dsm_detach_all` is similar but called from postmaster children
(non-attaching, e.g. logger) that need to release inherited DSM
mappings without doing the full detach dance.

## Implementations

Selected by `dynamic_shared_memory_type` GUC, dispatched through
`dsm_impl_op`:

- `DSM_IMPL_POSIX` — `shm_open` + `mmap` (default on most Unix).
- `DSM_IMPL_SYSV` — `shmget` + `shmat` (small default limits).
- `DSM_IMPL_WINDOWS` — `CreateFileMapping` + `MapViewOfFileEx`.
- `DSM_IMPL_MMAP` — file-backed mmap in `PG_DYNSHMEM_DIR =
  "pg_dynshmem"`. Slow (writeback), used as a fallback or for
  ports where shared anon-mmap is broken.

`dsm_cleanup_for_mmap` scans `pg_dynshmem/` at startup to clean up
files from a crashed postmaster (since mmap files can outlive even
a system reboot). `:319-366`.

## Cross-references

- `dsm_impl.c` — OS primitives behind `dsm_impl_op`.
- `dsm_registry.c` — named DSM segments (for extensions; segments
  outlive a single transaction).
- `utils/mmgr/dsa.c` — Dynamic Shared *Allocator*. Carves
  variable-size chunks out of DSM segments.
- `lib/dshash.c` — shared hash table on top of DSA.
- `storage/ipc/shm_mq.c`, `shm_toc.c` — usually placed inside a DSM
  segment for parallel query.
- `access/transam/parallel.c` — primary consumer (parallel query
  workers all `dsm_attach` to the leader's segment).

## Open questions / unverified

1. **Crash recovery and dangling segments**: `dsm_cleanup_using_control_segment`
   relies on being able to `dsm_impl_op(DSM_OP_ATTACH, old_handle)`
   to inspect the *old* control segment. If the OS rebooted between
   crash and restart, the segment is gone — the function returns
   quietly. For mmap impl, `dsm_cleanup_for_mmap` scans the directory
   instead. The two paths are independent; for POSIX/SysV on a
   reboot, **the leftover OS segments would never be cleaned up by
   PG itself** — relying on the OS reaping them on next boot.
   `[verified-by-code] :260-268`.
2. **Refcount race**: comment at `:80-88` says `refcnt 1 = moribund,
   0 = gone`. The atomic increment/decrement happens under the
   control segment's internal lock — I did not chase that lock.
   `[unverified-here]`.
3. The `even-handle-numbers-only` rule (`handle << 1` ensures even)
   reserves odd for main-region slots. `[from-comment] :220, :1270`.
   Backend code must use `is_main_region_dsm_handle(h)` rather than
   testing the low bit directly — this is the only canonical check.

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/optimizer.md](../../../../../subsystems/optimizer.md)
- [subsystems/storage-ipc.md](../../../../../subsystems/storage-ipc.md)
