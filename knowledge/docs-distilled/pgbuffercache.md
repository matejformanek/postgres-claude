---
source_url: https://www.postgresql.org/docs/current/pgbuffercache.html
fetched_at: 2026-06-23T00:00:00Z
anchor_sha: 9a60f295bcb1
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: false
---

# Docs distilled — pg_buffercache (shared buffer pool introspection)

`pg_buffercache` is the SQL window onto the shared buffer pool — one row per
`BufferDescriptor` — letting you see which relation/fork/block occupies each
buffer, its dirty/usage/pin state, and (PG18) its NUMA placement. The
load-bearing design choice: **it does NOT take buffer-manager locks**, so it
barely perturbs normal activity but gives only an *approximate* set. Default
access is **superuser + `pg_monitor`**; `GRANT`able. `[from-docs]`

## The view + its function

- `pg_buffercache` view (wrapping `pg_buffercache_pages()`), columns:
  `bufferid` (1..`shared_buffers`), `relfilenode` (→ `pg_class.relfilenode`),
  `reltablespace` (→ `pg_tablespace.oid`), `reldatabase` (→ `pg_database.oid`),
  `relforknumber` (fork number, `source/src/common/relpath.h`),
  `relblocknumber`, `isdirty`, `usagecount` (the clock-sweep counter),
  `pinning_backends`. **Unused buffers** show NULL everywhere except
  `bufferid`. `[from-docs]`

## The consistency model — the key caveat

- The module copies buffer state **without acquiring buffer-manager locks**.
  Consequence: each *individual* buffer's row is self-consistent, but the
  **set across all buffers is not a consistent snapshot** — concurrent activity
  causes minor inaccuracies. Perfect for steady-state pattern analysis, wrong
  for precise point-in-time accounting. `[from-docs]` This same caveat applies
  to `pg_buffercache_summary()` and `pg_buffercache_usage_counts()`. `[from-docs]`

## The cheap aggregates (skip the per-buffer scan)

- `pg_buffercache_summary() returns record`: `buffers_used, buffers_unused,
  buffers_dirty, buffers_pinned, usagecount_avg`. "Significantly cheaper" than
  scanning the full view. `[from-docs]`
- `pg_buffercache_usage_counts() returns setof record`: one row per possible
  `usage_count` value with `buffers, dirty, pinned` counts — a histogram of the
  clock-sweep counter. Also "significantly cheaper". `[from-docs]`

## NUMA mapping (PG18)

- `pg_buffercache_numa` view: `bufferid, os_page_num` (OS memory page),
  `numa_node` (NUMA node ID). **Warning**: it touches every memory page, which
  *forces allocation* of shared memory (possibly onto a single NUMA node
  depending on config) — the first call "can take a noticeable amount of time".
  `[from-docs]`

## Eviction functions — testing only, superuser only

All three are **superuser-only with no GRANT delegation**, exist purely for
testing (e.g. cold-cache benchmarks), and their return is "immediately out of
date upon return". `[from-docs]`

- `pg_buffercache_evict(bufferid)` → `(buffer_evicted bool, buffer_flushed
  bool)`. `buffer_evicted` is false if the buffer was invalid, pinned, or
  re-dirtied after the flush attempt. `[from-docs]`
- `pg_buffercache_evict_relation(regclass)` → evicts all unpinned buffers for
  all forks of the relation; returns evicted / flushed / unevictable counts.
  `[from-docs]`
- `pg_buffercache_evict_all()` → evicts all unpinned buffers in the pool;
  returns evicted / flushed / unevictable counts. `[from-docs]`

## Links into corpus

- Buffer manager internals (`BufferDesc`, clock sweep, pin/usagecount): [subsystems/storage-buffer.md](../subsystems/storage-buffer.md)
- Page-level inspection of what a buffer holds: [docs-distilled/pageinspect.md](./pageinspect.md)
- Fork numbering: [docs-distilled/storage-file-layout.md](./storage-file-layout.md)
- Relevant skills: `debugging` (names pg_buffercache as a runtime-inspection
  tool), `locking` (the lock-free read is why results are approximate),
  `memory-contexts` is unrelated; the relevant shared-memory story is in
  storage-buffer.
