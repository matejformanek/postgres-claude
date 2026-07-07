# Read-stream prefetch — read_stream API for sequential scans

PG 17 added the **read_stream API** — a unified mechanism
for sequential and bitmap-driven I/O that automatically
issues OS-level prefetch hints, batches buffer reads, and
adapts to slow storage. Replaces the per-AM
`StartReadBuffer` / `WaitReadBuffer` pattern with a single
`read_stream_*` family. New code is expected to use it; older
code is migrating.

Anchors:
- `source/src/include/storage/read_stream.h:85-106` —
  public API [verified-by-code]
- `source/src/backend/storage/aio/read_stream.c` —
  implementation
- `knowledge/idioms/vacuum-skip-pages.md` — VACUUM uses
  read_stream
- `knowledge/subsystems/contrib-pg_visibility.md` —
  also uses it

## The 3 entry points

[verified-by-code `read_stream.h:85-106`]

```c
extern ReadStream *
read_stream_begin_relation(int flags, BufferAccessStrategy strategy,
                           Relation rel, ForkNumber forknum,
                           ReadStreamBlockNumberCB cb,
                           void *callback_private_data,
                           size_t per_buffer_data_size);

extern BlockNumber
read_stream_next_block(ReadStream *stream, void **per_buffer_data);

extern void
read_stream_end(ReadStream *stream);
```

The pattern: caller creates a stream + provides a callback
that yields block numbers; the stream returns one buffer at
a time (or a sequence of pinned-and-ready-to-read buffers).

## The callback

```c
typedef BlockNumber (*ReadStreamBlockNumberCB)(
    ReadStream *stream,
    void *callback_private_data,
    void *per_buffer_data);
```

The caller's responsibility: return the next block number to
read, or `InvalidBlockNumber` to end the stream.

For a sequential scan, the callback is "blkno++ until
nblocks". For a bitmap scan, it's "next set bit in the
bitmap." For VACUUM, it's "next block not skippable by VM
bits."

## The look-ahead trick

The stream **calls the callback ahead of the caller's
consumption**. So:

1. Caller pulls block 0 → stream returns buf for block 0.
2. Stream internally calls callback for block 1, 2, 3...
3. Stream issues `posix_fadvise(POSIX_FADV_WILLNEED)` for
   the look-ahead blocks.
4. Caller pulls block 1 → buffer is already prefetched.

Look-ahead distance adapts based on observed I/O latency.
Slow storage = longer look-ahead; fast storage = shorter.

`io_combine_limit` GUC caps the look-ahead.

## The per-buffer-data trick

`per_buffer_data_size` lets the caller attach private state
to each buffer:

```c
typedef struct
{
    bool is_all_visible;
    bool was_eagerly_scanned;
} my_per_buffer_data;

stream = read_stream_begin_relation(..., sizeof(my_per_buffer_data));

while ((blkno = read_stream_next_block(stream, (void **) &data)) != InvalidBlockNumber) {
    /* data->is_all_visible set by callback */
}
```

The callback receives a void * to write its per-buffer
data; the consumer reads it. Useful when the
callback determines per-block state the consumer needs
without re-computing.

VACUUM uses this to pass "is this page all-visible?" from
the VM-walk callback to the actual page-process loop.

## The flags

[from `read_stream.h` definitions]

| Flag | Meaning |
|---|---|
| `READ_STREAM_SEQUENTIAL` | Hint: caller wants sequential reads (enables OS readahead) |
| `READ_STREAM_USE_BATCHING` | Batch buffer reads (multiple in one IO) |
| `READ_STREAM_FULL` | Caller will read every block (no skips) |

Combinations like `READ_STREAM_SEQUENTIAL |
READ_STREAM_USE_BATCHING` are typical for VACUUM and
sequential scans.

## BufferAccessStrategy

The optional `strategy` argument tells the buffer manager
to use a specific access pattern (e.g.,
`BAS_BULKREAD` for sequential scans). This prevents the
scan from polluting the buffer cache with pages that won't
be accessed again.

If NULL, the stream uses the default strategy (no
special handling).

## How VACUUM uses read_stream

From `knowledge/idioms/vacuum-skip-pages.md`:

