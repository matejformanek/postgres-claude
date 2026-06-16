# `src/backend/utils/misc/injection_point.c`

- **Last verified commit:** `e18b0cb7344`
- **Lines:** ~619
- **Source:** `source/src/backend/utils/misc/injection_point.c`

Test-instrumentation infrastructure: injection points let a developer
name a code location, attach a callback from a loadable module, and
have it executed when that named point is reached. Gated by
`USE_INJECTION_POINTS` (only built when `meson … -Dinjection_points=true`
or autoconf `--enable-injection-points`). When the macro is undefined,
every public entry point ereports "not supported by this build" — so
the test-only nature is enforced at link time. [verified-by-code]

## API / entry points

- `InjectionPointAttach(name, library, function, private_data, size)`
  — register a point in shared memory. Stores a name (≤63 chars),
  library name (≤127), function name (≤127), and ≤1024 bytes of
  opaque private data. Errors on name reuse or `MAX_INJECTION_POINTS`
  (128) exhaustion. [verified-by-code]
- `InjectionPointDetach(name)` — flip the entry's generation
  counter to "free" (even); returns true if found. [verified-by-code]
- `InjectionPointRun(name, arg)` — refresh local cache from shared
  state; if a callback is present, invoke it as
  `cb(name, private_data, arg)`. The common case (no points attached)
  is a single atomic load of `max_inuse`. [verified-by-code]
- `InjectionPointCached(name, arg)` — like `Run` but never goes back
  to shared memory; safe to call from critical sections. Caller is
  expected to have done `InjectionPointLoad(name)` earlier in a
  non-critical region. [verified-by-code] [from-comment]
- `InjectionPointLoad(name)` — populate the local cache for `name`
  (so a later `Cached` call has the callback). [verified-by-code]
- `IsInjectionPointAttached(name)` — refresh and report presence.
  [verified-by-code]
- `InjectionPointList(void)` — `palloc` a `List *` of
  `InjectionPointData` records for all attached points. Holds
  `InjectionPointLock` in SHARED mode. [verified-by-code]

## Shared-memory state

- `InjectionPointsCtl` (line 84-88): single fixed-size array of 128
  `InjectionPointEntry` slots plus a `pg_atomic_uint32 max_inuse`
  cursor (entries used + 1). [verified-by-code]
- Each `InjectionPointEntry` (line 42-73) is protected by a per-entry
  `pg_atomic_uint64 generation` counter using the **even=free, odd=in-use**
  protocol explained in the in-file comment block (lines 44-61).
  Readers do a "load generation → memcpy fields → reload generation
  → if changed, retry" dance. Writers hold `InjectionPointLock`
  EXCLUSIVE. [verified-by-code] [from-comment]
- `pg_write_barrier()` + `pg_atomic_write_u64(...generation, +1)` is
  the publish step in `InjectionPointAttach` (line 329-330). The
  matching `pg_read_barrier()` is at line 474, between the
  generation load and the field copy. [verified-by-code]

## Local cache

- `InjectionPointCache` is a `HTAB` in `TopMemoryContext`. Caches the
  resolved `InjectionPointCallback` function pointer (which is
  expensive to obtain — `load_external_function` performs a `dlopen`)
  along with `slot_idx` and the generation seen at load time. [verified-by-code]
- `InjectionPointCacheRefresh` (line 407-507) is the workhorse:
  1. Read `max_inuse`. If 0, drop the entire local cache.
  2. Check the local cache; if entry's generation still matches the
     shared slot's, return cached.
  3. Otherwise scan all in-use slots; on a name match, copy the
     entry into local, re-check generation, and `dlopen` the library
     to bind the callback. [verified-by-code]
- `injection_point_cache_remove` deliberately leaks a stale callback's
  loaded library mapping: "Note that this leaks a callback loaded
  but removed later on, which should have no consequence from a
  testing perspective." [from-comment]
  [ISSUE-leak: documented dlopen leak on detach-after-load (nit)]

## Notable invariants / details

- **Lock-free read protocol:** writers MUST publish the entry's
  payload before incrementing the generation (lines 322-330); readers
  MUST read generation first, then copy, then re-read generation
  (lines 471-489). The barriers on both sides are critical — without
  them, a reader on a relaxed-memory architecture could see a stale
  name field paired with the new generation. The comment in the
  struct calls this out (line 49-61). [verified-by-code] [from-comment]
