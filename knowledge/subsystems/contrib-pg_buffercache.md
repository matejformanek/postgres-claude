# contrib-pg_buffercache (shared buffer cache inspector)

- **Source path:** `source/contrib/pg_buffercache/`
- **Last verified commit:** `e18b0cb7344` (2026-06-13 anchor)
- **Extension version:** `1.7` (per `pg_buffercache.control`)
- **Trusted:** no (superuser to install; per-function grants gate use)

## 1. Purpose

Expose `shared_buffers` contents to SQL — which relation each
buffer page belongs to, dirty / valid / pinned state, usage
counts, and NUMA placement on Linux. Also offers *invasive*
diagnostic primitives: forced eviction (`pg_buffercache_evict*`)
and synthetic dirty marks (`pg_buffercache_mark_dirty*`). Designed
for buffer-management debugging, capacity planning, and exercising
buffer-manager code paths in CI.

## 2. Mental model

- **One row per buffer slot.** The SRF walks `NBuffers`
  `BufferDesc` entries; for each, formats a row with the
  rel/file/block tag plus state bits.
  [verified-by-code `pg_buffercache_pages.c:154-173`]
- **Two read modes.**
  - `pg_buffercache_pages()` — exact-snapshot mode: takes the
    buffer-header spinlock via `LockBufHdr()` per buffer
    [verified-by-code `pg_buffercache_pages.c:156`]. Accurate but
    serializes with bgwriter / backends.
  - `pg_buffercache_summary()`, `pg_buffercache_usage_counts()` —
    lock-free mode: reads `bufHdr->state` with
    `pg_atomic_read_u64()` and tolerates torn observations of the
    multi-field bitmask
    [verified-by-code `pg_buffercache_pages.c:602-616`, `:652-658`].
    Cheap; suitable for monitoring queries.
- **NUMA functions are Linux-specific.** `pg_buffercache_numa_pages()`
  + `pg_buffercache_os_pages()` (1.7) call `pg_numa_*` helpers
  (`port/pg_numa.h`); on non-NUMA builds they return null nodes or
  ERROR depending on the call. The `firstNumaTouch` flag warms the
  per-backend page table before sampling
  [verified-by-code `pg_buffercache_pages.c:83`].

## 3. SQL surface

| Function | Since | Behavior |
|---|---|---|
| `pg_buffercache_pages()` | 1.0 | Per-buffer SRF, exact snapshot via per-buffer spinlock |
| `pg_buffercache_summary()` | 1.4 | Aggregate counts (used/dirty/pinned), lock-free |
| `pg_buffercache_usage_counts()` | 1.4 | Histogram by `usage_count` 0..MAX, lock-free |
| `pg_buffercache_numa_pages()` | 1.6 | Per-OS-page NUMA node assignment |
| `pg_buffercache_evict(bufid)` | 1.5 | Force-evict one buffer; flushes if dirty |
| `pg_buffercache_evict_relation(regclass)` | 1.5 | Evict all buffers of one relation |
| `pg_buffercache_evict_all()` | 1.5 | Evict every buffer (test only) |
| `pg_buffercache_mark_dirty(bufid)` | 1.7 | Synthetically mark one buffer dirty (no content change) |
| `pg_buffercache_mark_dirty_relation()` | 1.7 | Mark all buffers of one relation dirty |
| `pg_buffercache_mark_dirty_all()` | 1.7 | Mark every buffer dirty (test only) |
| `pg_buffercache_os_pages()` | 1.7 | OS-page-granularity view (4KB / hugepage) |

[verified-by-code `pg_buffercache_pages.c:69-79` lists all PG_FUNCTION_INFO_V1]

The pinning_backends column on `pg_buffercache_pages` is optional —
the C code accepts both 8-element and 9-element tuple descriptors
to support upgrade from 1.0
[verified-by-code `pg_buffercache_pages.c:106-108`].

## 4. Performance posture

- **Exact-snapshot scan = O(NBuffers) header spinlocks.** On a
  `shared_buffers=128GB` system that's ~16M acquisitions. Hot
  monitoring should use the summary functions.
- **Lock-free scan races bgwriter.** Counts may be off by a few
  hundred on a busy system. That's the design point — torn reads
  are tolerated because the consumer is an operator dashboard, not
  recovery code.
- **Evict / mark_dirty are O(NBuffers) too** and they take the
  partition LWLock + the buffer-header spinlock; expect noticeable
  latency under concurrent OLTP.

## 5. Cautions & production-use guidance

- `pg_buffercache_evict_all()` and `pg_buffercache_mark_dirty_all()`
  are documented "test only" — they're for exercising WAL / writer
  paths under controlled load. Never run them on production traffic
  without expecting churn-induced latency spikes.
- `evict` of a dirty buffer triggers a synchronous flush before the
  slot is reused. The implementation calls
  `EvictUnpinnedBuffer()` which can block on the WAL flush sequence.
- `pg_buffercache_pages` requires `pg_monitor` membership or an
  explicit grant; the SQL grants `EXECUTE` to `pg_monitor`.
- **Don't conflate this with `pg_buffercache_summary().usagecount`.**
  The `usagecount` column on `pg_buffercache_pages()` is per-buffer;
  the histogram on `pg_buffercache_usage_counts()` aggregates.
  Comparing them across a busy system will show drift — that's
  expected.

## 6. Build-time / version notes

- `pg_buffercache.control` declares `default_version = '1.7'` and
  `relocatable = true` [verified-by-code `pg_buffercache.control:3-5`].
- The 1.6 → 1.7 upgrade adds the mark-dirty family; 1.5 added the
  evict family; 1.4 added summary + usage counts.
- The upgrade scripts use `CREATE OR REPLACE FUNCTION` for
  `pg_buffercache_numa_pages` because it gained an OUT parameter
  [verified-by-code `pg_buffercache--1.5--1.6.sql:7`].

## 7. Invariants

- **[INV-1]** `pg_buffercache_pages()` returns exactly `NBuffers`
  rows; one per slot, with the relation tag nulled when
  `!(buf_state & BM_TAG_VALID)`.
- **[INV-2]** Summary / histogram readers tolerate torn `buf_state`
  reads; no spinlock acquired.
- **[INV-3]** Evict and mark-dirty respect pin counts: pinned
  buffers fail rather than corrupting state.
- **[INV-4]** NUMA functions short-circuit on builds without
  `--with-libnuma` or non-Linux platforms.

## 8. Useful greps

- All SRF entry points:
  `grep -n 'PG_FUNCTION_INFO_V1' source/contrib/pg_buffercache/pg_buffercache_pages.c`
- Buffer-header read patterns:
  `grep -n 'LockBufHdr\|pg_atomic_read_u64.*state' source/contrib/pg_buffercache/pg_buffercache_pages.c`

## 9. Cross-references

- `knowledge/subsystems/storage-buffer.md` — the buffer manager
  this extension introspects. `BufferDesc`, `NBuffers`,
  `BM_DIRTY` / `BM_VALID` / `BM_TAG_VALID` flags.
- `knowledge/data-structures/bufferdesc-state.md` — the 64-bit
  packed state field this code reads (atomic vs spinlock paths).
- `.claude/skills/debugging/SKILL.md` — `pg_buffercache_summary()`
  is a recommended starter probe for cache-pressure diagnosis.
- `.claude/skills/extension-development/SKILL.md` — module loading
  + `PG_MODULE_MAGIC_EXT` pattern.
- `source/src/backend/storage/buffer/bufmgr.c` — `EvictUnpinnedBuffer`,
  the underlying eviction primitive.
- `source/contrib/pg_buffercache/pg_buffercache_pages.c` — implementation.
