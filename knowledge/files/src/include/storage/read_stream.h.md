# `src/include/storage/read_stream.h`

- **Last verified commit:** `4b0bf0788b066a4ca1d4f959566678e44ec93422`
- **Lines:** 109

## Role

PG17 **streaming-read** API: a callback returns the next
`BlockNumber` to read, the stream issues prefetches / batched
AIO ahead of consumers, and consumers pull `Buffer`s in order
via `read_stream_next_buffer`. Replaces ad-hoc per-AM
prefetch loops in seqscan, bitmap-heap-scan, vacuum, CREATE
INDEX, etc. Pairs with PG18 AIO worker (`io_worker.h`).

Cross-link: `knowledge/subsystems/storage-aio.md`.

## Public API

[verified-by-code] `source/src/include/storage/read_stream.h`

- Flags (lines 21-64):
  - `READ_STREAM_DEFAULT` = 0
  - `READ_STREAM_MAINTENANCE` (`maintenance_io_concurrency`)
  - `READ_STREAM_SEQUENTIAL` (disable explicit prefetch hint)
  - `READ_STREAM_FULL` (don't ramp up)
  - `READ_STREAM_USE_BATCHING` (opt-in AIO batchmode; callback
    has strict no-block, no-nested-batch restrictions)
- Callback type:
  `ReadStreamBlockNumberCB(stream, callback_private_data,
  per_buffer_data) → BlockNumber` (lines 78-80)
- `block_range_read_stream_cb` — pre-built for contiguous ranges
  using `BlockRangeReadStreamPrivate { current_blocknum,
  last_exclusive }` (lines 71-75)
- Lifecycle:
  `read_stream_begin_relation` / `read_stream_begin_smgr_relation`
  / `read_stream_next_buffer` / `read_stream_next_block` /
  `read_stream_pause` / `read_stream_resume` /
  `read_stream_reset` / `read_stream_end`
- Stats: `read_stream_enable_stats` (PG18)

## Invariants

- INV-1: callback returning `InvalidBlockNumber` ends the stream.
  No bounds validation against `RelationGetNumberOfBlocks`
  happens inside read_stream — caller's callback OWNS that check.
  [verified-by-code] no range Assert in `read_stream.c`.
- INV-2: with `READ_STREAM_USE_BATCHING`, the callback **must
  not** block (without first calling `pgaio_submit_staged`) and
  **must not** start another batch. [from-comment] lines 51-62.
  Violating either silently deadlocks in AIO.

## Trust boundary (Phase D)

- **Callback-returned BlockNumber is trusted blindly.** If a
  consumer's callback derives the BlockNumber from
  attacker-influenced metadata (e.g. an FDW responding to a
  remote scan) without validating against
  `RelationGetNumberOfBlocks`, the stream will happily prefetch
  beyond EOF. Bufmgr will catch the read failure (or zero-page
  via `RBM_ZERO_ON_ERROR`), but the request itself burns I/O.
- The batchmode restrictions (INV-2) are a deadlock surface; an
  extension wrapping read_stream that adds blocking work into
  the callback can hang a backend irrecoverably.

## Cross-refs

- `knowledge/subsystems/storage-aio.md` — the async backend
- `knowledge/files/src/include/storage/bufmgr.h.md`
- `knowledge/files/src/include/storage/io_worker.h.md`
- `knowledge/files/src/include/storage/aio.h.md` (existing)

## Issues

- ISSUE-DESIGN: no in-API validation that the callback's
  returned BlockNumber is in-range; caller-only contract.
  Adding an Assert in `read_stream_get_block` for
  `block <= last_known_nblocks` (where the stream cached a
  size) would catch buggy callbacks. Site: `source/src/include/storage/read_stream.h:77-80`. (Low — defensive.)
- ISSUE-COMMENT: the batchmode constraints (lines 45-62) are
  load-bearing for correctness; a static-analysis tag would
  help. (Informational.)
