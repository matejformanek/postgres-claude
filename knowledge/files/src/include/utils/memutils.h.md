# `src/include/utils/memutils.h`

- **File:** `source/src/include/utils/memutils.h` (322 lines)
- **Last verified commit:** `ef6a95c7c64de07dff4dd1f1da88ffae7b086ef3` (2026-06-01)

## Purpose

Public surface of the memory-context subsystem that is **not** so universal
that it needs to live in `palloc.h` (which is dragged in via `postgres.h`
into every TU). Declares the size-limit constants, the global top-level
context pointers, the type-independent `MemoryContext*` API
(`MemoryContextInit/Reset/Delete/...`), and the per-implementation
`*ContextCreate` constructors for AllocSet / Slab / Generation / Bump.
Also defines the recommended `ALLOCSET_*_SIZES` tuples and the
`pg_memory_is_all_zeros` inline scanner. (`memutils.h:1-16, 70-105`
[from-comment]).

## Public surface

### Size limits (`memutils.h:23-49`)

- `MaxAllocSize = 0x3fffffff` (1 GB - 1) — palloc enforces this; chosen to
  match TOAST varlena header limits so any allocatable size fits in a
  varlena and so doubling can't overflow `int`/`size_t`
  (`memutils.h:23-40` [from-comment]).
- `MaxAllocHugeSize = SIZE_MAX / 2` — ceiling for `MemoryContextAllocHuge`
  / `repalloc_huge`. Specifically `SIZE_MAX/2` so `add_size`/`mul_size`
  callers can still do safe arithmetic (`memutils.h:44-45`
  [from-comment]).
- `InvalidAllocSize = SIZE_MAX` — sentinel used by `aset.c` to mark a
  pfree'd chunk under `MEMORY_CONTEXT_CHECKING` (used for double-free
  detection in `AllocSetFree`) (`memutils.h:47` [verified-by-code]).
- `AllocSizeIsValid(size)` / `AllocHugeSizeIsValid(size)` — predicates
  used everywhere in the allocator implementations (`memutils.h:42, 49`).

### Top-level context pointers (`memutils.h:52-67`)

- `TopMemoryContext`, `ErrorContext`, `PostmasterContext`,
  `CacheMemoryContext`, `MessageContext`, `TopTransactionContext`,
  `CurTransactionContext`, `PortalContext` — all `PGDLLIMPORT
  MemoryContext` globals.
- Comment: "Only `TopMemoryContext` and `ErrorContext` are initialized by
  `MemoryContextInit()` itself" — every other one is created by its
  owning subsystem (`memutils.h:53-57` [from-comment]). See
  `mcxt.c:362-398` for the `TopMemoryContext`/`ErrorContext` setup.
- `PortalContext` is documented as a **transient link** that points at
  whichever portal is currently executing — not stably owned
  (`memutils.h:66-67` [from-comment]).

### Type-independent API (`memutils.h:70-105`)

`MemoryContextInit`, `MemoryContextReset`, `MemoryContextDelete`,
`MemoryContextResetOnly`, `MemoryContextResetChildren`,
`MemoryContextDeleteChildren`, `MemoryContextSetIdentifier`,
`MemoryContextSetParent`, `GetMemoryChunkContext`, `GetMemoryChunkSpace`,
`MemoryContextGetParent`, `MemoryContextIsEmpty`,
`MemoryContextMemAllocated`, `MemoryContextMemConsumed`,
`MemoryContextStats`, `MemoryContextStatsDetail`,
`MemoryContextAllowInCriticalSection`. Implementations all in
`mcxt.c` (`memutils.h:73-94` [verified-by-code]).

`MemoryContextCheck` is declared only under `MEMORY_CONTEXT_CHECKING`
(`:96-98`) — same #ifdef gate used in all per-impl `*Check` callbacks
(see `memutils_internal.h:34-36, 51-53, 69-71, 94-96`).

`MemoryContextCopyAndSetIdentifier(cxt, id)` macro — convenience that
calls `MemoryContextStrdup(cxt, id)` first; comment warns about double
evaluation of `id` (`memutils.h:100-102` [from-comment]).

`HandleLogMemoryContextInterrupt` / `ProcessLogMemoryContextInterrupt`
(`:104-105`) — signal hooks for `pg_log_backend_memory_contexts(pid)`;
implementations at `mcxt.c:1326, 1343`.

### Per-implementation creators (`memutils.h:108-151`)

- `AllocSetContextCreateInternal(parent, name, minContextSize,
  initBlockSize, maxBlockSize)` (`:112-116`).
- `SlabContextCreate(parent, name, blockSize, chunkSize)` (`:134-137`).
- `GenerationContextCreate(parent, name, minContextSize, initBlockSize,
  maxBlockSize)` (`:140-144`).
- `BumpContextCreate(parent, name, minContextSize, initBlockSize,
  maxBlockSize)` (`:147-151`).

### `AllocSetContextCreate` wrapper macro (`memutils.h:118-131`)

When `HAVE__BUILTIN_CONSTANT_P` is defined, the macro wraps
`AllocSetContextCreateInternal` in a `StaticAssertExpr` that requires
`__builtin_constant_p(name)` — i.e. **context names must be string
literals**. Variable identifiers must go through
`MemoryContextSetIdentifier` instead (`memutils.h:118-122`
[from-comment]). Otherwise (no GCC builtin) the macro reduces to a plain
alias.

