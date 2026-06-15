---
path: src/test/modules/test_shm_mq/test_shm_mq.h
anchor_sha: e18b0cb7344
loc: 45
depth: read
---

# src/test/modules/test_shm_mq/test_shm_mq.h

## Purpose

Shared header for the `test_shm_mq` module — defines the magic number,
the small synchronization header laid down in the DSM segment, and the two
cross-translation-unit entry points (`test_shm_mq_setup` and
`test_shm_mq_main`). Connects `test.c` (SQL-callable driver) with
`setup.c` (DSM + bgworker plumbing) and `worker.c` (worker main).
`[verified-by-code]` `test_shm_mq.h:21-43`

## Public symbols

| Symbol | Site | Notes |
|---|---|---|
| `PG_TEST_SHM_MQ_MAGIC` | `:22` | `0x79fb2447` — `shm_toc_create` magic for the segment |
| `struct test_shm_mq_header` | `:29-35` | `slock_t mutex` + worker total/attached/ready counters |
| `test_shm_mq_setup` | `:38` | DSM allocation + bgworker registration |
| `test_shm_mq_main` | `:43` | bgworker entry point (`pg_noreturn PGDLLEXPORT`) |

## Internal landmarks

- The header struct uses a spinlock — appropriate because the critical
  sections (incrementing the three counters) are bounded and very short.
- `test_shm_mq_main` is declared `pg_noreturn` because bgworker mains exit
  via `proc_exit`.

## Invariants & gotchas

- TEST MODULE — exercises the `shm_mq.h` ring-buffer API across multiple
  bgworkers; never to be loaded in production.
- The magic constant prevents a stray attach from mistaking some other
  module's DSM segment as this one's `[from-comment]` `shm_toc.h`.

## Cross-refs

- `knowledge/files/src/test/modules/test_shm_mq/setup.c.md` — segment
  creation and worker launch.
- `knowledge/files/src/test/modules/test_shm_mq/worker.c.md` — worker side.
- `knowledge/files/src/test/modules/test_shm_mq/test.c.md` — SQL driver.
- `source/src/include/storage/shm_mq.h` — the API under test.