- **Why this design:** injection points must be callable from
  critical sections (no LWLockAcquire, no memory allocation) — hence
  the `InjectionPointCached` path that touches only local memory.
  [from-comment]
- **`max_inuse` is monotonic-ish:** `Attach` may bump it up when
  using a fresh slot; `Detach` may bump it down only when releasing
  the highest-numbered slot. Stale "high water mark" is fine; it
  just means readers scan a few extra empty slots. [verified-by-code]
- **`memcmp(entry->name, name, namelen + 1)` at line 477** compares
  including the NUL terminator — so `"foo"` vs `"foobar"` don't
  alias. Caller of `Run` must have NUL-terminated `name` (it's `const
  char *`). [verified-by-code]
- **Generation re-check after memcpy** (line 488-501) guards against
  a name mismatch in a recycled slot. If the slot was detached and
  reattached with a different name during our copy, we continue the
  search rather than trust the local_copy fields. [verified-by-code]
- **Single global LWLock (`InjectionPointLock`)** serialises all
  modifications. Readers don't take it. With 128 slot ceiling, this
  is fine. [verified-by-code]
- **No-op when `USE_INJECTION_POINTS` undefined:** the `#else`
  branch of each entry point `elog(ERROR, ...)` so production
  binaries that have the symbols but no support will refuse to run a
  test. But: `InjectionPointAttach` raises ERROR — so a test module
  that calls it on a production build will fail at attach time. The
  *macros* in `utils/injection_point.h` (not in this file) are
  compiled out entirely, so production has zero overhead. [verified-by-code]
- **Library + function string lengths (64/128/128/1024):** hardcoded
  constants; long names error out at attach. [verified-by-code]

## Potential issues

- File-line: injection_point.c:162-173. `injection_point_cache_remove`
  documents that the dlopen'd library is **not** unloaded — comment
  says "no consequence from a testing perspective", true but means
  long-running test instances accumulate library mappings. [ISSUE-leak:
  documented dlopen leak (nit)]
- File-line: injection_point.c:189-198. `pg_file_exists` + then
  `load_external_function` is racy (TOCTOU) but the consequence is
  just a different error message; not a security issue in test-only
  builds. [ISSUE-correctness: TOCTOU between exists-check and dlopen
  (nit)]
- File-line: injection_point.c:359-390. The "shrink max_inuse" loop
  in `Detach` only walks down from the just-freed slot; if a slot
  in the middle was freed and the highest-numbered slot was still
  in use at that earlier point, max_inuse stays high. Acceptable —
  just costs slot scans. [ISSUE-style: max_inuse can drift higher
  than strictly needed (nit)]
- File-line: injection_point.c:460-505. Linear scan through up to 128
  slots per `Run` of a non-cached point. Negligible at test scale.
  [ISSUE-style: O(n) point lookup, fine at MAX=128 (nit)]
- File-line: injection_point.c:283. `private_data_size > INJ_PRIVATE_MAXLEN`
  uses `>` not `>=`, but the memcpy at line 327 only copies
  `private_data_size` bytes into a `INJ_PRIVATE_MAXLEN` buffer.
  Boundary OK. [ISSUE-correctness: off-by-one-eligible boundary
  correctly handled (nit)]
- File-line: injection_point.c:319. `Assert(generation % 2 == 0)`
  on the chosen `free_idx` — relies on the scan loop never picking
  an odd slot. Correct by construction (line 299-307 only records
  even slots), but the `Assert` is a safety net. [verified-by-code]
- File-line: injection_point.c:477. Using `memcmp` over `strncmp`
  gates the NUL-included compare. If the entry's `name` field ever
  contained un-NUL-terminated junk (it shouldn't — `strlcpy` at line
  322 guarantees NUL), `memcmp` could read past the live data and
  *match* if the trailing bytes happen to align. Defensive coding
  could use `strncmp(..., INJ_NAME_MAXLEN)`. [ISSUE-style: memcmp
  trusts strlcpy NUL termination (nit)]

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `utils`](../../../../../issues/utils.md)
<!-- issues:auto:end -->
