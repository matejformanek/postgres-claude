---
name: aio-readstream
description: PostgreSQL's async I/O subsystem + the read-stream API — `src/backend/storage/aio/` (introduced PG 17, matured PG 18). Loads when the user asks about the read_stream API, AIO methods (sync / worker / io_uring), how sequential + bitmap scans issue prefetch, migrating a code path from `StartReadBuffer`+`WaitReadBuffer` to `read_stream_*`, adding a new read-stream consumer, tuning `io_max_concurrency` / `io_workers` / `io_method`, or debugging AIO-related buildfarm failures. Also for the read-stream callbacks (per-block-lookup / per-buffer-release), completion callbacks (`aio_callback.c`), and the io_uring linkage. Skip when the ask is about client-side async (libpq) or about the WAL writer / walreceiver (those have their own I/O paths).
when_to_load: Migrate a scan / VACUUM / read path to the read_stream API; add a new AIO consumer; understand why a scan is faster on PG 17+ than on PG 16; tune AIO GUCs; debug a "read_stream_next_buffer returned InvalidBuffer" surprise.
companion_skills:
  - locking
  - executor-and-planner
  - access-method-apis
---

# aio-readstream — the async I/O and read-stream API

PostgreSQL 17 introduced the **`read_stream` API** — a unified way for scan-shaped code (sequential scans, bitmap heap scans, VACUUM, ANALYZE, some indexes) to issue reads. PG 18 promoted the underlying AIO layer to a first-class subsystem in `src/backend/storage/aio/`, adding pluggable methods (sync / worker / io_uring). Together they let PG overlap CPU work with I/O without per-caller `posix_fadvise` bookkeeping.

## The file map

| File | Lines | Role |
|---|---:|---|
| `aio.c` | 36.6K | Framework core — `PgAioHandle` pool, submit/wait state machine, method dispatch. |
| `aio_init.c` | 6.6K | Shmem init + GUCs (`io_method`, `io_max_concurrency`, `io_workers`, `io_uring_slots`). |
| `aio_callback.c` | 10.2K | Completion-callback registration + dispatch — modules extend AIO by registering a callback. |
| `aio_target.c` | 3.2K | The set of "things that can be read" — currently smgr (files by relfilenode) + WAL (in progress). |
| `aio_io.c` | 5.5K | The low-level read/write submission (per-target-per-method). |
| `aio_funcs.c` | 6.2K | SQL-callable helpers backing `pg_aios` view + statistics. |
| `method_sync.c` | 1.2K | Synchronous fallback — no actual async, just `pread`. Default on platforms without io_uring or when disabled. |
| `method_worker.c` | 27.6K | Background-worker method — a small pool of dedicated I/O workers do the reads. Portable across Unix/Windows. |
| `method_io_uring.c` | 22.1K | io_uring method (Linux 5.1+) — kernel-level async I/O ring. Highest throughput. |
| `read_stream.c` | 49.3K | The **`read_stream` API** — consumer-facing layer on top of AIO. What most PG code uses. |

## The two layers

**AIO layer** — low-level. `PgAioHandle`s from a shmem pool. Direct users are `read_stream` and (soon) WAL. Applications rarely touch AIO directly.

**read_stream layer** — high-level. What scan code uses. You give it a callback that returns "the next block number to read" (or a stream of blocks); it issues reads asynchronously in advance, and `read_stream_next_buffer` returns a ready-to-use pinned buffer.

## The read_stream API surface

Public headers: `src/include/storage/read_stream.h`.

```c
ReadStream *read_stream_begin_relation(int flags,
                                       BufferAccessStrategy strategy,
                                       Relation rel,
                                       ForkNumber forknum,
                                       ReadStreamBlockNumberCB callback,
                                       void *callback_private_data,
                                       size_t per_buffer_data_size);

Buffer read_stream_next_buffer(ReadStream *stream, void **per_buffer_data);

void read_stream_end(ReadStream *stream);
```

The `callback` returns the next `BlockNumber` to read (or `InvalidBlockNumber` to signal end-of-stream). The API buffers reads ahead so `next_buffer` rarely stalls.

Flags:
- `READ_STREAM_SEQUENTIAL` — hint that access is sequential (larger prefetch).
- `READ_STREAM_MAINTENANCE` — for VACUUM / CLUSTER (uses `maintenance_io_concurrency` instead of `effective_io_concurrency`).
- `READ_STREAM_USE_BATCHING` — batches reads for the `smgr` layer.

## Where read_stream is used

As of PG 18, roughly:

- `access/heap/heapam.c` — `heap_beginscan` builds a read-stream for sequential scans (both parallel and non-parallel).
- `access/heap/heapam_handler.c` — `bitmapheap_stream_read_next` for bitmap heap scans.
- `commands/vacuumlazy.c` — VACUUM pass-1 (heap scan) and pass-2 (index cleanup with read-stream).
- `commands/analyze.c` — sampled block reads.
- `access/nbtree/nbtsort.c` — parallel index build.
- Buffer-manager utility functions (`bufmgr.c` — `pg_prewarm`-like paths).

Grep for `read_stream_begin_relation` in `source/src/backend/` for the full list — as of PG 18 it's around 15 sites.

## Callbacks vs streams — the dual

