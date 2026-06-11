# `src/backend/storage/ipc/shmem_hash.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~206
- **Source:** `source/src/backend/storage/ipc/shmem_hash.c`

Thin "carve a hash table out of a fixed shmem area" layer on top of
`utils/hash/dynahash.c`. Every shmem hash gets its own private free
list within its region — so deletes don't fragment some global heap.
Provides both the modern `ShmemRequestHash` callback-driven flow and a
legacy `ShmemInitHash` entry point retained for backwards compatibility
with extensions. [verified-by-code] [from-comment]

## API / entry points

- `ShmemRequestHashWithOpts(const ShmemHashOpts *options)` — copy the
  caller's `ShmemHashOpts` into TopMemoryContext (so it survives the
  request → init phase boundary), compute the area size via
  `hash_estimate_size`, and dispatch to `ShmemRequestInternal` with
  kind `SHMEM_KIND_HASH` (lines 43-60). [verified-by-code]
- `shmem_hash_init(location, base_options)` — `init_fn` registered for
  shmem hash structs; sets `hash_info.hctl = location` and calls
  `shmem_hash_create(found=false, ...)`. Optionally writes the HTAB
  pointer to `*options->ptr` (lines 62-76). [verified-by-code]
- `shmem_hash_attach(location, base_options)` — `attach_fn` for
  EXEC_BACKEND-style attach. Sets `HASH_ATTACH`, then
  `shmem_hash_create(found=true, ...)` (lines 78-95). [verified-by-code]
- `ShmemInitHash(name, nelems, infoP, hash_flags)` — **legacy** entry
  for extensions. Wraps `ShmemInitStruct` + `shmem_hash_create`.
  Comment at lines 113-115 advises new code to use `ShmemRequestHash`.
  Note at lines 128-135 explains an internal accounting quirk: the area
  is registered as `SHMEM_KIND_STRUCT` (opaque) rather than `_HASH`
  because this path does the hash init itself, by hand, rather than via
  callbacks. [from-comment]
- `shmem_hash_create(location, size, found, name, nelems, infoP,
  hash_flags)` — the actual heavy lifting. Sets `HASH_SHARED_MEM |
  HASH_ALLOC | HASH_FIXED_SIZE` on the flags; supplies `ShmemHashAlloc`
  as the dynahash allocator with a `shmem_hash_allocator` walking
  pointer from `location` to `location+size`. On `found = true`, sets
  `HASH_ATTACH` instead and passes the pre-existing HCTL header
  (lines 149-183). [verified-by-code]
- `ShmemHashAlloc(size, alloc_arg)` (static) — bump-pointer allocator;
  MAXALIGNs `size`, returns NULL if no room. Used only during creation
  because `HASH_FIXED_SIZE` means no growth post-init (lines 192-206).
  [verified-by-code]

## Notable invariants / details

- "Each hash table has its own free list" (header comment line 11) is
  achieved by giving dynahash a private allocator (`ShmemHashAlloc`)
  whose carve-out region is local to one hash table. There is no
  global free list of dead hash entries across tables. [from-comment]
- `HASH_FIXED_SIZE` is forced on (line 163) — shmem hash tables can
  never grow, because shmem itself can't grow. The size requested at
  `ShmemRequestHashWithOpts` time is the cap forever. [verified-by-code]
- `HASH_ALLOC` is forced on (line 163), which directs dynahash to use
  the supplied `infoP->alloc` callback rather than its built-in
  `ShmemAllocNoError`. The custom allocator allows bump-pointer
  carving from the pre-reserved region. [verified-by-code]
- `MAXALIGN` of every individual allocation (line 198): dynahash
  internals do their own alignment too, but this is a defensive
  belt-and-suspenders ensuring the bump pointer always sits on aligned
  boundaries. [verified-by-code]
- Legacy `ShmemInitHash` (lines 116-140) is the "old style" extension
  API that does request + init in one call, suitable for extensions
  loaded via `shared_preload_libraries` that allocate from their own
  `shmem_request_hook`. Comment marks it as legacy but it's still in
  use by many in-tree subsystems (e.g. several lock-table inits).
  [from-comment]
- `SHMEM_KIND_STRUCT` accounting in `ShmemInitHash` (line 128-135) —
  the area is reported as a generic struct in `pg_shmem_allocations`,
  not as a hash table. Quirky but documented. [from-comment]
- The two paths (`shmem_hash_init` callback vs `ShmemInitHash` direct)
  share `shmem_hash_create` to keep the actual creation logic single-sourced.
  [verified-by-code]
- `shmem_hash_create` is exported (lines 148-183) "to allow
  InitShmemAllocator() to share the logic for bootstrapping the
  ShmemIndex hash table" (comment at 142-146) — the chicken-and-egg
  bootstrap dance for `ShmemIndex` itself uses this directly.
  [from-comment]

## Potential issues

- Line 50-52. `MemoryContextAlloc(TopMemoryContext, sizeof(ShmemHashOpts))`
  leaks across the request → init phase boundary by design; the copy
  must outlive the caller's stack frame. The leak is bounded by the
  number of distinct shmem hash tables requested at postmaster startup
  (small). Not really a leak — just a long-lived allocation. [verified-by-code]
- Line 200-201. `if (allocator->end - allocator->next < size) return
  NULL;` — dynahash will turn this into an error inside `hash_create`
  if the very first chunk fails (segment-zero allocation), but later
  failures (during hash-table growth attempts) are mostly impossible
  because `HASH_FIXED_SIZE` prevents growth. The returned NULL would be
  surprising to read since the allocator is documented as "no locking
  required because all allocations happen upfront". [verified-by-code]
- The `shmem_hash_allocator` struct (lines 29-33) is a stack local
  inside `shmem_hash_create` (line 152) and the dynahash routine
  consumes it via `infoP->alloc_arg`. This works because the dynahash
  call completes before `shmem_hash_create` returns, but the lifetime
  contract (allocator must outlive every `alloc()` call) is not stated
  in a comment. [ISSUE-undocumented-invariant: shmem_hash_allocator
  lifetime contract is implicit — must outlive dynahash creation but
  no comment says so (nit)]
