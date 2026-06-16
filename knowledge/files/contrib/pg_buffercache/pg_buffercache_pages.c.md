# `pg_buffercache/pg_buffercache_pages.c` — shared-buffer introspection + evict/dirty surgery

**Verified against source pin `4b0bf0788b0`** (path: `source/contrib/pg_buffercache/pg_buffercache_pages.c`)

## Role

Walks `NBuffers` and exposes per-buffer state (relfilenode, fork, blocknum,
usage count, dirty/pin flags), an OS/NUMA mapping, summary stats, and a
small set of **destructive** operations (`pg_buffercache_evict*`,
`pg_buffercache_mark_dirty*`) used by core developers to simulate cache
pressure or force dirty writebacks. Reads are gated only via SQL
`REVOKE`; writes additionally pass through a C-side `superuser()` check.

## Public API

(see `pg_buffercache--1.2.sql`, `--1.5--1.6.sql`, `--1.6--1.7.sql`)

- `pg_buffercache_pages() -> SETOF record` — `source/contrib/pg_buffercache/pg_buffercache_pages.c:85`
- `pg_buffercache_os_pages(bool) -> SETOF record` — `:502`
- `pg_buffercache_numa_pages() -> SETOF record` (compat wrapper) — `:514`
- `pg_buffercache_summary() -> record` — `:521`
- `pg_buffercache_usage_counts() -> SETOF record` — `:588`
- `pg_buffercache_evict(int) -> (evicted, flushed)` — `:647`
- `pg_buffercache_evict_relation(regclass) -> (evicted, flushed, skipped)` — `:679`
- `pg_buffercache_evict_all() -> (...)` — `:729`
- `pg_buffercache_mark_dirty(int) -> (...)` — `:763`
- `pg_buffercache_mark_dirty_relation(regclass) -> (...)` — `:796`
- `pg_buffercache_mark_dirty_all() -> (...)` — `:845`

`pg_buffercache_pages` view (the read path) is `REVOKE ALL ... FROM
PUBLIC`; NUMA/os_pages views are additionally `GRANT ... TO pg_monitor`
in `pg_buffercache--1.6--1.7.sql:5-12` [verified-by-code].

## Invariants

- Read functions do NOT take the buffer-mapping partition lock — by
  design, snapshot is not globally consistent [from-comment]
  (`source/contrib/pg_buffercache/pg_buffercache_pages.c:111-115`).
- Per-buffer reads do take the buffer header spinlock via `LockBufHdr` /
  `UnlockBufHdr` so each row is self-consistent [verified-by-code]
  (`source/contrib/pg_buffercache/pg_buffercache_pages.c:137-159`).
- `pg_buffercache_summary` / `pg_buffercache_usage_counts` deliberately
  use only `pg_atomic_read_u64(&bufHdr->state)` without locking, on the
  rationale that locking would not improve accuracy [from-comment]
  (`source/contrib/pg_buffercache/pg_buffercache_pages.c:545-552`).
- `CHECK_FOR_INTERRUPTS()` called inside every per-buffer loop
  (`:133,401,543,605,709,...`) [verified-by-code].
- Destructive entrypoints all call `pg_buffercache_superuser_check()`
  before doing anything [verified-by-code]
  (`source/contrib/pg_buffercache/pg_buffercache_pages.c:661,697,744,778,814,860`).
- `evict_relation` / `mark_dirty_relation` reject local-buffer relations
  with a hard error [verified-by-code]
  (`source/contrib/pg_buffercache/pg_buffercache_pages.c:703-707,
   820-824`).
- NUMA path uses `pg_numa_query_pages` against an aligned page-pointer
  array; expects `BLCKSZ % os_page_size == 0` or vice versa
  [verified-by-code asserted line 279].

## Notable internals

- `pg_buffercache_os_pages_internal` does two-phase work in firstcall:
  (1) compute OS-page→buffer alignment, (2) lock each buffer header
  briefly to read `BufferDescriptorGetBuffer(bufHdr)` only.
- The NUMA path "touches" pages via `pg_numa_touch_mem_if_required` to
  page them in so `move_pages(2)` returns a real node id, with a
  one-shot per-backend flag `firstNumaTouch`
  (`source/contrib/pg_buffercache/pg_buffercache_pages.c:81,310-314`).
- `MemoryContextAllocHuge` is used for the OS-page array because
  `NBuffers * pages_per_buffer * sizeof(BufferCacheOsPagesRec)` can
  exceed 1 GB [from-comment lines 361-374].
- The v1.0→v1.x compat shim accepts result tupledescs with 8 OR 9
  columns (`NUM_BUFFERCACHE_PAGES_MIN_ELEM=8`,
  `NUM_BUFFERCACHE_PAGES_ELEM=9`)
  (`source/contrib/pg_buffercache/pg_buffercache_pages.c:91-104`).

## Trust-boundary / Phase D surface

