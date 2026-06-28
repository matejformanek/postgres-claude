---
source_url: https://www.postgresql.org/docs/current/pgprewarm.html
fetched_at: 2026-06-28T00:00:00Z
anchor_sha: 4abf411e2328
distilled_by: pg-docs-miner (cloud routine)
docs_version: current (PG18)
primary: false
---

# Docs distilled — pg_prewarm (buffer loading + the autoprewarm bgworker)

`contrib/pg_prewarm` does two things: a SQL function to manually load relation
blocks into a cache layer, and an **autoprewarm background worker** that
persists the shared-buffer contents across a restart. The autoprewarm side is a
compact, real-world `RegisterBackgroundWorker` + `WaitLatch` + durable-dump
example. `[from-docs]`

## pg_prewarm() — the three modes

- `pg_prewarm(regclass, mode text DEFAULT 'buffer', fork text DEFAULT 'main',
  first_block int8 DEFAULT NULL, last_block int8 DEFAULT NULL) RETURNS int8`
  (returns blocks loaded). `[from-docs]`
- `mode`:
  - `prefetch` — async OS hint (`posix_fadvise POSIX_FADV_WILLNEED`); errors if
    the platform lacks it.
  - `read` — synchronous read into the **OS** cache only (works everywhere,
    slower than prefetch).
  - `buffer` — synchronous read into **PostgreSQL shared buffers** (the default).
  `[from-docs]`
- `fork` ∈ `'main'`/`'fsm'`/`'vm'`/`'init'`, default `'main'`. `NULL`
  first/last_block mean "from block 0" / "through the last block." `[from-docs]`
- **No eviction protection**: prewarmed blocks are ordinary buffers; prewarming
  more than fits just evicts the earlier ones. Most useful right after startup
  when the cache is cold. `[from-docs]`

## autoprewarm — the bgworker (verified against source)

- Requires `shared_preload_libraries = 'pg_prewarm'`; `_PG_init` registers a
  worker whose entry is `autoprewarm_main` (`bgw_flags = BGWORKER_SHMEM_ACCESS`,
  `bgw_start_time = BgWorkerStart_ConsistentState`,
  `bgw_function_name = "autoprewarm_main"`) at
  `source/contrib/pg_prewarm/autoprewarm.c:909-917`. `[verified-by-code]`
- On startup the worker calls `apw_load_buffers()` (`autoprewarm.c:225,293`) to
  reload blocks from the dump file; the dump file is **`autoprewarm.blocks`** in
  PGDATA (`#define AUTOPREWARM_FILE "autoprewarm.blocks"`, `:53`).
  `[verified-by-code]`
- Periodic dumps via `apw_dump_now()` (`:665`) write a transient
  `autoprewarm.blocks.tmp` then **`durable_rename(... AUTOPREWARM_FILE, ERROR)`**
  (`:737,802`) — the same crash-safe "temp + durable rename" pattern basic_archive
  uses. A final dump fires on shutdown (`:285`). `[verified-by-code]`
- GUCs: `pg_prewarm.autoprewarm` (bool, default **on**, `autoprewarm.c:145`) and
  `pg_prewarm.autoprewarm_interval` (default **300 s**, `:129`; `0` disables
  *periodic* dumps but the shutdown dump still happens). `[verified-by-code]`
- Manual control: `autoprewarm_start_worker()` (launch the worker if it wasn't
  configured) and `autoprewarm_dump_now()` (force an immediate dump, returns the
  record count). `[from-docs]`

## Links into corpus

- `[[knowledge/subsystems/storage-buffer.md]]` — what `mode='buffer'` populates
  (the shared buffer pool, BufferDesc state).
- `[[knowledge/docs-distilled/pgbuffercache.md]]` — the read side: inspect what
  autoprewarm restored.
- `[[knowledge/docs-distilled/bgworker.md]]` — the `BackgroundWorker` struct /
  registration API autoprewarm instantiates.
- Skills: `bgworker-and-extensions` (worker registration + WaitLatch loop),
  `gucs-config`.
