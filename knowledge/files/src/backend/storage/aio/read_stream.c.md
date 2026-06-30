---
path: src/backend/storage/aio/read_stream.c
anchor_sha: 4b0bf0788b0
loc: 1471
depth: deep
---

# read_stream.c

- **Source path:** `source/src/backend/storage/aio/read_stream.c`
- **Last verified commit:** `4b0bf0788b0`
- **LOC:** 1471

## Purpose

The **Read Stream** helper — the high-level abstraction most code uses
instead of the raw AIO API. A caller supplies a callback that yields a
stream of block numbers; the stream looks ahead, **combines neighboring
blocks into vectored reads** (up to `io_combine_limit`) and issues them
ahead of time with an **adaptive look-ahead distance**, then hands back
pinned buffers one at a time via `read_stream_next_buffer()`. Used by
seq scans, vacuum, analyze, bitmap heap scans, etc. This is the most
frequently asked-about AIO file. [from-comment, read_stream.c:1-73]

## Public symbols

| Symbol | Line | Role |
|---|---|---|
| `read_stream_begin_relation(...)` | `read_stream.c:975` | create a stream for a `Relation` fork |
| `read_stream_begin_smgr_relation(...)` | `read_stream.c:999` | create a stream for an `SMgrRelation` |
| `read_stream_next_buffer(stream, **pbd)` | `read_stream.c:1029` | pull the next pinned buffer (+ per-buffer data) |
| `read_stream_next_block(stream, *strategy)` | `read_stream.c:1376` | transitional: consume next block number only |
| `read_stream_pause` / `read_stream_resume` | `read_stream.c:1388,1403` | stop/restart look-ahead (self-referential streams) |
| `read_stream_reset(stream)` | `read_stream.c:1416` | release queued buffers, reuse the stream |
| `read_stream_end(stream)` | `read_stream.c:1466` | reset + free |
| `read_stream_enable_stats(stream, *stats)` | `read_stream.c:254` | route stats into an `IOStats` |
| `block_range_read_stream_cb(...)` | `read_stream.c:182` | ready-made callback for `[cur, last)` ranges |

## Internal landmarks

- **`struct ReadStream` (read_stream.c:95-166)** — a circular queue of
  `buffers[]` (FLEXIBLE_ARRAY) plus a parallel circular queue of
  in-progress `ios[]` (`InProgressIO` = buffer_index +
  `ReadBuffersOperation`). Carries `combine_distance` and
  `readahead_distance` (the two adaptive knobs), the `pending_read`
  being assembled, a one-block `buffered_blocknum` "unget" slot, and a
  `fast_path` flag.
- **`read_stream_start_pending_read` (read_stream.c:317)** — issues as
  much of the pending read as buffer/IO limits allow via
  `StartReadBuffers()`; handles per-backend pin limits, forwarded
  buffers from a prior short read, and the queue-overflow copy so a
  multi-block read is always contiguous.
- **`read_stream_look_ahead` (read_stream.c:657)** — the driver loop:
  pull block numbers from the callback, merge into the pending read or
  start a new one, issue when `read_stream_should_issue_now`. Optionally
  wraps the whole loop in `pgaio_enter_batchmode()` /
  `pgaio_exit_batchmode()` when `READ_STREAM_USE_BATCHING`.
- **`read_stream_next_buffer` (read_stream.c:1029)** — has a specialized
  **fast path** (all-cached, no per-buffer data, one block ahead) that
  skips queue management entirely (read_stream.c:1043-1142), and the
  general path that waits on the head IO (`WaitReadBuffers`), adapts the
  distances, and re-cranks look-ahead.

## The adaptive distance algorithm (the part people ask about)

- **Two separate knobs** (read_stream.c:105-116): `combine_distance`
  controls IO-combining size; `readahead_distance` controls how far
  ahead to issue. Both start at 1 (or jump to `io_combine_limit` with
  `READ_STREAM_FULL`).
- **On a wait** (`WaitReadBuffers` returned true, or the IO ran
  `SYNCHRONOUSLY` which is *treated* as a wait, read_stream.c:1199-1207):
  `readahead_distance *= 2` (capped at `max_pinned_buffers`) and
  `combine_distance *= 2` (capped at `io_combine_limit`). Only growing
  on waits avoids pinning more buffers than needed.
- **On cache hits** with no IO in progress: both distances *decay* by 1,
  but only after a `distance_decay_holdoff` countdown (set to
  `max_pinned_buffers` whenever IO was needed) — so a workload that's
  mostly cached but occasionally misses doesn't collapse the distance
  and then eat synchronous IO (read_stream.c:455-487, 1239-1251).
- **`max_pinned_buffers`** (read_stream.c:834-858) bounds everything:
  `(max_ios+1) * io_combine_limit`, then clamped by strategy pin limit,
  buffer-manager pin limit, and `PG_INT16_MAX`. `max_ios` comes from
  `effective_io_concurrency` / per-tablespace IO concurrency.