- **read_stream_*_CB** — the per-block-lookup callback (which block to read next).
- **PgAioHandleCallbacks** (in `aio_callback.c`) — completion callbacks that run when an AIO handle completes. Modules register a family via `pgaio_register_callbacks`. Used by smgr to update the buffer-manager state on completion.

Extending AIO with a new "kind of read" = registering a callback family + adding a target in `aio_target.c`.

## The three methods

Configured at postmaster start via `io_method`:

| Method | Where | When to use |
|---|---|---|
| `sync` | `method_sync.c` | Fallback / testing / disabling AIO. Just `pread`, no async. |
| `worker` | `method_worker.c` | Portable. Small pool of I/O worker processes handle reads. `io_workers` GUC. |
| `io_uring` | `method_io_uring.c` | Linux only. Kernel async. Highest throughput; requires Linux 5.1+. |

Switching methods requires postmaster restart (they allocate different shmem structures).

Note: PG 18's assumption is that ordinary backends dispatch AIO work; workers or the kernel completes it. Backends still block in `read_stream_next_buffer` if a read they need isn't yet complete, but this is transparent.

## Common patch shapes

### Migrate an existing scan to read_stream

- Identify the block-source loop (usually `foreach block: StartReadBuffer + WaitReadBuffer + ReleaseBuffer`).
- Refactor into a callback that returns the next `BlockNumber`.
- Replace the loop with `read_stream_begin_relation` + a `while ((buf = read_stream_next_buffer(stream, NULL)) != InvalidBuffer) { ... ReleaseBuffer(buf); }`.
- `read_stream_end(stream)` in the cleanup path.
- Test with all 3 methods (`io_method=sync/worker/io_uring`) locally.

### Add per-buffer callback data

If your callback needs to remember per-block metadata (e.g. TID range for bitmap scans), size it via `per_buffer_data_size` in `read_stream_begin_relation`; retrieve via the `per_buffer_data` out-param of `read_stream_next_buffer`. Example: `bitmapheap_stream_read_next` stores the block-level TID list per buffer.

### Extend AIO with a new completion callback

- Define a new `PgAioTargetInfo` in `aio_target.c` (if the object being read is neither smgr nor WAL).
- Register `PgAioHandleCallbacks` via `pgaio_register_callbacks` at postmaster startup (or when the extension loads for extensions with `shared_preload_libraries`).
- Handle `PGAIO_HCB_INVALID` for callback lookups on stale handles.

## Pitfalls

- **Callback runs in the CALLER's context** — the block-lookup callback executes in the process that called `read_stream_next_buffer`, NOT in a worker. If the callback allocates memory, it goes in the caller's CurrentMemoryContext. Long-running callbacks stall the stream.
- **read_stream_reset is for restarting** — if you need to seek back / restart, `read_stream_reset` discards any in-flight reads. It's cheap; don't fear using it.
- **`InvalidBuffer` from `next_buffer` means EOS, not error** — errors get raised via `ereport(ERROR)` inside the API. If you check for InvalidBuffer, that's the "stream is done" signal.
- **BufferAccessStrategy is honored** — a stream inherits the strategy passed in. VACUUM's ring buffer, `pg_prewarm`, and default all work as expected.
- **`io_method=sync` disables AIO but not read_stream** — you can still call the read_stream API; it just resolves to synchronous reads under the hood.
- **`method_worker` scaling** — `io_workers` defaults low (3). If you're benchmarking a heavy AIO workload, bump it; otherwise workers become the bottleneck.
- **io_uring limits on non-root** — some Linux distros restrict io_uring to root or CAP_SYS_ADMIN. Postmaster startup will fall back to `worker` and log; verify via `SHOW io_method`.
- **Read-ahead does not fetch across relation boundaries** — the callback deals in `(rel, forknum, blocknum)` tuples all pinned to the same relation. If you need cross-relation prefetch, wrap multiple streams.

## Related corpus

- **Idiom**: `read-stream-prefetch` (this file's home idiom).
- **File docs**: `knowledge/files/src/backend/storage/aio/*.md` — 12 files, one per source file.
- **Subsystems**: `storage-buffer` (buffer-manager interface — every read_stream buffer is a shared-buffer), `access-heap` (main consumer via `heap_beginscan`).
- **Data structures**: `bufferdesc-state` (the BufferDesc AIO adds a completion-in-progress state to).
- **Sessions**: `2026-06-08-aio-rmgrdesc-sweep.md` — corpus sweep of the AIO subsystem when it was added.

## Corpus-chain shortcut

```
python3 scripts/corpus-chain.py --idiom read-stream-prefetch
python3 scripts/corpus-chain.py --file src/backend/storage/aio/read_stream.c
```

Both surface the ~15 callers + the AIO handle machinery.

## Boundary

**Use this skill** for `src/backend/storage/aio/` + `read_stream.c` + AIO-consuming scan code.

**Don't use** for:
- **libpq async** — client-side, entirely separate; use libpq skill.
- **WAL writing** (`xlog.c`, `walwriter.c`) — separate I/O path; AIO integration is in-progress but not yet the primary path.
- **`walreceiver`** — replication-side network I/O; also unrelated.
- **`smgr` layer directly** — that's `storage/smgr/`; AIO uses it but consumers don't reach through AIO to smgr.