1. **Read path is NOT superuser-only at C level.** The view + function
   are `REVOKE ALL FROM PUBLIC` in the install script, but a DB owner
   GRANT yields full shared-buffer enumeration to that role. The leak
   surface is the `(reltablespace, reldatabase, relfilenumber, forknum,
   blocknum, isdirty, usagecount)` tuple per buffer — an attacker can
   reverse-map to relations they otherwise lack `pg_read_all_data` for.
   [ISSUE-audit-gap: pg_buffercache_pages / _summary / _usage_counts /
   _os_pages have no C-side privilege check; only SQL REVOKE
   protects them — same pattern as pg_visibility (likely)]
   (`source/contrib/pg_buffercache/pg_buffercache_pages.c:85-206`).
2. **OS pages → pg_monitor.** v1.6/1.7 GRANT NUMA + os_pages to
   `pg_monitor`. `pg_monitor` is a non-superuser monitoring role. The
   buffer mapping (relfilenode, blocknum) is exposed via the regular
   `pg_buffercache_pages` view to anyone with EXECUTE — but the NUMA
   variant only adds the OS-page node id. That seems fine, but worth
   noting: pg_monitor was originally intended for *aggregated* stats,
   not per-block address introspection. [ISSUE-defense-in-depth: NUMA
   variant exposes virtual page residency info to pg_monitor; useful
   for ops but lets monitoring roles infer working-set patterns of
   relations they can't read (nit)]
   (`source/contrib/pg_buffercache/pg_buffercache--1.6--1.7.sql:10-12`).
3. **`pg_buffercache_evict_relation` only takes `AccessShareLock`** on
   the relation, then calls `EvictRelUnpinnedBuffers` on every buffer
   tagged for that relfilenode. The C-side check is only
   `superuser()`; ownership is not checked. Superuser already has
   everything, so the risk here is only "superuser destructive
   testing function accidentally targeted at production"
   [verified-by-code lines 697-712]. [ISSUE-resource:
   pg_buffercache_evict_all and _mark_dirty_all do a full NBuffers
   sweep with no rate limit — on a 128 GB shared_buffers cluster this
   stalls visibly (nit)]
   (`source/contrib/pg_buffercache/pg_buffercache_pages.c:729-757`).
4. **Mark-dirty for a relation that already had a checkpoint can amplify
   WAL.** `pg_buffercache_mark_dirty_relation` dirties every cached
   buffer of a relation; the next checkpoint must FPI all of them.
   Documented in nowhere C-side. Superuser-only mitigates [ISSUE-documentation:
   mark_dirty_relation amplification is non-obvious; comment "Try to
   mark all the shared buffers of a relation as dirty" understates
   the WAL/IO impact (nit)]
   (`source/contrib/pg_buffercache/pg_buffercache_pages.c:794-839`).
5. **Header-spinlock acquired then immediately released to read
   `bufferid`** in `pg_buffercache_os_pages_internal`
   (`source/contrib/pg_buffercache/pg_buffercache_pages.c:406-408`).
   The only piece of state read between Lock/Unlock is the bufferid,
   which is derived from `bufHdr` itself and never changes. The lock
   is therefore a no-op for this use [from-comment-elsewhere]; consider
   `BufferDescriptorGetBuffer(bufHdr)` directly. [ISSUE-nit:
   LockBufHdr/UnlockBufHdr pair around just bufferid read is
   defensive but unnecessary (nit)]
   (`source/contrib/pg_buffercache/pg_buffercache_pages.c:405-408`).

## Cross-refs

- `knowledge/subsystems/storage-buffer.md` — BufferDesc / BM_DIRTY / BM_VALID flag semantics
- `knowledge/files/contrib/pg_prewarm/pg_prewarm.c.md` — counterpart: pulls data INTO buffers
- `knowledge/files/contrib/pg_prewarm/autoprewarm.c.md` — uses same LockBufHdr pattern
- `knowledge/idioms/error-handling.md` — `superuser_check` pattern

<!-- issues:auto:begin -->
- [Issue register — `pg_buffercache`](../../../issues/pg_buffercache.md)
<!-- issues:auto:end -->

## Issues

1. [ISSUE-audit-gap: read entrypoints have no C-side privilege check; SQL REVOKE is sole gate (likely)] — `source/contrib/pg_buffercache/pg_buffercache_pages.c:85,521,588,502`
2. [ISSUE-defense-in-depth: NUMA/OS-pages GRANTed to pg_monitor exposes working-set info beyond aggregated stats (nit)] — `source/contrib/pg_buffercache/pg_buffercache--1.6--1.7.sql:10-12`
3. [ISSUE-resource: evict_all / mark_dirty_all are O(NBuffers) with no rate limit (nit)] — `source/contrib/pg_buffercache/pg_buffercache_pages.c:729-757,845-873`
4. [ISSUE-documentation: mark_dirty_relation comment understates WAL amplification (nit)] — `source/contrib/pg_buffercache/pg_buffercache_pages.c:794-839`
5. [ISSUE-nit: LockBufHdr/UnlockBufHdr around lone bufferid read in os_pages_internal (nit)] — `source/contrib/pg_buffercache/pg_buffercache_pages.c:405-408`