## Invariants & gotchas

- **`max_ios == 0` disables AIO but the stream still works** — it bumps
  `max_ios` to 1 internally and forces `READ_BUFFERS_SYNCHRONOUSLY`
  (read_stream.c:911-915). `effective_io_concurrency = 0` therefore
  yields all-synchronous reads; the "treat synchronous as a wait"
  rule (read_stream.c:1199-1207) is what still lets combining ramp up.
- **Synchronous IO must be counted as a wait or combining never grows**
  — the comment (read_stream.c:1198-1205) flags this as "particularly
  crucial" for `effective_io_concurrency=0`, and also for io_uring,
  which never signals a wait when data is page-cache resident.
- **Reading another session's temp relation is rejected** — the stream
  has no visibility into another session's local buffers, so
  `RELATION_IS_OTHER_TEMP` → ERROR (read_stream.c:784-787). Wrong data,
  not just a perf issue.
- **Forwarded buffers**: a `StartReadBuffers()` that splits leaves the
  leading already-pinned buffers in place to be picked up by the next
  call; they're counted toward the backend's pin limit but *not* in
  `pinned_buffers` (read_stream.c:392-407, 512-516). Mishandling them
  double-counts pins.
- **Queue overflow zone**: because a multi-block read must be a
  contiguous array, the queue has `io_combine_limit - 1` extra slots and
  overflowing buffers are copied both to the front (for the consumer)
  and left in the overflow zone (for the in-flight IO's pointer)
  (read_stream.c:518-533); both copies are zapped when handed to the
  consumer (read_stream.c:1287-1295).
- **Fast-path entry requires `combine_distance == 1`** (and readahead 1,
  one pinned buffer, no pending read, no per-buffer data) — the comment
  at read_stream.c:472-482 explains why combine_distance must decay to 1
  or the fast path would be wrongly re-entered.
- **Advice (posix_fadvise) is only used in sync mode** (read_stream.c:
  891-904): `advice_enabled` requires `io_method=sync`, no direct IO,
  caller didn't promise sequential, and `max_ios > 0`. With real AIO
  there's no fadvise; the kernel's own readahead is left alone once the
  preadv pattern catches up (read_stream.c:365-390).
- **GUC values are captured at `begin`** — `io_combine_limit` and the
  resolved `max_ios` are frozen for the stream's lifetime
  (read_stream.c:917-923) so a mid-stream GUC change can't corrupt the
  geometry.
- **`read_stream_reset` unpins everything including forwarded buffers**
  (read_stream.c:1430-1449) and restarts at distance 1; `read_stream_end`
  is reset + `pfree`.

## Cross-refs

- Buffer-manager primitives it drives: `bufmgr.c::StartReadBuffers`,
  `StartReadBuffer`, `WaitReadBuffers` —
  `knowledge/files/src/backend/storage/buffer/bufmgr.c.md`.
- Batchmode it uses: `aio.c::pgaio_enter_batchmode` /
  `pgaio_exit_batchmode`.
- Header (public API + flags `READ_STREAM_*`):
  `src/include/storage/read_stream.h`.
- Pin-limit helpers: `bufmgr.c::GetAdditionalPinLimit`,
  `GetAccessStrategyPinLimit`.
- Subsystem overview: `knowledge/subsystems/storage-buffer.md`;
  AIO core `knowledge/files/src/backend/storage/aio/aio.c.md`.

<!-- issues:auto:begin -->
- [Issue register — `storage-aio`](../../../../../issues/storage-aio.md)
<!-- issues:auto:end -->

## Potential issues

- **[ISSUE-undocumented-invariant: `int16` geometry caps the stream at
  ~32k pinned buffers]** `read_stream.c:828-836` — the comment notes
  this is "an artificial limit of ~32k buffers and we'd need to adjust
  the types to exceed that." With very large `io_combine_limit` ×
  `effective_io_concurrency` and huge `shared_buffers`, the geometry is
  silently clamped to `PG_INT16_MAX - queue_overflow - 1`. Not a bug
  today, but a hard ceiling future tuning could hit. Severity: nit.
- **[ISSUE-question: distance decay tuning is heuristic / admitted
  soft]** `read_stream.c:472-484` — the comment says reducing
  `combine_distance` after cache hits has "no clear performance
  argument" beyond making fast-path entry work; the whole decay/growth
  schedule is hand-tuned. A future regression here would be subtle
  (throughput, not correctness). Severity: nit.

## Tally

`[verified-by-code]=9 [from-comment]=6 [inferred]=0`

## Synthesized by
<!-- backlinks:auto -->
- [idioms/read-stream-prefetch.md](../../../../../idioms/read-stream-prefetch.md)
