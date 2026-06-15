---
path: src/port/pg_numa.c
anchor_sha: e18b0cb7344
loc: 143
depth: read
---

# src/port/pg_numa.c

## Purpose

Thin portability layer over Linux's `libnuma` for the PG18-era NUMA
introspection features (notably the `pg_buffercache_numa` view, which
reports which NUMA node each shared-buffer page is resident on). Only
Linux is supported today; the file header notes future Win32/FreeBSD
support is "possible". When `USE_LIBNUMA` is undefined, all entry points
become empty wrappers that report "NUMA not available". `[verified-by-code]`
`[from-comment]`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `int pg_numa_init(void)` | `pg_numa.c:48` (libnuma) / `:125` (stub) | Returns `numa_available()` or -1 if EPERM/unsupported |
| `int pg_numa_query_pages(int pid, unsigned long count, void **pages, int *status)` | `:76` / `:132` | Bulk query of NUMA node for an array of page pointers via `move_pages(2)` |
| `int pg_numa_get_max_node(void)` | `:116` / `:138` | Highest possible NUMA node number |

## Internal landmarks

- `NUMA_QUERY_CHUNK_SIZE` (`:40-44`) — 16 on 32-bit, 1024 on 64-bit.
  Working around a Linux kernel bug in `do_pages_stat()` that batches at 16
  internally; we use 16 on 32-bit even on a fixed kernel because the cost
  is small. `[from-comment]`
- `pg_numa_init` (`:48`) — pre-probes `get_mempolicy(NULL, NULL, 0, 0, 0)`
  to detect a seccomp-disabled environment that would otherwise cause
  libnuma < 2.0.19 to falsely report NUMA-available and then explode later.
  Returns -1 on EPERM so the caller treats NUMA as unavailable. `[from-comment]`
- `pg_numa_query_pages` (`:76`) — chunks the array, calls
  `numa_move_pages(... 0)` (NULL nodes array = query-only, no migration),
  and inserts `CHECK_FOR_INTERRUPTS()` between chunks (only in backend
  builds, gated by `#ifndef FRONTEND`). The chunking serves two purposes:
  kernel-bug workaround and interruptibility for long queries.
  `[verified-by-code]` `[from-comment]`

## Invariants & gotchas

- **`numa_move_pages` ret > 0 means "number of non-migrated pages"** — we
  only error on `ret < 0` because we never migrate (the `nodes` pointer is
  NULL). A positive return is harmless in query mode. `[from-comment]`
- The `CHECK_FOR_INTERRUPTS()` gate means `pg_numa_query_pages` is
  interruptible by query cancel between chunks, but not within a chunk. On
  64-bit (1024-page chunks) that's up to ~4 MB queried atomically — fine.
- The stub `pg_numa_query_pages` returns 0 (success) with `status` left
  untouched. Callers must initialize `status` before calling, or accept
  whatever was there.

## Cross-refs

- `source/contrib/pg_buffercache/pg_buffercache_pages.c` — primary caller via
  the `pg_buffercache_numa` view.
- `source/src/include/port/pg_numa.h` — prototypes.
- Linux `numa(3)`, `move_pages(2)` man pages.
