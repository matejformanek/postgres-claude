# `storage/ipc/dsm_registry.c`

- **Source:** `source/src/backend/storage/ipc/dsm_registry.c` (492 lines)
- **Header:** `source/src/include/storage/dsm_registry.h`
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** read

## Purpose

**Named DSM segments** — lets an extension allocate shared memory at
runtime (in any backend, not just at postmaster startup via the
shmem_request_hook) without race-prone double-creation.

Without this, an extension that needed shared memory had two bad
options:
1. Be registered in `shared_preload_libraries` so it can hook
   `shmem_request_hook` at startup.
2. Roll its own `dsm_create` + handle-broadcast.

`dsm_registry` solves both: any backend can ask "give me the DSM
segment named `foo`, allocate it if no one has yet, initializing with
this callback". The first caller wins; everyone else gets the
existing segment.

## API

- `GetNamedDSMSegment(name, size, init_callback, found)` — raw DSM
  segment.
- `GetNamedDSA(name, found)` — Dynamic Shared *Allocator* (heap-like
  shared-mem allocator).
- `GetNamedDSHash(name, params, found)` — concurrent shared hash table
  on top of a DSA.

`*found` tells the caller whether the area was already initialized
(so they know not to re-fill it).

## Internal shape

The registry itself is a `dshash` table keyed by name string, stored
inside a DSA. Two layers of indirection:

- `DSMRegistryShmemCallbacks` registers a small struct
  `DSMRegistryCtxStruct { dsa_handle, dshash_table_handle }` in the
  main shared memory (via `subsystemlist.h` callbacks).
- The DSA itself is lazily created on first use; the dshash table is
  inside it.
- Each registered named region has an entry in the dshash with the
  appropriate handle (a `dsm_handle`, a `dsa_handle`, or a dshash
  handle, depending on kind).

## Concurrency

`GetNamedDSMSegment` takes the dshash partition lock; if the name is
new, it calls `dsm_create`, `init_callback(addr)`, then inserts.
Others see the entry and `dsm_attach`. So initialization runs exactly
once. `[inferred]` — standard dshash idiom; not re-traced in detail.

## SQL-visible

`pg_dsm_registry_allocations` SRF — lists all registered names and
sizes.

## Cross-references

- `lib/dshash.c` — backing concurrent hash table.
- `utils/mmgr/dsa.c` — the dynamic shared allocator.
- Used by many extensions (e.g. `pg_prewarm`'s autoprewarm,
  `pg_stat_statements`'s spilling, etc.) and by some built-in
  facilities that came after `subsystemlist.h` was viable.

## Open questions

1. Whether `init_callback` is allowed to throw `ERROR`. If yes, the
   registry needs to leave the entry uninstalled so a retry isn't
   blocked. `[unverified]` — would need to read `GetNamedDSMSegment`
   body in detail.
2. **`pg_dsm_registry_allocations` race** with concurrent
   creation/destroy — the SRF holds the partition lock during the
   walk, so reads are consistent. `[inferred]`.