This is also why every constructor in `aset.c` / `slab.c` /
`generation.c` / `bump.c` takes `const char *name` and stashes the
pointer without copying — the assumption is the name lives forever in
text memory.

### Recommended `ALLOCSET_*_SIZES` (`memutils.h:153-178`)

- `ALLOCSET_DEFAULT_SIZES` = `(0, 8K, 8M)` — ordinary contexts
  (`:157-161`).
- `ALLOCSET_SMALL_SIZES` = `(0, 1K, 8K)` — small/bounded contexts e.g.
  per-query plan storage (`:166-171`).
- `ALLOCSET_START_SMALL_SIZES` = `(0, 1K, 8M)` — start small, may grow
  (`:174-178`).

These two **exact** shapes (`ALLOCSET_DEFAULT_*` and `ALLOCSET_SMALL_*`,
ignoring `maxBlockSize`) are what `aset.c`'s `context_freelists[2]`
recycle cache keys on (`aset.c:219-241` [verified-by-code]).

### `ALLOCSET_SEPARATE_THRESHOLD = 8192` (`memutils.h:182-187`)

> "Threshold above which a request in an AllocSet context is certain to
> be allocated separately (and thereby have constant allocation
> overhead). Few callers should be interested in this, but
> tuplesort/tuplestore need to know it."

Statically asserted equal to `aset.c`'s `ALLOC_CHUNK_LIMIT`
(`aset.c:91-92` [verified-by-code]). External consumers: `tuplesort.c`,
`tuplestore.c` [unverified — declared in comment].

### Slab block-size defaults (`memutils.h:189-190`)

- `SLAB_DEFAULT_BLOCK_SIZE = 8K`
- `SLAB_LARGE_BLOCK_SIZE = 8M`

Consumed by callers of `SlabContextCreate`. (See `slab.c.md` for usage
patterns.)

### `pg_memory_is_all_zeros` (`memutils.h:192-320`)

Inline-defined, no out-of-line implementation. Hot inline helper that
tests whether `len` bytes at `ptr` are all zero. Three-case structure:

- **Case 1**: `len < sizeof(size_t)` → byte-by-byte (`:226-234`).
- **Case 2**: `len < 8 * sizeof(size_t)` → align then `size_t` stride,
  then trailing bytes (`:237-267`).
- **Case 3**: `len >= 8 * sizeof(size_t)` → align, then unrolled
  8×`size_t` loop with bitwise-OR combination so the compiler can emit
  SIMD, then `size_t` stride, then trailing bytes (`:269-319`).

The unrolled inner loop **purposefully uses bitwise-OR** ("not boolean
short-circuiting") so all 8 lanes are read regardless of result,
making it vectorizable (`:281-290` [from-comment]).

Caller must ensure `ptr != NULL` — documented but not asserted
(`:216` [from-comment]).

## Key invariants

- **Context names must be string literals** (compile-time constant) when
  using `AllocSetContextCreate` macro form. Use
  `MemoryContextSetIdentifier` for runtime-computed identifiers
  (`memutils.h:118-122` [from-comment]).
- **`MaxAllocSize` is the soft ceiling**; only `*Huge` variants exceed
  it. The 1 GB - 1 bound is locked to varlena header semantics — any
  change cascades into TOAST and many datatype assumptions
  (`memutils.h:31-38` [from-comment]).
- **`ALLOCSET_SEPARATE_THRESHOLD == ALLOC_CHUNK_LIMIT == 8192`**, locked
  by `StaticAssertDecl` in `aset.c`. Callers like tuplesort use this
  exact constant to decide when to spill to tape (`memutils.h:182-187`
  + `aset.c:91-92` [verified-by-code]).
- **Only `TopMemoryContext` + `ErrorContext` are guaranteed to exist
  after `MemoryContextInit`**; everything else (`CacheMemoryContext`,
  `MessageContext`, `TopTransactionContext`, …) is created lazily by
  the subsystem that owns it (`memutils.h:53-57` [from-comment]).

## Cross-references

- `mcxt.c` — implements every `MemoryContext*` and the global pointer
  definitions (`mcxt.c:161-176, 362-398`).
- `aset.c`, `slab.c`, `generation.c`, `bump.c` — per-impl creators
  declared here.
- `palloc.h` — the *other* half of the public memory-mgmt API, kept
  small because it's pulled in by every backend TU via `postgres.h`.
- `memutils_internal.h` — per-impl callback prototypes + the
  `MemoryContextMethodID` enum that gates `mcxt_methods[]` dispatch.
- `memutils_memorychunk.h` — `MemoryChunk` header that every impl uses
  for `MemoryContextMethodID` encoding.
- `knowledge/idioms/memory-contexts.md` — idiom-level digest.
- `knowledge/files/src/backend/utils/mmgr/README.md` — canonical design
  doc index.

## Confidence tag tally

- `[verified-by-code]` × 6
- `[from-comment]` × 11
- `[unverified]` × 1

## Synthesized by
<!-- backlinks:auto -->
- [idioms/memory-contexts.md](../../../../idioms/memory-contexts.md)
- [subsystems/utils-mmgr.md](../../../../subsystems/utils-mmgr.md)
- [idioms/memory-context-allocset-internals.md](../../../../idioms/memory-context-allocset-internals.md)
