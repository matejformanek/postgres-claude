# `storage/dsm_registry.h`

- **Source:** `source/src/include/storage/dsm_registry.h` (26 lines)
- **Last verified commit:** `ef6a95c7c64` (2026-06-01)
- **Depth:** full-read

Three functions:

- `GetNamedDSMSegment(name, size, init_cb, *found, arg)` — name → raw
  DSM segment. On first call, the system allocates and runs
  `init_cb(ptr, arg)`. Sets `*found = true` if it already existed.
- `GetNamedDSA(name, *found)` — name → `dsa_area *` (dynamic shared
  allocator).
- `GetNamedDSHash(name, params, *found)` — name → `dshash_table *`
  (concurrent shared hash table on top of a DSA).

See `dsm_registry.c.md`. This API is **the answer for extensions that
need shared memory but cannot be in `shared_preload_libraries`** — for
example because their hook activates only when a feature is used.
