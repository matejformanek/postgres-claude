# `src/include/port/pg_numa.h`

## Role

Cross-platform NUMA (Non-Uniform Memory Access) topology query API.
New in PG 18 (copyright 2025-) `[verified-by-code]`
`source/src/include/port/pg_numa.h:7`. Provides three functions:

- `pg_numa_init()` — initialize NUMA state (libnuma binding on Linux).
- `pg_numa_query_pages(pid, count, pages, status)` — for each
  page in `pages[]`, fill `status[]` with the NUMA node it's
  resident on (or error).
- `pg_numa_get_max_node()` — highest NUMA node ID in the system.

Plus an inline `pg_numa_touch_mem_if_required(ptr)` that page-faults
a region by reading one volatile uint64 — required on Linux before
`move_pages(2)` returns valid results (the kernel doesn't track pages
that have never been faulted in).

## Public API

`[verified-by-code]` `source/src/include/port/pg_numa.h:17-40`:

- `extern PGDLLIMPORT int pg_numa_init(void)` — return 0 success.
- `extern PGDLLIMPORT int pg_numa_query_pages(int pid, unsigned long
  count, void **pages, int *status)`.
- `extern PGDLLIMPORT int pg_numa_get_max_node(void)`.
- `static inline void pg_numa_touch_mem_if_required(void *ptr)` —
  active under `USE_LIBNUMA`, no-op otherwise.

## Invariants

1. **`USE_LIBNUMA` gates real behavior.** Without libnuma (compile
   without `--with-libnuma` or non-Linux), `pg_numa_touch_mem_if_required`
   is a `do {} while(0)` no-op and the other three functions return
   "not supported" stubs `[verified-by-code]`
   `source/src/include/port/pg_numa.h:21-40`.
2. **`pg_numa_query_pages` requires touching pages first.** The
   `move_pages(2)` syscall returns `-ENOENT` for pages that haven't
   been allocated to a physical frame yet. The inline touch helper
   forces a fault `[from-comment]`
   `source/src/include/port/pg_numa.h:23-26`.
3. **`volatile uint64 touch pg_attribute_unused()`** — the volatile
   prevents the compiler from optimizing the read away; the
   `pg_attribute_unused` silences "set but not used" warnings
   `[verified-by-code]` `source/src/include/port/pg_numa.h:30-32`.

## Notable internals

The query API is a thin wrapper over Linux `move_pages(pid, count,
pages, NULL, status, 0)` — same semantics: `status[i]` returns the
NUMA node or a negative errno.

The `pid` parameter implies a backend can query another backend's
NUMA placement (with `CAP_SYS_NICE` or matching uid). For shared
memory, `pid=0` ≡ current process.

The `pg_buffercache` extension v1.6→v1.7 (PG 18) added per-block
NUMA columns surfaced via these calls — exposing for each shared
buffer which NUMA node currently holds the page. The grant on the
new view is to `pg_monitor`, NOT public — see A14 finding about
working-set information leakage.

## Trust-boundary / Phase D surface

- **`pg_numa_query_pages(pid, ...)` with non-zero pid is a privacy
  probe.** Reading another process's page placement reveals its
  memory footprint (which addresses are mapped, which are faulted
  in). PG's NUMA API is intentionally pg_monitor-gated in
  pg_buffercache to keep this away from PUBLIC.
  **Phase-D-cluster-echo:** A14 pg_buffercache NUMA/OS-pages columns
  exposed *only* via pg_monitor (commit history shows the deliberate
  GRANT restriction). The header itself is not the boundary; the SQL
  GRANT is. But any new SQL-callable function built on this API must
  preserve the gate.
- **Touch-side-effect.** `pg_numa_touch_mem_if_required` reads from
  the pointer — if the pointer is invalid, SIGSEGV. Callers must
  pre-validate the address range. Common-case is "the address is a
  shared-buffer page" so safe; new callers must justify.
- **`move_pages(2)` requires `CAP_SYS_NICE` for cross-pid queries.**
  PG runs as a non-root user; querying another user's process would
  fail with EPERM. Same-uid same-pid is always allowed.
- **Statically-linked libnuma version mismatches**. PG's binary
  build may link a different libnuma than what's on the runtime
  system. Standard ELF dynamic-loader rules apply. Out of scope for
  this header.
- **`pg_numa_get_max_node()` returns the topology snapshot at init
  time.** If the system is hot-plugged with new NUMA nodes
  post-startup (rare in practice), the value is stale.

## Cross-refs

- `source/src/port/pg_numa.c` — the .c implementation
  (libnuma + fallback) `[unverified path]`.
- `source/contrib/pg_buffercache/pg_buffercache--1.6--1.7.sql` —
  added NUMA columns (A14 finding).
- `source/contrib/pg_buffercache/pg_buffercache_numa.c` — the SQL
  function definition `[unverified path]`.
- A14 pg_buffercache — NUMA/OS-pages exposure surface.

## Issues / unresolved

- **ISSUE-trust**: cross-pid querying is allowed by the API surface
  even though SQL only exposes it for current-process buffers. Any
  future caller of `pg_numa_query_pages` with `pid > 0` needs an
  explicit privilege check. (severity: medium — the SQL layer is
  currently the gate; if a new C consumer bypasses it, leak risk
  resurfaces)
- **ISSUE-portability**: header advertises the API on all platforms
  but only Linux+libnuma has real behavior; macOS / Windows / *BSD
  stubs return "not supported" silently. A caller would need to
  check return values to discover. (severity: low, doc)
- **ISSUE-A14-echo**: working-set info via NUMA columns
  (pg_buffercache_numa) is currently pg_monitor-gated; any new SQL
  function exposing pg_numa data must preserve that grant pattern.
  (severity: medium, audit lane)

## Synthesized by
<!-- backlinks:auto -->
- [subsystems/port.md](../../../../subsystems/port.md)
