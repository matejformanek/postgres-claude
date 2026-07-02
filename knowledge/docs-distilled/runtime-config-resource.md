---
source_url: https://www.postgresql.org/docs/current/runtime-config-resource.html
fetched_at: 2026-07-01T20:47:00Z
anchor_sha: c776550e4662
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18/19devel)
primary: true
---

# Docs distilled — Resource Consumption configuration

The memory / I/O / parallel-worker GUC reference, distilled to the semantics a
backend hacker gets wrong. Companion: `knowledge/idioms/memory-contexts.md`,
`knowledge/subsystems/storage-buffer.md`.

## Memory: the "per-what" traps

- **`work_mem` (4MB) is PER sort/hash node, NOT per query.** A single complex
  query with several sorts + hashes can allocate many multiples of it
  simultaneously — the classic OOM surprise. [from-docs]
- **`hash_mem_multiplier` (2.0) means hash nodes get `work_mem ×
  hash_mem_multiplier`** — so the effective hash budget is 8MB by default, not
  4MB. Raise the multiplier (not work_mem) when hashes spill but sorts are fine.
  [from-docs]
- **`maintenance_work_mem` (64MB) is used by VACUUM, CREATE INDEX, ALTER TABLE
  ADD FOREIGN KEY** — but **autovacuum workers use `autovacuum_work_mem` if set
  (default −1 = inherit maintenance_work_mem)**. And for a *parallel* utility
  command it's a **shared total across workers, not per-worker** (unlike
  work_mem). [from-docs]
- **`shared_buffers` (128MB) is restart-only**; many SLRU-cache knobs added in
  recent versions are also restart-only and auto-size from shared_buffers
  (`transaction_buffers`, `subtransaction_buffers`, `commit_timestamp_buffers`
  default 0 = `shared_buffers/512`, clamped [16,1024] blocks;
  `multixact_member_buffers` 32, `multixact_offset_buffers` 16, `notify_buffers`
  16, `serializable_buffers` 32). [from-docs]
- **`max_stack_depth` (2MB, superuser) must stay ~1MB under `ulimit -s`** — set
  too high and a runaway recursion crashes the backend instead of erroring.
  **`vacuum_buffer_usage_limit` (2MB) is the VACUUM/ANALYZE ring-buffer size**,
  capped at `shared_buffers/8`. [from-docs]

## Disk / kernel

- **`temp_file_limit` (−1, superuser) counts per-process temp files (sorts,
  hashes, cursors) but NOT explicit temp tables** — exceed it and the
  transaction is cancelled. [from-docs]
- `file_copy_method` (COPY|CLONE) speeds `CREATE DATABASE STRATEGY=FILE_COPY` /
  `ALTER DATABASE SET TABLESPACE` via kernel block-sharing. `max_files_per_process`
  (1000, restart-only) — lower it on "Too many open files". [from-docs]

## Background writer + async I/O (PG18 io_method is the headline)

- **`io_method` (default `worker`, restart-only) is NEW in PG18**: `worker`
  (dedicated I/O worker processes, count = `io_workers` default 3), `io_uring`
  (needs `--with-liburing` build), or `sync` (old synchronous fallback). This is
  the async-I/O subsystem's front door. [from-docs]
- **`effective_io_concurrency` / `maintenance_io_concurrency` both default 16**
  (was 1 historically) and set prefetch depth; 0 disables async I/O.
  `io_combine_limit` (128kB) is silently capped by `io_max_combine_limit`
  (restart-only) — raise both to grow combined reads. [from-docs]
- BgWriter: `bgwriter_delay` 200ms, `bgwriter_lru_maxpages` 100 (0 = disable),
  `bgwriter_lru_multiplier` 2.0 (cushion over just-in-time demand),
  `bgwriter_flush_after` 512kB Linux / 0 elsewhere. `backend_flush_after` 0.
  [from-docs]

## Parallel-worker pool hierarchy

- **Nested caps**: `max_parallel_workers` (8) ≤ `max_worker_processes` (8,
  restart-only, cluster-wide pool shared with extensions/bgworkers);
  `max_parallel_workers_per_gather` (2) and `max_parallel_maintenance_workers`
  (2) draw from that pool. Setting per-gather to 0 disables query parallelism.
  [from-docs]
- **A parallel query costs ~5× the resources of a serial one** (4 workers ⇒ ~4×
  work_mem, ~4× I/O bandwidth) — the docs' explicit warning. On a standby,
  `max_worker_processes` / `max_prepared_transactions` must be ≥ the primary's.
  [from-docs]

## Links into corpus

- [[knowledge/idioms/memory-contexts.md]] — palloc contexts work_mem bounds.
- [[knowledge/subsystems/storage-buffer.md]] — shared_buffers, ring buffers,
  bgwriter.
- [[knowledge/docs-distilled/parallel-plans.md]] — parallel worker plan side.
- [[knowledge/docs-distilled/runtime-config-vacuum.md]] — autovacuum_work_mem.
- Skill: `memory-contexts`, `parallel-query`, `gucs-config`.

## Confidence note

All claims `[from-docs]` (Resource Consumption chapter, fetched 2026-07-01).
`io_method` semantics and defaults quoted from the page; the aio implementation
in `src/backend/storage/aio/` is `[unverified]` this run.