```c
struct vacuum_scan_state {
    ...
};

static BlockNumber
vacuum_scan_next_block(ReadStream *stream, void *state,
                       void *per_buffer_data)
{
    /* consult VM bits; return next non-skippable block */
}

stream = read_stream_begin_relation(
    READ_STREAM_SEQUENTIAL | READ_STREAM_USE_BATCHING,
    strategy, rel, MAIN_FORKNUM,
    vacuum_scan_next_block, &state, 0);

while ((blkno = read_stream_next_block(stream, NULL)) !=
       InvalidBlockNumber) {
    buf = ReadBuffer(rel, blkno);   /* already prefetched */
    /* process the page */
}

read_stream_end(stream);
```

The callback handles the "should I skip this block?" logic;
the stream handles the "make sure the block is in memory by
the time the caller asks for it" plumbing.

## Migration from older APIs

Older code uses:

```c
for (blkno = 0; blkno < nblocks; blkno++) {
    buf = ReadBufferExtended(rel, MAIN_FORKNUM, blkno, ...);
    /* process */
    ReleaseBuffer(buf);
}
```

The migration:

1. Wrap the "next block" decision in a callback.
2. Replace `ReadBufferExtended` with `read_stream_next_block`
   (or use the next-buffer accessor).
3. Add appropriate flags.

The payoff: automatic prefetch, adaptive look-ahead, OS
readahead integration. Sequential scans get 2-5× faster on
slow storage; minor improvement on fast storage.

## Common review-time concerns

- **The callback runs ahead of the consumer**, possibly
  many blocks. Don't keep state in the callback that depends
  on order-of-consumption.
- **`READ_STREAM_FULL` is required** if the consumer might
  call `next_block` for blocks that don't exist; otherwise
  unspecified behavior.
- **Buffer access strategies matter** — `BAS_BULKREAD` for
  scans; default for normal queries.
- **Read streams hold pins** — release via `read_stream_end`
  + `ReleaseBuffer` on each consumed buffer.
- **Don't mix with manual `ReadBuffer`** for the same scan
  — the stream's prefetch tracking would be confused.

## Invariants

- **[INV-1]** Callback yields block numbers; stream
  prefetches ahead of consumer.
- **[INV-2]** `per_buffer_data` carries callback-to-consumer
  state.
- **[INV-3]** Look-ahead distance adapts to observed
  latency; capped by `io_combine_limit`.
- **[INV-4]** `BufferAccessStrategy` controls buffer-cache
  pollution.
- **[INV-5]** `read_stream_end` releases the stream's pins
  + state.

## Useful greps

- The public API:
  `grep -n 'read_stream_' source/src/include/storage/read_stream.h`
- All current users:
  `grep -RIn 'read_stream_begin_relation' source/src/backend | head -15`
- The look-ahead logic:
  `grep -n 'distance\|max_pinned_buffers' source/src/backend/storage/aio/read_stream.c | head -10`

## Call sites
<!-- callsites:auto -->

*Auto-extracted from `source/<path>:<line>` cites in this doc's prose (bullets and free text).*
*Refresh via `scripts/populate-idiom-callsites.py` — edits inside this block are overwritten.*

| File | Line | Role |
|---|---:|---|
| [`src/backend/storage/aio/read_stream.c`](../files/src/backend/storage/aio/read_stream.c.md) | — | implementation |
| [`src/include/storage/read_stream.h`](../files/src/include/storage/read_stream.h.md) | 85 | public API |
| [`src/include/storage/read_stream.h`](../files/src/include/storage/read_stream.h.md) | — | public API |

<!-- /callsites:auto -->

## Scenarios that use me
<!-- scenarios:auto -->

*Auto-derived from direct references + transitive file-overlap.*
*Refresh via `scripts/build-scenario-idiom-matrix.py`.*

_(none detected — this idiom is either cross-cutting infrastructure or an internal helper pattern)_

<!-- /scenarios:auto -->
## Cross-references

- `knowledge/idioms/vacuum-skip-pages.md` — canonical
  consumer.
- `knowledge/subsystems/contrib-pg_visibility.md` —
  uses read_stream for the corruption scans.
- `knowledge/data-structures/buffertag.md` — read_stream
  ends up at the buffer-manager layer.
- `knowledge/subsystems/storage-buffer.md` — buffer
  manager.
- `.claude/skills/debugging/SKILL.md` — performance
  observability.
- `source/src/include/storage/read_stream.h` — public
  API.
- `source/src/backend/storage/aio/read_stream.c` —
  implementation.
