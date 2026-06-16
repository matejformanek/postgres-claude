# datapagemap.h

## Purpose

Header for the dirty-page bitmap used by `pg_rewind` to record which blocks
of which relfile changed on the target since the divergence point. Declares
`datapagemap_t`, the opaque iterator type, and the four public functions.

## Role in pg_rewind

Part of the filemap layer. After `parsexlog.c::extractPageInfo()` walks the
target's WAL from the last common checkpoint and identifies dirty blocks
per-relfile, the result is accumulated into one `datapagemap_t` per
`file_entry_t` ([from-comment] `filemap.h`). Later, `pg_rewind.c`'s copy
pass iterates each bitmap to request just those blocks from the source via
`rewind_source::queue_fetch_range`.

## Public API

`source/src/bin/pg_rewind/datapagemap.h:23-26`:

- `datapagemap_add(map, BlockNumber blkno)` — set a bit.
- `datapagemap_iterate(map)` → `datapagemap_iterator_t *` (caller `pg_free`s).
- `datapagemap_next(iter, *blkno)` → bool, advances to next set bit.
- `datapagemap_print(map)` — debug dump via `pg_log_debug`.

## State

`struct datapagemap` (`:14-18`) holds a `char *bitmap` and `int bitmapsize`
(bytes). Note `bitmapsize` is `int`, not `size_t`. [verified-by-code]

## Phase D notes

The struct is intentionally exposed by value (not opaque) — callers stack-
allocate `datapagemap_t` zero-initialised inside `file_entry_t`. Iterator
is opaque (forward-declared only).

## Potential issues

- `[ISSUE-undocumented-invariant: bitmapsize as signed int caps relation
  at ~16 TB of dirty bits in a single file (maybe)]` — `int bitmapsize`
  combined with `BlockNumber` being `uint32` (`source/src/include/storage/block.h:31`)
  means once a relfile has > `INT_MAX * 8` dirty blocks the offset
  arithmetic in `.c` overflows. In practice a relfile is capped at 1 GB
  segments / `MaxBlockNumber`, so unreachable — but unstated.

## Cross-references

<!-- issues:auto:begin -->
- [Issue register — `pg_rewind`](../../../../issues/pg_rewind.md)
<!-- issues:auto:end -->
